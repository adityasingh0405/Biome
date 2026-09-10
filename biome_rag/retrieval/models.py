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
    sparse_score: float          # BM25 score (hand-tuned, legacy)
    fused_score: float
    rerank_score: float
    chunk_index: int = 0
    bge_sparse_score: float = 0.0   # Phase 3: BGE-M3 lexical dot-product score
    token_count: int = 0             # Phase 2: populated by Phase 2 chunkers
    source_type: str = "unknown"     # Phase 2: "document" | "postgresql" | "slack"
    access_scope: list[str] = field(default_factory=list)  # Phase 1: ACL scope list
    metadata: dict[str, Any] = field(default_factory=dict)
