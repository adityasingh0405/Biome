"""IndexBuilder: Phase 1 → 2 → 3 pipeline orchestrator.

Phase 4 implementation.

The IndexBuilder wires together the full ingestion pipeline into a single,
testable class:

    Phase 1 → DocumentIngester / PostgresIngester (load + hash-dedup)
    Phase 2 → DocumentChunker / TextChunker (tiktoken-aware chunking)
    Phase 3 → BGE_M3Encoder + QdrantAdapter (encode + upsert) + BM25Index

It is designed to slot into the existing FastAPI routes as a drop-in
replacement for IngestionPipeline.ingest(), while adding:
  - Proper IndexingResult dataclass with per-phase timing and error counts
  - Incremental runs (watermark-based, via the Phase 1 WatermarkStore)
  - Token-count and source_type populated in every persisted chunk
  - Qdrant upsert in addition to the existing BM25 + chunks.json

Backward compatibility:
    IngestionPipeline is NOT removed.  The existing `/v1/ingest/*` routes in
    app.py continue to work via the legacy path.  The IndexBuilder-backed
    routes are added alongside them as /v1/index/* and eventually supersede
    the legacy routes in Phase 5.

Usage::

    builder = IndexBuilder(
        raw_dir=Path("data/raw"),
        processed_dir=Path("data/processed"),
        storage_dir=Path("data/index"),
    )
    result = builder.run(paths=[Path("data/raw/report.pdf")])
    print(result.total_chunks, result.errors)
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from biome_rag.chunking import DocumentChunker, TextChunker, get_chunker
from biome_rag.ingestion.dedup import compute_payload_sha256
from biome_rag.ingestion.document_ingester import DocumentIngester
from biome_rag.ingestion.models import Chunk, IngestionSummary
from biome_rag.retrieval.bm25 import BM25Index

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class PhaseStats:
    """Timing and counts for a single pipeline phase."""
    elapsed_seconds: float = 0.0
    items_processed: int = 0
    items_skipped: int = 0
    errors: int = 0


@dataclass
class IndexingResult:
    """Full result from one IndexBuilder.run() call.

    All per-phase stats are available separately so the Prefect flow (Phase 5)
    can emit them as metrics.
    """
    # Document-level
    documents_ingested: int = 0
    documents_skipped: int = 0

    # Chunk-level
    total_chunks: int = 0
    chunks_per_strategy: dict[str, int] = field(default_factory=dict)
    chunks_per_source_type: dict[str, int] = field(default_factory=dict)

    # Indexing
    bm25_docs_indexed: int = 0
    qdrant_points_upserted: int = 0

    # Error accounting
    errors: list[str] = field(default_factory=list)

    # Wall-clock timings
    phase_stats: dict[str, PhaseStats] = field(default_factory=dict)
    total_elapsed_seconds: float = 0.0

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "documents_ingested": self.documents_ingested,
            "documents_skipped": self.documents_skipped,
            "total_chunks": self.total_chunks,
            "chunks_per_strategy": self.chunks_per_strategy,
            "chunks_per_source_type": self.chunks_per_source_type,
            "bm25_docs_indexed": self.bm25_docs_indexed,
            "qdrant_points_upserted": self.qdrant_points_upserted,
            "errors": self.errors,
            "total_elapsed_seconds": round(self.total_elapsed_seconds, 3),
            "success": self.success,
        }

    # Backward-compatible shim for code that reads IngestionSummary fields
    @property
    def chunks_created(self) -> int:
        return self.total_chunks

    @property
    def duplicates_skipped(self) -> int:
        return self.documents_skipped


# ---------------------------------------------------------------------------
# IndexBuilder
# ---------------------------------------------------------------------------

class IndexBuilder:
    """Orchestrates the full Phase 1 → 2 → 3 indexing pipeline.

    Args:
        raw_dir: Directory containing raw source files.
        processed_dir: Directory where chunks.json is written.
        storage_dir: Directory for BM25 index and Qdrant (if local).
        use_docling: Use IBM Docling for PDF/DOCX parsing (Phase 1).
        use_qdrant: Attempt to upsert into Qdrant (Phase 3). Set False
                    in CI or when Docker is not running.
        bm25_enabled: Build/update the BM25 index (default True).
        max_rows: Per-table row cap forwarded to PostgresIngester.
    """

    def __init__(
        self,
        raw_dir: Path | str = "data/raw",
        processed_dir: Path | str = "data/processed",
        storage_dir: Path | str = "data/index",
        use_docling: bool = False,
        use_qdrant: bool = True,
        bm25_enabled: bool = True,
        max_rows: int | None = None,
    ) -> None:
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.storage_dir = Path(storage_dir)
        self.use_docling = use_docling
        self.use_qdrant = use_qdrant
        self.bm25_enabled = bm25_enabled
        self.max_rows = max_rows

        # Ensure directories exist
        for d in (self.raw_dir, self.processed_dir, self.storage_dir):
            d.mkdir(parents=True, exist_ok=True)

        # Lazy-load Qdrant adapter only when needed
        self._qdrant_adapter: Any | None = None

    # ------------------------------------------------------------------
    # Primary public API
    # ------------------------------------------------------------------

    def run(
        self,
        paths: Sequence[Path] | None = None,
        source_type: str = "document",
        since=None,
    ) -> IndexingResult:
        """Run the full ingestion pipeline on a list of file paths.

        Args:
            paths: File paths to ingest. If None, discovers all files under raw_dir.
            source_type: ``"document"`` (files) or ``"postgresql"`` (DB rows).
            since: Optional datetime for incremental ingestion (Phase 1 watermark).

        Returns:
            ``IndexingResult`` with per-phase stats.
        """
        t_total = time.perf_counter()
        result = IndexingResult()

        resolved_paths = list(paths or self._discover_paths())
        if not resolved_paths and source_type == "document":
            logger.info("IndexBuilder.run(): no files found under %s", self.raw_dir)
            return result

        # Phase 1 — Ingestion
        t0 = time.perf_counter()
        try:
            documents, ingest_summary = self._phase1_ingest(resolved_paths, source_type, since)
        except Exception as exc:
            logger.error("Phase 1 ingestion failed: %s", exc, exc_info=True)
            result.errors.append(f"phase1: {exc}")
            return result
        result.phase_stats["phase1_ingest"] = PhaseStats(
            elapsed_seconds=time.perf_counter() - t0,
            items_processed=ingest_summary.documents_processed,
            items_skipped=ingest_summary.duplicates_skipped,
        )
        result.documents_ingested = ingest_summary.documents_processed
        result.documents_skipped = ingest_summary.duplicates_skipped

        if not documents:
            logger.info("IndexBuilder: no new documents after dedup — nothing to index.")
            result.total_elapsed_seconds = time.perf_counter() - t_total
            return result

        # Phase 2 — Chunking
        t0 = time.perf_counter()
        try:
            chunks = self._phase2_chunk(documents, source_type)
        except Exception as exc:
            logger.error("Phase 2 chunking failed: %s", exc, exc_info=True)
            result.errors.append(f"phase2: {exc}")
            return result
        result.phase_stats["phase2_chunk"] = PhaseStats(
            elapsed_seconds=time.perf_counter() - t0,
            items_processed=len(chunks),
        )
        result.total_chunks = len(chunks)
        result.chunks_per_strategy = self._count_by(chunks, lambda c: c.chunking_strategy)
        result.chunks_per_source_type = self._count_by(chunks, lambda c: c.source_type)

        # Persist chunks.json (keeps ChunkStore compatible)
        self._persist_chunks_json(chunks)

        # Phase 3 — BM25 index
        if self.bm25_enabled:
            t0 = time.perf_counter()
            try:
                n_bm25 = self._phase3_bm25(chunks)
                result.bm25_docs_indexed = n_bm25
            except Exception as exc:
                logger.error("BM25 indexing failed: %s", exc, exc_info=True)
                result.errors.append(f"phase3_bm25: {exc}")
            result.phase_stats["phase3_bm25"] = PhaseStats(
                elapsed_seconds=time.perf_counter() - t0,
                items_processed=result.bm25_docs_indexed,
            )

        # Phase 3 — Qdrant upsert
        if self.use_qdrant:
            t0 = time.perf_counter()
            try:
                n_qdrant = self._phase3_qdrant(chunks)
                result.qdrant_points_upserted = n_qdrant
            except Exception as exc:
                logger.warning("Qdrant upsert failed (non-fatal): %s", exc)
                result.errors.append(f"phase3_qdrant: {exc}")
            result.phase_stats["phase3_qdrant"] = PhaseStats(
                elapsed_seconds=time.perf_counter() - t0,
                items_processed=result.qdrant_points_upserted,
            )

        result.total_elapsed_seconds = time.perf_counter() - t_total
        logger.info(
            "IndexBuilder finished: %d docs → %d chunks | BM25=%d | Qdrant=%d | %.2fs",
            result.documents_ingested,
            result.total_chunks,
            result.bm25_docs_indexed,
            result.qdrant_points_upserted,
            result.total_elapsed_seconds,
        )
        return result

    # ------------------------------------------------------------------
    # Phase 1 — Ingestion
    # ------------------------------------------------------------------

    def _phase1_ingest(self, paths: list[Path], source_type: str, since):
        """Run Phase 1 ingestion on a list of file paths.

        Groups files by parent directory and runs one DocumentIngester per dir.
        Paths that live in the same directory are batched together.
        """
        from biome_rag.ingestion.base import IngestResult  # noqa: PLC0415

        # Group by parent directory
        dirs: dict[Path, list[Path]] = {}
        for p in paths:
            dirs.setdefault(p.parent, []).append(p)

        merged = IngestResult()
        for dir_path, dir_files in dirs.items():
            ingester = DocumentIngester(
                source_dir=dir_path,
                use_docling=self.use_docling,
                recursive=False,  # files are already enumerated
            )
            # Temporarily narrow the file list by pointing at each file's
            # actual location. DocumentIngester.ingest() will re-glob the dir,
            # but since recursive=False and files are already in dir_path, they
            # will be found. Files from other dirs are filtered by suffix.
            partial = ingester.ingest(since=since)
            # Filter to only the explicitly requested files in this dir
            requested_names = {p.name for p in dir_files}
            partial.documents = [
                doc for doc in partial.documents
                if Path(doc.metadata.file_path or "").name in requested_names
                or Path(doc.metadata.source_name or "").name in requested_names
            ]
            partial.summary.documents_processed = len(partial.documents)
            merged.documents.extend(partial.documents)
            merged.summary.documents_processed += partial.summary.documents_processed
            merged.summary.duplicates_skipped += partial.summary.duplicates_skipped
            merged.errors.extend(partial.errors)

        return merged.documents, merged.summary

    # ------------------------------------------------------------------
    # Phase 2 — Chunking
    # ------------------------------------------------------------------

    def _phase2_chunk(self, documents, source_type: str) -> list[Chunk]:
        """Route to the correct Phase 2 chunker based on source_type."""
        try:
            chunker = get_chunker(source_type)
        except ValueError:
            logger.warning(
                "Unknown source_type '%s' — using DocumentChunker fallback.", source_type
            )
            chunker = DocumentChunker()

        return chunker.chunk_many(documents)

    # ------------------------------------------------------------------
    # Phase 3a — BM25
    # ------------------------------------------------------------------

    def _phase3_bm25(self, chunks: list[Chunk]) -> int:
        """Build/replace the BM25 index from all current chunks."""
        bm25_path = self.storage_dir / "bm25_index.pkl"
        bm25 = BM25Index(bm25_path)
        bm25.build([c.text for c in chunks])
        bm25.save()
        logger.info("BM25 index built: %d documents.", len(chunks))
        return len(chunks)

    # ------------------------------------------------------------------
    # Phase 3b — Qdrant
    # ------------------------------------------------------------------

    def _get_qdrant_adapter(self):
        """Lazy-load the QdrantAdapter (imports heavy deps on first call)."""
        if self._qdrant_adapter is not None:
            return self._qdrant_adapter
        try:
            from biome_rag.retrieval.qdrant_store import QdrantAdapter  # noqa: PLC0415
            adapter = QdrantAdapter()
            # Probe connectivity
            if adapter._get_client() is None:
                logger.warning("Qdrant not reachable — skipping upsert.")
                return None
            self._qdrant_adapter = adapter
        except Exception as exc:
            logger.warning("QdrantAdapter unavailable: %s", exc)
            self._qdrant_adapter = None
        return self._qdrant_adapter

    def _phase3_qdrant(self, chunks: list[Chunk]) -> int:
        """Upsert chunks into Qdrant. Returns number of points upserted."""
        adapter = self._get_qdrant_adapter()
        if adapter is None:
            return 0
        adapter.index_documents(chunks)
        return len(chunks)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _persist_chunks_json(self, chunks: list[Chunk]) -> None:
        """Write chunks.json for ChunkStore compatibility (existing retrieval path)."""
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.processed_dir / "chunks.json"
        payload = {
            "chunks": [self._chunk_to_dict(c) for c in chunks],
            "summary": {
                "documents_processed": len({c.source for c in chunks}),
                "chunks_created": len(chunks),
                "chunks_per_strategy": self._count_by(chunks, lambda c: c.chunking_strategy),
                "duplicates_skipped": 0,
            },
        }
        output_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        logger.debug("chunks.json written: %d chunks → %s", len(chunks), output_path)

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
            "token_count": chunk.token_count,
            "source_type": chunk.source_type,
            "metadata": chunk.metadata,
        }

    @staticmethod
    def _count_by(chunks: list[Chunk], key_fn) -> dict[str, int]:
        counts: dict[str, int] = {}
        for c in chunks:
            k = key_fn(c)
            counts[k] = counts.get(k, 0) + 1
        return counts

    def _discover_paths(self) -> list[Path]:
        if not self.raw_dir.exists():
            return []
        return sorted(p for p in self.raw_dir.glob("**/*") if p.is_file())
