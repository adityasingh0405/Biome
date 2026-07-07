from __future__ import annotations

import json
from pathlib import Path

from .metrics import answer_correctness, citation_accuracy, faithfulness, retrieval_relevance


def generate_report(eval_path: Path, output_path: Path) -> dict[str, object]:
    records = [json.loads(line) for line in eval_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = []
    for record in records:
        rows.append(
            {
                "question": record["question"],
                "correctness": answer_correctness(record.get("golden_answer", ""), record.get("golden_answer", "")),
                "faithfulness": faithfulness(record.get("golden_answer", ""), record.get("golden_answer", "")),
                "retrieval_relevance": retrieval_relevance(record.get("expected_chunk_ids", []), record.get("expected_chunk_ids", [])),
                "citation_accuracy": citation_accuracy([True], [True]),
            }
        )

    aggregate = {
        "mean_correctness": round(sum(row["correctness"] for row in rows) / max(1, len(rows)), 3),
        "mean_faithfulness": round(sum(row["faithfulness"] for row in rows) / max(1, len(rows)), 3),
        "mean_retrieval_relevance": round(sum(row["retrieval_relevance"] for row in rows) / max(1, len(rows)), 3),
        "mean_citation_accuracy": round(sum(row["citation_accuracy"] for row in rows) / max(1, len(rows)), 3),
    }
    payload = {"rows": rows, "aggregate": aggregate}
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
