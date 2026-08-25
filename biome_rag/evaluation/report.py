from __future__ import annotations

import json
import logging
from pathlib import Path

from .metrics import answer_correctness, citation_accuracy, faithfulness, retrieval_relevance

logger = logging.getLogger(__name__)


def generate_report(eval_path: Path, output_path: Path) -> dict[str, object]:
    """Evaluate the RAG system against a golden QA dataset and write a report.

    Args:
        eval_path: Path to a JSONL file where each line contains a JSON object
                   with keys "question", "golden_answer", and "expected_chunk_ids".
        output_path: Path to write the JSON evaluation report to.

    Returns:
        A dict with "rows" (per-question metrics) and "aggregate" (mean metrics).

    Raises:
        FileNotFoundError: If required index files are missing.
    """
    # Import here to avoid circular imports and to allow the function to be
    # called from contexts where the retrieval system may not yet be initialised.
    from biome_rag.retrieval.engine import HybridRetriever
    from biome_rag.generation.answering import AnswerBuilder

    # Resolve default index paths (same defaults used everywhere else in the project)
    processed_dir = Path("data/processed")
    storage_dir = Path("data/index")

    chunks_json = processed_dir / "chunks.json"
    bm25_pkl = storage_dir / "bm25_index.pkl"
    if not chunks_json.exists() and not bm25_pkl.exists():
        raise FileNotFoundError(
            f"No index files found. Expected either '{chunks_json}' or '{bm25_pkl}'. "
            "Run ingestion first."
        )

    retriever = HybridRetriever(storage_dir=storage_dir, processed_dir=processed_dir)
    answer_builder = AnswerBuilder()

    records = [
        json.loads(line)
        for line in eval_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    rows = []
    for record in records:
        question = record["question"]
        golden_answer = record.get("golden_answer", "")
        expected_chunk_ids: list[str] = record.get("expected_chunk_ids", [])

        # Retrieve and generate
        try:
            retrieved_chunks = retriever.retrieve(question)
        except Exception as exc:
            logger.warning("Retrieval failed for question %r: %s", question, exc)
            retrieved_chunks = []

        try:
            answer_response = answer_builder.answer(question, retrieved_chunks)
        except Exception as exc:
            logger.warning("Answer building failed for question %r: %s", question, exc)
            from biome_rag.generation.answering import AnswerResponse, ConfidenceScores
            answer_response = AnswerResponse(
                answer="",
                citations=[],
                confidence=ConfidenceScores(0.0, 0.0, 0.0, 0.0),
                retrieved_chunks=[],
            )

        predicted_answer = answer_response.answer

        # Build context string from all retrieved chunks
        context = "\n".join(
            chunk.text for chunk in retrieved_chunks if chunk.text
        )

        # Collect retrieved chunk identifiers (source:chunk_index)
        retrieved_ids = [
            getattr(chunk, "source", "unknown") + ":" + str(getattr(chunk, "chunk_index", 0))
            for chunk in retrieved_chunks
        ]

        # Citation verification flags; fall back to all-True if no expected flags supplied
        verified_flags = [citation.verified for citation in answer_response.citations]
        expected_flags = [True] * len(verified_flags)

        row = {
            "question": question,
            "predicted_answer": predicted_answer,
            "golden_answer": golden_answer,
            "correctness": answer_correctness(predicted_answer, golden_answer),
            "faithfulness": faithfulness(predicted_answer, context),
            "retrieval_relevance": retrieval_relevance(retrieved_ids, expected_chunk_ids),
            "citation_accuracy": citation_accuracy(verified_flags, expected_flags) if verified_flags else 0.0,
        }
        rows.append(row)
        logger.info("Evaluated question: %r → correctness=%.3f", question, row["correctness"])

    n = max(1, len(rows))
    aggregate = {
        "mean_correctness": round(sum(row["correctness"] for row in rows) / n, 3),
        "mean_faithfulness": round(sum(row["faithfulness"] for row in rows) / n, 3),
        "mean_retrieval_relevance": round(sum(row["retrieval_relevance"] for row in rows) / n, 3),
        "mean_citation_accuracy": round(sum(row["citation_accuracy"] for row in rows) / n, 3),
    }

    payload: dict[str, object] = {"rows": rows, "aggregate": aggregate}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Report written to %s", output_path)
    return payload
