"""
RAG Service
Full retrieval-augmented generation pipeline:
  1. Embed question via sentence-transformers (local, free)
  2. Vector search ChromaDB for top-k relevant code chunks
  3. Assemble context with file paths + line numbers
  4. Call GPT-4o-mini with mode-specific system prompt
  5. Return answer with source citations
Also exposes an async generator for SSE streaming.
"""

import os
from typing import List, Dict, Any, AsyncGenerator
from openai import AsyncOpenAI

from core.vector_store import VectorStore

vector_store = VectorStore()
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# ── Mode-specific system prompts ──────────────────────────────────────────────

SYSTEM_PROMPTS = {
    "explain": """You are CodeMind, an expert AI code assistant. Your job is to explain code clearly and precisely.
Given relevant code chunks from a repository, answer the developer's question with:
- Clear explanations of what the code does and why
- References to specific files and line numbers from the context
- Code examples when helpful
- Honest admission when something is outside the provided context
Be concise but thorough. Format your response with markdown.""",

    "bugs": """You are CodeMind, an expert security and code quality engineer.
Given relevant code chunks from a repository, analyze the code for:
- Security vulnerabilities (injection, XSS, auth bypass, exposed secrets, etc.)
- Logic errors and edge cases
- Missing error handling or null checks
- Race conditions or concurrency issues
- Performance anti-patterns
For each issue found: describe the problem, cite the exact file + line, explain the risk, and suggest a fix.
If no serious issues are found, say so clearly. Format with markdown and severity levels (🔴 Critical / 🟡 Warning / 🟢 Info).""",

    "tests": """You are CodeMind, an expert test engineer.
Given relevant code chunks from a repository, generate comprehensive unit tests.
- Detect the language and use the appropriate framework (pytest for Python, Jest/Vitest for JS/TS)
- Cover happy paths, edge cases, and error conditions
- Mock external dependencies (databases, APIs, file system)
- Include test docstrings explaining what each test verifies
- Make tests runnable — import the correct modules from the codebase
Format the output as a complete, runnable test file with markdown code blocks.""",

    "architecture": """You are CodeMind, an expert software architect.
Given relevant code chunks from a repository, provide a high-level architectural analysis:
- Identify the architectural pattern (MVC, microservices, layered, event-driven, etc.)
- Map component relationships and data flow
- Identify the technology stack
- Point out coupling concerns, separation of concerns issues
- Generate a Mermaid diagram (graph TD) showing component relationships
Be specific — reference actual files and modules from the context. Format with markdown.""",
}


class RAGService:

    async def answer(self, question: str, repo_id: str, mode: str = "explain") -> Dict[str, Any]:
        """
        Full RAG pipeline. Returns answer + citations.
        """
        hits = vector_store.search(question, repo_id, top_k=8)

        if not hits:
            return {
                "answer": "⚠ No relevant code found. Make sure the repository has been indexed first.",
                "citations": [],
                "mode": mode,
            }

        context = self._build_context(hits)
        system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["explain"])

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"## Relevant Code Context\n\n{context}\n\n## Question\n\n{question}",
            },
        ]

        response = await openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.2,
            max_tokens=2000,
        )

        answer_text = response.choices[0].message.content

        citations = [
            {
                "file": h["file_path"],
                "lines": f"{h['start_line']}–{h['end_line']}",
                "function": h["function_name"],
                "relevance": h["similarity"],
            }
            for h in hits[:5]
        ]

        return {
            "answer": answer_text,
            "citations": citations,
            "mode": mode,
            "model": LLM_MODEL,
        }

    async def stream_answer(
        self, question: str, repo_id: str, mode: str = "explain"
    ) -> AsyncGenerator[str, None]:
        """
        SSE streaming version — yields tokens as they arrive from the LLM.
        """
        hits = vector_store.search(question, repo_id, top_k=8)

        if not hits:
            yield "⚠ No relevant code found. Make sure the repository has been indexed first."
            return

        context = self._build_context(hits)
        system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["explain"])

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"## Relevant Code Context\n\n{context}\n\n## Question\n\n{question}",
            },
        ]

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
