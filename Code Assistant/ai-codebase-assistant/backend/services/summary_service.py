"""
Summary Service
Generates AI-powered repository summaries and Mermaid architecture diagrams.
Uses GPT-4o-mini to produce meaningful summaries instead of hardcoded heuristics.
"""

import os
from typing import Dict, Any, List
from openai import AsyncOpenAI

from services.ingestion_service import REPO_REGISTRY

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# Cache summaries to avoid recomputation
SUMMARY_CACHE: Dict[str, Dict[str, Any]] = {}


class SummaryService:

    async def get_summary(self, repo_id: str) -> Dict[str, Any]:
        """Return cached summary or generate a new one via LLM."""
        if repo_id in SUMMARY_CACHE:
            return SUMMARY_CACHE[repo_id]

        if repo_id not in REPO_REGISTRY:
            raise ValueError(f"Repo '{repo_id}' not found. Ingest it first.")

        meta = REPO_REGISTRY[repo_id]
        summary = await self._generate_summary(meta)

        SUMMARY_CACHE[repo_id] = summary
        return summary

    def invalidate_cache(self, repo_id: str):
        SUMMARY_CACHE.pop(repo_id, None)

    async def _generate_summary(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        file_tree = meta.get("file_tree", [])
        file_tree_str = "\n".join(file_tree[:80])

        # ── Static analysis (no LLM cost) ─────────────────────────────────────
        language_count: Dict[str, int] = {}
        for f in file_tree:
            ext = f.rsplit(".", 1)[-1] if "." in f else "unknown"
            language_count[ext] = language_count.get(ext, 0) + 1

        primary_language = max(language_count, key=lambda k: language_count[k]) if language_count else "Unknown"
        modules = self._extract_modules(file_tree)
        key_files = self._get_key_files(file_tree)
        dependencies = self._extract_dependencies(file_tree)

        # ── LLM-powered summary ────────────────────────────────────────────────
        llm_result = await self._llm_analyze(
            repo_name=meta["repo_name"],
            file_tree_str=file_tree_str,
            file_count=meta["file_count"],
            chunk_count=meta["chunk_count"],
            modules=modules,
            primary_language=primary_language,
        )

        return {
            "repo_id": meta["repo_id"],
            "repo_name": meta["repo_name"],
            "file_count": meta["file_count"],
            "chunk_count": meta["chunk_count"],
            "language": primary_language,
            "architecture": llm_result["architecture"],
            "overview": llm_result["overview"],
            "modules": modules,
            "key_files": key_files,
            "dependencies": dependencies,
            "architecture_explanation": llm_result["architecture_explanation"],
            "mermaid_diagram": llm_result["mermaid_diagram"],
        }

    async def _llm_analyze(
        self,
        repo_name: str,
        file_tree_str: str,
        file_count: int,
        chunk_count: int,
        modules: List[str],
        primary_language: str,
    ) -> Dict[str, Any]:
        """Use GPT-4o-mini to generate a real summary and Mermaid diagram."""

        prompt = f"""You are CodeMind, an expert software architect analyzing a codebase.

Repository: {repo_name}
Primary Language: {primary_language}
Total Files: {file_count} | Code Chunks: {chunk_count}
Top-level Modules: {', '.join(modules) or 'N/A'}

File Tree (first 80 files):
{file_tree_str}

Based on this file structure, provide:

1. ARCHITECTURE: One-line architectural pattern (e.g. "REST API / MVC", "React SPA", "Microservices", "CLI Tool", "Full-stack Next.js")

2. OVERVIEW: 2-3 sentence summary of what this repository does and how it's organized. Be specific.

3. ARCHITECTURE_EXPLANATION: A paragraph explaining the architectural decisions, how components interact, and the data flow.

4. MERMAID_DIAGRAM: A valid Mermaid `graph TD` diagram showing the main components and their relationships. Use the actual folder/file names. Keep it to 8-15 nodes max. Example format:
```
graph TD
    User[👤 User] --> Frontend[React Frontend]
    Frontend --> API[FastAPI Backend]
    API --> DB[(PostgreSQL)]
```

Respond in this exact format:
ARCHITECTURE: <one line>
OVERVIEW: <2-3 sentences>
ARCHITECTURE_EXPLANATION: <paragraph>
MERMAID_DIAGRAM:
```
<mermaid code>
```"""

        try:
            response = await openai_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=800,
            )
            text = response.choices[0].message.content
            return self._parse_llm_response(text, modules)
        except Exception as e:
            print(f"[summary] LLM call failed: {e}. Falling back to heuristics.")
            return self._fallback_summary(modules)

    def _parse_llm_response(self, text: str, modules: List[str]) -> Dict[str, Any]:
        """Parse the structured LLM response."""
        result = {
            "architecture": "General Codebase",
            "overview": "An AI-indexed repository.",
            "architecture_explanation": "Architecture analysis unavailable.",
            "mermaid_diagram": self._fallback_mermaid(modules),
        }

        lines = text.strip().split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("ARCHITECTURE:"):
                result["architecture"] = line.replace("ARCHITECTURE:", "").strip()
            elif line.startswith("OVERVIEW:"):
                result["overview"] = line.replace("OVERVIEW:", "").strip()
            elif line.startswith("ARCHITECTURE_EXPLANATION:"):
                result["architecture_explanation"] = line.replace("ARCHITECTURE_EXPLANATION:", "").strip()
            elif line.startswith("MERMAID_DIAGRAM:"):
                # Collect everything in the code block
                diagram_lines = []
                i += 1
                while i < len(lines) and not lines[i].startswith("```"):
                    i += 1
                i += 1  # skip opening ```
                while i < len(lines) and not lines[i].startswith("```"):
                    diagram_lines.append(lines[i])
                    i += 1
                if diagram_lines:
                    result["mermaid_diagram"] = "\n".join(diagram_lines)
            i += 1

        return result

    def _fallback_summary(self, modules: List[str]) -> Dict[str, Any]:
        return {
            "architecture": "General Codebase",
            "overview": "Repository successfully indexed. AI summary unavailable — check OPENAI_API_KEY.",
            "architecture_explanation": "Set OPENAI_API_KEY in backend/.env for AI-powered architecture analysis.",
            "mermaid_diagram": self._fallback_mermaid(modules),
        }

    def _fallback_mermaid(self, modules: List[str]) -> str:
        diagram = "graph TD\n    Root[Repository]\n"
        for m in modules[:8]:
            safe_id = m.replace("-", "_").replace(".", "_")
            diagram += f"    Root --> {safe_id}[{m}]\n"
        return diagram

    # ─── Static Helpers ───────────────────────────────────────────────────────

    def _extract_modules(self, file_tree: List[str]) -> List[str]:
        """Extract top-level folders as modules."""
        modules = set()
        for f in file_tree:
            parts = f.replace("\\", "/").split("/")
            if len(parts) > 1:
                modules.add(parts[0])
        return sorted(list(modules))[:10]

    def _get_key_files(self, file_tree: List[str]) -> List[str]:
        """Identify important files by name pattern."""
        keywords = ["main", "app", "index", "server", "config", "routes", "schema", "models"]
        return [f for f in file_tree if any(k in f.lower() for k in keywords)][:10]

    def _extract_dependencies(self, file_tree: List[str]) -> List[str]:
        """Detect dependency files present."""
        dep_files = {
            "requirements.txt": "Python (pip)",
            "package.json": "Node.js (npm)",
            "go.mod": "Go modules",
            "Cargo.toml": "Rust (cargo)",
            "pyproject.toml": "Python (poetry/uv)",
            "Gemfile": "Ruby (bundler)",
        }
        found = []
        flat = " ".join(file_tree)
        for fname, label in dep_files.items():
            if fname in flat:
                found.append(label)
        return found
