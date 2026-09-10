"""Enterprise Ingestion Module — Root Package Wrapper.

Re-exports core models, loaders, deduplicators, and pipeline orchestration from biome_rag.ingestion.
"""

from biome_rag.ingestion.cli import build_parser, main
from biome_rag.ingestion.dedup import (
    Deduplicator,
    SQLiteStateTracker,
    compute_file_sha256,
    compute_payload_sha256,
    filter_duplicates,
)
from biome_rag.ingestion.loaders import (
    BaseLoader,
    CodeLoader,
    CsvLoader,
    DocxLoader,
    HtmlLoader,
    JsonLoader,
    MarkdownLoader,
    PdfLoader,
    PlainTextLoader,
    PostgreSQLLoader,
    PptxLoader,
    UnstructuredBucketLoader,
    load_documents,
)
from biome_rag.ingestion.models import (
    Chunk,
    DocumentMetadata,
    DocumentNode,
    IngestionConfig,
    IngestionSummary,
    NormalizedDocument,
)
from biome_rag.ingestion.pipeline import IngestionPipeline, IngestionSource

__all__ = [
    "BaseLoader",
    "Chunk",
    "CodeLoader",
    "CsvLoader",
    "Deduplicator",
    "DocxLoader",
    "DocumentMetadata",
    "DocumentNode",
    "HtmlLoader",
    "IngestionConfig",
    "IngestionPipeline",
    "IngestionSource",
    "IngestionSummary",
    "JsonLoader",
    "MarkdownLoader",
    "NormalizedDocument",
    "PdfLoader",
    "PlainTextLoader",
    "PostgreSQLLoader",
    "PptxLoader",
    "SQLiteStateTracker",
    "UnstructuredBucketLoader",
    "build_parser",
    "compute_file_sha256",
    "compute_payload_sha256",
    "filter_duplicates",
    "load_documents",
    "main",
]
