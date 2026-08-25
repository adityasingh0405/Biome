from types import SimpleNamespace

from biome_rag.retrieval.dense import ChromaDenseEmbeddingAdapter
from biome_rag.retrieval.engine import Reranker


class FakeCollection:
    def __init__(self, returned_ids, returned_distances):
        self.returned_ids = returned_ids
        self.returned_distances = returned_distances

    def query(self, query_texts, n_results):
        return {
            "ids": [self.returned_ids],
            "documents": [["matched"]],
            "distances": [self.returned_distances],
        }


def test_chroma_dense_search_returns_the_actual_matched_chunk(tmp_path):
    adapter = ChromaDenseEmbeddingAdapter.__new__(ChromaDenseEmbeddingAdapter)
    adapter.storage_dir = tmp_path
    adapter.collection_name = "demo"
    adapter._collection = None

    chunks = [
        SimpleNamespace(text=f"chunk-{index}", source="source", section_heading=None, page_number=None, chunk_index=index)
        for index in range(5)
    ]
    target = chunks[3]
    adapter._collection = FakeCollection([adapter._chunk_id(target)], [0.25])

    ranked = adapter.search("query", chunks, top_k=3)

    assert ranked[0][0] is target
    assert ranked[0][1] == 0.75


def test_reranker_uses_semantic_relevance_not_keyword_overlap():
    reranker = Reranker(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2")
    chunks = [
        SimpleNamespace(text="The meeting agenda covers staffing and budget planning.", source="notes", section_heading=None, page_number=None, chunk_index=0),
        SimpleNamespace(text="To regain entry to the account, follow the recovery steps for account access.", source="docs", section_heading=None, page_number=None, chunk_index=1),
    ]

    ranked = reranker.rerank("How can I recover access to my account?", chunks)

    assert ranked[0].text == "To regain entry to the account, follow the recovery steps for account access."
