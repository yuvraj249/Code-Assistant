"""
Summary Service
Generates AI-powered repository summaries and Mermaid architecture diagrams.
Uses Gemini (or OpenAI) to produce meaningful summaries.
"""

import os
import json
import httpx
from typing import Dict, Any, List

from services.ingestion_service import REPO_REGISTRY

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
PROVIDER   = os.getenv("LLM_PROVIDER", "gemini" if GEMINI_KEY else "openai")
MODEL_NAME = os.getenv("LLM_MODEL", "gemini-3.6-flash" if PROVIDER == "gemini" else "gpt-4o-mini")

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

        language_count: Dict[str, int] = {}
        for f in file_tree:
            ext = f.rsplit(".", 1)[-1] if "." in f else "unknown"
            language_count[ext] = language_count.get(ext, 0) + 1

        primary_language = max(language_count, key=lambda k: language_count[k]) if language_count else "Unknown"
        modules = self._extract_modules(file_tree)
        key_files = self._get_key_files(file_tree)
        dependencies = self._extract_dependencies(file_tree)

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
        """Use Gemini / OpenAI to generate a real summary and Mermaid diagram."""

        prompt = f"""You are CodeMind, an expert software architect analyzing a codebase.

Repository: {repo_name}
Primary Language: {primary_language}
Total Files: {file_count} | Code Chunks: {chunk_count}
Top-level Modules: {', '.join(modules) or 'N/A'}

File Tree (first 80 files):
{file_tree_str}

Based on this file structure, provide:

1. ARCHITECTURE: One-line architectural pattern (e.g. "REST API / MVC", "React SPA", "Microservices", "CLI Tool")

2. OVERVIEW: 2-3 sentence summary of what this repository does and how it's organized.

3. ARCHITECTURE_EXPLANATION: A paragraph explaining the architectural decisions, component interactions, and data flow.

4. MERMAID_DIAGRAM: A valid Mermaid `graph TD` diagram showing main components (8-12 nodes max).

Respond in this exact format:
ARCHITECTURE: <one line>
OVERVIEW: <2-3 sentences>
ARCHITECTURE_EXPLANATION: <paragraph>
MERMAID_DIAGRAM:
```
<mermaid code>
```"""

        try:
            if GEMINI_KEY or PROVIDER == "gemini":
                key = GEMINI_KEY or os.getenv("GEMINI_API_KEY")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={key}"
                async with httpx.AsyncClient(timeout=30.0) as client:
                    res = await client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
                    if res.status_code == 200:
                        text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                        return self._parse_llm_response(text, modules)
            else:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=OPENAI_KEY)
                res = await client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=800,
                )
                return self._parse_llm_response(res.choices[0].message.content, modules)
        except Exception as e:
            print(f"[summary] LLM call failed: {e}. Falling back to heuristics.")

        return self._fallback_summary(modules)

    def _parse_llm_response(self, text: str, modules: List[str]) -> Dict[str, Any]:
        result = {
            "architecture": "General Codebase",
            "overview": "An AI-indexed repository.",
            "architecture_explanation": "Architecture analysis complete.",
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
                diagram_lines = []
                i += 1
                while i < len(lines) and not lines[i].startswith("```"):
                    i += 1
                i += 1
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
            "overview": "Repository successfully indexed.",
            "architecture_explanation": "Structure based on directory organization.",
            "mermaid_diagram": self._fallback_mermaid(modules),
        }

    def _fallback_mermaid(self, modules: List[str]) -> str:
        diagram = "graph TD\n    Root[Repository]\n"
        for m in modules[:8]:
            safe_id = m.replace("-", "_").replace(".", "_")
            diagram += f"    Root --> {safe_id}[{m}]\n"
        return diagram

    def _extract_modules(self, file_tree: List[str]) -> List[str]:
        modules = set()
        for f in file_tree:
            parts = f.replace("\\", "/").split("/")
            if len(parts) > 1:
                modules.add(parts[0])
        return sorted(list(modules))[:10]

    def _get_key_files(self, file_tree: List[str]) -> List[str]:
        keywords = ["main", "app", "index", "server", "config", "routes", "schema", "models"]
        return [f for f in file_tree if any(k in f.lower() for k in keywords)][:10]

    def _extract_dependencies(self, file_tree: List[str]) -> List[str]:
        dep_files = {
            "requirements.txt": "Python (pip)",
            "package.json": "Node.js (npm)",
            "go.mod": "Go modules",
            "Cargo.toml": "Rust (cargo)",
            "pyproject.toml": "Python (poetry/uv)",
        }
        found = []
        flat = " ".join(file_tree)
        for fname, label in dep_files.items():
            if fname in flat:
                found.append(label)
        return found
