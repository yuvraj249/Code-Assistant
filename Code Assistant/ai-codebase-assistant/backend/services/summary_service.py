# """
# Summary Service
# Auto-generates a repository overview when a repo is first loaded:
# - Language breakdown, architecture style, modules, dependencies
# - High-level architecture explanation
# - Mermaid diagram
# """

# import os
# from typing import Dict, Any, List
# from openai import OpenAI

# from core.vector_store import VectorStore
# from services.ingestion_service import REPO_REGISTRY

# vector_store = VectorStore()
# openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# # Cache summaries so we don't re-generate on every GET
# SUMMARY_CACHE: Dict[str, Dict[str, Any]] = {}

# SUMMARY_SYSTEM_PROMPT = """You are a senior software architect analyzing a codebase.
# Given a list of files and sample code from a repository, produce a structured summary.

# Return a JSON object with exactly these fields:
# {
#   "language": "primary language (e.g. Python, TypeScript)",
#   "architecture": "architecture style (e.g. REST API, Microservices, MVC, CLI tool)",
#   "overview": "2-3 sentence plain-English overview of what this project does",
#   "modules": ["list", "of", "main", "module", "names"],
#   "key_files": ["list", "of", "important", "file", "paths"],
#   "dependencies": ["key", "libraries", "or", "frameworks"],
#   "architecture_explanation": "3-5 sentence detailed architecture explanation",
#   "mermaid_diagram": "valid Mermaid graph TD diagram as a string (no backticks)"
# }

# Return ONLY the JSON object, no markdown, no extra text."""


# class SummaryService:

#     async def get_summary(self, repo_id: str) -> Dict[str, Any]:
#         """Return cached summary or generate a new one."""
#         if repo_id in SUMMARY_CACHE:
#             return SUMMARY_CACHE[repo_id]

#         if repo_id not in REPO_REGISTRY:
#             raise ValueError(f"Repo '{repo_id}' not found. Ingest it first.")

#         summary = await self._generate_summary(repo_id)
#         SUMMARY_CACHE[repo_id] = summary
#         return summary

#     async def _generate_summary(self, repo_id: str) -> Dict[str, Any]:
#         meta = REPO_REGISTRY[repo_id]
#         file_tree = meta.get("file_tree", [])

#         # Pull a broad sample of code from various modules
#         sample_queries = [
#             "main entry point application setup",
#             "database models schema",
#             "authentication authorization",
#             "API routes endpoints",
#             "configuration settings environment",
#         ]

#         code_samples = []
#         seen_files = set()
#         for query in sample_queries:
#             hits = vector_store.search(query, repo_id, top_k=3)
#             for hit in hits:
#                 if hit["file_path"] not in seen_files:
#                     seen_files.add(hit["file_path"])
#                     code_samples.append(
#                         f"# {hit['file_path']}\n{hit['content'][:500]}"
#                     )

#         file_list = "\n".join(file_tree[:60])
#         code_context = "\n\n".join(code_samples[:12])

#         user_msg = f"""Repository: {meta['repo_name']}
# Total files: {meta['file_count']}
# Total chunks: {meta['chunk_count']}

# File tree (first 60 files):
# {file_list}

# Code samples:
# {code_context}"""

#         import json
#         response = openai_client.chat.completions.create(
#             model=LLM_MODEL,
#             messages=[
#                 {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
#                 {"role": "user", "content": user_msg},
#             ],
#             temperature=0.1,
#             max_tokens=1500,
#             response_format={"type": "json_object"},
#         )

#         raw = response.choices[0].message.content
#         try:
#             result = json.loads(raw)
#         except json.JSONDecodeError:
#             result = {
#                 "language": "Unknown",
#                 "architecture": "Unknown",
#                 "overview": "Summary could not be parsed.",
#                 "modules": [],
#                 "key_files": [],
#                 "dependencies": [],
#                 "architecture_explanation": raw,
#                 "mermaid_diagram": "graph TD\n  A[Repository] --> B[Code]",
#             }

#         # Merge with ingestion metadata
#         result["repo_id"] = repo_id
#         result["repo_name"] = meta["repo_name"]
#         result["file_count"] = meta["file_count"]
#         result["chunk_count"] = meta["chunk_count"]
#         return result



"""
Summary Service (FREE VERSION - NO OPENAI)
Generates repository summary using metadata + simple heuristics.
"""

from typing import Dict, Any, List
from services.ingestion_service import REPO_REGISTRY

# Cache summaries to avoid recomputation
SUMMARY_CACHE: Dict[str, Dict[str, Any]] = {}


class SummaryService:

    async def get_summary(self, repo_id: str) -> Dict[str, Any]:
        """Return cached summary or generate a new one."""
        if repo_id in SUMMARY_CACHE:
            return SUMMARY_CACHE[repo_id]

        if repo_id not in REPO_REGISTRY:
            raise ValueError(f"Repo '{repo_id}' not found. Ingest it first.")

        meta = REPO_REGISTRY[repo_id]
        summary = self._generate_summary(meta)

        SUMMARY_CACHE[repo_id] = summary
        return summary

    def _generate_summary(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        file_tree = meta.get("file_tree", [])

        # 🔹 Detect languages from file extensions
        language_count = {}
        for file in file_tree:
            ext = file.split(".")[-1] if "." in file else "unknown"
            language_count[ext] = language_count.get(ext, 0) + 1

        primary_language = max(language_count, key=language_count.get) if language_count else "Unknown"

        # 🔹 Detect architecture (simple heuristic)
        architecture = self._detect_architecture(file_tree)

        # 🔹 Extract modules (top-level folders)
        modules = self._extract_modules(file_tree)

        # 🔹 Identify key files
        key_files = self._get_key_files(file_tree)

        return {
            "repo_id": meta["repo_id"],
            "repo_name": meta["repo_name"],
            "file_count": meta["file_count"],
            "chunk_count": meta["chunk_count"],
            "language": primary_language,
            "architecture": architecture,
            "overview": f"This repository contains {meta['file_count']} files and {meta['chunk_count']} code chunks.",
            "modules": modules,
            "key_files": key_files,
            "dependencies": [],
            "architecture_explanation": self._generate_architecture_explanation(architecture),
            "mermaid_diagram": self._generate_mermaid_diagram(modules),
        }

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _extract_modules(self, file_tree: List[str]) -> List[str]:
        """Extract top-level folders as modules."""
        modules = set()
        for file in file_tree:
            parts = file.split("/")
            if len(parts) > 1:
                modules.add(parts[0])
        return list(modules)[:10]

    def _get_key_files(self, file_tree: List[str]) -> List[str]:
        """Identify important files."""
        keywords = ["main", "app", "index", "server", "config", "routes"]
        key_files = [
            f for f in file_tree
            if any(k in f.lower() for k in keywords)
        ]
        return key_files[:10]

    def _detect_architecture(self, file_tree: List[str]) -> str:
        """Basic architecture detection."""
        joined = " ".join(file_tree).lower()

        if "routes" in joined or "controller" in joined:
            return "REST API / MVC"
        elif "components" in joined or "pages" in joined:
            return "Frontend (React/SPA)"
        elif "cli" in joined:
            return "CLI Tool"
        elif "services" in joined:
            return "Service-based Architecture"
        else:
            return "General Codebase"

    def _generate_architecture_explanation(self, architecture: str) -> str:
        return f"This project appears to follow a {architecture} structure based on file organization."

    def _generate_mermaid_diagram(self, modules: List[str]) -> str:
        """Generate simple Mermaid diagram."""
        diagram = "graph TD\n"
        for module in modules:
            diagram += f"  A[Repo] --> {module}[{module}]\n"
        return diagram
