"""ChromaDB persistent vector store for report chunks (RAG stage).

Each user gets their own Chroma collection, and every chunk carries a
`report_id` metadata field so queries are scoped to one report. The embedding
function is injected so the store can be tested without any network calls.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

import chromadb
from chromadb.config import Settings as ChromaSettings

Embedder = Callable[[list[str]], list[list[float]]]


@dataclass
class RetrievedChunk:
    chunk_index: int
    text: str
    score: float | None  # cosine distance from Chroma (lower = closer)


class VectorStore:
    def __init__(self, persist_dir: str | Path, embed: Embedder):
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(persist_dir), settings=ChromaSettings(anonymized_telemetry=False)
        )
        self._embed = embed

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _collection_name(user_id: str) -> str:
        # Chroma names: 3-63 chars, alphanumeric/underscore/hyphen.
        return f"user_{''.join(ch for ch in user_id if ch.isalnum())[:50]}"

    def _collection(self, user_id: str):
        return self._client.get_or_create_collection(
            name=self._collection_name(user_id), metadata={"hnsw:space": "cosine"}
        )

    @staticmethod
    def _ids(report_id: str, n: int) -> list[str]:
        return [f"{report_id}:{i}" for i in range(n)]

    # ------------------------------------------------------------ public API
    def index_report(self, user_id: str, report_id: str, chunks: Sequence[str]) -> int:
        """(Re)index a report. Old vectors for the same report are removed first."""
        col = self._collection(user_id)
        self.delete_report(user_id, report_id)
        chunks = [c for c in chunks if c and c.strip()]
        if not chunks:
            return 0
        embeddings = self._embed(list(chunks))
        col.add(
            ids=self._ids(report_id, len(chunks)),
            documents=list(chunks),
            embeddings=embeddings,
            metadatas=[{"report_id": report_id, "chunk_index": i} for i in range(len(chunks))],
        )
        return len(chunks)

    def delete_report(self, user_id: str, report_id: str) -> None:
        col = self._collection(user_id)
        existing = col.get(where={"report_id": report_id}, include=[])
        if existing["ids"]:
            col.delete(ids=existing["ids"])

    def count(self, user_id: str, report_id: str) -> int:
        col = self._collection(user_id)
        return len(col.get(where={"report_id": report_id}, include=[])["ids"])

    def has_index(self, user_id: str, report_id: str) -> bool:
        return self.count(user_id, report_id) > 0

    def query(self, user_id: str, report_id: str, question: str, top_k: int = 5) -> list[RetrievedChunk]:
        col = self._collection(user_id)
        available = self.count(user_id, report_id)
        if available == 0:
            return []
        q_emb = self._embed([question])[0]
        res = col.query(
            query_embeddings=[q_emb],
            n_results=min(top_k, available),
            where={"report_id": report_id},
            include=["documents", "metadatas", "distances"],
        )
        docs = res["documents"][0]
        metas = res["metadatas"][0]
        dists = res.get("distances", [[None] * len(docs)])[0]
        return [
            RetrievedChunk(chunk_index=int(m["chunk_index"]), text=d, score=(float(s) if s is not None else None))
            for d, m, s in zip(docs, metas, dists)
        ]


# ---------------------------------------------------------------- FastAPI wiring
_store_singleton: "VectorStore | None" = None


def get_vector_store() -> "VectorStore":
    """FastAPI dependency: a process-wide store that embeds with Gemini."""
    global _store_singleton
    if _store_singleton is None:
        from app.config import get_settings
        from app.services.gemini_client import get_gemini

        gemini = get_gemini()
        _store_singleton = VectorStore(persist_dir=get_settings().chroma_dir, embed=gemini.embed)
    return _store_singleton
