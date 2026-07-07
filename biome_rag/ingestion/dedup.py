from __future__ import annotations

import math
from typing import Iterable

from .models import Chunk


class Deduplicator:
    def __init__(self, threshold: float = 0.95):
        self.threshold = threshold

    def is_duplicate(self, candidate: Chunk, existing: Iterable[Chunk]) -> bool:
        for item in existing:
            if self._cosine_similarity(candidate.text, item.text) >= self.threshold:
                return True
        return False

    def _cosine_similarity(self, left: str, right: str) -> float:
        left_tokens = self._tokenize(left)
        right_tokens = self._tokenize(right)
        if not left_tokens or not right_tokens:
            return 0.0
        left_vector = self._vectorize(left_tokens)
        right_vector = self._vectorize(right_tokens)
        numerator = sum(left_vector.get(token, 0.0) * right_vector.get(token, 0.0) for token in set(left_vector) | set(right_vector))
        left_norm = math.sqrt(sum(value * value for value in left_vector.values()))
        right_norm = math.sqrt(sum(value * value for value in right_vector.values()))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)

    def _tokenize(self, text: str) -> list[str]:
        return [token.lower() for token in text.split() if token]

    def _vectorize(self, tokens: list[str]) -> dict[str, float]:
        counts: dict[str, float] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0.0) + 1.0
        return counts
