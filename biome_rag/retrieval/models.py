from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RankedChunk:
    text: str
    source: str
    section_heading: str | None
    page_number: int | None
    dense_score: float
    sparse_score: float
    fused_score: float
    rerank_score: float
    chunk_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
