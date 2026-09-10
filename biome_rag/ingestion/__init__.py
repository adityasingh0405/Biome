"""Enterprise Ingestion Module — biome_rag.ingestion.

Exports all ingestion primitives: models, loaders, chunkers, dedup,
and the Phase 1 ingester classes.
"""

from biome_rag.ingestion.base import (
    Ingester,
    IngestResult,
    WatermarkStore,
)
from biome_rag.ingestion.chunkers import (
    FixedSizeChunker,
    SemanticChunker,
    StructureAwareChunker,
)
from biome_rag.ingestion.dedup import (
    Deduplicator,
    SQLiteStateTracker,
    compute_file_sha256,
    compute_payload_sha256,
    filter_duplicates,
)
from biome_rag.ingestion.document_ingester import DocumentIngester
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
from biome_rag.ingestion.postgres_ingester import PostgresIngester
from biome_rag.ingestion.slack_ingester import SlackIngester

__all__ = [
    # Base ABC
    "Ingester",
    "IngestResult",
    "WatermarkStore",
    # Phase 1 ingesters
    "DocumentIngester",
    "PostgresIngester",
    "SlackIngester",
    # Models
    "Chunk",
    "DocumentMetadata",
    "DocumentNode",
    "IngestionConfig",
    "IngestionPipeline",
    "IngestionSource",
    "IngestionSummary",
    "NormalizedDocument",
    # Chunkers
    "FixedSizeChunker",
    "SemanticChunker",
    "StructureAwareChunker",
    # Dedup
    "Deduplicator",
    "SQLiteStateTracker",
    "compute_file_sha256",
    "compute_payload_sha256",
    "filter_duplicates",
    # Loaders (legacy)
    "BaseLoader",
    "CodeLoader",
    "CsvLoader",
    "DocxLoader",
    "HtmlLoader",
    "JsonLoader",
    "MarkdownLoader",
    "PdfLoader",
    "PlainTextLoader",
    "PostgreSQLLoader",
    "PptxLoader",
    "UnstructuredBucketLoader",
    "load_documents",
]
