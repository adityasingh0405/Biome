from biome_rag.retrieval.bm25 import BM25Index
from biome_rag.retrieval.engine import HybridRetriever, reciprocal_rank_fusion
from biome_rag.retrieval.models import RankedChunk
from biome_rag.retrieval.dense import DenseEmbeddingAdapter


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


def test_bm25_index_persists_and_reloads(tmp_path):
    path = tmp_path / "bm25.pkl"
    index = BM25Index(path)
    index.build(["Authentication token required", "Deployment target missing"])
    index.save()

    reloaded = BM25Index(path)
    reloaded.load()

    assert reloaded.search("authentication", top_k=1)[0][0] == 0


class StubDenseAdapter(DenseEmbeddingAdapter):
    def search(self, query: str, chunks: list[object], top_k: int = 5) -> list[tuple[object, float]]:
        dense_order = ["dense-only", "sparse-only"]
        return [(chunks[dense_order.index(chunk.text)] if chunk.text in dense_order else chunks[0], 0.95) for chunk in chunks]


def test_hybrid_retriever_fuses_dense_and_sparse_signals(tmp_path):
    chunks = [
        type("Chunk", (), {"text": "dense-only", "source": "a", "section_heading": None, "page_number": None, "chunk_index": 0, "chunking_strategy": "fixed", "character_count": 30})(),
        type("Chunk", (), {"text": "sparse-only", "source": "b", "section_heading": None, "page_number": None, "chunk_index": 1, "chunking_strategy": "fixed", "character_count": 30})(),
    ]

    retriever = HybridRetriever(storage_dir=tmp_path, processed_dir=tmp_path, dense_adapter=StubDenseAdapter())
    retriever.chunk_store.chunks = chunks
    retriever.bm25_index.documents = ["sparse-only", "dense-only"]
    retriever.bm25_index.index = {"sparse": {0: 1}, "dense": {1: 1}}
    retriever.bm25_index.doc_freq = {"sparse": 1, "dense": 1}

    ranked = retriever.retrieve("dense sparse", top_k=2)

    assert [chunk.text for chunk in ranked] == ["dense-only", "sparse-only"]
    assert ranked[0].fused_score >= ranked[1].fused_score
