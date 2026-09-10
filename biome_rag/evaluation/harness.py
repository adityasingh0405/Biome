"""EvaluationHarness — Phase 6 end-to-end evaluation orchestrator.

Orchestrates the full evaluation pipeline:
  1. Load a golden QA dataset (JSONL or JSON list)
  2. For each Q&A pair: retrieve → generate → score all metrics
  3. Produce ``EvalResult`` objects with per-question and aggregate scores
  4. Write markdown + JSON reports to ``eval/reports/``
  5. Optionally: enforce quality gates via ``EvalThresholds``

Metric coverage:
  **Lexical (always available)**
    - answer_correctness (token F1)
    - faithfulness (claim-in-context overlap)
    - retrieval_relevance (recall@retrieved)
    - citation_accuracy
    - precision_at_5, MRR

  **Extended (Phase 6, always available — pure Python)**
    - context_precision, context_recall   (RAGAS-style proxies)
    - answer_relevancy
    - hallucination_score
    - noise_robustness

  **Semantic (requires sentence-transformers)**
    - semantic_similarity (MiniLM cosine; falls back to token-F1)

  **RAGAS (optional, requires ``ragas`` package + LLM API)**
    - ragas_faithfulness, ragas_answer_relevancy, ragas_context_recall,
      ragas_context_precision, ragas_answer_correctness

  **DeepEval (optional, requires ``deepeval`` package + LLM API)**
    - deepeval_hallucination, deepeval_answer_relevancy, deepeval_faithfulness,
      deepeval_contextual_precision, deepeval_contextual_recall

Usage::

    harness = EvaluationHarness(
        processed_dir="data/processed",
        storage_dir="data/index",
        reports_dir="eval/reports",
    )
    results = harness.run(golden_path="eval/golden_dataset.json")
    harness.write_report(results)

    # With quality gates
    violations = harness.check_quality_gate(results, thresholds=EvalThresholds.strict())
    if violations:
        raise SystemExit(f"Quality gate FAILED: {violations}")
"""
from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from biome_rag.evaluation.metrics import (
    answer_correctness,
    citation_accuracy,
    faithfulness,
    mean_reciprocal_rank,
    precision_at_k,
    retrieval_relevance,
)
from biome_rag.evaluation.extended_metrics import (
    EvalThresholds,
    ThresholdViolation,
    answer_relevancy,
    check_thresholds,
    context_precision,
    context_recall,
    hallucination_score,
    noise_robustness,
    semantic_similarity,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class QuestionResult:
    """All metric scores for a single Q&A evaluation."""
    id: str
    question: str
    question_type: str
    predicted_answer: str
    golden_answer: str
    context_chunks: list[str]

    # Lexical metrics
    correctness: float = 0.0
    faithfulness: float = 0.0
    retrieval_relevance: float = 0.0
    citation_accuracy: float = 0.0
    precision_at_5: float = 0.0
    mrr: float = 0.0
    confidence_composite: float = 0.0
    num_retrieved: int = 0

    # Extended Phase 6 metrics
    context_precision: float = 0.0
    context_recall: float = 0.0
    answer_relevancy: float = 0.0
    hallucination_score: float = 0.0
    noise_robustness: float = 1.0
    semantic_similarity: float = 0.0

    # Optional RAGAS / DeepEval metrics (None = not computed)
    ragas_scores: dict[str, float] = field(default_factory=dict)
    deepeval_scores: dict[str, float] = field(default_factory=dict)

    # Threshold violations for this question
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "question_type": self.question_type,
            "predicted_answer": self.predicted_answer,
            "golden_answer": self.golden_answer,
            "correctness": self.correctness,
            "faithfulness": self.faithfulness,
            "retrieval_relevance": self.retrieval_relevance,
            "citation_accuracy": self.citation_accuracy,
            "precision_at_5": self.precision_at_5,
            "mrr": self.mrr,
            "confidence_composite": self.confidence_composite,
            "num_retrieved": self.num_retrieved,
            "context_precision": self.context_precision,
            "context_recall": self.context_recall,
            "answer_relevancy": self.answer_relevancy,
            "hallucination_score": self.hallucination_score,
            "noise_robustness": self.noise_robustness,
            "semantic_similarity": self.semantic_similarity,
            "ragas_scores": self.ragas_scores,
            "deepeval_scores": self.deepeval_scores,
            "violations": self.violations,
        }


@dataclass
class AggregateResult:
    """Mean scores across all evaluated questions."""
    n: int = 0
    mean_correctness: float = 0.0
    mean_faithfulness: float = 0.0
    mean_retrieval_relevance: float = 0.0
    mean_citation_accuracy: float = 0.0
    mean_precision_at_5: float = 0.0
    mean_mrr: float = 0.0
    mean_confidence: float = 0.0
    mean_context_precision: float = 0.0
    mean_context_recall: float = 0.0
    mean_answer_relevancy: float = 0.0
    mean_hallucination_score: float = 0.0
    mean_noise_robustness: float = 1.0
    mean_semantic_similarity: float = 0.0
    questions_hallucinated: int = 0   # count with hallucination_score > 0.6
    questions_passed_gate: int = 0
    questions_failed_gate: int = 0
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class EvalReport:
    """Full evaluation report: per-question rows + aggregate."""
    rows: list[QuestionResult] = field(default_factory=list)
    aggregate: AggregateResult = field(default_factory=AggregateResult)
    retrieval_mode: str = "hybrid"
    timestamp: str = ""
    ragas_enabled: bool = False
    deepeval_enabled: bool = False


# ---------------------------------------------------------------------------
# EvaluationHarness
# ---------------------------------------------------------------------------

class EvaluationHarness:
    """Orchestrates the full Phase 6 evaluation pipeline.

    Args:
        processed_dir: Path to ``chunks.json``.
        storage_dir: Path to ``bm25_index.pkl``.
        reports_dir: Output directory for reports.
        retrieval_mode: One of ``"hybrid"``, ``"dense"``, ``"sparse"``.
        thresholds: Pass/fail gates; ``None`` skips gate checks.
        use_ragas: Attempt RAGAS evaluation (requires package + LLM API key).
        use_deepeval: Attempt DeepEval evaluation (requires package + LLM API key).
        ragas_llm_model: Model name for RAGAS (e.g. ``"gpt-4o-mini"``).
    """

    def __init__(
        self,
        processed_dir: str | Path = "data/processed",
        storage_dir: str | Path = "data/index",
        reports_dir: str | Path = "eval/reports",
        retrieval_mode: str = "hybrid",
        thresholds: EvalThresholds | None = None,
        use_ragas: bool = False,
        use_deepeval: bool = False,
        ragas_llm_model: str = "gpt-4o-mini",
        top_k: int = 5,
        rerank: bool = True,
    ) -> None:
        self.processed_dir = Path(processed_dir)
        self.storage_dir = Path(storage_dir)
        self.reports_dir = Path(reports_dir)
        self.retrieval_mode = retrieval_mode
        self.thresholds = thresholds
        self.use_ragas = use_ragas
        self.use_deepeval = use_deepeval
        self.ragas_llm_model = ragas_llm_model
        self.top_k = top_k
        self.rerank = rerank

        self._retriever = None
        self._builder = None

    # ------------------------------------------------------------------
    # Lazy init
    # ------------------------------------------------------------------

    def _get_pipeline(self):
        if self._retriever is None:
            from biome_rag.retrieval.engine import HybridRetriever  # noqa: PLC0415
            from biome_rag.generation.answering import AnswerBuilder  # noqa: PLC0415
            self._retriever = HybridRetriever(
                storage_dir=self.storage_dir,
                processed_dir=self.processed_dir,
            )
            self._builder = AnswerBuilder()
        return self._retriever, self._builder

    # ------------------------------------------------------------------
    # Golden dataset loading
    # ------------------------------------------------------------------

    @staticmethod
    def load_golden(path: str | Path) -> list[dict]:
        """Load JSONL (one record per line) or JSON array from path."""
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        if p.suffix == ".jsonl":
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        return json.loads(text)

    # ------------------------------------------------------------------
    # Per-question evaluation
    # ------------------------------------------------------------------

    def _eval_one(
        self,
        record: dict,
        retriever,
        builder,
        thresholds: EvalThresholds | None,
    ) -> QuestionResult:
        question = record.get("question", "")
        golden = record.get("golden_answer", "")
        expected_ids: list[str] = record.get("expected_chunk_ids", [])
        q_type = record.get("question_type", "simple")
        q_id = record.get("id", question[:40])

        # --- Retrieve ---
        try:
            chunks = retriever.retrieve(
                question,
                top_k=self.top_k,
                retrieval_mode=self.retrieval_mode,
                rerank=self.rerank,
            )
        except Exception as exc:
            logger.warning("Retrieval failed for %r: %s", question, exc)
            chunks = []


        # --- Generate ---
        try:
            response = builder.answer(question, chunks)
        except Exception as exc:
            logger.warning("Generation failed for %r: %s", question, exc)
            from biome_rag.generation.answering import AnswerResponse, ConfidenceScores  # noqa: PLC0415
            response = AnswerResponse(
                answer="", citations=[], confidence=ConfidenceScores(0, 0, 0, 0),
                retrieved_chunks=[],
            )

        predicted = response.answer
        context_texts = [c.text for c in chunks if c.text]
        combined_ctx = "\n".join(context_texts)
        retrieved_ids = [
            f"{getattr(c, 'source', 'unknown')}:{getattr(c, 'chunk_index', 0)}"
            for c in chunks
        ]
        verified_flags = [c.verified for c in response.citations]
        confidence = response.confidence.composite if response.confidence else 0.0

        result = QuestionResult(
            id=q_id,
            question=question,
            question_type=q_type,
            predicted_answer=predicted,
            golden_answer=golden,
            context_chunks=context_texts,
            num_retrieved=len(chunks),
            confidence_composite=round(confidence, 4),
        )

        # --- Lexical metrics ---
        result.correctness         = answer_correctness(predicted, golden)
        result.faithfulness        = faithfulness(predicted, combined_ctx)
        result.retrieval_relevance = retrieval_relevance(retrieved_ids, expected_ids)
        result.citation_accuracy   = citation_accuracy(verified_flags, [True] * len(verified_flags)) if verified_flags else 0.0
        result.precision_at_5      = precision_at_k(retrieved_ids, expected_ids, k=5)
        result.mrr                 = mean_reciprocal_rank(retrieved_ids, expected_ids)

        # --- Extended Phase 6 metrics ---
        result.context_precision   = context_precision(context_texts, golden)
        result.context_recall      = context_recall(context_texts, golden)
        result.answer_relevancy    = answer_relevancy(question, predicted)
        result.hallucination_score = hallucination_score(predicted, combined_ctx)
        result.noise_robustness    = noise_robustness(predicted, [])  # no noise chunks in std eval
        result.semantic_similarity = semantic_similarity(predicted, golden)

        # --- Threshold check ---
        if thresholds:
            scores = {
                "correctness":         result.correctness,
                "faithfulness":        result.faithfulness,
                "context_precision":   result.context_precision,
                "context_recall":      result.context_recall,
                "retrieval_relevance": result.retrieval_relevance,
                "mrr":                 result.mrr,
                "answer_relevancy":    result.answer_relevancy,
                "hallucination_score": result.hallucination_score,
            }
            violations = check_thresholds(scores, thresholds)
            result.violations = [str(v) for v in violations]

        return result

    # ------------------------------------------------------------------
    # Optional: RAGAS integration
    # ------------------------------------------------------------------

    def _run_ragas(self, records: list[dict], rows: list[QuestionResult]) -> None:
        """Attempt RAGAS evaluation and attach scores to each QuestionResult row."""
        try:
            from ragas import evaluate as ragas_evaluate  # type: ignore
            from ragas.metrics import (  # type: ignore
                faithfulness as ragas_faithfulness,
                answer_relevancy as ragas_answer_relevancy,
                context_recall as ragas_context_recall,
                context_precision as ragas_context_precision,
                answer_correctness as ragas_answer_correctness,
            )
            from datasets import Dataset as HFDataset  # type: ignore
        except ImportError:
            logger.warning("ragas or datasets not installed — skipping RAGAS eval.")
            return

        logger.info("Running RAGAS evaluation on %d questions…", len(rows))
        data = {
            "question":   [r.question for r in rows],
            "answer":     [r.predicted_answer for r in rows],
            "contexts":   [r.context_chunks for r in rows],
            "ground_truth": [r.golden_answer for r in rows],
        }
        try:
            ds = HFDataset.from_dict(data)
            result = ragas_evaluate(
                ds,
                metrics=[
                    ragas_faithfulness,
                    ragas_answer_relevancy,
                    ragas_context_recall,
                    ragas_context_precision,
                    ragas_answer_correctness,
                ],
            )
            df = result.to_pandas()
            for i, row in enumerate(rows):
                row.ragas_scores = {
                    "ragas_faithfulness":      float(df.iloc[i].get("faithfulness", 0.0)),
                    "ragas_answer_relevancy":  float(df.iloc[i].get("answer_relevancy", 0.0)),
                    "ragas_context_recall":    float(df.iloc[i].get("context_recall", 0.0)),
                    "ragas_context_precision": float(df.iloc[i].get("context_precision", 0.0)),
                    "ragas_answer_correctness":float(df.iloc[i].get("answer_correctness", 0.0)),
                }
        except Exception as exc:
            logger.error("RAGAS evaluation failed: %s", exc)

    # ------------------------------------------------------------------
    # Optional: DeepEval integration
    # ------------------------------------------------------------------

    def _run_deepeval(self, rows: list[QuestionResult]) -> None:
        """Attempt DeepEval evaluation and attach scores to each row."""
        try:
            import deepeval  # type: ignore
            from deepeval.metrics import (  # type: ignore
                HallucinationMetric,
                AnswerRelevancyMetric,
                FaithfulnessMetric,
                ContextualPrecisionMetric,
                ContextualRecallMetric,
            )
            from deepeval.test_case import LLMTestCase  # type: ignore
        except ImportError:
            logger.warning("deepeval not installed — skipping DeepEval eval.")
            return

        logger.info("Running DeepEval on %d questions…", len(rows))
        metrics = [
            HallucinationMetric(threshold=0.5),
            AnswerRelevancyMetric(threshold=0.5),
            FaithfulnessMetric(threshold=0.5),
            ContextualPrecisionMetric(threshold=0.5),
            ContextualRecallMetric(threshold=0.5),
        ]
        for row in rows:
            try:
                tc = LLMTestCase(
                    input=row.question,
                    actual_output=row.predicted_answer,
                    expected_output=row.golden_answer,
                    retrieval_context=row.context_chunks,
                )
                for metric in metrics:
                    try:
                        metric.measure(tc)
                        row.deepeval_scores[type(metric).__name__] = round(metric.score, 4)
                    except Exception as exc:
                        logger.debug("DeepEval metric %s failed: %s", type(metric).__name__, exc)
            except Exception as exc:
                logger.warning("DeepEval test case failed for %r: %s", row.question, exc)

    # ------------------------------------------------------------------
    # Main run method
    # ------------------------------------------------------------------

    def run(
        self,
        golden_path: str | Path,
        question_types: list[str] | None = None,
    ) -> EvalReport:
        """Run the full evaluation pipeline.

        Args:
            golden_path: Path to the golden Q&A dataset (JSONL or JSON).
            question_types: Optional filter (e.g. ``["simple", "multi_hop"]``).

        Returns:
            ``EvalReport`` with per-question and aggregate results.
        """
        t0 = time.perf_counter()
        records = self.load_golden(golden_path)
        if question_types:
            records = [r for r in records if r.get("question_type", "simple") in question_types]
        logger.info("Evaluating %d questions (mode=%s)…", len(records), self.retrieval_mode)

        retriever, builder = self._get_pipeline()
        rows: list[QuestionResult] = []
        for i, record in enumerate(records):
            logger.debug("  Q%d: %s", i + 1, record.get("question", "")[:60])
            result = self._eval_one(record, retriever, builder, self.thresholds)
            rows.append(result)
            self._print_row(result)

        # --- Optional RAGAS / DeepEval ---
        if self.use_ragas and rows:
            self._run_ragas(records, rows)
        if self.use_deepeval and rows:
            self._run_deepeval(rows)

        # --- Aggregate ---
        agg = self._aggregate(rows, time.perf_counter() - t0)
        report = EvalReport(
            rows=rows,
            aggregate=agg,
            retrieval_mode=self.retrieval_mode,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            ragas_enabled=self.use_ragas,
            deepeval_enabled=self.use_deepeval,
        )
        return report

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    @staticmethod
    def _aggregate(rows: list[QuestionResult], elapsed: float) -> AggregateResult:
        n = max(1, len(rows))
        agg = AggregateResult(n=len(rows), elapsed_seconds=round(elapsed, 2))

        def _mean(attr: str) -> float:
            return round(sum(getattr(r, attr) for r in rows) / n, 4)

        agg.mean_correctness         = _mean("correctness")
        agg.mean_faithfulness        = _mean("faithfulness")
        agg.mean_retrieval_relevance = _mean("retrieval_relevance")
        agg.mean_citation_accuracy   = _mean("citation_accuracy")
        agg.mean_precision_at_5      = _mean("precision_at_5")
        agg.mean_mrr                 = _mean("mrr")
        agg.mean_confidence          = _mean("confidence_composite")
        agg.mean_context_precision   = _mean("context_precision")
        agg.mean_context_recall      = _mean("context_recall")
        agg.mean_answer_relevancy    = _mean("answer_relevancy")
        agg.mean_hallucination_score = _mean("hallucination_score")
        agg.mean_noise_robustness    = _mean("noise_robustness")
        agg.mean_semantic_similarity = _mean("semantic_similarity")
        agg.questions_hallucinated   = sum(1 for r in rows if r.hallucination_score >= 0.6)
        agg.questions_passed_gate    = sum(1 for r in rows if not r.violations)
        agg.questions_failed_gate    = sum(1 for r in rows if r.violations)
        return agg

    @staticmethod
    def _print_row(r: QuestionResult) -> None:
        # Use ASCII fallback symbols if stdout can't encode Unicode check marks
        _enc = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
        try:
            "\u2717\u2713".encode(_enc)
            flag = "\u2717" if r.violations else "\u2713"
        except (UnicodeEncodeError, LookupError):
            flag = "X" if r.violations else "v"
        try:
            print(
                f"  [{flag}] [{r.id[:12]:12s}] {r.question_type:10s}"
                f"  corr={r.correctness:.3f}"
                f"  faith={r.faithfulness:.3f}"
                f"  hall={r.hallucination_score:.3f}"
                f"  ctxP={r.context_precision:.3f}"
            )
        except UnicodeEncodeError:
            # Final fallback: ASCII-only safe version
            print(
                f"  [{flag}] [{r.id[:12]:12s}] {r.question_type:10s}"
                f"  corr={r.correctness:.3f}"
                f"  faith={r.faithfulness:.3f}"
                f"  hall={r.hallucination_score:.3f}"
                f"  ctxP={r.context_precision:.3f}".encode("ascii", errors="replace").decode()
            )

    # ------------------------------------------------------------------
    # Quality gate
    # ------------------------------------------------------------------

    def check_quality_gate(
        self,
        report: EvalReport,
        thresholds: EvalThresholds | None = None,
    ) -> list[ThresholdViolation]:
        """Check aggregate scores against quality gate thresholds.

        Returns a list of violations (empty = pass).
        """
        t = thresholds or self.thresholds or EvalThresholds()
        agg_scores = {
            "correctness":         report.aggregate.mean_correctness,
            "faithfulness":        report.aggregate.mean_faithfulness,
            "context_precision":   report.aggregate.mean_context_precision,
            "context_recall":      report.aggregate.mean_context_recall,
            "retrieval_relevance": report.aggregate.mean_retrieval_relevance,
            "mrr":                 report.aggregate.mean_mrr,
            "answer_relevancy":    report.aggregate.mean_answer_relevancy,
            "hallucination_score": report.aggregate.mean_hallucination_score,
        }
        return check_thresholds(agg_scores, t)

    # ------------------------------------------------------------------
    # Report writing
    # ------------------------------------------------------------------

    def write_report(self, report: EvalReport, tag: str = "") -> tuple[Path, Path]:
        """Write JSON + Markdown reports to ``reports_dir``.

        Returns:
            Tuple of (json_path, md_path).
        """
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        stem = f"eval_report{'_' + tag if tag else ''}_{report.retrieval_mode}"
        json_path = self.reports_dir / f"{stem}.json"
        md_path   = self.reports_dir / f"{stem}.md"

        # --- JSON ---
        payload = {
            "timestamp": report.timestamp,
            "retrieval_mode": report.retrieval_mode,
            "ragas_enabled": report.ragas_enabled,
            "deepeval_enabled": report.deepeval_enabled,
            "aggregate": report.aggregate.to_dict(),
            "rows": [r.to_dict() for r in report.rows],
        }
        json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

        # --- Markdown ---
        md = self._render_markdown(report)
        md_path.write_text(md, encoding="utf-8")

        logger.info("Reports written: %s | %s", json_path, md_path)
        return json_path, md_path

    @staticmethod
    def _render_markdown(report: EvalReport) -> str:
        a = report.aggregate
        lines = [
            f"# Biome RAG Evaluation Report",
            f"",
            f"**Generated:** {report.timestamp}  ",
            f"**Retrieval mode:** `{report.retrieval_mode}`  ",
            f"**Questions evaluated:** {a.n}  ",
            f"**Elapsed:** {a.elapsed_seconds:.1f}s  ",
            f"**RAGAS enabled:** {report.ragas_enabled}  ",
            f"**DeepEval enabled:** {report.deepeval_enabled}",
            f"",
            f"## Aggregate Scores",
            f"",
            f"| Metric | Score |",
            f"|--------|-------|",
            f"| Answer Correctness (token F1) | {a.mean_correctness:.4f} |",
            f"| Faithfulness | {a.mean_faithfulness:.4f} |",
            f"| Context Precision | {a.mean_context_precision:.4f} |",
            f"| Context Recall | {a.mean_context_recall:.4f} |",
            f"| Retrieval Relevance | {a.mean_retrieval_relevance:.4f} |",
            f"| Answer Relevancy | {a.mean_answer_relevancy:.4f} |",
            f"| Hallucination Score ↓ | {a.mean_hallucination_score:.4f} |",
            f"| Noise Robustness | {a.mean_noise_robustness:.4f} |",
            f"| Semantic Similarity | {a.mean_semantic_similarity:.4f} |",
            f"| MRR | {a.mean_mrr:.4f} |",
            f"| Precision@5 | {a.mean_precision_at_5:.4f} |",
            f"| Citation Accuracy | {a.mean_citation_accuracy:.4f} |",
            f"| Confidence (composite) | {a.mean_confidence:.4f} |",
            f"",
            f"## Quality Gate",
            f"",
            f"- ✅ Passed: **{a.questions_passed_gate}** / {a.n}",
            f"- ❌ Failed: **{a.questions_failed_gate}** / {a.n}",
            f"- ⚠️  Hallucinated: **{a.questions_hallucinated}** / {a.n} (score ≥ 0.6)",
            f"",
            f"## Per-Question Results",
            f"",
            f"| # | Question (truncated) | Type | Corr | Faith | CtxP | Hall | Violations |",
            f"|---|---------------------|------|------|-------|------|------|-----------|",
        ]
        for i, row in enumerate(report.rows, 1):
            q_short = row.question[:45].replace("|", "\\|")
            v = len(row.violations)
            lines.append(
                f"| {i} | {q_short} | {row.question_type} "
                f"| {row.correctness:.3f} | {row.faithfulness:.3f} "
                f"| {row.context_precision:.3f} | {row.hallucination_score:.3f} "
                f"| {'❌ ' + str(v) if v else '✓'} |"
            )
        return "\n".join(lines) + "\n"
