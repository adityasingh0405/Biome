from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any


class ChunkStore:
    def __init__(self, processed_dir: Path, storage_dir: Path):
        self.processed_dir = processed_dir
        self.storage_dir = storage_dir
        self.chunks: list[Any] = []
        self._load_chunks()

    def _load_chunks(self) -> None:
        payload_path = self.processed_dir / "chunks.json"
        if payload_path.exists():
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            self.chunks = payload.get("chunks", [])
            return

        bm25_path = self.storage_dir / "bm25_index.pkl"
        if bm25_path.exists():
            with bm25_path.open("rb") as handle:
                data = pickle.load(handle)
            self.chunks = [{"text": chunk} for chunk in data.get("chunks", [])]

    def get_chunks(self) -> list[Any]:
        return self.chunks
