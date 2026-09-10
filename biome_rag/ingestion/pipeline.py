from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Literal, Sequence

from .chunkers import Chunker, FixedSizeChunker, SemanticChunker, StructureAwareChunker
from .dedup import Deduplicator, SQLiteStateTracker
from .loaders import PostgreSQLLoader, UnstructuredBucketLoader, load_documents
from .models import (
    Chunk,
    DocumentNode,
    IngestionConfig,
    IngestionSummary,
    NormalizedDocument,
)

logger = logging.getLogger(__name__)

IngestionSource = Literal["all", "postgres", "files"]


class IngestionPipeline:
    """Enterprise-grade local data ingestion pipeline orchestrator.

    Handles unstructured files (local data bucket) and structured relational data (PostgreSQL),
    enforces cryptographic SHA-256 state tracking deduplication, emits validated DocumentNode
    models to a local Silver Layer (JSONL), and coordinates downstream chunking and indexing.
    """

    def __init__(
        self,
        config: IngestionConfig | None = None,
        dense_adapter: Any | None = None,
    ):
        self.config = config or IngestionConfig()

        # Deduplication and state tracker
        self.state_tracker = SQLiteStateTracker(self.config.state_db_path)
        self.deduplicator = Deduplicator(self.config.dedup_threshold)

        # Chunkers for downstream indexing
        self.chunkers: list[Chunker] = [
            FixedSizeChunker(self.config.chunk_size, self.config.chunk_overlap),
            StructureAwareChunker(self.config.chunk_size, self.config.chunk_overlap),
            SemanticChunker(self.config.chunk_size, self.config.chunk_overlap),
        ]

        # Vector store adapter (lazy or injected)
        self.dense_adapter = dense_adapter
        self._dense_initialized = False

        # Ensure directory structure
        self.config.processed_dir.mkdir(parents=True, exist_ok=True)
        self.config.storage_dir.mkdir(parents=True, exist_ok=True)
        self.config.silver_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Silver Layer Orchestration API
    # ------------------------------------------------------------------

    def run_pipeline(
        self,
        source: IngestionSource = "all",
        limit: int | None = None,
        save_silver: bool = True,
    ) -> tuple[list[DocumentNode], IngestionSummary]:
        """Orchestrate the end-to-end ingestion to Silver Layer.

        Flow:
        1. Trigger loaders for unstructured bucket files and/or Postgres rows.
        2. Deduplicate candidates against SQLiteStateTracker using SHA-256 hashes.
        3. Standardize and format output into DocumentNode objects.
        4. Persist newly accepted documents to Silver Layer JSON/JSONL.
        """
        logger.info("Starting ingestion pipeline run (source='%s', limit=%s)", source, limit)
        summary = IngestionSummary()
        all_candidates: list[DocumentNode] = []

        # 1. Trigger Loaders
        if source in ("all", "files"):
            bucket_loader = UnstructuredBucketLoader(self.config.bucket_dir)
            file_nodes = bucket_loader.load()
            logger.info("Discovered %d documents from local unstructured bucket.", len(file_nodes))
            summary.unstructured_processed = len(file_nodes)
            all_candidates.extend(file_nodes)

        if source in ("all", "postgres"):
            try:
                pg_loader = PostgreSQLLoader(
                    db_uri=self.config.postgres_uri,
                    table_name=self.config.postgres_table,
                )
                pg_nodes = pg_loader.load(limit=limit)
                logger.info("Extracted %d structured rows from PostgreSQL table '%s'.", len(pg_nodes), self.config.postgres_table)
                summary.postgres_processed = len(pg_nodes)
                all_candidates.extend(pg_nodes)
            except Exception as e:
                logger.error("Failed to load records from PostgreSQL: %s", e, exc_info=True)
                if source == "postgres":
                    raise

        # 2. Cryptographic State Tracker Deduplication
        new_nodes: list[DocumentNode] = []
        state_records_to_add: list[dict[str, Any]] = []

        # Extract all content hashes
        candidate_hashes = [
            node.metadata.file_hash
            for node in all_candidates
            if node.metadata.file_hash
        ]
        indexed_hash_set = self.state_tracker.batch_check_indexed(candidate_hashes)

        for node in all_candidates:
            h = node.metadata.file_hash
            if h and h in indexed_hash_set:
                summary.duplicates_skipped += 1
                logger.debug("Skipping duplicate record: %s (%s)", node.metadata.source_name, h[:8])
                continue

            new_nodes.append(node)
            if h:
                indexed_hash_set.add(h)  # Prevent duplicates within current batch
                state_records_to_add.append({
                    "content_hash": h,
                    "source_type": node.metadata.source_type,
                    "source_name": node.metadata.source_name,
                    "primary_key": node.metadata.primary_key,
                    "metadata": node.metadata.model_dump(),
                })

        summary.documents_processed = len(new_nodes)

        # 3. Persist Silver Layer Output
        if save_silver and new_nodes:
            self._save_silver_layer(new_nodes)
            self.state_tracker.batch_mark_indexed(state_records_to_add)
            logger.info(
                "Persisted %d new documents to Silver Layer (%s). Total state tracker records: %d",
                len(new_nodes),
                self.config.silver_dir,
                self.state_tracker.count(),
            )
        elif not new_nodes:
            logger.info("No new documents to persist. All %d records were deduplicated.", summary.duplicates_skipped)

        return new_nodes, summary

    def _save_silver_layer(self, nodes: list[DocumentNode]) -> None:
        """Write clean, validated DocumentNode items to Silver Layer JSONL and JSON."""
        self.config.silver_dir.mkdir(parents=True, exist_ok=True)
        jsonl_path = self.config.silver_dir / "documents.jsonl"
        json_path = self.config.silver_dir / "documents.json"

        # Append to JSONL (standard production append-only stream)
        with jsonl_path.open("a", encoding="utf-8") as fh:
            for node in nodes:
                line = json.dumps(node.to_dict(), default=str, ensure_ascii=False)
                fh.write(line + "\n")

        # Also write/update consolidated JSON snapshot
        existing_records: list[dict[str, Any]] = []
        if json_path.exists():
            try:
                existing_records = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                existing_records = []

        existing_records.extend(n.to_dict() for n in nodes)
        json_path.write_text(json.dumps(existing_records, indent=2, default=str, ensure_ascii=False), encoding="utf-8")

    # ------------------------------------------------------------------
    # Legacy / Downstream Chunking & Indexing Ingestion API
    # ------------------------------------------------------------------

    def ingest(self, paths: Sequence[Path] | None = None) -> tuple[list[Chunk], IngestionSummary]:
        """Ingest documents, generate chunks, update BM25 index and dense vector store.

        Maintains full backwards compatibility with existing test and evaluation suites.
        """
        input_paths = list(paths or self._discover_paths())
        logger.info("Legacy ingestion invoked. Discovered %d input files.", len(input_paths))

        documents = load_documents(input_paths)
        logger.info("Loaded %d normalized documents.", len(documents))

        chunks, summary = self._chunk_and_dedup(documents)
        self._persist(chunks, summary)

        return chunks, summary

    def _discover_paths(self) -> list[Path]:
        if not self.config.raw_dir.exists():
            return []
        return sorted(p for p in self.config.raw_dir.glob("**/*") if p.is_file())

    def _chunk_and_dedup(
        self, documents: list[NormalizedDocument]
    ) -> tuple[list[Chunk], IngestionSummary]:
        """Chunk all documents, remove exact + near-duplicates, return chunks + summary."""
        import hashlib
        chunks: list[Chunk] = []
        dedup_skipped = 0
        exact_hashes: set[str] = set()
        summary = IngestionSummary(
            documents_processed=len(documents), chunks_per_strategy={}
        )

        self.deduplicator.reset()

        for document in documents:
            for chunker in self.chunkers:
                generated = chunker.chunk(
                    document.text,
                    document.source,
                    document.section_heading,
                    document.page_number,
                )
                for chunk in generated:
                    chunk_hash = hashlib.md5(chunk.text.strip().lower().encode()).hexdigest()
                    if chunk_hash in exact_hashes:
                        dedup_skipped += 1
                        continue
                    exact_hashes.add(chunk_hash)

                    if self.deduplicator.is_duplicate(chunk.text):
                        dedup_skipped += 1
                        continue

                    chunks.append(chunk)

        summary.chunks_created = len(chunks)
        summary.duplicates_skipped = dedup_skipped
        for chunker in self.chunkers:
            summary.chunks_per_strategy[chunker.name] = sum(
                1 for c in chunks if c.chunking_strategy == chunker.name
            )

        return chunks, summary

    def _ensure_dense_adapter(self) -> None:
        if self._dense_initialized:
            return
        if self.dense_adapter is None:
            try:
                from ..retrieval.dense import ChromaDenseEmbeddingAdapter, SimpleDenseEmbeddingAdapter
                try:
                    self.dense_adapter = ChromaDenseEmbeddingAdapter(self.config.storage_dir)
                except Exception as exc:
                    logger.warning("Chroma adapter unavailable (%s). Using Simple adapter.", exc)
                    self.dense_adapter = SimpleDenseEmbeddingAdapter()
            except ImportError:
                logger.warning("Retrieval modules not importable.")
        self._dense_initialized = True

    def _persist(self, chunks: list[Chunk], summary: IngestionSummary) -> None:
        from ..retrieval.bm25 import BM25Index

        self.config.processed_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.config.processed_dir / "chunks.json"
        payload = {
            "chunks": [self._chunk_to_dict(c) for c in chunks],
            "summary": {
                "documents_processed": summary.documents_processed,
                "chunks_created": summary.chunks_created,
                "chunks_per_strategy": summary.chunks_per_strategy,
                "duplicates_skipped": summary.duplicates_skipped,
            },
        }
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        # BM25 index
        bm25_path = self.config.storage_dir / "bm25_index.pkl"
        bm25_index = BM25Index(bm25_path)
        bm25_index.build([c.text for c in chunks])
        bm25_index.save()

        # Dense vector store index
        self._ensure_dense_adapter()
        if self.dense_adapter and hasattr(self.dense_adapter, "index_documents"):
            self.dense_adapter.index_documents(chunks)

    @staticmethod
    def _chunk_to_dict(chunk: Chunk) -> dict[str, Any]:
        return {
            "text": chunk.text,
            "source": chunk.source,
            "section_heading": chunk.section_heading,
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
            "chunking_strategy": chunk.chunking_strategy,
            "character_count": chunk.character_count,
        }
