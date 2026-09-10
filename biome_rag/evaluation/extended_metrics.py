"""Phase 6 evaluation metrics — extends the lexical baseline in metrics.py.

New additions (all pure-Python, no LLM API required at import time):

  **Semantic similarity** (sentence-transformers, optional)
    - ``semantic_similarity(pred, golden)``  cosine sim of MiniLM embeddings

  **RAGAS-style metrics** (reference implementations without the RAGAS package)
    - ``context_precision(contexts, golden_answer)``  fraction of context chunks
      that contributed to the answer (token-overlap proxy)
    - ``context_recall(contexts, golden_answer)``  recall of golden answer tokens
      from the context window
    - ``answer_relevancy(question, answer)``  how directly the answer addresses
      the question (shared token coverage)
    - ``noise_robustness(answer, noise_chunks)``  1 − fraction of answer tokens
      sourced exclusively from irrelevant (noise) chunks

  **Hallucination detection** (lexical entailment proxy)
    - ``hallucination_score(answer, context)``  fraction of answer n-grams NOT
      entailed by the context; 0.0 = fully grounded, 1.0 = fully hallucinated
    - ``is_hallucinated(answer, context, threshold)``  boolean gate

  All of the above also work when ``sentence-transformers`` is not installed;
  they fall back to lexical methods in that case.

  **Threshold enforcement**
    - ``EvalThresholds`` dataclass — configurable pass/fail gates
    - ``check_thresholds(scores, thresholds)`` — returns list of violations

All functions are deterministic (no LLM calls) so they can run in CI without
any API keys.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Iterable

# sentence-transformers is optional
try:
    from sentence_transformers import SentenceTransformer as _ST  # type: ignore
    _ST_MODEL: _ST | None = None  # lazy-loaded
    _ST_AVAILABLE = True
except ImportError:
    _ST = None  # type: ignore
    _ST_AVAILABLE = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _tokens(text: str) -> set[str]:
    return set(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())


def _token_list(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9 ]", " ", text.lower()).split()


def _get_st_model():
    global _ST_MODEL
    if not _ST_AVAILABLE:
        return None
    if _ST_MODEL is None:
        try:
            _ST_MODEL = _ST("all-MiniLM-L6-v2")
        except Exception:
            return None
    return _ST_MODEL


def _cosine(a, b) -> float:
    """Cosine similarity between two numeric sequences."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _ngrams(tokens: list[str], n: int = 2) -> set[tuple[str, ...]]:
    return {tuple(tokens[i: i + n]) for i in range(len(tokens) - n + 1)}


# ---------------------------------------------------------------------------
# Semantic similarity (MiniLM fallback → token-F1)
# ---------------------------------------------------------------------------

def semantic_similarity(predicted: str, golden: str) -> float:
    """Cosine similarity of MiniLM sentence embeddings.

    Falls back to token-F1 (``answer_correctness``) when
    sentence-transformers is not installed.
    """
    if not predicted or not golden:
        return 0.0
    model = _get_st_model()
    if model is not None:
        try:
            embs = model.encode([predicted, golden], normalize_embeddings=True)
            score = float(_cosine(embs[0].tolist(), embs[1].tolist()))
            return round(max(0.0, score), 4)
        except Exception:
            pass
    # Token-F1 fallback
    from biome_rag.evaluation.metrics import answer_correctness  # noqa: PLC0415
    return answer_correctness(predicted, golden)


# ---------------------------------------------------------------------------
# RAGAS-style proxy metrics (no RAGAS package required)
# ---------------------------------------------------------------------------

def context_precision(contexts: list[str], golden_answer: str) -> float:
    """Fraction of context chunks that share ≥1 token with the golden answer.

    Approximates RAGAS context_precision without an LLM judge.
    """
    if not contexts or not golden_answer:
        return 0.0
    gold_tokens = _tokens(golden_answer)
    relevant = sum(1 for ctx in contexts if _tokens(ctx) & gold_tokens)
    return round(relevant / len(contexts), 4)


def context_recall(contexts: list[str], golden_answer: str) -> float:
    """Fraction of golden answer tokens covered by the context window.

    Approximates RAGAS context_recall without an LLM judge.
    """
    if not contexts or not golden_answer:
        return 0.0
    gold_tokens = _tokens(golden_answer)
    if not gold_tokens:
        return 0.0
    combined_tokens = set()
    for ctx in contexts:
        combined_tokens |= _tokens(ctx)
    covered = gold_tokens & combined_tokens
    return round(len(covered) / len(gold_tokens), 4)


def answer_relevancy(question: str, answer: str) -> float:
    """Token-overlap between question and answer (shared key-word coverage).

    A proxy for RAGAS answer_relevancy; higher = answer directly addresses q.
    """
    if not question or not answer:
        return 0.0
    q_tokens = _tokens(question)
    a_tokens = _tokens(answer)
    # Remove trivial stop words
    stop = {"what", "is", "the", "a", "an", "of", "in", "to", "how", "does", "do", "are", "why", "when", "where", "which", "who"}
    q_tokens -= stop
    if not q_tokens:
        return 0.0
    shared = q_tokens & a_tokens
    return round(len(shared) / len(q_tokens), 4)


def noise_robustness(answer: str, noise_chunks: list[str]) -> float:
    """1 − fraction of answer tokens that come ONLY from noise (irrelevant) chunks.

    noise_chunks should be chunks that were retrieved but are NOT relevant
    to the question.  A score of 1.0 means the answer is unaffected by noise.
    """
    if not answer or not noise_chunks:
        return 1.0
    a_tokens = _token_list(answer)
    if not a_tokens:
        return 1.0
    noise_tokens: set[str] = set()
    for nc in noise_chunks:
        noise_tokens |= _tokens(nc)
    noise_only = sum(1 for t in a_tokens if t in noise_tokens)
    fraction_noisy = noise_only / len(a_tokens)
    return round(1.0 - fraction_noisy, 4)


# ---------------------------------------------------------------------------
# Hallucination detection (lexical entailment proxy)
# ---------------------------------------------------------------------------

def hallucination_score(answer: str, context: str, ngram_n: int = 2) -> float:
    """Fraction of answer bigrams NOT entailed by the context.

    0.0 = fully grounded (no hallucination)
    1.0 = fully hallucinated (no bigrams in context)

    Uses bigram overlap as a proxy for semantic entailment.  For single-word
    answers (no bigrams), falls back to unigram overlap.
    """
    if not answer:
        return 0.0
    if not context:
        return 1.0

    a_tokens = _token_list(answer)
    c_tokens = _token_list(context)

    a_ng = _ngrams(a_tokens, ngram_n)
    c_ng = _ngrams(c_tokens, ngram_n)

    if not a_ng:
        # Fallback to unigram for very short answers
        a_set = set(a_tokens)
        c_set = set(c_tokens)
        if not a_set:
            return 0.0
        unentailed = a_set - c_set
        return round(len(unentailed) / len(a_set), 4)

    unentailed = a_ng - c_ng
    return round(len(unentailed) / len(a_ng), 4)


def is_hallucinated(answer: str, context: str, threshold: float = 0.6) -> bool:
    """Return True if hallucination_score ≥ threshold.

    Default threshold 0.6: more than 60% of answer bigrams are ungrounded.
    """
    return hallucination_score(answer, context) >= threshold


# ---------------------------------------------------------------------------
# Threshold enforcement
# ---------------------------------------------------------------------------

@dataclass
class EvalThresholds:
    """Pass/fail gates for evaluation metrics.

    Any metric with a value below its threshold is flagged as a violation.
    Set a threshold to ``None`` to skip that check.
    """
    min_correctness: float | None = 0.30
    min_faithfulness: float | None = 0.50
    min_context_precision: float | None = 0.40
    min_context_recall: float | None = 0.40
    min_retrieval_relevance: float | None = 0.30
    max_hallucination: float | None = 0.60     # fail if hallucination > this
    min_mrr: float | None = 0.20
    min_answer_relevancy: float | None = 0.25

    @classmethod
    def strict(cls) -> "EvalThresholds":
        """Higher thresholds for production readiness checks."""
        return cls(
            min_correctness=0.50,
            min_faithfulness=0.70,
            min_context_precision=0.60,
            min_context_recall=0.60,
            min_retrieval_relevance=0.50,
            max_hallucination=0.40,
            min_mrr=0.40,
            min_answer_relevancy=0.40,
        )

    @classmethod
    def lenient(cls) -> "EvalThresholds":
        """Lower thresholds for early-stage development."""
        return cls(
            min_correctness=0.10,
            min_faithfulness=0.25,
            min_context_precision=0.20,
            min_context_recall=0.20,
            min_retrieval_relevance=0.10,
            max_hallucination=0.80,
            min_mrr=0.10,
            min_answer_relevancy=0.10,
        )


@dataclass
class ThresholdViolation:
    metric: str
    value: float
    threshold: float
    direction: str  # "below" | "above"

    def __str__(self) -> str:
        return (
            f"{self.metric}={self.value:.4f} is {self.direction} "
            f"threshold {self.threshold:.4f}"
        )


def check_thresholds(
    scores: dict[str, float],
    thresholds: EvalThresholds | None = None,
) -> list[ThresholdViolation]:
    """Return a list of threshold violations.  Empty list = all checks passed.

    Args:
        scores: Dict of metric_name → score value.
        thresholds: ``EvalThresholds`` instance. Defaults to ``EvalThresholds()``.

    Returns:
        List of ``ThresholdViolation`` objects (empty if all pass).
    """
    if thresholds is None:
        thresholds = EvalThresholds()

    violations: list[ThresholdViolation] = []

    checks: list[tuple[str, str, float | None, str]] = [
        ("correctness",        "min_correctness",       thresholds.min_correctness,       "below"),
        ("faithfulness",       "min_faithfulness",      thresholds.min_faithfulness,      "below"),
        ("context_precision",  "min_context_precision", thresholds.min_context_precision, "below"),
        ("context_recall",     "min_context_recall",    thresholds.min_context_recall,    "below"),
        ("retrieval_relevance","min_retrieval_relevance",thresholds.min_retrieval_relevance,"below"),
        ("mrr",                "min_mrr",               thresholds.min_mrr,               "below"),
        ("answer_relevancy",   "min_answer_relevancy",  thresholds.min_answer_relevancy,  "below"),
        ("hallucination_score","max_hallucination",     thresholds.max_hallucination,     "above"),
    ]

    for score_key, _tkey, threshold, direction in checks:
        if threshold is None:
            continue
        value = scores.get(score_key)
        if value is None:
            continue
        if direction == "below" and value < threshold:
            violations.append(ThresholdViolation(score_key, value, threshold, "below"))
        elif direction == "above" and value > threshold:
            violations.append(ThresholdViolation(score_key, value, threshold, "above"))

    return violations
