from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import IngestionPipeline
from .models import IngestionConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest raw documents into chunk stores")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--storage-dir", type=Path, default=Path("data/index"))
    args = parser.parse_args()

    config = IngestionConfig(raw_dir=args.raw_dir, processed_dir=args.processed_dir, storage_dir=args.storage_dir)
    pipeline = IngestionPipeline(config)
    chunks, summary = pipeline.ingest()
    print(f"Documents processed: {summary.documents_processed}")
    print(f"Chunks created: {summary.chunks_created}")
    print(f"Duplicates skipped: {summary.duplicates_skipped}")
    print("Chunks per strategy:")
    for strategy, count in summary.chunks_per_strategy.items():
        print(f"- {strategy}: {count}")


if __name__ == "__main__":
    main()
