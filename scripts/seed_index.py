#!/usr/bin/env python3
"""Seed the index from data/raw/ and validate index consistency.

Usage:
    python scripts/seed_index.py
    python scripts/seed_index.py --validate-only
    python scripts/seed_index.py --raw-dir path/to/docs
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path regardless of how the script is invoked
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from biome_rag.ingestion.models import IngestionConfig
from biome_rag.ingestion.pipeline import IngestionPipeline
from biome_rag.retrieval.bm25 import BM25Index
from biome_rag.retrieval.stores import ChunkStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("seed_index")


def validate_only(storage_dir: Path, processed_dir: Path) -> None:
    """Check that existing indexes are coherent without re-running ingestion."""
    chunks_json = processed_dir / "chunks.json"
    bm25_pkl = storage_dir / "bm25_index.pkl"

    if not chunks_json.exists():
        logger.error("chunks.json not found at %s. Run without --validate-only to ingest.", chunks_json)
        sys.exit(1)
    if not bm25_pkl.exists():
        logger.error("bm25_index.pkl not found at %s. Run without --validate-only to ingest.", bm25_pkl)
        sys.exit(1)

    store = ChunkStore(processed_dir, storage_dir)
    chunks = store.get_chunks()
    bm25 = BM25Index(bm25_pkl)

    if len(chunks) != len(bm25.documents):
        logger.error(
            "E3002 — Index sync mismatch: %d chunks in JSON vs %d in BM25.",
            len(chunks),
            len(bm25.documents),
        )
        sys.exit(1)
    else:
        logger.info("✓ Index sync OK — %d chunks in both BM25 and ChunkStore.", len(chunks))


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Biome RAG index from raw documents.")
    parser.add_argument("--raw-dir", default="data/raw", help="Directory of raw input documents.")
    parser.add_argument("--processed-dir", default="data/processed", help="Output directory for processed chunks.")
    parser.add_argument("--storage-dir", default="data/index", help="Output directory for indexes.")
    parser.add_argument("--validate-only", action="store_true", help="Only validate existing indexes without re-ingesting.")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    processed_dir = Path(args.processed_dir)
    storage_dir = Path(args.storage_dir)

    if args.validate_only:
        logger.info("Running index validation only.")
        validate_only(storage_dir, processed_dir)
        return

    if not raw_dir.exists() or not any(raw_dir.iterdir()):
        logger.error("raw_dir '%s' is empty or does not exist. Add documents and re-run.", raw_dir)
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("Biome RAG — Seeding Index")
    logger.info("  raw_dir      : %s", raw_dir)
    logger.info("  processed_dir: %s", processed_dir)
    logger.info("  storage_dir  : %s", storage_dir)
    logger.info("=" * 60)

    config = IngestionConfig(
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        storage_dir=storage_dir,
    )
    pipeline = IngestionPipeline(config)
    chunks, summary = pipeline.ingest()

    logger.info("=" * 60)
    logger.info("Ingestion complete.")
    logger.info("  Documents processed : %d", summary.documents_processed)
    logger.info("  Chunks created      : %d", summary.chunks_created)
    logger.info("  Duplicates skipped  : %d", summary.duplicates_skipped)
    for strategy, count in sorted(summary.chunks_per_strategy.items()):
        logger.info("    %-20s: %d chunks", strategy, count)
    logger.info("  BM25 index          : %s", storage_dir / "bm25_index.pkl")
    logger.info("  Chroma collection   : %s", storage_dir / "chroma")
    logger.info("=" * 60)

    # Post-ingestion validation
    logger.info("Running index sync validation …")
    validate_only(storage_dir, processed_dir)
    logger.info("Seed complete. The API is ready to serve queries.")


if __name__ == "__main__":
    main()
