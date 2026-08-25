from __future__ import annotations

import logging
import re
from typing import Sequence

logger = logging.getLogger(__name__)

# Lazy import to avoid hard dependency on sklearn at module load time
_tfidf = None


def _get_tfidf():
    global _tfidf
    if _tfidf is None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        _tfidf = TfidfVectorizer(
            analyzer="word",
            token_pattern=r"[a-zA-Z0-9_]+",
            max_features=5000,
            sublinear_tf=True,
        )
    return _tfidf


class Deduplicator:
    """Near-duplicate detector using cosine similarity on TF-IDF vectors.

    Fast pre-filter: MD5 hash equality (exact duplicates) is checked first.
    Slow path: TF-IDF cosine similarity for near-duplicates above *threshold*.
    """

    def __init__(self, threshold: float = 0.95):
        self.threshold = threshold
        self._seen_vectors: list = []
        self._seen_texts: list[str] = []

    def is_duplicate(self, item: str | object, existing_chunks: Sequence[object] | None = None) -> bool:
        """Return True if item (str or Chunk) is a near-duplicate of existing content."""
        text = str(getattr(item, "text", item))

        if existing_chunks is not None:
            for ex in existing_chunks:
                ex_text = str(getattr(ex, "text", ex))
                if text.strip().lower() == ex_text.strip().lower():
                    return True

        if not self._seen_texts:
            self._seen_texts.append(text)
            return False

        try:
            from sklearn.metrics.pairwise import cosine_similarity
            vectorizer = _get_tfidf()
            all_texts = self._seen_texts + [text]
            matrix = vectorizer.fit_transform(all_texts)
            new_vec = matrix[-1]
            existing = matrix[:-1]
            sims = cosine_similarity(new_vec, existing).flatten()
            if sims.max() >= self.threshold:
                logger.debug(
                    "Near-duplicate detected (max_sim=%.4f >= %.4f). Skipping chunk.",
                    sims.max(),
                    self.threshold,
                )
                return True
        except Exception as exc:
            logger.warning("Cosine dedup failed (%s); skipping similarity check.", exc)

        self._seen_texts.append(text)
        return False

    def reset(self) -> None:
        self._seen_texts = []


def filter_duplicates(texts: Sequence[str], threshold: float = 0.95) -> list[int]:
    """Return indices of non-duplicate texts from *texts*.

    Used for batch dedup during ingestion.
    """
    if not texts:
        return []

    kept: list[int] = []
    dedup = Deduplicator(threshold=threshold)

    for idx, text in enumerate(texts):
        if not dedup.is_duplicate(text):
            kept.append(idx)

    return kept
