
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