"""
Vector Store - ChromaDB Integration
Handles embedding generation (via local sentence-transformers) and similarity search.
Embeddings are free/local — no OpenAI cost for indexing.
"""

import os
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from core.parser import CodeChunk

CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
TOP_K = 8


class VectorStore:
    """Wraps ChromaDB + local sentence-transformers embeddings for the RAG pipeline."""

    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
        print("[vectorstore] Loading embedding model (all-MiniLM-L6-v2)…")
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        print("[vectorstore] Embedding model loaded.")

    # ─── Embedding Helpers ────────────────────────────────────────────────────

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Batch-embed strings using the local model."""
        return self.model.encode(texts, show_progress_bar=False).tolist()

    def embed_query(self, query: str) -> List[float]:
        """Embed a single query string."""
        return self.model.encode([query], show_progress_bar=False)[0].tolist()

    # ─── Collection Management ────────────────────────────────────────────────

    def _collection_name(self, repo_id: str) -> str:
        """ChromaDB collection names must be 3-63 chars, alphanumeric + hyphens."""
        safe = repo_id[:58].replace("/", "-").replace("_", "-").replace(".", "-")
        return f"r-{safe}"

    def get_or_create_collection(self, repo_id: str):
        return self.client.get_or_create_collection(
            name=self._collection_name(repo_id),
            metadata={"hnsw:space": "cosine"},
        )

    def collection_exists(self, repo_id: str) -> bool:
        try:
            self.client.get_collection(self._collection_name(repo_id))
            return True
        except Exception:
            return False

    def delete_collection(self, repo_id: str):
        """Delete all vectors for a repo (used before re-ingesting)."""
        try:
            self.client.delete_collection(self._collection_name(repo_id))
            print(f"[vectorstore] Deleted collection for repo '{repo_id}'")
        except Exception:
            pass

    # ─── Indexing ─────────────────────────────────────────────────────────────

    def index_chunks(self, chunks: List[CodeChunk], repo_id: str):
        """
        Embed all code chunks and upsert them into ChromaDB.
        Processes in batches to stay within memory limits.
        """
        collection = self.get_or_create_collection(repo_id)
        batch_size = 50

        print(f"[vectorstore] Indexing {len(chunks)} chunks for repo '{repo_id}'…")

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c.content for c in batch]
            embeddings = self.embed_texts(texts)

            ids = [c.chunk_id for c in batch]
            metadatas = [
                {
                    "file_path": c.file_path,
                    "language": c.language,
                    "function_name": c.function_name,
                    "module_name": c.module_name,
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                    "repo_id": c.repo_id,
                }
                for c in batch
            ]

            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )

        print(f"[vectorstore] Done indexing {len(chunks)} chunks.")

    # ─── Retrieval ────────────────────────────────────────────────────────────

    def search(
        self, query: str, repo_id: str, top_k: int = TOP_K
    ) -> List[Dict[str, Any]]:
        """
        Embed the query, run cosine similarity search in ChromaDB,
        return top-k results with content + metadata.
        """
        if not self.collection_exists(repo_id):
            return []

        collection = self.get_or_create_collection(repo_id)
        query_embedding = self.embed_query(query)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        hits = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            hits.append(
                {
                    "content": doc,
                    "file_path": meta.get("file_path", ""),
                    "function_name": meta.get("function_name", ""),
                    "module_name": meta.get("module_name", ""),
                    "language": meta.get("language", ""),
                    "start_line": meta.get("start_line", 0),
                    "end_line": meta.get("end_line", 0),
                    "similarity": round(1 - dist, 4),  # cosine distance → similarity
                }
            )

        return hits

    def list_repo_ids(self) -> List[str]:
        """Return all indexed repo IDs from ChromaDB collections."""
        collections = self.client.list_collections()
        return [c.name[2:] for c in collections if c.name.startswith("r-")]
