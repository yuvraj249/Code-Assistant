"""
Ingestion Service
Handles: ZIP upload extraction, GitHub repo cloning,
then runs the parse → embed → store pipeline.
"""

import os
import re
import uuid
import zipfile
import tempfile
import subprocess
from typing import Dict, Any, List

from core.parser import CodeParser
from core.vector_store import VectorStore

parser = CodeParser()
vector_store = VectorStore()

# In-memory registry: repo_id → repo metadata
REPO_REGISTRY: Dict[str, Dict[str, Any]] = {}


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
        repo_name = self._repo_name_from_url(github_url)
        repo_id = self._make_repo_id(repo_name)

        with tempfile.TemporaryDirectory() as tmpdir:
            clone_path = os.path.join(tmpdir, repo_name)
            self._clone_repo(github_url, clone_path, branch)
            return await self._run_pipeline(
                clone_path, repo_id, repo_name,
                source="github", github_url=github_url
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

        # 1. Parse all supported files into chunks
        chunks = parser.parse_repository(repo_path, repo_id)
        if not chunks:
            raise ValueError("No supported source files found in repository.")

        # 2. Get file tree for metadata
        file_tree = parser.get_file_tree(repo_path)

        # 3. Embed + store in ChromaDB
        vector_store.index_chunks(chunks, repo_id)

        # 4. Register repo metadata
        REPO_REGISTRY[repo_id] = {
            "repo_id": repo_id,
            "repo_name": repo_name,
            "source": source,
            "github_url": github_url,
            "file_count": len(file_tree),
            "chunk_count": len(chunks),
            "file_tree": file_tree[:100],  # cap at 100 for response size
        }

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
                "file_count": v["file_count"],
                "chunk_count": v["chunk_count"],
            }
            for v in REPO_REGISTRY.values()
        ]

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
