from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .models import RankedChunk
from .stores import ChunkStore


def reciprocal_rank_fusion(dense_ranks: list[str], sparse_ranks: list[str], dense_weight: float = 0.7, sparse_weight: float = 0.3) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for rank, item in enumerate(dense_ranks, start=1):
        scores[item] = scores.get(item, 0.0) + dense_weight * (1.0 / rank)
    for rank, item in enumerate(sparse_ranks, start=1):
        scores[item] = scores.get(item, 0.0) + sparse_weight * (1.0 / rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


class DenseScorer:
    def score(self, query: str, chunk: Any) -> float:
        query_tokens = set(query.lower().split())
        chunk_tokens = set(getattr(chunk, "text", str(chunk)).lower().split())
        overlap = len(query_tokens & chunk_tokens)
        return float(overlap)


class SparseScorer:
    def score(self, query: str, chunk: Any) -> float:
        query_tokens = set(query.lower().split())
        chunk_tokens = set(getattr(chunk, "text", str(chunk)).lower().split())
        return float(len(query_tokens & chunk_tokens))


class Reranker:
    def rerank(self, query: str, chunks: list[Any]) -> list[RankedChunk]:
        ranked: list[RankedChunk] = []
        for chunk in chunks:
            text = getattr(chunk, "text", str(chunk))
            score = self._keyword_overlap(query, text)
            ranked.append(
                RankedChunk(
                    text=text,
                    source=getattr(chunk, "source", "unknown"),
                    section_heading=getattr(chunk, "section_heading", None),
                    page_number=getattr(chunk, "page_number", None),
                    dense_score=0.0,
                    sparse_score=0.0,
                    fused_score=0.0,
                    rerank_score=score,
                )
            )
        ranked.sort(key=lambda item: item.rerank_score, reverse=True)
        return ranked

    def _keyword_overlap(self, query: str, text: str) -> float:
        query_terms = set(query.lower().split())
        text_terms = set(text.lower().split())
        return float(len(query_terms & text_terms))


class HybridRetriever:
    def __init__(self, storage_dir: Path | str, processed_dir: Path | str):
        self.storage_dir = Path(storage_dir)
        self.processed_dir = Path(processed_dir)
        self.chunk_store = ChunkStore(self.processed_dir, self.storage_dir)
        self.dense_scorer = DenseScorer()
        self.sparse_scorer = SparseScorer()
        self.reranker = Reranker()

    def retrieve(self, query: str, top_k: int = 5) -> list[RankedChunk]:
        chunks = self.chunk_store.get_chunks()
        dense_scores = [(chunk, self.dense_scorer.score(query, chunk)) for chunk in chunks]
        sparse_scores = [(chunk, self.sparse_scorer.score(query, chunk)) for chunk in chunks]
        dense_ranks = [self._to_identifier(chunk) for chunk, _ in sorted(dense_scores, key=lambda item: item[1], reverse=True)[:10]]
        sparse_ranks = [self._to_identifier(chunk) for chunk, _ in sorted(sparse_scores, key=lambda item: item[1], reverse=True)[:10]]
        fused = reciprocal_rank_fusion(dense_ranks, sparse_ranks)
        fused_ids = [item[0] for item in fused[:20]]
        candidate_chunks = [chunk for chunk in chunks if self._to_identifier(chunk) in fused_ids]
        reranked = self.reranker.rerank(query, candidate_chunks)
        ranked = []
        for chunk in reranked[:top_k]:
            ranked.append(
                RankedChunk(
                    text=chunk.text,
                    source=chunk.source,
                    section_heading=chunk.section_heading,
                    page_number=chunk.page_number,
                    dense_score=self.dense_scorer.score(query, chunk),
                    sparse_score=self.sparse_scorer.score(query, chunk),
                    fused_score=0.0,
                    rerank_score=chunk.rerank_score,
                )
            )
        return ranked[:top_k]

    def _to_identifier(self, chunk: Any) -> str:
        return getattr(chunk, "source", str(chunk)) + ":" + str(getattr(chunk, "chunk_index", 0))
