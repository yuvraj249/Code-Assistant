"""
Code Parser & Chunker
Parses source files and splits them into semantically meaningful chunks
with metadata (file path, function name, module name).
"""

import os
import re
import ast
from typing import List, Dict, Any
from dataclasses import dataclass

# Supported file extensions → language label
SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".go": "go",
    ".json": "json",
    ".md": "markdown",
}

# Directories / patterns to skip
IGNORE_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", "coverage", ".mypy_cache",
}

IGNORE_FILES = {
    "package-lock.json", "yarn.lock", "poetry.lock", "go.sum",
}

CHUNK_SIZE = 60       # lines per chunk
CHUNK_OVERLAP = 10    # overlapping lines between chunks


@dataclass
class CodeChunk:
    chunk_id: str
    repo_id: str
    file_path: str
    language: str
    content: str
    start_line: int
    end_line: int
    function_name: str = ""
    module_name: str = ""
    chunk_index: int = 0


class CodeParser:
    """Walks a repository directory and produces CodeChunk objects."""

    def parse_repository(self, repo_path: str, repo_id: str) -> List[CodeChunk]:
        """
        Walk all files in repo_path, filter supported types,
        parse and chunk each file.
        """
        chunks: List[CodeChunk] = []

        for root, dirs, files in os.walk(repo_path):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for filename in files:
                if filename in IGNORE_FILES:
                    continue

                ext = os.path.splitext(filename)[1].lower()
                if ext not in SUPPORTED_EXTENSIONS:
                    continue

                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, repo_path)
                language = SUPPORTED_EXTENSIONS[ext]

                try:
                    file_chunks = self._parse_file(full_path, rel_path, repo_id, language)
                    chunks.extend(file_chunks)
                except Exception as e:
                    print(f"[parser] Skipping {rel_path}: {e}")

        print(f"[parser] Total chunks generated: {len(chunks)}")
        return chunks

    def _parse_file(
        self, full_path: str, rel_path: str, repo_id: str, language: str
    ) -> List[CodeChunk]:
        """Read a single file and return its chunks."""
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        if not content.strip():
            return []

        lines = content.splitlines()
        module_name = self._extract_module_name(rel_path)

        # For Python files, try function-aware splitting
        if language == "python":
            return self._chunk_python(lines, rel_path, repo_id, module_name)

        # For all others, use sliding-window line chunking
        return self._chunk_by_lines(lines, rel_path, repo_id, language, module_name)

    def _chunk_python(
        self, lines: List[str], rel_path: str, repo_id: str, module_name: str
    ) -> List[CodeChunk]:
        """
        Split Python files by top-level function/class definitions
        so each chunk stays semantically cohesive.
        """
        chunks: List[CodeChunk] = []
        current_block: List[str] = []
        current_func = ""
        current_start = 1
        chunk_index = 0

        func_pattern = re.compile(r"^(def |class )\s*(\w+)")

        for i, line in enumerate(lines, start=1):
            match = func_pattern.match(line)
            if match and current_block:
                # Flush previous block
                chunk = self._make_chunk(
                    repo_id, rel_path, "python", module_name,
                    current_block, current_start, i - 1, current_func, chunk_index
                )
                chunks.append(chunk)
                chunk_index += 1
                current_block = []
                current_start = i
                current_func = match.group(2)

            elif match:
                current_func = match.group(2)
                current_start = i

            current_block.append(line)

        # Flush last block
        if current_block:
            chunks.append(self._make_chunk(
                repo_id, rel_path, "python", module_name,
                current_block, current_start, len(lines), current_func, chunk_index
            ))

        return chunks if chunks else self._chunk_by_lines(
            lines, rel_path, repo_id, "python", module_name
        )

    def _chunk_by_lines(
        self,
        lines: List[str],
        rel_path: str,
        repo_id: str,
        language: str,
        module_name: str,
    ) -> List[CodeChunk]:
        """Sliding-window chunker: works for any language."""
        chunks: List[CodeChunk] = []
        step = CHUNK_SIZE - CHUNK_OVERLAP
        chunk_index = 0

        for start in range(0, len(lines), step):
            end = min(start + CHUNK_SIZE, len(lines))
            block = lines[start:end]
            if not "".join(block).strip():
                continue

            chunk = self._make_chunk(
                repo_id, rel_path, language, module_name,
                block, start + 1, end, "", chunk_index
            )
            chunks.append(chunk)
            chunk_index += 1

        return chunks

    def _make_chunk(
        self,
        repo_id: str,
        rel_path: str,
        language: str,
        module_name: str,
        lines: List[str],
        start_line: int,
        end_line: int,
        function_name: str,
        chunk_index: int,
    ) -> CodeChunk:
        safe_path = rel_path.replace("/", "_").replace("\\", "_").replace(".", "_")
        chunk_id = f"{repo_id}_{safe_path}_{chunk_index}"
        return CodeChunk(
            chunk_id=chunk_id,
            repo_id=repo_id,
            file_path=rel_path,
            language=language,
            content="\n".join(lines),
            start_line=start_line,
            end_line=end_line,
            function_name=function_name,
            module_name=module_name,
            chunk_index=chunk_index,
        )

    def _extract_module_name(self, rel_path: str) -> str:
        """Derive a human-readable module name from the file path."""
        parts = rel_path.replace("\\", "/").split("/")
        # Use the parent directory name as module (if not root)
        if len(parts) > 1:
            return parts[-2]
        return os.path.splitext(parts[-1])[0]

    def get_file_tree(self, repo_path: str) -> List[str]:
        """Return sorted list of relative file paths (supported types only)."""
        files = []
        for root, dirs, filenames in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for f in filenames:
                ext = os.path.splitext(f)[1].lower()
                if ext in SUPPORTED_EXTENSIONS and f not in IGNORE_FILES:
                    full = os.path.join(root, f)
                    files.append(os.path.relpath(full, repo_path))
        return sorted(files)
