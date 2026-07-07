from biome_rag.evaluation.metrics import (
    answer_correctness,
    citation_accuracy,
    faithfulness,
    retrieval_relevance,
)


def test_metrics_return_numeric_scores():
    assert 0.0 <= answer_correctness("A", "A") <= 1.0
    assert 0.0 <= faithfulness("A", "A") <= 1.0
    assert 0.0 <= retrieval_relevance(["doc-1"], ["doc-1"]) <= 1.0
    assert 0.0 <= citation_accuracy([True, False], [True, True]) <= 1.0
