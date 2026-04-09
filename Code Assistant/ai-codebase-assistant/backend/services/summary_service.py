
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
