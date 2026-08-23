"""
Ingestion Service
Handles: ZIP upload extraction, GitHub repo cloning,
then runs the parse → embed → store pipeline.
Persists repo registry to disk so it survives server restarts.
"""

import os
import re
import json
import uuid
import zipfile
import tempfile
import subprocess
from typing import Dict, Any, List

from core.parser import CodeParser
from core.vector_store import VectorStore

parser = CodeParser()
vector_store = VectorStore()

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "..", "registry.json")

# ── Registry: persisted to disk ───────────────────────────────────────────────

def _load_registry() -> Dict[str, Dict[str, Any]]:
    """Load repo registry from disk."""
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_registry(registry: Dict[str, Dict[str, Any]]):
    """Persist repo registry to disk."""
    try:
        with open(REGISTRY_PATH, "w") as f:
            json.dump(registry, f, indent=2)
    except Exception as e:
        print(f"[ingestion] Failed to save registry: {e}")


REPO_REGISTRY: Dict[str, Dict[str, Any]] = _load_registry()


class IngestionService:

    async def ingest_zip(self, zip_path: str, extract_dir: str) -> Dict[str, Any]:
        """Extract a ZIP archive and ingest the code inside."""
        extract_to = os.path.join(extract_dir, "extracted")
        os.makedirs(extract_to, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_to)

        # If ZIP contains a single root folder, descend into it
        contents = os.listdir(extract_to)
        if len(contents) == 1 and os.path.isdir(os.path.join(extract_to, contents[0])):
            repo_path = os.path.join(extract_to, contents[0])
            repo_name = contents[0]
        else:
            repo_path = extract_to
            repo_name = "uploaded-repo"

        repo_id = self._make_repo_id(repo_name)
        return await self._run_pipeline(repo_path, repo_id, repo_name, source="upload")

    async def ingest_github(self, github_url: str, branch: str = "main") -> Dict[str, Any]:
        """Clone a GitHub repo and ingest its code."""
        # Sanitize URL — allow only github.com URLs
        url = github_url.strip()
        if not re.match(r"^https://github\.com/[\w.\-]+/[\w.\-]+(\.git)?$", url):
            raise ValueError("Invalid GitHub URL. Only https://github.com/owner/repo is supported.")

        repo_name = self._repo_name_from_url(url)
        repo_id = self._make_repo_id(repo_name)

        with tempfile.TemporaryDirectory() as tmpdir:
            clone_path = os.path.join(tmpdir, repo_name)
            self._clone_repo(url, clone_path, branch)
            return await self._run_pipeline(
                clone_path, repo_id, repo_name,
                source="github", github_url=url
            )

    async def _run_pipeline(
        self,
        repo_path: str,
        repo_id: str,
        repo_name: str,
        source: str,
        github_url: str = "",
    ) -> Dict[str, Any]:
        """Parse → Chunk → Embed → Store in ChromaDB."""
        print(f"[ingestion] Starting pipeline for '{repo_name}' (id={repo_id})")

        # Delete existing collection to avoid duplicate chunks on re-ingest
        vector_store.delete_collection(repo_id)

        # 1. Parse all supported files into chunks
        chunks = parser.parse_repository(repo_path, repo_id)
        if not chunks:
            raise ValueError("No supported source files found in repository.")

        # 2. Get file tree for metadata
        file_tree = parser.get_file_tree(repo_path)

        # 3. Embed + store in ChromaDB
        vector_store.index_chunks(chunks, repo_id)

        # 4. Register repo metadata and persist to disk
        REPO_REGISTRY[repo_id] = {
            "repo_id": repo_id,
            "repo_name": repo_name,
            "source": source,
            "github_url": github_url,
            "file_count": len(file_tree),
            "chunk_count": len(chunks),
            "file_tree": file_tree[:100],  # cap at 100 for response size
        }
        _save_registry(REPO_REGISTRY)

        print(f"[ingestion] Pipeline complete: {len(chunks)} chunks from {len(file_tree)} files")

        return {
            "repo_id": repo_id,
            "repo_name": repo_name,
            "file_count": len(file_tree),
            "chunk_count": len(chunks),
        }

    def list_repos(self) -> List[Dict[str, Any]]:
        return [
            {
                "repo_id": v["repo_id"],
                "repo_name": v["repo_name"],
                "source": v["source"],
                "github_url": v.get("github_url", ""),
                "file_count": v["file_count"],
                "chunk_count": v["chunk_count"],
            }
            for v in REPO_REGISTRY.values()
        ]

    def delete_repo(self, repo_id: str):
        """Remove a repo from the registry and delete its ChromaDB collection."""
        if repo_id not in REPO_REGISTRY:
            raise ValueError(f"Repo '{repo_id}' not found.")
        vector_store.delete_collection(repo_id)
        del REPO_REGISTRY[repo_id]
        _save_registry(REPO_REGISTRY)

    def get_repo(self, repo_id: str) -> Dict[str, Any]:
        if repo_id not in REPO_REGISTRY:
            raise ValueError(f"Repo '{repo_id}' not found.")
        return REPO_REGISTRY[repo_id]

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _make_repo_id(self, name: str) -> str:
        safe = re.sub(r"[^a-z0-9-]", "-", name.lower())[:40]
        return f"{safe}-{uuid.uuid4().hex[:6]}"

    def _repo_name_from_url(self, url: str) -> str:
        """Extract 'owner-repo' from a GitHub URL."""
        parts = url.rstrip("/").split("/")
        if len(parts) >= 2:
            return f"{parts[-2]}-{parts[-1].replace('.git', '')}"
        return parts[-1].replace(".git", "")

    def _clone_repo(self, url: str, path: str, branch: str):
        cmd = ["git", "clone", "--depth=1", f"--branch={branch}", url, path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            # Retry without branch spec (handles repos with non-standard default branch)
            cmd_fallback = ["git", "clone", "--depth=1", url, path]
            result2 = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=120)
            if result2.returncode != 0:
                raise RuntimeError(f"git clone failed: {result2.stderr}")
