from __future__ import annotations

from pathlib import Path
from biome_rag.retrieval.engine import HybridRetriever
from biome_rag.retrieval.dense import DenseEmbeddingAdapter
from biome_rag.retrieval.models import RankedChunk


class DenseMissAdapter(DenseEmbeddingAdapter):
    """Simulates a dense retriever that ranks generic semantic text above exact code terms."""

    def index_documents(self, chunks: list[object]) -> None:
        pass

    def search(self, query: str, chunks: list[object], top_k: int = 5) -> list[tuple[object, float]]:
        # Dense vector search ranks doc-0 (generic security text) higher than doc-1 (exact key)
        return [(chunks[0], 0.90), (chunks[1], 0.30)]


def test_hybrid_retrieval_outperforms_dense_only_on_exact_term_query(tmp_path: Path):
    """Smoke test demonstrating the Hybrid Search advantage over Dense-Only.

    For an exact technical term query like 'BIOME_API_KEY', dense vector embeddings
    often smooth over exact token matches and rank general prose higher.
    BM25 sparse search correctly identifies the exact token match, and RRF fusion
    ensures the exact match chunk is ranked #1 in hybrid mode.
    """
    storage_dir = tmp_path / "index"
    processed_dir = tmp_path / "processed"
    storage_dir.mkdir(parents=True)
    processed_dir.mkdir(parents=True)

    retriever = HybridRetriever(
        storage_dir=storage_dir,
        processed_dir=processed_dir,
        dense_adapter=DenseMissAdapter(),
        rrf_dense_weight=0.5,
        rrf_sparse_weight=0.5,
    )
    # Mock reranker to pass candidate_chunks through in fused order for testing RRF
    retriever.reranker.rerank = lambda query, chunks: [
        RankedChunk(
            text=getattr(c, "text", str(c)),
            source=getattr(c, "source", "unknown"),
            section_heading=getattr(c, "section_heading", None),
            page_number=getattr(c, "page_number", None),
            dense_score=0.0,
            sparse_score=0.0,
            fused_score=getattr(c, "fused_score", 0.0),
            rerank_score=1.0,
        )
        for c in chunks
    ]

    chunk_generic = type(
        "Chunk",
        (),
        {
            "text": "Security guidelines for application deployment and network firewalls.",
            "source": "security.md",
            "section_heading": "Overview",
            "page_number": None,
            "chunk_index": 0,
            "chunking_strategy": "fixed",
            "character_count": 60,
        },
    )()

    chunk_exact = type(
        "Chunk",
        (),
        {
            "text": "All API requests require the BIOME_API_KEY environment variable.",
            "source": "api-reference.md",
            "section_heading": "Authentication",
            "page_number": None,
            "chunk_index": 1,
            "chunking_strategy": "fixed",
            "character_count": 65,
        },
    )()

    retriever.chunk_store.chunks = [chunk_generic, chunk_exact]
    retriever.bm25_index.documents = [chunk_generic.text, chunk_exact.text]
    retriever.bm25_index.build([chunk_generic.text, chunk_exact.text])

    query = "BIOME_API_KEY"

    # Dense-only retrieval ranks generic text #1 (simulated vector miss)
    dense_results = retriever.retrieve(query, top_k=2, retrieval_mode="dense")
    assert dense_results[0].source == "security.md"

    # Hybrid retrieval uses BM25 exact match + RRF to rank exact key chunk #1
    hybrid_results = retriever.retrieve(query, top_k=2, retrieval_mode="hybrid")
    assert hybrid_results[0].source == "api-reference.md"
    assert "BIOME_API_KEY" in hybrid_results[0].text
    assert hybrid_results[0].fused_score > hybrid_results[1].fused_score
