from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

from sentence_transformers import CrossEncoder

from ..config import get_runtime_settings
from .bm25 import BM25Index
from .dense import ChromaDenseEmbeddingAdapter, DenseEmbeddingAdapter, SimpleDenseEmbeddingAdapter
from .models import RankedChunk
from .stores import ChunkStore

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(dense_ranks: list[str], sparse_ranks: list[str], dense_weight: float = 0.7, sparse_weight: float = 0.3) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for rank, item in enumerate(dense_ranks, start=1):
        scores[item] = scores.get(item, 0.0) + dense_weight * (1.0 / rank)
    for rank, item in enumerate(sparse_ranks, start=1):
        scores[item] = scores.get(item, 0.0) + sparse_weight * (1.0 / rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


class Reranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        try:
            self.model = CrossEncoder(model_name, device="cpu")
            self.enabled = True
            logger.info("Reranker CrossEncoder loaded successfully.")
        except Exception as e:
            logger.error("Failed to load CrossEncoder model %s. Reranking will be disabled: %s", model_name, e)
            self.enabled = False

    def rerank(self, query: str, chunks: list[Any]) -> list[RankedChunk]:
        ranked: list[RankedChunk] = []
        if not chunks:
            return ranked

        if self.enabled:
            try:
                pairs = [(query, getattr(chunk, "text", str(chunk))) for chunk in chunks]
                scores = self.model.predict(pairs)
                for chunk, score in zip(chunks, scores):
                    ranked.append(
                        RankedChunk(
                            text=getattr(chunk, "text", str(chunk)),
                            source=getattr(chunk, "source", "unknown"),
                            section_heading=getattr(chunk, "section_heading", None),
                            page_number=getattr(chunk, "page_number", None),
                            dense_score=0.0,
                            sparse_score=0.0,
                            fused_score=0.0,
                            rerank_score=float(score),
                            chunk_index=getattr(chunk, "chunk_index", 0),
                        )
                    )
                ranked.sort(key=lambda item: item.rerank_score, reverse=True)
                logger.debug("Reranked %d chunks successfully.", len(chunks))
                return ranked
            except Exception as e:
                logger.error("Reranking prediction failed: %s. Falling back to simple ranking.", e)

        # Fallback simple ranking using token overlap
        normalized_query = query.lower().split()
        for chunk in chunks:
            text = getattr(chunk, "text", str(chunk)).lower()
            overlap = sum(1 for token in normalized_query if token in text)
            score = float(overlap) / max(1, len(normalized_query))
            ranked.append(
                RankedChunk(
                    text=getattr(chunk, "text", str(chunk)),
                    source=getattr(chunk, "source", "unknown"),
                    section_heading=getattr(chunk, "section_heading", None),
                    page_number=getattr(chunk, "page_number", None),
                    dense_score=0.0,
                    sparse_score=0.0,
                    fused_score=0.0,
                    rerank_score=score,
                    chunk_index=getattr(chunk, "chunk_index", 0),
                )
            )
        ranked.sort(key=lambda item: item.rerank_score, reverse=True)
        return ranked


class HybridRetriever:
    def __init__(
        self,
        storage_dir: Path | str,
        processed_dir: Path | str,
        dense_adapter: DenseEmbeddingAdapter | None = None,
        rrf_dense_weight: float | None = None,
        rrf_sparse_weight: float | None = None,
    ):
        self.storage_dir = Path(storage_dir)
        self.processed_dir = Path(processed_dir)
        self.chunk_store = ChunkStore(self.processed_dir, self.storage_dir)
        self.reranker = Reranker()
        self.bm25_index = BM25Index(self.storage_dir / "bm25_index.pkl")
        self.settings = get_runtime_settings()
        self.dense_adapter = dense_adapter or self._build_dense_adapter()
        self.rrf_dense_weight = (
            rrf_dense_weight if rrf_dense_weight is not None else self.settings.rrf_dense_weight
        )
        self.rrf_sparse_weight = (
            rrf_sparse_weight if rrf_sparse_weight is not None else self.settings.rrf_sparse_weight
        )

    def _build_dense_adapter(self) -> DenseEmbeddingAdapter:
        try:
            adapter = ChromaDenseEmbeddingAdapter(self.storage_dir, self.settings.embedding_collection_name)
            logger.info("ChromaDenseEmbeddingAdapter successfully initialized for retrieval.")
            return adapter
        except Exception as e:
            logger.warning("Failed to initialize ChromaDenseEmbeddingAdapter: %s. Falling back to SimpleDenseEmbeddingAdapter.", e)
            return SimpleDenseEmbeddingAdapter()

    def retrieve(self, query: str, top_k: int = 5, retrieval_mode: str = "hybrid") -> list[RankedChunk]:
        logger.info("Starting retrieval for query: '%s', mode: %s, top_k: %d", query, retrieval_mode, top_k)
        chunks = self.chunk_store.get_chunks()
        if not chunks:
            logger.warning("No chunks available in ChunkStore. Retrieval returning empty list.")
            return []

        # --- Dense results ---
        dense_search_results = self.dense_adapter.search(query, chunks, top_k=self.settings.dense_top_k)
        dense_scores: dict[str, float] = {
            self._to_identifier(chunk): score for chunk, score in dense_search_results
        }
        dense_ranks: list[str] = [
            identifier
            for identifier, _ in sorted(dense_scores.items(), key=lambda kv: kv[1], reverse=True)
        ]
        logger.debug("Dense retrieval returned %d candidates.", len(dense_ranks))

        # --- Sparse / BM25 results ---
        sparse_scores: dict[str, float] = {}
        if self.bm25_index.documents:
            bm25_results = self.bm25_index.search(query, top_k=10)
            for doc_id, score in bm25_results:
                if doc_id < len(chunks):
                    identifier = self._to_identifier(chunks[doc_id])
                    sparse_scores[identifier] = score
        else:
            logger.warning("BM25 index is empty; sparse retrieval skipped")

        sparse_ranks: list[str] = [
            identifier
            for identifier, _ in sorted(sparse_scores.items(), key=lambda kv: kv[1], reverse=True)
        ]
        logger.debug("Sparse retrieval returned %d candidates.", len(sparse_ranks))

        # --- Fusion ---
        if retrieval_mode == "dense":
            fused = [(identifier, 1.0 / (rank + 1)) for rank, identifier in enumerate(dense_ranks)]
        elif retrieval_mode == "sparse":
            fused = [(identifier, 1.0 / (rank + 1)) for rank, identifier in enumerate(sparse_ranks)]
        else:
            fused = reciprocal_rank_fusion(
                dense_ranks,
                sparse_ranks,
                dense_weight=self.rrf_dense_weight,
                sparse_weight=self.rrf_sparse_weight,
            )

        fused_score_map: dict[str, float] = {item[0]: item[1] for item in fused}
        fused_items = fused[: self.settings.dense_top_k * 2]
        chunk_by_id = {self._to_identifier(chunk): chunk for chunk in chunks}
        candidate_chunks: list[Any] = []
        for identifier, fused_score in fused_items:
            if identifier in chunk_by_id:
                chunk = chunk_by_id[identifier]
                setattr(chunk, "fused_score", fused_score)
                candidate_chunks.append(chunk)
        logger.debug("Selected %d candidate chunks for reranking.", len(candidate_chunks))
        reranked = self.reranker.rerank(query, candidate_chunks)

        # --- Build final ranked list ---
        ranked: list[RankedChunk] = []
        for chunk in reranked[:top_k]:
            identifier = self._to_identifier(chunk)
            ranked.append(
                RankedChunk(
                    text=chunk.text,
                    source=chunk.source,
                    section_heading=chunk.section_heading,
                    page_number=chunk.page_number,
                    dense_score=dense_scores.get(identifier, 0.0),
                    sparse_score=sparse_scores.get(identifier, 0.0),
                    fused_score=fused_score_map.get(identifier, 0.0),
                    rerank_score=chunk.rerank_score,
                    chunk_index=getattr(chunk, "chunk_index", 0),
                )
            )
            logger.debug(
                "Result chunk: source=%s, page=%s, rerank_score=%.4f, fused_score=%.4f, dense=%.4f, sparse=%.4f",
                chunk.source,
                chunk.page_number,
                chunk.rerank_score,
                fused_score_map.get(identifier, 0.0),
                dense_scores.get(identifier, 0.0),
                sparse_scores.get(identifier, 0.0)
            )
        logger.info("Retrieval completed. Returning top %d chunks.", len(ranked))
        return ranked

    def _to_identifier(self, chunk: Any) -> str:
        return getattr(chunk, "source", str(chunk)) + ":" + str(getattr(chunk, "chunk_index", 0))
