from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class NormalizedDocument:
    text: str
    source: str
    section_heading: str | None = None
    page_number: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    text: str
    source: str
    section_heading: str | None
    page_number: int | None
    chunk_index: int
    chunking_strategy: str
    character_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestionSummary:
    documents_processed: int = 0
    chunks_created: int = 0
    chunks_per_strategy: dict[str, int] = field(default_factory=dict)
    duplicates_skipped: int = 0


@dataclass
class IngestionConfig:
    raw_dir: Path = Path("data/raw")
    processed_dir: Path = Path("data/processed")
    storage_dir: Path = Path("data/index")
    chunk_size: int = 800
    chunk_overlap: int = 120
    dedup_threshold: float = 0.95
    embedding_model: str = "sentence-transformers"
