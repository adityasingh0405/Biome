"""Root wrapper for retrieval module — mirrors target architecture layout."""
from biome_rag.retrieval import (
    BM25Index,
    ChunkStore,
    DenseEmbeddingAdapter,
    HybridRetriever,
    NL2SQLEngine,
    QdrantAdapter,
    QueryRouter,
    RankedChunk,
    Reranker,
    RouteDecision,
    StructuredQueryResult,
    reciprocal_rank_fusion,
)

__all__ = [
    "HybridRetriever",
    "Reranker",
    "reciprocal_rank_fusion",
    "QueryRouter",
    "NL2SQLEngine",
    "RouteDecision",
    "StructuredQueryResult",
    "RankedChunk",
    "DenseEmbeddingAdapter",
    "QdrantAdapter",
    "BM25Index",
    "ChunkStore",
]
