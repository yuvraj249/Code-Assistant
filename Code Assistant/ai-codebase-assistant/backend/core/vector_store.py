# """
# Vector Store - ChromaDB Integration
# Handles embedding generation (via OpenAI) and similarity search.
# """

# import os
# from typing import List, Dict, Any, Tuple
# import chromadb
# from chromadb.config import Settings
# from openai import OpenAI

# from core.parser import CodeChunk

# EMBED_MODEL = "text-embedding-3-small"
# CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
# TOP_K = 8  # number of chunks to retrieve per query


# class VectorStore:
#     """Wraps ChromaDB + OpenAI embeddings for the RAG pipeline."""

#     def __init__(self):
#         self.client = chromadb.PersistentClient(
#             path=CHROMA_PATH,
#             settings=Settings(anonymized_telemetry=False),
#         )
#         self.openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

#     # ─── Embedding Helpers ────────────────────────────────────────────────────

#     def embed_texts(self, texts: List[str]) -> List[List[float]]:
#         """Batch-embed a list of strings using OpenAI."""
#         # OpenAI supports up to 2048 inputs per call; chunk if needed
#         all_embeddings: List[List[float]] = []
#         batch_size = 100

#         for i in range(0, len(texts), batch_size):
#             batch = texts[i : i + batch_size]
#             response = self.openai.embeddings.create(
#                 model=EMBED_MODEL, input=batch
#             )
#             all_embeddings.extend([item.embedding for item in response.data])

#         return all_embeddings

#     def embed_query(self, query: str) -> List[float]:
#         """Embed a single query string."""
#         response = self.openai.embeddings.create(
#             model=EMBED_MODEL, input=[query]
#         )
#         return response.data[0].embedding

#     # ─── Collection Management ────────────────────────────────────────────────

#     def _collection_name(self, repo_id: str) -> str:
#         """ChromaDB collection names must be 3-63 chars, alphanumeric + hyphens."""
#         safe = repo_id[:60].replace("/", "-").replace("_", "-").replace(".", "-")
#         return f"repo-{safe}"

#     def get_or_create_collection(self, repo_id: str):
#         return self.client.get_or_create_collection(
#             name=self._collection_name(repo_id),
#             metadata={"hnsw:space": "cosine"},
#         )

#     def collection_exists(self, repo_id: str) -> bool:
#         try:
#             self.client.get_collection(self._collection_name(repo_id))
#             return True
#         except Exception:
#             return False

#     def delete_collection(self, repo_id: str):
#         try:
#             self.client.delete_collection(self._collection_name(repo_id))
#         except Exception:
#             pass

#     # ─── Indexing ──────────
# ───────────────────────────────────────────────────

#     def index_chunks(self, chunks: List[CodeChunk], repo_id: str):
#         """
#         Embed all code chunks and upsert them into ChromaDB.
#         Processes in batches to stay within API limits.
#         """
#         collection = self.get_or_create_collection(repo_id)
#         batch_size = 50

#         print(f"[vectorstore] Indexing {len(chunks)} chunks for repo '{repo_id}'…")

#         for i in range(0, len(chunks), batch_size):
#             batch = chunks[i : i + batch_size]
#             texts = [c.content for c in batch]
#             embeddings = self.embed_texts(texts)

#             ids = [c.chunk_id for c in batch]
#             metadatas = [
#                 {
#                     "file_path": c.file_path,
#                     "language": c.language,
#                     "function_name": c.function_name,
#                     "module_name": c.module_name,
#                     "start_line": c.start_line,
#                     "end_line": c.end_line,
#                     "repo_id": c.repo_id,
#                 }
#                 for c in batch
#             ]

#             collection.upsert(
#                 ids=ids,
#                 embeddings=embeddings,
#                 documents=texts,
#                 metadatas=metadatas,
#             )

#         print(f"[vectorstore] Done indexing {len(chunks)} chunks.")

#     # ─── Retrieval ────────────────────────────────────────────────────────────

#     def search(
#         self, query: str, repo_id: str, top_k: int = TOP_K
#     ) -> List[Dict[str, Any]]:
#         """
#         Embed the query, run cosine similarity search in ChromaDB,
#         return top-k results with content + metadata.
#         """
#         collection = self.get_or_create_collection(repo_id)
#         query_embedding = self.embed_query(query)

#         results = collection.query(
#             query_embeddings=[query_embedding],
#             n_results=top_k,
#             include=["documents", "metadatas", "distances"],
#         )

#         hits = []
#         for doc, meta, dist in zip(
#             results["documents"][0],
#             results["metadatas"][0],
#             results["distances"][0],
#         ):
#             hits.append(
#                 {
#                     "content": doc,
#                     "file_path": meta.get("file_path", ""),
#                     "function_name": meta.get("function_name", ""),
#                     "module_name": meta.get("module_name", ""),
#                     "language": meta.get("language", ""),
#                     "start_line": meta.get("start_line", 0),
#                     "end_line": meta.get("end_line", 0),
#                     "similarity": 1 - dist,  # cosine distance → similarity
#                 }
#             )

#         return hits

#     def list_repos(self) -> List[str]:
#         """Return all repo_ids that have been indexed."""
#         collections = self.client.list_collections()
#         return [c.name.replace("repo-", "", 1) for c in collections]


"""
Vector Store - ChromaDB Integration
Handles embedding generation (via local sentence-transformers) and similarity search.
"""

import os
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from core.parser import CodeChunk

CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
TOP_K = 8  # number of chunks to retrieve per query


class VectorStore:
    """Wraps ChromaDB + local embeddings for the RAG pipeline."""

    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
        # ✅ Load local embedding model
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    # ─── Embedding Helpers ────────────────────────────────────────────────────

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of strings using local model."""
        return self.model.encode(texts).tolist()

    def embed_query(self, query: str) -> List[float]:
        """Embed a single query string."""
        return self.model.encode([query])[0].tolist()

    # ─── Collection Management ────────────────────────────────────────────────

    def _collection_name(self, repo_id: str) -> str:
        """ChromaDB collection names must be 3-63 chars."""
        safe = repo_id[:60].replace("/", "-").replace("_", "-").replace(".", "-")
        return f"repo-{safe}"

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
        try:
            self.client.delete_collection(self._collection_name(repo_id))
        except Exception:
            pass

    # ─── Indexing ─────────────────────────────────────────────────────────────

    def index_chunks(self, chunks: List[CodeChunk], repo_id: str):
        """
        Embed all code chunks and store them in ChromaDB.
        """
        collection = self.get_or_create_collection(repo_id)
        batch_size = 50

        print(f"[vectorstore] Indexing {len(chunks)} chunks for repo '{repo_id}'…")

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i: i + batch_size]
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
        Embed query and perform similarity search.
        """
        collection = self.get_or_create_collection(repo_id)
        query_embedding = self.embed_query(query)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
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
                    "similarity": 1 - dist,
                }
            )

        return hits

    def list_repos(self) -> List[str]:
        """Return all indexed repo IDs."""
        collections = self.client.list_collections()
        return [c.name.replace("repo-", "", 1) for c in collections]
