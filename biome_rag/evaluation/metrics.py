from __future__ import annotations

from typing import Iterable


def answer_correctness(predicted: str, golden: str) -> float:
    if not predicted or not golden:
        return 0.0
    predicted_tokens = set(predicted.lower().split())
    golden_tokens = set(golden.lower().split())
    if not golden_tokens:
        return 0.0
    overlap = predicted_tokens & golden_tokens
    return round(len(overlap) / max(1, len(golden_tokens)), 3)


def faithfulness(claim: str, context: str) -> float:
    if not claim or not context:
        return 0.0
    claim_tokens = set(claim.lower().split())
    context_tokens = set(context.lower().split())
    overlap = claim_tokens & context_tokens
    return round(len(overlap) / max(1, len(claim_tokens)), 3)


def retrieval_relevance(retrieved_ids: Iterable[str], golden_ids: Iterable[str]) -> float:
    retrieved = set(retrieved_ids)
    golden = set(golden_ids)
    if not golden:
        return 0.0
    overlap = retrieved & golden
    return round(len(overlap) / len(golden), 3)


def citation_accuracy(verified_flags: Iterable[bool], expected_flags: Iterable[bool]) -> float:
    verified = list(verified_flags)
    expected = list(expected_flags)
    if not verified or not expected:
        return 0.0
    matches = sum(1 for left, right in zip(verified, expected) if left == right)
    return round(matches / max(1, min(len(verified), len(expected))), 3)
