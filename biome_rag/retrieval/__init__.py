"""Retrieval package — biome_rag.retrieval.

Exports all retrieval primitives including the Phase 3 additions.

Priority adapter chain:
    QdrantAdapter (bge-m3, native hybrid)
    → ChromaDenseEmbeddingAdapter (sentence-transformers, local ChromaDB)
    → SimpleDenseEmbeddingAdapter (token-overlap fallback)
"""
from biome_rag.retrieval.bm25 import BM25Index
from biome_rag.retrieval.dense import (
    ChromaDenseEmbeddingAdapter,
    DenseEmbeddingAdapter,
    SimpleDenseEmbeddingAdapter,
)
from biome_rag.retrieval.embeddings import BGE_M3Encoder
from biome_rag.retrieval.engine import HybridRetriever, Reranker, reciprocal_rank_fusion
from biome_rag.retrieval.models import RankedChunk
from biome_rag.retrieval.qdrant_store import QdrantAdapter
from biome_rag.retrieval.stores import ChunkStore

__all__ = [
    # Engine
    "HybridRetriever",
    "Reranker",
    "reciprocal_rank_fusion",
    # Models
    "RankedChunk",
    # Adapters
    "DenseEmbeddingAdapter",
    "SimpleDenseEmbeddingAdapter",
    "ChromaDenseEmbeddingAdapter",
    "QdrantAdapter",          # Phase 3: primary dense adapter
    "BGE_M3Encoder",          # Phase 3: dual-encoder
    # Stores
    "BM25Index",
    "ChunkStore",
]
