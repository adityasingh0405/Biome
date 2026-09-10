from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from .models import IngestionConfig
from .pipeline import IngestionPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingestion.cli")

DEFAULT_DB_URI = os.getenv(
    "DB_URI",
    "postgresql://postgres:Aditya%402005@localhost:5432/enterprise_rag",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Enterprise RAG Local Data Ingestion CLI — Multi-stream Ingestion & Deduplication",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--source",
        choices=["all", "postgres", "files"],
        default="all",
        help="Data stream to ingest: 'all', 'postgres' (structured rows), or 'files' (unstructured bucket).",
    )
    parser.add_argument(
        "--db-uri",
        type=str,
        default=DEFAULT_DB_URI,
        help="PostgreSQL database connection URI.",
    )
    parser.add_argument(
        "--table",
        type=str,
        default="enterprise_tickets",
        help="PostgreSQL table name to ingest from.",
    )
    parser.add_argument(
        "--bucket-dir",
        type=Path,
        default=Path("local_data_bucket/unstructured"),
        help="Directory containing unstructured local files (PDF, DOCX, PPTX, TXT).",
    )
    parser.add_argument(
        "--silver-dir",
        type=Path,
        default=Path("data/silver"),
        help="Output directory for Silver Layer clean JSONL documents.",
    )
    parser.add_argument(
        "--state-db",
        type=Path,
        default=Path("data/ingestion_state.db"),
        help="Path to SQLite state tracker database for deduplication.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional row limit when reading from PostgreSQL.",
    )
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help="Reset and clear the state tracker database before ingestion.",
    )
    # Legacy arguments for backwards compatibility
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw"),
        help="Legacy raw directory for markdown/chunking pipeline.",
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=Path("data/processed"),
        help="Legacy processed directory for chunk persistence.",
    )
    parser.add_argument(
        "--storage-dir",
        type=Path,
        default=Path("data/index"),
        help="Legacy storage directory for BM25 and vector stores.",
    )
    parser.add_argument(
        "--chunk-and-index",
        action="store_true",
        help="Also trigger legacy chunking and indexing pass after Silver Layer ingestion.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = IngestionConfig(
        raw_dir=args.raw_dir,
        bucket_dir=args.bucket_dir,
        processed_dir=args.processed_dir,
        storage_dir=args.storage_dir,
        silver_dir=args.silver_dir,
        state_db_path=args.state_db,
        postgres_uri=args.db_uri,
        postgres_table=args.table,
    )

    pipeline = IngestionPipeline(config)

    if args.reset_state:
        logger.info("Resetting deduplication state database...")
        pipeline.state_tracker.reset_state()

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print("\n" + "=" * 60)
    print("[*] ENTERPRISE RAG LOCAL INGESTION PIPELINE")
    print("=" * 60)
    print(f"  Source Mode     : {args.source.upper()}")
    print(f"  Silver Directory: {config.silver_dir.resolve()}")
    print(f"  State Database  : {config.state_db_path.resolve()}")
    if args.source in ("all", "files"):
        print(f"  Bucket Directory: {config.bucket_dir.resolve()}")
    if args.source in ("all", "postgres"):
        print(f"  PostgreSQL Table: {config.postgres_table}")
    print("=" * 60 + "\n")

    try:
        nodes, summary = pipeline.run_pipeline(source=args.source, limit=args.limit)

        print("\n" + "-" * 60)
        print("[SUCCESS] INGESTION RUN COMPLETED")
        print("-" * 60)
        if args.source in ("all", "files"):
            print(f"  Unstructured Files Discovered : {summary.unstructured_processed}")
        if args.source in ("all", "postgres"):
            print(f"  PostgreSQL Rows Extracted    : {summary.postgres_processed}")
        print(f"  Duplicates Skipped (Dedup)   : {summary.duplicates_skipped}")
        print(f"  New Documents Persisted      : {summary.documents_processed}")
        print(f"  Total Indexed State Records  : {pipeline.state_tracker.count()}")
        print(f"  Silver Layer Output Path     : {config.silver_dir / 'documents.jsonl'}")
        print("-" * 60 + "\n")

        if args.chunk_and_index:
            print("Running downstream chunking and indexing...")
            chunks, legacy_summary = pipeline.ingest()
            print(f"Chunks created: {legacy_summary.chunks_created}")

        return 0

    except Exception as e:
        logger.error("Ingestion failed: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
