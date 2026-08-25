from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from sklearn.metrics.pairwise import cosine_similarity


import logging

logger = logging.getLogger(__name__)


class DenseEmbeddingAdapter:
    """Simple adapter interface for dense retrieval backends."""

    def index_documents(self, chunks: list[object]) -> None:
        raise NotImplementedError

    def search(self, query: str, chunks: list[object], top_k: int = 5) -> list[tuple[object, float]]:
        raise NotImplementedError


class SimpleDenseEmbeddingAdapter(DenseEmbeddingAdapter):
    """Fallback adapter that uses token overlap as a lightweight dense signal when Chroma is unavailable."""

    def index_documents(self, chunks: list[object]) -> None:
        return None

    def search(self, query: str, chunks: list[object], top_k: int = 5) -> list[tuple[object, float]]:
        normalized_query = query.lower().split()
        scored: list[tuple[object, float]] = []
        for chunk in chunks:
            text = str(getattr(chunk, "text", chunk)).lower()
            token_matches = sum(1 for token in normalized_query if token in text)
            score = float(token_matches) / max(1, len(normalized_query))
            scored.append((chunk, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]


class ChromaDenseEmbeddingAdapter(DenseEmbeddingAdapter):
    """Persisted vector-search adapter backed by a local Chroma collection when available."""

    def __init__(self, storage_dir: str | Path, collection_name: str | None = None):
        self.storage_dir = Path(storage_dir)
        self.collection_name = collection_name or os.getenv("EMBEDDING_COLLECTION_NAME", "biome-chunks")
        self._collection = None
        self._ensure_dependencies()

    def _ensure_dependencies(self) -> None:
        try:
            import chromadb  # type: ignore
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("chromadb is required for dense retrieval") from exc
        self._chromadb = chromadb

    def _get_collection(self):
        if self._collection is not None:
            return self._collection
        client = self._chromadb.PersistentClient(path=str(self.storage_dir / "chroma"))
        self._collection = client.get_or_create_collection(name=self.collection_name)
        return self._collection

    def index_documents(self, chunks: list[object]) -> None:
        if not chunks:
            return None
        try:
            collection = self._get_collection()
            ids = [self._chunk_id(chunk) for chunk in chunks]
            texts = [str(getattr(chunk, "text", chunk)) for chunk in chunks]
            collection.add(ids=ids, documents=texts, metadatas=[self._metadata(chunk) for chunk in chunks])
            logger.info("Indexed %d documents into Chroma collection: %s", len(chunks), self.collection_name)
        except Exception as e:
            logger.exception("Failed to index documents in Chroma: %s", e)

    def search(self, query: str, chunks: list[object], top_k: int = 5) -> list[tuple[object, float]]:
        if not chunks:
            return []
        try:
            collection = self._get_collection()
            results = collection.query(query_texts=[query], n_results=min(top_k, len(chunks)))
            returned_ids = results.get("ids", [[]])[0]
            distances = results.get("distances", [[]])[0]
            chunk_by_id = {self._chunk_id(chunk): chunk for chunk in chunks}
            ranked: list[tuple[object, float]] = []
            for chunk_id, distance in zip(returned_ids, distances):
                chunk = chunk_by_id.get(chunk_id)
                if chunk is None:
                    continue
                # Convert distance to a similarity score (cosine distance is typically 0 to 2)
                # Keep similarity score bounded between 0 and 1
                sim_score = max(0.0, min(1.0, 1.0 - float(distance)))
                ranked.append((chunk, sim_score))
            logger.debug("Chroma dense search completed successfully. Returned %d matches.", len(ranked))
            return ranked
        except Exception as e:
            logger.error("Chroma query failed (falling back to empty dense results): %s", e, exc_info=True)
            return []

    def _chunk_id(self, chunk: object) -> str:
        return hashlib.sha256(json.dumps(getattr(chunk, "text", str(chunk)), sort_keys=True).encode("utf-8")).hexdigest()

    def _metadata(self, chunk: object) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "source": str(getattr(chunk, "source", "unknown")),
            "chunk_index": int(getattr(chunk, "chunk_index", 0)),
        }
        heading = getattr(chunk, "section_heading", None)
        if heading is not None:
            meta["section_heading"] = str(heading)
        page = getattr(chunk, "page_number", None)
        if page is not None:
            meta["page_number"] = int(page)
        return meta
