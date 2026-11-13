#!/usr/bin/env python3
"""Verification Script: Ingestion Pipeline Health Check.

Verifies that the document ingestion and chunking pipeline processes
files across supported extensions without crashing, emitting valid Chunks.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from biome_rag.ingestion.models import IngestionConfig
from biome_rag.ingestion.pipeline import IngestionPipeline


def main() -> int:
    print("=== Step 1: Testing Ingestion Pipeline on sample documents ===")
    tmp_dir = tempfile.mkdtemp(prefix="biome_verify_ingest_")
    try:
        tmp_path = Path(tmp_dir)
        raw_dir = tmp_path / "raw"
        processed_dir = tmp_path / "processed"
        storage_dir = tmp_path / "storage"

        raw_dir.mkdir(parents=True)
        processed_dir.mkdir(parents=True)
        storage_dir.mkdir(parents=True)

        # Create sample files
        doc1 = raw_dir / "sample_policy.txt"
        doc1.write_text("All remote employees must connect via corporate VPN. Access is revoked after 30 days of inactivity.", encoding="utf-8")

        doc2 = raw_dir / "sample_guide.md"
        doc2.write_text("# Deployment Guide\n\nEnsure Redis and Qdrant containers are running before starting the API server.", encoding="utf-8")

        config = IngestionConfig(
            raw_dir=raw_dir,
            processed_dir=processed_dir,
            storage_dir=storage_dir,
        )
        pipeline = IngestionPipeline(config)
        chunks, summary = pipeline.ingest([doc1, doc2])

        print(f"Chunks created: {summary.chunks_created}")
        print(f"Duplicates skipped: {summary.duplicates_skipped}")
        print(f"Strategies used: {summary.chunks_per_strategy}")

        if summary.chunks_created < 2:
            print("ERROR: Expected at least 2 chunks created from sample docs.")
            return 1

        print("Ingestion verification passed successfully.")
        return 0
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
