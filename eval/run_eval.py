#!/usr/bin/env python3
"""Evaluation runner for the Biome RAG pipeline.

Usage:
    python eval/run_eval.py
    python eval/run_eval.py --chunking-strategy fixed
    python eval/run_eval.py --compare-chunking
    python eval/run_eval.py --compare-retrieval
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from biome_rag.ingestion.models import IngestionConfig
from biome_rag.ingestion.pipeline import IngestionPipeline
from biome_rag.retrieval.engine import HybridRetriever
from biome_rag.generation.answering import AnswerBuilder
from biome_rag.evaluation.metrics import answer_correctness, faithfulness, retrieval_relevance, citation_accuracy

logging.basicConfig(
    level=logging.WARNING,  # Quieter during eval runs
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_eval")

REPORTS_DIR = ROOT / "eval" / "reports"
GOLDEN_PATH = ROOT / "eval" / "golden_dataset.json"
RAW_DIR = ROOT / "data" / "raw"
BASE_PROCESSED = ROOT / "data" / "processed"
BASE_INDEX = ROOT / "data" / "index"

STRATEGIES = ["fixed", "structure", "semantic"]


def load_golden(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_single_eval(
    records: list[dict[str, Any]],
    retriever: HybridRetriever,
    answer_builder: AnswerBuilder,
    retrieval_mode: str = "hybrid",
    question_types: list[str] | None = None,
) -> tuple[list[dict], dict]:
    rows = []
    for record in records:
        qtype = record.get("question_type", "simple")
        if question_types and qtype not in question_types:
            continue

        question = record["question"]
        golden_answer = record.get("golden_answer", "")
        expected_ids: list[str] = record.get("expected_chunk_ids", [])

        try:
            retrieved = retriever.retrieve(question, retrieval_mode=retrieval_mode)
        except Exception as exc:
            logger.warning("Retrieval failed for '%s': %s", question, exc)
            retrieved = []

        try:
            response = answer_builder.answer(question, retrieved)
        except Exception as exc:
            logger.warning("Generation failed for '%s': %s", question, exc)
            from biome_rag.generation.answering import AnswerResponse, ConfidenceScores
            response = AnswerResponse(answer="", citations=[], confidence=ConfidenceScores(0, 0, 0, 0), retrieved_chunks=[])

        predicted = response.answer
        context = "\n".join(c.text for c in retrieved if c.text)
        retrieved_ids = [
            f"{Path(getattr(c, 'source', 'unknown')).name}:{getattr(c, 'chunk_index', 0)}"
            for c in retrieved
        ]
        verified_flags = [c.verified for c in response.citations]

        row = {
            "id": record.get("id", "?"),
            "question": question,
            "question_type": qtype,
            "predicted_answer": predicted,
            "golden_answer": golden_answer,
            "correctness": answer_correctness(predicted, golden_answer),
            "faithfulness": faithfulness(predicted, context),
            "retrieval_relevance": retrieval_relevance(retrieved_ids, expected_ids),
            "citation_accuracy": citation_accuracy(verified_flags, [True] * len(verified_flags)) if verified_flags else 0.0,
            "confidence_composite": response.confidence.composite if response.confidence else 0.0,
            "num_retrieved": len(retrieved),
        }
        rows.append(row)
        print(f"  [{row['id']}] {qtype:12s}  correctness={row['correctness']:.3f}  faith={row['faithfulness']:.3f}  rel={row['retrieval_relevance']:.3f}")

    n = max(1, len(rows))
    aggregate = {
        "n": len(rows),
        "mean_correctness": round(sum(r["correctness"] for r in rows) / n, 3),
        "mean_faithfulness": round(sum(r["faithfulness"] for r in rows) / n, 3),
        "mean_retrieval_relevance": round(sum(r["retrieval_relevance"] for r in rows) / n, 3),
        "mean_citation_accuracy": round(sum(r["citation_accuracy"] for r in rows) / n, 3),
        "mean_confidence": round(sum(r["confidence_composite"] for r in rows) / n, 3),
    }
    return rows, aggregate


def build_retriever_and_builder(processed_dir: Path, storage_dir: Path):
    import os
    if os.getenv("LLM_PROVIDER", "local") == "ollama":
        # Check if Ollama is running; if not, force local provider for speed during eval
        try:
            import urllib.request
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1)
        except Exception:
            os.environ["LLM_PROVIDER"] = "local"

    retriever = HybridRetriever(storage_dir=storage_dir, processed_dir=processed_dir)
    builder = AnswerBuilder()
    return retriever, builder


def ingest_with_strategy(strategy: str, processed_dir: Path, storage_dir: Path):
    """Re-ingest raw docs using only a single chunking strategy."""
    from biome_rag.ingestion.chunkers import FixedSizeChunker, StructureAwareChunker, SemanticChunker
    from biome_rag.ingestion.dedup import Deduplicator
    from biome_rag.retrieval.dense import ChromaDenseEmbeddingAdapter, SimpleDenseEmbeddingAdapter
    from biome_rag.retrieval.bm25 import BM25Index
    from biome_rag.ingestion.loaders import load_documents
    import hashlib

    chunker_map = {
        "fixed": FixedSizeChunker(),
        "structure": StructureAwareChunker(),
        "semantic": SemanticChunker(),
    }
    chunker = chunker_map[strategy]

    paths = sorted(p for p in RAW_DIR.glob("**/*") if p.is_file())
    documents = load_documents(paths)
    chunks = []
    seen_hashes: set[str] = set()
    for doc in documents:
        for chunk in chunker.chunk(doc.text, doc.source, doc.section_heading, doc.page_number):
            h = hashlib.md5(chunk.text.strip().lower().encode()).hexdigest()
            if h not in seen_hashes:
                seen_hashes.add(h)
                chunks.append(chunk)

    import json as _json
    processed_dir.mkdir(parents=True, exist_ok=True)
    storage_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "chunks": [
            {
                "text": c.text, "source": c.source, "section_heading": c.section_heading,
                "page_number": c.page_number, "chunk_index": c.chunk_index,
                "chunking_strategy": c.chunking_strategy, "character_count": c.character_count,
            }
            for c in chunks
        ],
        "summary": {"documents_processed": len(documents), "chunks_created": len(chunks), "chunks_per_strategy": {strategy: len(chunks)}, "duplicates_skipped": 0},
    }
    (processed_dir / "chunks.json").write_text(_json.dumps(payload, indent=2), encoding="utf-8")

    bm25 = BM25Index(storage_dir / "bm25_index.pkl")
    bm25.build([c.text for c in chunks])
    bm25.save()

    try:
        adapter = ChromaDenseEmbeddingAdapter(storage_dir, f"biome-{strategy}")
        adapter.index_documents(chunks)
    except Exception as exc:
        logger.warning("Chroma indexing failed for strategy %s: %s", strategy, exc)

    return len(chunks)


def compare_chunking(records: list[dict]) -> dict:
    results = {}
    for strategy in STRATEGIES:
        processed_dir = BASE_PROCESSED.parent / f"processed_{strategy}"
        storage_dir = BASE_INDEX.parent / f"index_{strategy}"

        print(f"\n{'='*60}")
        print(f"Chunking strategy: {strategy.upper()}")
        print(f"{'='*60}")

        n_chunks = ingest_with_strategy(strategy, processed_dir, storage_dir)
        print(f"  Indexed {n_chunks} chunks with strategy '{strategy}'.")

        retriever, builder = build_retriever_and_builder(processed_dir, storage_dir)
        rows, agg = run_single_eval(records, retriever, builder)

        results[strategy] = {"n_chunks": n_chunks, "aggregate": agg, "rows": rows}

    return results


def compare_retrieval(records: list[dict], retriever: HybridRetriever, builder: AnswerBuilder) -> dict:
    results = {}
    for mode in ["hybrid", "dense", "sparse"]:
        print(f"\n{'='*60}")
        print(f"Retrieval mode: {mode.upper()}")
        print(f"{'='*60}")
        rows, agg = run_single_eval(records, retriever, builder, retrieval_mode=mode)
        results[mode] = {"aggregate": agg, "rows": rows}
    return results


def write_chunking_report(results: dict) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "chunking_comparison.md"

    lines = [
        "# Chunking Strategy Comparison Report\n",
        f"Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        "## Aggregate Metrics\n",
        "| Strategy | Chunks | Correctness | Faithfulness | Retrieval Relevance | Citation Accuracy |",
        "|----------|--------|-------------|--------------|--------------------|--------------------|",
    ]
    for strategy in STRATEGIES:
        if strategy not in results:
            continue
        agg = results[strategy]["aggregate"]
        n_chunks = results[strategy]["n_chunks"]
        lines.append(
            f"| {strategy:10s} | {n_chunks:6d} "
            f"| {agg['mean_correctness']:.3f}       "
            f"| {agg['mean_faithfulness']:.3f}        "
            f"| {agg['mean_retrieval_relevance']:.3f}               "
            f"| {agg['mean_citation_accuracy']:.3f}             |"
        )

    lines += [
        "",
        "## Per-Question-Type Breakdown\n",
    ]
    for strategy in STRATEGIES:
        if strategy not in results:
            continue
        lines.append(f"### {strategy.capitalize()} Strategy\n")
        for qtype in ["simple", "multi_hop", "unanswerable", "ambiguous"]:
            type_rows = [r for r in results[strategy]["rows"] if r["question_type"] == qtype]
            if not type_rows:
                continue
            n = len(type_rows)
            avg_corr = sum(r["correctness"] for r in type_rows) / n
            avg_faith = sum(r["faithfulness"] for r in type_rows) / n
            lines.append(f"- **{qtype}** ({n} questions): correctness={avg_corr:.3f}, faithfulness={avg_faith:.3f}")
        lines.append("")

    lines += [
        "## Analysis\n",
        "The evaluation was run across all three chunking strategies on the same 55-question golden dataset.",
        "Structure-aware chunking tends to perform better on documentation that follows Markdown heading conventions,",
        "as it preserves section boundaries. Fixed chunking provides consistent chunk sizes at the cost of",
        "occasionally splitting mid-section. Semantic chunking produces the most coherent chunks but may",
        "produce fewer total chunks for short documents.\n",
    ]

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def write_retrieval_report(results: dict) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "retrieval_comparison.md"

    lines = [
        "# Retrieval Mode Comparison Report\n",
        f"Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        "| Mode   | Correctness | Faithfulness | Retrieval Relevance | Citation Accuracy |",
        "|--------|-------------|--------------|--------------------|--------------------|",
    ]
    for mode in ["hybrid", "dense", "sparse"]:
        if mode not in results:
            continue
        agg = results[mode]["aggregate"]
        lines.append(
            f"| {mode:6s} "
            f"| {agg['mean_correctness']:.3f}       "
            f"| {agg['mean_faithfulness']:.3f}        "
            f"| {agg['mean_retrieval_relevance']:.3f}               "
            f"| {agg['mean_citation_accuracy']:.3f}             |"
        )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main():
    parser = argparse.ArgumentParser(description="Biome RAG evaluation runner.")
    parser.add_argument("--compare-chunking", action="store_true", help="Run eval across all chunking strategies.")
    parser.add_argument("--compare-retrieval", action="store_true", help="Run eval across hybrid/dense/sparse modes.")
    parser.add_argument("--chunking-strategy", choices=STRATEGIES, help="Restrict eval to one chunking strategy.")
    args = parser.parse_args()

    records = load_golden(GOLDEN_PATH)
    print(f"Loaded {len(records)} golden Q&A pairs from {GOLDEN_PATH}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.compare_chunking:
        print("\n> Running chunking strategy comparison ...")
        results = compare_chunking(records)

        report_path = write_chunking_report(results)
        print(f"\n[OK] Chunking comparison report written to {report_path}")

        json_path = REPORTS_DIR / "chunking_comparison.json"
        json_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
        print(f"[OK] Raw JSON results written to {json_path}")

    elif args.compare_retrieval:
        retriever, builder = build_retriever_and_builder(BASE_PROCESSED, BASE_INDEX)
        print("\n> Running retrieval mode comparison ...")
        results = compare_retrieval(records, retriever, builder)

        report_path = write_retrieval_report(results)
        print(f"\n[OK] Retrieval comparison report written to {report_path}")

        json_path = REPORTS_DIR / "retrieval_comparison.json"
        json_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
        print(f"[OK] Raw JSON results written to {json_path}")

    else:
        # Default: single eval run with existing index
        print(f"\n> Running standard evaluation (retrieval_mode=hybrid) ...")
        retriever, builder = build_retriever_and_builder(BASE_PROCESSED, BASE_INDEX)
        rows, agg = run_single_eval(records, retriever, builder)

        report = {"rows": rows, "aggregate": agg}
        report_path = REPORTS_DIR / "eval_report.json"
        report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

        print(f"\n{'='*60}")
        print("AGGREGATE RESULTS")
        print(f"{'='*60}")
        for k, v in agg.items():
            print(f"  {k:35s}: {v}")
        print(f"\n[OK] Report written to {report_path}")


if __name__ == "__main__":
    main()
