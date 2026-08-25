from __future__ import annotations

from typing import Iterable


def answer_correctness(predicted: str, golden: str) -> float:
    """F1-based token overlap between predicted and golden answers.

    Combines precision and recall so short exact answers and long paraphrased
    answers are both handled fairly.
    """
    if not predicted or not golden:
        return 0.0
    pred_tokens = set(predicted.lower().split())
    gold_tokens = set(golden.lower().split())
    if not gold_tokens:
        return 0.0
    overlap = pred_tokens & gold_tokens
    if not overlap:
        return 0.0
    precision = len(overlap) / len(pred_tokens)
    recall = len(overlap) / len(gold_tokens)
    f1 = 2 * precision * recall / (precision + recall)
    return round(f1, 3)


def faithfulness(claim: str, context: str) -> float:
    """Fraction of claim tokens that appear in the retrieved context.

    A score of 1.0 means every word in the answer is grounded in the context.
    """
    if not claim or not context:
        return 0.0
    claim_tokens = set(claim.lower().split())
    context_tokens = set(context.lower().split())
    if not claim_tokens:
        return 0.0
    overlap = claim_tokens & context_tokens
    return round(len(overlap) / len(claim_tokens), 3)


def _doc_name(chunk_id: str) -> str:
    """Extract document filename (e.g. 'api-reference.md') from 'path/to/api-reference.md:0'."""
    part = chunk_id.split(":")[0]
    return part.replace("\\", "/").split("/")[-1]


def retrieval_relevance(retrieved_ids: Iterable[str], golden_ids: Iterable[str]) -> float:
    """Recall@retrieved: fraction of expected chunk/doc IDs that were retrieved."""
    retrieved_list = list(retrieved_ids)
    golden_list = list(golden_ids)

    if not golden_list:
        return 0.0

    retrieved_set = set(retrieved_list)
    golden_set = set(golden_list)

    # First check exact ID overlap
    exact_overlap = retrieved_set & golden_set
    if exact_overlap:
        return round(len(exact_overlap) / len(golden_set), 3)

    # Fallback to document filename matching
    retrieved_docs = {_doc_name(r) for r in retrieved_list}
    golden_docs = {_doc_name(g) for g in golden_list}
    doc_overlap = retrieved_docs & golden_docs
    return round(len(doc_overlap) / len(golden_docs), 3)


def citation_accuracy(verified_flags: Iterable[bool], expected_flags: Iterable[bool]) -> float:
    """Fraction of citations that match their expected verification status."""
    verified = list(verified_flags)
    expected = list(expected_flags)
    if not verified or not expected:
        return 0.0
    n = min(len(verified), len(expected))
    matches = sum(1 for i in range(n) if verified[i] == expected[i])
    return round(matches / n, 3)


def precision_at_k(retrieved_ids: Iterable[str], golden_ids: Iterable[str], k: int = 5) -> float:
    """Precision at k: fraction of top-k retrieved that are relevant."""
    retrieved = list(retrieved_ids)[:k]
    golden = set(golden_ids)
    if not retrieved or not golden:
        return 0.0
    relevant = sum(1 for r in retrieved if r in golden)
    return round(relevant / len(retrieved), 3)
