"""
RAG Service
Hybrid AI Assistant supporting Google Gemini (100% Free) & OpenAI.
  - Automatically selects Gemini if GEMINI_API_KEY is configured (or LLM_PROVIDER=gemini).
  - Handles RAG codebase search (ChromaDB) and conversational general coding Q&A.
  - Supports SSE streaming response generation.
"""

import os
import json
import httpx
from typing import List, Dict, Any, AsyncGenerator

from core.vector_store import VectorStore

vector_store = VectorStore()

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
PROVIDER   = os.getenv("LLM_PROVIDER", "gemini" if GEMINI_KEY else "openai")
MODEL_NAME = os.getenv("LLM_MODEL", "gemini-3.6-flash" if PROVIDER == "gemini" else "gpt-4o-mini")

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
        Hybrid answering pipeline (Gemini / OpenAI).
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

        if GEMINI_KEY or PROVIDER == "gemini":
            answer_text = await self._call_gemini(system_prompt, user_content)
        else:
            answer_text = await self._call_openai(system_prompt, user_content)

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
            "model": MODEL_NAME,
            "provider": PROVIDER,
            "has_context": has_context,
        }

    async def stream_answer(
        self, question: str, repo_id: str = None, mode: str = "explain"
    ) -> AsyncGenerator[str, None]:
        """
        SSE streaming generator for Gemini / OpenAI.
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

        if GEMINI_KEY or PROVIDER == "gemini":
            async for token in self._stream_gemini(system_prompt, user_content):
                yield token
        else:
            async for token in self._stream_openai(system_prompt, user_content):
                yield token

    # ── Gemini API Helpers ───────────────────────────────────────────────────

    async def _call_gemini(self, system_prompt: str, user_content: str) -> str:
        """Call Google Gemini REST API using httpx."""
        key = GEMINI_KEY or os.getenv("GEMINI_API_KEY")
        if not key:
            return "⚠️ **Gemini API Key missing**. Please set `GEMINI_API_KEY` in `backend/.env`."

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={key}"
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_content}"}]}
            ]
        }
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code != 200:
                    return f"⚠️ **Gemini API Error ({res.status_code})**: {res.text}"
                data = res.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            return f"⚠️ **Gemini Error**: {str(e)}"

    async def _stream_gemini(self, system_prompt: str, user_content: str) -> AsyncGenerator[str, None]:
        """Stream response tokens from Google Gemini REST API."""
        key = GEMINI_KEY or os.getenv("GEMINI_API_KEY")
        if not key:
            yield "⚠️ **Gemini API Key missing**. Please set `GEMINI_API_KEY` in `backend/.env`."
            return

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:streamGenerateContent?alt=sse&key={key}"
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_content}"}]}
            ]
        }
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                async with client.stream("POST", url, json=payload) as res:
                    if res.status_code != 200:
                        yield f"⚠️ **Gemini API Error ({res.status_code})**"
                        return
                    async for line in res.aiter_lines():
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                text = data["candidates"][0]["content"]["parts"][0]["text"]
                                if text:
                                    yield text
                            except (json.JSONDecodeError, KeyError, IndexError):
                                pass
        except Exception as e:
            yield f"⚠️ **Gemini Stream Error**: {str(e)}"

    # ── OpenAI Helpers ────────────────────────────────────────────────────────

    async def _call_openai(self, system_prompt: str, user_content: str) -> str:
        from openai import AsyncOpenAI, APIError
        client = AsyncOpenAI(api_key=OPENAI_KEY)
        try:
            res = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.2,
                max_tokens=2000,
            )
            return res.choices[0].message.content
        except APIError as e:
            return f"⚠️ **OpenAI API Error**: {e.message if hasattr(e, 'message') else str(e)}"

    async def _stream_openai(self, system_prompt: str, user_content: str) -> AsyncGenerator[str, None]:
        from openai import AsyncOpenAI, APIError
        client = AsyncOpenAI(api_key=OPENAI_KEY)
        try:
            stream = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.2,
                max_tokens=2000,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except APIError as e:
            yield f"⚠️ **OpenAI API Error**: {e.message if hasattr(e, 'message') else str(e)}"

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
