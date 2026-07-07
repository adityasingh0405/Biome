from biome_rag.retrieval.engine import HybridRetriever, reciprocal_rank_fusion
from biome_rag.retrieval.models import RankedChunk


def test_reciprocal_rank_fusion_orders_candidates_by_weighted_ranks():
    dense_ranks = ["doc-a", "doc-b", "doc-c"]
    sparse_ranks = ["doc-b", "doc-a", "doc-d"]

    fused = reciprocal_rank_fusion(dense_ranks, sparse_ranks, dense_weight=0.7, sparse_weight=0.3)

    assert fused[0][0] == "doc-a"
    assert fused[1][0] == "doc-b"
    assert fused[2][0] == "doc-c"


def test_reranker_prefers_keyword_overlap(tmp_path):
    retriever = HybridRetriever(storage_dir=tmp_path, processed_dir=tmp_path)
    retriever.chunk_store.chunks = [
        type("Chunk", (), {"text": "Authentication failed with error E1001", "source": "a", "section_heading": None, "page_number": None, "chunk_index": 0, "chunking_strategy": "fixed", "character_count": 30})(),
        type("Chunk", (), {"text": "Deployment target missing", "source": "b", "section_heading": None, "page_number": None, "chunk_index": 1, "chunking_strategy": "fixed", "character_count": 30})(),
    ]

    ranked = retriever.reranker.rerank("authentication error", retriever.chunk_store.chunks[:2])

    assert ranked[0].text.startswith("Authentication")
