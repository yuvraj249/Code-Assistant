# """
# RAG Service
# Orchestrates: question → vector search → context assembly → LLM → answer.
# Supports four modes: explain | bugs | tests | architecture
# """

# import os
# from typing import List, Dict, Any
# from openai import OpenAI

# from core.vector_store import VectorStore

# vector_store = VectorStore()
# openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
# MAX_CONTEXT_CHARS = 12_000  # stay within context window


# # ─── System Prompts per Mode ──────────────────────────────────────────────────

# SYSTEM_PROMPTS = {
#     "explain": """You are an expert software engineer and code reviewer.
# Given relevant code chunks from a repository, answer the developer's question clearly.
# - Explain what the code does and how it works
# - Point to specific files and functions when relevant
# - Summarize architecture patterns you observe
# - Be concise but thorough. Use markdown formatting.""",

#     "bugs": """You are a senior code auditor specializing in finding bugs and security issues.
# Given relevant code chunks, analyze them for:
# - Logical errors and incorrect assumptions
# - Security vulnerabilities (SQL injection, XSS, unvalidated input, etc.)
# - Missing error handling and edge cases
# - Race conditions or concurrency issues
# - Inefficient patterns that could cause production issues
# List findings with severity (HIGH/MEDIUM/LOW) and file + line references.""",

#     "tests": """You are a test-driven development expert.
# Given relevant code chunks, generate comprehensive unit tests.
# - For Python: use pytest with clear test function names
# - For JavaScript/TypeScript: use Jest with describe/it blocks
# - Cover happy paths, edge cases, and error conditions
# - Include mock setup where needed
# - Add brief comments explaining each test's purpose
# Return only runnable test code with minimal prose.""",

#     "architecture": """You are a software architect.
# Given relevant code chunks and the developer's question, produce:
# 1. A high-level architecture explanation in plain English
# 2. A Mermaid diagram (graph TD) showing component relationships
# 3. Key design patterns you observe
# 4. Recommendations for improvement
# Format the Mermaid diagram inside a ```mermaid code block.""",
# }


# class RAGService:

#     async def answer(self, question: str, repo_id: str, mode: str = "explain") -> str:
#         """
#         Full RAG pipeline:
#         1. Retrieve top-k relevant code chunks from ChromaDB
#         2. Assemble context string
#         3. Call LLM with mode-specific system prompt
#         4. Return the answer
#         """
#         # 1. Vector search
#         hits = vector_store.search(question, repo_id, top_k=8)
#         if not hits:
#             return "No relevant code found. Make sure the repository has been indexed."

#         # 2. Assemble context (truncate to avoid token overflow)
#         context = self._build_context(hits)

#         # 3. Build messages
#         system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["explain"])
#         user_message = f"""Repository code context:
# ---
# {context}
# ---

# Developer question: {question}"""

#         # 4. Call LLM
#         response = openai_client.chat.completions.create(
#             model=LLM_MODEL,
#             messages=[
#                 {"role": "system", "content": system_prompt},
#                 {"role": "user", "content": user_message},
#             ],
#             temperature=0.2,
#             max_tokens=2000,
#         )

#         return response.choices[0].message.content

#     def _build_context(self, hits: List[Dict[str, Any]]) -> str:
#         """
#         Format retrieved chunks into a readable context string.
#         Truncate if total length exceeds MAX_CONTEXT_CHARS.
#         """
#         parts = []
#         total_chars = 0

#         for hit in hits:
#             header = (
#                 f"### File: {hit['file_path']}"
#                 + (f" | Function: {hit['function_name']}" if hit.get("function_name") else "")
#                 + f" (lines {hit['start_line']}-{hit['end_line']})"
#                 + f" | Relevance: {hit['similarity']:.2f}"
#             )
#             block = f"{header}\n```{hit['language']}\n{hit['content']}\n```\n"

#             if total_chars + len(block) > MAX_CONTEXT_CHARS:
#                 break

#             parts.append(block)
#             total_chars += len(block)

#         return "\n".join(parts)


"""
RAG Service (FREE VERSION - NO OPENAI)
Retrieves relevant code and formats response.
"""

from typing import List, Dict, Any
from core.vector_store import VectorStore

vector_store = VectorStore()


class RAGService:

    async def answer(self, question: str, repo_id: str, mode: str = "explain") -> str:
        """
        Retrieval-only pipeline (no LLM).
        """
        hits = vector_store.search(question, repo_id, top_k=8)

        if not hits:
            return "No relevant code found. Make sure the repository has been indexed."

        return self._format_response(question, hits)

    def _format_response(self, question: str, hits: List[Dict[str, Any]]) -> str:
        """
        Convert retrieved chunks into readable answer.
        """
        response = f"# 🔍 Results for: {question}\n\n"

        for i, hit in enumerate(hits[:5], 1):
            code_block = hit.get("content", "")[:500]

            response += (
                f"## {i}. {hit.get('file_path', 'Unknown')}\n"
                f"Function: {hit.get('function_name', 'N/A')}\n"
                f"Relevance: {hit.get('similarity', 0):.2f}\n\n"
                f"```{hit.get('language', '')}\n"
                f"{code_block}\n"
                f"```\n\n"
            )

        return response