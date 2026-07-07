from __future__ import annotations

import math
import pickle
from pathlib import Path
from typing import Iterable


class BM25Index:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.documents: list[str] = []
        self.index: dict[str, dict[int, int]] = {}
        self.doc_freq: dict[str, int] = {}
        self.load()

    def build(self, documents: Iterable[str]) -> None:
        self.documents = list(documents)
        self.index = {}
        self.doc_freq = {}
        for doc_id, document in enumerate(self.documents):
            tokens = self._tokenize(document)
            counts: dict[str, int] = {}
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1
            for token, count in counts.items():
                self.index.setdefault(token, {})[doc_id] = count
                self.doc_freq[token] = self.doc_freq.get(token, 0) + 1

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("wb") as handle:
            pickle.dump({"documents": self.documents, "index": self.index, "doc_freq": self.doc_freq}, handle)

    def load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open("rb") as handle:
            payload = pickle.load(handle)
        self.documents = payload.get("documents", [])
        self.index = payload.get("index", {})
        self.doc_freq = payload.get("doc_freq", {})

    def search(self, query: str, top_k: int = 5) -> list[tuple[int, float]]:
        tokens = self._tokenize(query)
        if not self.documents:
            return []
        scores: dict[int, float] = {}
        for token in tokens:
            if token not in self.index:
                continue
            for doc_id, term_freq in self.index[token].items():
                idf = self._idf(len(self.documents), self.doc_freq.get(token, 0))
                scores[doc_id] = scores.get(doc_id, 0.0) + idf * term_freq
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        return ranked[:top_k]

    def _tokenize(self, text: str) -> list[str]:
        return [token.lower() for token in text.split() if token]

    def _idf(self, doc_count: int, doc_freq: int) -> float:
        return float(math.log((1 + doc_count) / (1 + doc_freq)))
