"""Prefect orchestration flow for the Biome RAG index pipeline — Phase 5.

This flow wraps the Phase 4 ``IndexBuilder`` as a set of Prefect tasks so the
pipeline can be:
  - Scheduled (e.g. nightly via a Prefect deployment)
  - Monitored in the Prefect UI (task run states, retries, logs)
  - Run ad-hoc from the CLI: ``python -m biome_rag.flows.index_flow``

Flow: ``biome_index_pipeline``
  Task 1: ``ingest_documents``   — Phase 1: load files, hash-dedup
  Task 2: ``chunk_documents``    — Phase 2: tiktoken-aware chunking
  Task 3: ``build_bm25_index``   — Phase 3a: BM25
  Task 4: ``upsert_qdrant``      — Phase 3b: BGE-M3 encode + Qdrant upsert
  Task 5: ``notify_completion``  — summary log / optional webhook

Each task emits structured Prefect artifacts via ``create_markdown_artifact``.

Graceful degradation:
  - If Prefect is not installed, ``run_pipeline_direct()`` executes the same
    logic using the ``IndexBuilder`` directly (no Prefect tasks).
  - If Qdrant is unreachable, the upsert task logs a warning but does NOT
    fail the flow (it marks itself as ``SKIPPED``).

Usage::

    # Run once (dev / manual trigger)
    python -m biome_rag.flows.index_flow

    # Deploy as a scheduled flow (production)
    prefect deployment build biome_rag/flows/index_flow.py:biome_index_pipeline \\
        --name "nightly-index" --cron "0 2 * * *" --apply
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Prefect is optional — graceful fallback
try:
    from prefect import flow, get_run_logger, task  # type: ignore
    from prefect.artifacts import create_markdown_artifact  # type: ignore
    _PREFECT_AVAILABLE = True
except ImportError:
    _PREFECT_AVAILABLE = False
    logger.warning(
        "Prefect not installed (`pip install prefect`). "
        "Use run_pipeline_direct() for non-orchestrated runs."
    )

    # Shim decorators so the file imports cleanly without Prefect
    def flow(fn=None, **kwargs):  # type: ignore
        if fn is None:
            return lambda f: f
        return fn

    def task(fn=None, **kwargs):  # type: ignore
        if fn is None:
            return lambda f: f
        return fn

    def get_run_logger():  # type: ignore
        return logger

    def create_markdown_artifact(*args, **kwargs):  # type: ignore
        pass


from biome_rag.indexing import IndexBuilder, IndexingResult


# ---------------------------------------------------------------------------
# Prefect tasks
# ---------------------------------------------------------------------------

@task(name="ingest-documents", retries=2, retry_delay_seconds=30)
def ingest_documents(
    raw_dir: str,
    processed_dir: str,
    storage_dir: str,
    use_docling: bool,
    since_str: str | None,
) -> dict:
    """Phase 1: discover and load documents from raw_dir."""
    from datetime import datetime, timezone  # noqa: PLC0415

    plog = get_run_logger()
    plog.info("Phase 1 — ingesting documents from: %s", raw_dir)

    since = None
    if since_str:
        try:
            since = datetime.fromisoformat(since_str).replace(tzinfo=timezone.utc)
        except ValueError:
            plog.warning("Could not parse since_str='%s' — full run.", since_str)

    builder = IndexBuilder(
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        storage_dir=storage_dir,
        use_docling=use_docling,
        use_qdrant=False,   # Qdrant handled in its own task
        bm25_enabled=False,  # BM25 handled in its own task
    )

    paths = builder._discover_paths()
    plog.info("Discovered %d files.", len(paths))

    if not paths:
        plog.warning("No files found — nothing to index.")
        return {"documents": 0, "chunks": 0, "paths": []}

    # Phase 1 only
    docs, summary = builder._phase1_ingest(paths, "document", since)
    plog.info(
        "Ingested %d documents (%d skipped).",
        summary.documents_processed,
        summary.duplicates_skipped,
    )
    return {
        "documents": summary.documents_processed,
        "skipped": summary.duplicates_skipped,
        "paths": [str(p) for p in paths],
    }


@task(name="chunk-documents", retries=1)
def chunk_documents(
    raw_dir: str,
    processed_dir: str,
    storage_dir: str,
    use_docling: bool,
) -> dict:
    """Phase 2: chunk all discovered documents and write chunks.json."""
    plog = get_run_logger()
    plog.info("Phase 2 — chunking documents.")

    builder = IndexBuilder(
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        storage_dir=storage_dir,
        use_docling=use_docling,
        use_qdrant=False,
        bm25_enabled=False,
    )

    paths = builder._discover_paths()
    if not paths:
        plog.warning("No files to chunk.")
        return {"chunks": 0}

    docs, _ = builder._phase1_ingest(paths, "document", None)
    if not docs:
        plog.warning("No new documents after dedup.")
        return {"chunks": 0}

    chunks = builder._phase2_chunk(docs, "document")
    builder._persist_chunks_json(chunks)
    plog.info("Produced %d chunks.", len(chunks))

    strategy_counts = builder._count_by(chunks, lambda c: c.chunking_strategy)
    return {
        "chunks": len(chunks),
        "per_strategy": strategy_counts,
    }


@task(name="build-bm25-index", retries=1)
def build_bm25_index(
    raw_dir: str,
    processed_dir: str,
    storage_dir: str,
    use_docling: bool,
) -> dict:
    """Phase 3a: rebuild BM25 index from current chunks.json."""
    import json  # noqa: PLC0415
    plog = get_run_logger()
    chunks_path = Path(processed_dir) / "chunks.json"
    if not chunks_path.exists():
        plog.warning("chunks.json not found — skipping BM25 build.")
        return {"bm25_docs": 0}

    from biome_rag.ingestion.models import Chunk  # noqa: PLC0415
    raw = json.loads(chunks_path.read_text())
    chunks = [
        Chunk(
            text=c["text"],
            source=c.get("source", ""),
            section_heading=c.get("section_heading"),
            page_number=c.get("page_number"),
            chunk_index=c.get("chunk_index", 0),
            chunking_strategy=c.get("chunking_strategy", "unknown"),
            character_count=c.get("character_count", 0),
            token_count=c.get("token_count", 0),
            source_type=c.get("source_type", "document"),
        )
        for c in raw.get("chunks", [])
    ]

    builder = IndexBuilder(raw_dir, processed_dir, storage_dir, use_qdrant=False)
    n = builder._phase3_bm25(chunks)
    plog.info("BM25 index built: %d documents.", n)
    return {"bm25_docs": n}


@task(name="upsert-qdrant")
def upsert_qdrant(
    processed_dir: str,
    storage_dir: str,
) -> dict:
    """Phase 3b: encode and upsert chunks into Qdrant."""
    import json  # noqa: PLC0415
    plog = get_run_logger()
    chunks_path = Path(processed_dir) / "chunks.json"
    if not chunks_path.exists():
        plog.warning("chunks.json not found — skipping Qdrant upsert.")
        return {"qdrant_points": 0}

    from biome_rag.ingestion.models import Chunk  # noqa: PLC0415
    from biome_rag.retrieval.qdrant_store import QdrantAdapter  # noqa: PLC0415

    raw = json.loads(chunks_path.read_text())
    chunks = [
        Chunk(
            text=c["text"],
            source=c.get("source", ""),
            section_heading=c.get("section_heading"),
            page_number=c.get("page_number"),
            chunk_index=c.get("chunk_index", 0),
            chunking_strategy=c.get("chunking_strategy", "unknown"),
            character_count=c.get("character_count", 0),
            token_count=c.get("token_count", 0),
            source_type=c.get("source_type", "document"),
        )
        for c in raw.get("chunks", [])
    ]

    adapter = QdrantAdapter()
    client = adapter._get_client()
    if client is None:
        plog.warning("Qdrant not reachable — skipping upsert.")
        return {"qdrant_points": 0, "skipped": True}

    adapter.index_documents(chunks)
    plog.info("Upserted %d points to Qdrant.", len(chunks))
    return {"qdrant_points": len(chunks)}


@task(name="emit-summary-artifact")
def emit_summary_artifact(
    ingest_stats: dict,
    chunk_stats: dict,
    bm25_stats: dict,
    qdrant_stats: dict,
    elapsed_s: float,
) -> None:
    """Write a Prefect markdown artifact summarizing the run."""
    md = f"""# Biome RAG Index Pipeline — Run Summary

| Phase | Metric | Value |
|-------|--------|-------|
| Phase 1 | Documents ingested | {ingest_stats.get("documents", 0)} |
| Phase 1 | Documents skipped (dedup) | {ingest_stats.get("skipped", 0)} |
| Phase 2 | Total chunks | {chunk_stats.get("chunks", 0)} |
| Phase 3a | BM25 documents | {bm25_stats.get("bm25_docs", 0)} |
| Phase 3b | Qdrant points upserted | {qdrant_stats.get("qdrant_points", 0)} |
| Total | Elapsed seconds | {round(elapsed_s, 1)} |

### Chunks per strategy
```
{chunk_stats.get("per_strategy", {})}
```
"""
    create_markdown_artifact(
        key="index-pipeline-summary",
        markdown=md,
        description="Biome RAG index pipeline run summary",
    )


# ---------------------------------------------------------------------------
# Prefect flow
# ---------------------------------------------------------------------------

@flow(
    name="biome-index-pipeline",
    description="Phase 1→2→3 index pipeline orchestrated by Prefect.",
    log_prints=True,
)
def biome_index_pipeline(
    raw_dir: str = "data/raw",
    processed_dir: str = "data/processed",
    storage_dir: str = "data/index",
    use_docling: bool = False,
    since_str: str | None = None,
) -> IndexingResult:
    """Prefect-orchestrated Phase 1→2→3 index pipeline.

    Args:
        raw_dir: Directory containing raw source documents.
        processed_dir: Directory for chunks.json output.
        storage_dir: Directory for BM25 index and Qdrant storage.
        use_docling: Use IBM Docling for document parsing.
        since_str: ISO 8601 datetime string for incremental runs (e.g. ``2024-01-01T00:00:00Z``).
                   ``None`` = full re-index.

    Returns:
        ``IndexingResult`` with per-phase stats.
    """
    t0 = time.perf_counter()

    ingest_stats = ingest_documents(raw_dir, processed_dir, storage_dir, use_docling, since_str)
    chunk_stats  = chunk_documents(raw_dir, processed_dir, storage_dir, use_docling)
    bm25_stats   = build_bm25_index(raw_dir, processed_dir, storage_dir, use_docling)
    qdrant_stats = upsert_qdrant(processed_dir, storage_dir)

    elapsed = time.perf_counter() - t0
    emit_summary_artifact(ingest_stats, chunk_stats, bm25_stats, qdrant_stats, elapsed)

    # Build a unified IndexingResult from task outputs
    result = IndexingResult(
        documents_ingested=ingest_stats.get("documents", 0),
        documents_skipped=ingest_stats.get("skipped", 0),
        total_chunks=chunk_stats.get("chunks", 0),
        chunks_per_strategy=chunk_stats.get("per_strategy", {}),
        bm25_docs_indexed=bm25_stats.get("bm25_docs", 0),
        qdrant_points_upserted=qdrant_stats.get("qdrant_points", 0),
        total_elapsed_seconds=elapsed,
    )
    logger.info("biome_index_pipeline complete: %s", result.to_dict())
    return result


# ---------------------------------------------------------------------------
# Direct (non-Prefect) runner — used in CI and when Prefect is absent
# ---------------------------------------------------------------------------

def run_pipeline_direct(
    raw_dir: str = "data/raw",
    processed_dir: str = "data/processed",
    storage_dir: str = "data/index",
    use_docling: bool = False,
    use_qdrant: bool = True,
) -> IndexingResult:
    """Run the index pipeline without Prefect (direct Python call).

    Equivalent to ``IndexBuilder.run()`` but with explicit logging.
    """
    logger.info("Running index pipeline directly (no Prefect).")
    builder = IndexBuilder(
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        storage_dir=storage_dir,
        use_docling=use_docling,
        use_qdrant=use_qdrant,
    )
    result = builder.run()
    logger.info(
        "Pipeline complete: %d docs → %d chunks in %.1fs",
        result.documents_ingested,
        result.total_chunks,
        result.total_elapsed_seconds,
    )
    return result


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="Run the Biome RAG index pipeline.")
    parser.add_argument("--raw-dir",       default="data/raw",       help="Source documents directory")
    parser.add_argument("--processed-dir", default="data/processed", help="Output directory for chunks.json")
    parser.add_argument("--storage-dir",   default="data/index",     help="BM25 + Qdrant storage directory")
    parser.add_argument("--use-docling",   action="store_true",      help="Enable Docling document parser")
    parser.add_argument("--since",         default=None,             help="ISO 8601 datetime for incremental run")
    parser.add_argument("--no-prefect",    action="store_true",      help="Skip Prefect orchestration")
    args = parser.parse_args()

    if args.no_prefect or not _PREFECT_AVAILABLE:
        result = run_pipeline_direct(
            raw_dir=args.raw_dir,
            processed_dir=args.processed_dir,
            storage_dir=args.storage_dir,
            use_docling=args.use_docling,
        )
    else:
        result = biome_index_pipeline(
            raw_dir=args.raw_dir,
            processed_dir=args.processed_dir,
            storage_dir=args.storage_dir,
            use_docling=args.use_docling,
            since_str=args.since,
        )

    print(result.to_dict())
