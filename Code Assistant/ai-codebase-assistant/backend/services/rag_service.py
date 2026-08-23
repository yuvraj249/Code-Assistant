"""
RAG Service
Hybrid AI Assistant:
  - If a valid repo_id is provided and indexed: runs vector retrieval (ChromaDB)
    and attaches code context + file citations to the prompt.
  - If NO repo_id is provided (or repo not indexed): functions as a conversational AI coding assistant
    using GPT-4o-mini to answer general programming, architecture, and debugging questions.
  - Gracefully catches OpenAI API errors (quota exceeded, invalid key, rate limits) and returns
    clear, user-friendly markdown error explanations.
"""

import os
from typing import List, Dict, Any, AsyncGenerator
from openai import AsyncOpenAI, APIError

from core.vector_store import VectorStore

vector_store = VectorStore()
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# ── System prompts for general & RAG modes ────────────────────────────────────

GENERAL_SYSTEM_PROMPT = """You are CodeMind, an expert AI software developer and coding assistant.
You help developers write code, debug issues, explain concepts, and design architectures.
Answer the user's question with clear explanations, best practices, and well-structured code snippets.
Format your output with clean GitHub-flavored markdown."""

SYSTEM_PROMPTS = {
    "explain": """You are CodeMind, an expert AI code assistant. Your job is to explain code clearly and precisely.
Given relevant code chunks from a repository, answer the developer's question with:
- Clear explanations of what the code does and why
- References to specific files and line numbers from the context
- Code examples when helpful
- Honest admission when something is outside the provided context
Be concise but thorough. Format your response with markdown.""",

    "bugs": """You are CodeMind, an expert security and code quality engineer.
Analyze the provided code (or question) for:
- Security vulnerabilities (injection, XSS, auth bypass, exposed secrets, etc.)
- Logic errors and edge cases
- Missing error handling or null checks
- Performance anti-patterns
For each issue found: describe the problem, cite file + line if available, explain the risk, and suggest a fix.
Format with markdown and severity levels (🔴 Critical / 🟡 Warning / 🟢 Info).""",

    "tests": """You are CodeMind, an expert test engineer.
Generate comprehensive unit tests based on the question or code context:
- Detect language (pytest for Python, Jest/Vitest for JS/TS, etc.)
- Cover happy paths, edge cases, and error conditions
- Mock external dependencies
Format as clean, runnable test files with markdown code blocks.""",

    "architecture": """You are CodeMind, an expert software architect.
Provide a high-level architectural analysis:
- Identify architectural patterns (MVC, microservices, layered, event-driven)
- Map component relationships and data flow
- Point out coupling concerns or performance bottlenecks
- Include a Mermaid diagram (graph TD) showing component relationships when appropriate
Format with markdown.""",
}


class RAGService:

    async def answer(self, question: str, repo_id: str = None, mode: str = "explain") -> Dict[str, Any]:
        """
        Hybrid answering pipeline with friendly error formatting.
        """
        hits = []
        if repo_id and repo_id.strip() and repo_id.lower() != "none":
            hits = vector_store.search(question, repo_id, top_k=8)

        has_context = len(hits) > 0
        system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["explain"]) if has_context else GENERAL_SYSTEM_PROMPT

        if has_context:
            context = self._build_context(hits)
            user_content = f"## Relevant Code Context from Repository\n\n{context}\n\n## Question\n\n{question}"
        else:
            user_content = question

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        try:
            response = await openai_client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                temperature=0.2,
                max_tokens=2000,
            )
            answer_text = response.choices[0].message.content
        except APIError as e:
            answer_text = self._format_openai_error(e)

        citations = [
            {
                "file": h["file_path"],
                "lines": f"{h['start_line']}–{h['end_line']}",
                "function": h["function_name"],
                "relevance": h["similarity"],
            }
            for h in hits[:5]
        ] if has_context else []

        return {
            "answer": answer_text,
            "citations": citations,
            "mode": mode,
            "model": LLM_MODEL,
            "has_context": has_context,
        }

    async def stream_answer(
        self, question: str, repo_id: str = None, mode: str = "explain"
    ) -> AsyncGenerator[str, None]:
        """
        SSE streaming version — yields tokens or friendly error message.
        """
        hits = []
        if repo_id and repo_id.strip() and repo_id.lower() != "none":
            hits = vector_store.search(question, repo_id, top_k=8)

        has_context = len(hits) > 0
        system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["explain"]) if has_context else GENERAL_SYSTEM_PROMPT

        if has_context:
            context = self._build_context(hits)
            user_content = f"## Relevant Code Context from Repository\n\n{context}\n\n## Question\n\n{question}"
        else:
            user_content = question

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        try:
            stream = await openai_client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                temperature=0.2,
                max_tokens=2000,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except APIError as e:
            yield self._format_openai_error(e)

    def _format_openai_error(self, e: APIError) -> str:
        """Convert OpenAI API errors into clean markdown messages."""
        err_str = str(e)
        if "insufficient_quota" in err_str or "quota" in err_str:
            return (
                "⚠️ **OpenAI Quota Exceeded**\n\n"
                "The OpenAI API key configured in `backend/.env` has run out of credits or billing quota.\n\n"
                "**How to fix:**\n"
                "1. Visit [platform.openai.com/account/billing](https://platform.openai.com/account/billing) to add credits or check your usage.\n"
                "2. Or replace `OPENAI_API_KEY` in `backend/.env` with an active key."
            )
        elif "invalid_api_key" in err_str:
            return (
                "⚠️ **Invalid OpenAI API Key**\n\n"
                "The `OPENAI_API_KEY` set in `backend/.env` is invalid or expired. "
                "Please update it with a valid key from [platform.openai.com/api-keys](https://platform.openai.com/api-keys)."
            )
        else:
            return f"⚠️ **OpenAI API Error**: {e.message if hasattr(e, 'message') else str(e)}"

    def _build_context(self, hits: List[Dict[str, Any]]) -> str:
        """Assemble retrieved chunks into a well-formatted context block."""
        parts = []
        for i, hit in enumerate(hits, 1):
            parts.append(
                f"### [{i}] {hit['file_path']} (lines {hit['start_line']}–{hit['end_line']})"
                + (f" — `{hit['function_name']}`" if hit.get("function_name") else "")
                + f"\n```{hit.get('language', '')}\n{hit['content']}\n```"
            )
        return "\n\n".join(parts)
