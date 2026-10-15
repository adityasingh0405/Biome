#!/usr/bin/env python3
"""Automated one-command setup script for the Biome Enterprise RAG Pipeline.

Acceptance criteria (Phase 9):
    A fresh clone + .env filled from SETUP_INTEGRATIONS.md + docker compose up
    + python scripts/setup_system.py brings the entire system to a working state.

Operations performed:
1. Validates configuration and environment variables.
2. Initializes required filesystem directories (raw, processed, storage).
3. Seeds PostgreSQL relational table 'enterprise_tickets' if database is reachable.
4. Orchestrates ingestion across raw enterprise documents and builds indexes (BM25, Qdrant/Chroma).
5. Asserts index synchronization (E3002 validation).
6. Runs a self-check against the retrieval and query router engines.

Usage:
    python scripts/setup_system.py
    python scripts/setup_system.py --validate-only
    python scripts/setup_system.py --skip-db-seed
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from biome_rag.config import get_settings
from biome_rag.indexing import IndexBuilder
from biome_rag.retrieval import (
    BM25Index,
    ChunkStore,
    HybridRetriever,
    NL2SQLEngine,
    QueryRouter,
    RouteDecision,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("setup_system")


# ---------------------------------------------------------------------------
# Setup Helpers
# ---------------------------------------------------------------------------

def check_environment() -> None:
    """Validate that environment file or settings exist."""
    env_file = ROOT / ".env"
    example_file = ROOT / ".env.example"

    if not env_file.exists():
        if example_file.exists():
            logger.warning(".env not found. Copying .env.example to .env with defaults...")
            shutil.copy(example_file, env_file)
        else:
            logger.warning("Neither .env nor .env.example found. Relying on default settings.")

    settings = get_settings()
    logger.info("✓ Configuration loaded. LLM Provider: %s | Qdrant: %s:%s",
                settings.llm_provider, settings.qdrant_host, settings.qdrant_port)


def init_directories(data_dir: Path) -> tuple[Path, Path, Path]:
    """Ensure data/raw, data/processed, and data/index exist."""
    raw_dir = data_dir / "raw"
    processed_dir = data_dir / "processed"
    storage_dir = data_dir / "index"

    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    storage_dir.mkdir(parents=True, exist_ok=True)

    # If raw_dir is empty, copy from local_data_bucket if available
    bucket_dir = ROOT / "local_data_bucket"
    if not any(raw_dir.iterdir()) and bucket_dir.exists():
        logger.info("data/raw is empty. Seeding initial documents from local_data_bucket...")
        for item in bucket_dir.glob("**/*"):
            if item.is_file():
                dest = raw_dir / item.name
                if not dest.exists():
                    shutil.copy(item, dest)

    logger.info("✓ Directories initialized at %s", data_dir)
    return raw_dir, processed_dir, storage_dir


def seed_database(settings) -> bool:
    """Attempt to seed enterprise_tickets in PostgreSQL if reachable."""
    try:
        from seed_db import generate_enterprise_data
        from sqlalchemy import create_engine, text

        engine = create_engine(
            settings.postgres_uri,
            pool_size=1,
            max_overflow=0,
            connect_args={"connect_timeout": 3},
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        logger.info("PostgreSQL reachable at %s. Seeding 500 enterprise tickets...", settings.postgres_uri)
        df = generate_enterprise_data(500)
        df.to_sql(settings.postgres_table, engine, if_exists="replace", index=False)
        logger.info("✓ PostgreSQL database populated successfully.")
        return True
    except Exception as exc:
        logger.warning(
            "PostgreSQL seeding skipped (%s). NL2SQLEngine will use in-memory SQLite schema fallback.",
            exc,
        )
        return False


def build_and_sync_indexes(raw_dir: Path, processed_dir: Path, storage_dir: Path) -> int:
    """Run IndexBuilder to index all raw documents and verify BM25/Store sync."""
    builder = IndexBuilder(
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        storage_dir=storage_dir,
        use_docling=False,
        use_qdrant=True,
    )

    logger.info("Running IndexBuilder over %s...", raw_dir)
    result = builder.build()
    logger.info("✓ Indexing finished in %.1f ms. Chunks produced: %d",
                result.elapsed_ms, result.total_chunks)

    # Sync verification (E3002 check)
    chunks_json = processed_dir / "chunks.json"
    bm25_pkl = storage_dir / "bm25_index.pkl"

    if not chunks_json.exists() or not bm25_pkl.exists():
        logger.error("Missing index artifacts after indexing: chunks.json or bm25_index.pkl")
        return 1

    store = ChunkStore(processed_dir, storage_dir)
    bm25 = BM25Index(bm25_pkl)
    chunks = store.get_chunks()

    if len(chunks) != len(bm25.documents):
        logger.error("E3002: Index sync mismatch: %d chunks vs %d BM25 documents",
                     len(chunks), len(bm25.documents))
        return 1

    logger.info("✓ Index synchronization verified: %d chunks aligned across BM25 and ChunkStore.", len(chunks))
    return 0


def verify_system_health(raw_dir: Path, processed_dir: Path, storage_dir: Path) -> bool:
    """Run quick self-checks across hybrid retrieval and query routing."""
    logger.info("Verifying system self-checks...")
    try:
        # 1. Query Router Check
        router = QueryRouter()
        assert router.classify("how many total tickets") == RouteDecision.STRUCTURED
        assert router.classify("how to reset password") == RouteDecision.SEMANTIC
        logger.info("✓ QueryRouter self-check passed.")

        # 2. NL2SQL Engine Check
        engine = NL2SQLEngine()
        sql_res = engine.execute("How many total tickets are in the database?")
        assert sql_res.sql_query != ""
        logger.info("✓ NL2SQLEngine self-check passed.")

        # 3. Hybrid Retriever Check
        retriever = HybridRetriever(storage_dir=storage_dir, processed_dir=processed_dir)
        results = retriever.retrieve("equipment security policy", top_k=3)
        logger.info("✓ HybridRetriever self-check passed (retrieved %d candidates).", len(results))

        return True
    except Exception as exc:
        logger.error("Health self-check failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Biome RAG Pipeline Automated Setup & Self-Check")
    parser.add_argument("--validate-only", action="store_true", help="Only validate environment and index sync")
    parser.add_argument("--skip-db-seed", action="store_true", help="Skip PostgreSQL seeding")
    parser.add_argument("--data-dir", default=str(ROOT / "data"), help="Data directory path")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    print("\n" + "=" * 60)
    print("🌿  Biome Enterprise RAG — System Setup & Self-Check")
    print("=" * 60 + "\n")

    # Step 1: Environment check
    check_environment()
    settings = get_settings()

    # Step 2: Directory initialization
    raw_dir, processed_dir, storage_dir = init_directories(data_dir)

    if args.validate_only:
        logger.info("Running in validate-only mode...")
        store = ChunkStore(processed_dir, storage_dir)
        bm25 = BM25Index(storage_dir / "bm25_index.pkl")
        chunks = store.get_chunks()
        if len(chunks) == len(bm25.documents):
            logger.info("✓ System index is healthy (%d synchronized chunks).", len(chunks))
            return 0
        else:
            logger.error("System index mismatch: %d chunks vs %d BM25 docs.", len(chunks), len(bm25.documents))
            return 1

    # Step 3: Database seeding
    if not args.skip_db_seed:
        seed_database(settings)

    # Step 4: Index building & sync check
    ret = build_and_sync_indexes(raw_dir, processed_dir, storage_dir)
    if ret != 0:
        return ret

    # Step 5: System health checks
    if not verify_system_health(raw_dir, processed_dir, storage_dir):
        logger.warning("One or more self-checks failed. Review log output above.")
        return 1

    print("\n" + "=" * 60)
    print("🎉  SYSTEM SETUP COMPLETE AND VERIFIED!")
    print("=" * 60)
    print("\nTo start the application:")
    print("  1. Backend API:     uvicorn biome_rag.api.app:app --host 0.0.0.0 --port 8000 --reload")
    print("  2. React Frontend:  cd frontend && npm run dev (http://localhost:5173)")
    print("  3. API Docs:        http://localhost:8000/docs")
    print("  4. Qdrant UI:       http://localhost:6333/dashboard\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
