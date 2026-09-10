from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


SourceType = Literal["unstructured", "postgresql", "document", "slack"]


class DocumentMetadata(BaseModel):
    """Strict metadata schema for ingested documents."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    source_type: SourceType = Field(
        ...,
        description="Origin stream: 'unstructured' files or 'postgresql' database records.",
    )
    source_name: str = Field(
        ...,
        description="Origin identifier: filename or table name.",
    )
    primary_key: Optional[str] = Field(
        default=None,
        description="Primary key identifier for database records or row entities.",
    )
    file_hash: Optional[str] = Field(
        default=None,
        description="SHA-256 hash of the source file or deterministic row payload.",
    )
    access_level: str = Field(
        default="internal",
        description="Role-Based Access Control (RBAC) sensitivity tier (e.g. 'public', 'internal', 'confidential', 'restricted').",
    )
    access_scope: List[str] = Field(
        default_factory=list,
        description="ACL scope list: Slack channel IDs, Postgres role tags, or doc folder identifiers that may access this document.",
    )
    file_path: Optional[str] = Field(
        default=None,
        description="Absolute or relative file path for local files.",
    )
    file_extension: Optional[str] = Field(
        default=None,
        description="File extension (e.g. '.pdf', '.docx', '.pptx', '.txt').",
    )
    created_at: Optional[str] = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Timestamp when document was generated or ingested.",
    )
    department: Optional[str] = Field(
        default=None,
        description="Organizational department tag for RBAC or category filtering.",
    )
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary domain-specific attributes.",
    )


class DocumentNode(BaseModel):
    """Standard representation of an ingested document node in the Silver Layer."""
    model_config = ConfigDict(
        extra="ignore",
        arbitrary_types_allowed=True,  # Needed to store Docling document objects
    )

    page_content: str = Field(
        ...,
        description="Extracted clean text or natural-language formatted database row.",
    )
    metadata: DocumentMetadata = Field(
        ...,
        description="Strict validated document metadata.",
    )
    # Docling document object — preserved for Phase 2 HybridChunker.
    # Excluded from all serialization (JSON, model_dump, etc.).
    docling_doc: Optional[Any] = Field(
        default=None,
        exclude=True,
        repr=False,
        description="IBM Docling DoclingDocument object. Not serialized. Only present for Docling-parsed files.",
    )

    @property
    def text(self) -> str:
        """Alias for page_content for backward compatibility."""
        return self.page_content

    @property
    def source(self) -> str:
        """Alias for source file or origin."""
        return self.metadata.file_path or self.metadata.source_name

    @property
    def section_heading(self) -> Optional[str]:
        return self.metadata.extra.get("section_heading")

    @property
    def page_number(self) -> Optional[int]:
        return self.metadata.extra.get("page_number")

    def to_dict(self) -> dict[str, Any]:
        """Serialize DocumentNode to standard dictionary."""
        return {
            "page_content": self.page_content,
            "metadata": self.metadata.model_dump(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentNode":
        """Construct DocumentNode from dictionary."""
        metadata_val = data.get("metadata", {})
        if isinstance(metadata_val, dict):
            metadata_obj = DocumentMetadata(**metadata_val)
        elif isinstance(metadata_val, DocumentMetadata):
            metadata_obj = metadata_val
        else:
            raise ValueError(f"Invalid metadata type: {type(metadata_val)}")
        return cls(page_content=data.get("page_content", ""), metadata=metadata_obj)

    def to_normalized_document(self) -> NormalizedDocument:
        """Adapter for legacy downstream chunkers and indexers."""
        return NormalizedDocument(
            text=self.page_content,
            source=self.metadata.file_path or self.metadata.source_name,
            section_heading=self.metadata.extra.get("section_heading") or self.metadata.source_name,
            page_number=self.metadata.extra.get("page_number"),
            metadata=self.metadata.model_dump(),
        )


# ----------------------------------------------------------------------
# Legacy / Downstream Compatibility Models
# ----------------------------------------------------------------------

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
    token_count: int = 0          # Phase 2: populated by new chunkers; 0 for legacy chunks
    source_type: str = "unknown"  # Phase 2: "document" | "postgresql" | "slack" | "unstructured"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestionSummary:
    documents_processed: int = 0
    chunks_created: int = 0
    chunks_per_strategy: dict[str, int] = field(default_factory=dict)
    duplicates_skipped: int = 0
    unstructured_processed: int = 0
    postgres_processed: int = 0


@dataclass
class IngestionConfig:
    raw_dir: Path = Path("data/raw")
    bucket_dir: Path = Path("local_data_bucket/unstructured")
    processed_dir: Path = Path("data/processed")
    storage_dir: Path = Path("data/index")
    silver_dir: Path = Path("data/silver")
    state_db_path: Path = Path("data/ingestion_state.db")
    chunk_size: int = 800
    chunk_overlap: int = 120
    dedup_threshold: float = 0.95
    embedding_model: str = "sentence-transformers"
    postgres_uri: str = field(default_factory=lambda: os.getenv("POSTGRES_URI", "postgresql://localhost:5432/enterprise_rag"))
    postgres_table: str = field(default_factory=lambda: os.getenv("POSTGRES_TABLE", "enterprise_tickets"))
