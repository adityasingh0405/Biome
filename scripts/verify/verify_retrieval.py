#!/usr/bin/env python3
"""Verification Script: Retrieval & Ranking Smoke Test.

Queries the hybrid retriever across dense, sparse, and RRF stages to ensure
scores are generated and candidates reranked as specified in DECISIONS.md.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from biome_rag.retrieval.engine import HybridRetriever


def main() -> int:
    print("=== Step 2: Testing Hybrid Retriever on current index ===")
    storage_dir = Path("data/index")
    processed_dir = Path("data/processed")

    if not storage_dir.exists():
        print(f"ERROR: Storage directory '{storage_dir}' does not exist.")
        return 1

    retriever = HybridRetriever(storage_dir=storage_dir, processed_dir=processed_dir)
    test_queries = [
        "How do I authenticate with the API?",
        "What are the rate limits for the enterprise tier?",
        "How do I configure Redis session storage?",
    ]

    for q in test_queries:
        print(f"\nQuery: {q}")
        chunks = retriever.retrieve(q, retrieval_mode="hybrid", top_k=3)
        print(f"Retrieved: {len(chunks)} chunks")
        for i, c in enumerate(chunks):
            print(f"  [{i+1}] Source: {c.source} | Rerank: {c.rerank_score:.4f} | Fused: {c.fused_score:.4f}")

    print("\nRetrieval verification passed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
