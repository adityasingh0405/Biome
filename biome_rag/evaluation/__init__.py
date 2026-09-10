"""biome_rag.evaluation — Phase 6 evaluation package."""
from biome_rag.evaluation.metrics import (
    answer_correctness,
    citation_accuracy,
    faithfulness,
    mean_reciprocal_rank,
    precision_at_k,
    retrieval_relevance,
)
from biome_rag.evaluation.extended_metrics import (
    EvalThresholds,
    ThresholdViolation,
    answer_relevancy,
    check_thresholds,
    context_precision,
    context_recall,
    hallucination_score,
    is_hallucinated,
    noise_robustness,
    semantic_similarity,
)
from biome_rag.evaluation.harness import (
    AggregateResult,
    EvalReport,
    EvaluationHarness,
    QuestionResult,
)

__all__ = [
    # Lexical metrics
    "answer_correctness", "citation_accuracy", "faithfulness",
    "mean_reciprocal_rank", "precision_at_k", "retrieval_relevance",
    # Extended metrics
    "answer_relevancy", "context_precision", "context_recall",
    "hallucination_score", "is_hallucinated", "noise_robustness",
    "semantic_similarity",
    # Thresholds
    "EvalThresholds", "ThresholdViolation", "check_thresholds",
    # Harness
    "EvaluationHarness", "EvalReport", "QuestionResult", "AggregateResult",
]
