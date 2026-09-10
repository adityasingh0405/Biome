"""Phase 7 — Ablation Runner.

Systematically compares RAG configuration axes and produces a ranked table of
metric scores. Each "arm" (experiment variant) is evaluated against the golden
dataset using :class:`EvaluationHarness`.

Axes swept:
  - ``retrieval_mode``: ``dense`` | ``sparse`` | ``hybrid``
  - ``top_k``:          3 | 5 | 10
  - ``rerank``:         True | False
  - ``chunk_strategy``: from processed_dir layout (``fixed`` | ``structure`` | ``semantic``)

Usage (CLI)::

    python eval/ablation_runner.py \\
        --golden eval/golden_qa.jsonl \\
        --output eval/ABLATION_RESULTS.md \\
        --axes retrieval_mode top_k rerank

Usage (programmatic)::

    from eval.ablation_runner import AblationRunner
    runner = AblationRunner(golden_path="eval/golden_qa.jsonl")
    results = runner.run()
    runner.write_markdown(results, "eval/ABLATION_RESULTS.md")
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from itertools import product
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Experiment configuration
# ---------------------------------------------------------------------------

_DEFAULT_AXES: dict[str, list[Any]] = {
    "retrieval_mode": ["dense", "sparse", "hybrid"],
    "top_k":          [3, 5, 10],
    "rerank":         [True, False],
}


@dataclass
class AblationArm:
    """One variant of the ablation experiment."""
    arm_id: str                     # e.g. "hybrid_k5_rerank"
    retrieval_mode: str = "hybrid"
    top_k: int = 5
    rerank: bool = True
    chunk_strategy: str = "default"

    # --- Results (filled after run) ---
    correctness: float = 0.0
    faithfulness: float = 0.0
    context_precision: float = 0.0
    context_recall: float = 0.0
    hallucination_score: float = 0.0
    answer_relevancy: float = 0.0
    semantic_similarity: float = 0.0
    mrr: float = 0.0
    latency_ms: float = 0.0
    n_questions: int = 0
    error: str = ""

    def composite_score(self) -> float:
        """Weighted composite: higher = better."""
        return (
            0.30 * self.correctness
            + 0.20 * self.faithfulness
            + 0.15 * self.context_precision
            + 0.10 * self.context_recall
            + 0.10 * self.answer_relevancy
            + 0.10 * self.semantic_similarity
            - 0.05 * self.hallucination_score  # penalise hallucination
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["composite_score"] = round(self.composite_score(), 4)
        return d


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class AblationRunner:
    """Run a sweep of EvaluationHarness across configuration arms.

    Args:
        golden_path:    Path to JSONL/JSON golden dataset.
        processed_dir:  Directory containing processed chunks.
        storage_dir:    Directory containing the BM25 index + Qdrant storage.
        reports_dir:    Where to write per-arm JSON reports.
        axes:           Dict of {axis_name: [values]} to sweep.
                        Defaults to :data:`_DEFAULT_AXES`.
        question_types: Optional filter — only evaluate these question types.
    """

    def __init__(
        self,
        golden_path: str | Path = "eval/golden_qa.jsonl",
        processed_dir: str | Path = "data/processed",
        storage_dir: str | Path = "data/index",
        reports_dir: str | Path = "eval/reports/ablation",
        axes: dict[str, list[Any]] | None = None,
        question_types: list[str] | None = None,
    ) -> None:
        self.golden_path   = Path(golden_path)
        self.processed_dir = Path(processed_dir)
        self.storage_dir   = Path(storage_dir)
        self.reports_dir   = Path(reports_dir)
        self.axes          = axes or deepcopy(_DEFAULT_AXES)
        self.question_types = question_types
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enumerate_arms(self) -> list[AblationArm]:
        """Return all arms produced by the Cartesian product of axes."""
        axis_names  = list(self.axes.keys())
        axis_values = [self.axes[k] for k in axis_names]
        arms: list[AblationArm] = []
        for combo in product(*axis_values):
            params = dict(zip(axis_names, combo))
            parts: list[str] = []
            for k, v in params.items():
                if k == "retrieval_mode":
                    parts.append(str(v))
                elif k == "top_k":
                    parts.append(f"k{v}")
                elif k == "rerank":
                    parts.append("rerank" if v else "no_rerank")
                else:
                    parts.append(f"{k}{v}".replace(" ", "").replace("/", "-"))
            arm_id = "_".join(parts)
            arm = AblationArm(arm_id=arm_id, **params)
            arms.append(arm)
        logger.info("Enumerated %d ablation arms", len(arms))
        return arms

    def run(
        self,
        arms: list[AblationArm] | None = None,
        dry_run: bool = False,
    ) -> list[AblationArm]:
        """Run all arms and return them with results filled in.

        Args:
            arms:    Override the default arm list (for targeted re-runs).
            dry_run: Skip actual evaluation; fill results with random scores.
                     Useful for validating the runner config before a real run.
        """
        if arms is None:
            arms = self.enumerate_arms()

        for i, arm in enumerate(arms):
            tag = f"[{i+1}/{len(arms)}] arm={arm.arm_id}"
            logger.info("%s  starting ...", tag)
            if dry_run:
                self._fill_synthetic(arm)
                continue
            try:
                self._run_arm(arm)
                self._save_arm(arm)
                logger.info(
                    "%s  composite=%.4f  latency=%.0fms",
                    tag, arm.composite_score(), arm.latency_ms,
                )
            except Exception as exc:  # noqa: BLE001
                arm.error = str(exc)
                logger.warning("%s  FAILED: %s", tag, exc)

        return arms


    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run_arm(self, arm: AblationArm) -> None:
        """Evaluate one arm with EvaluationHarness."""
        from biome_rag.evaluation.harness import EvaluationHarness  # noqa: PLC0415
        from biome_rag.evaluation.extended_metrics import EvalThresholds  # noqa: PLC0415

        harness = EvaluationHarness(
            processed_dir=self.processed_dir,
            storage_dir=self.storage_dir,
            reports_dir=self.reports_dir / arm.arm_id,
            retrieval_mode=arm.retrieval_mode,
            thresholds=EvalThresholds.lenient(),
            top_k=arm.top_k,
            rerank=arm.rerank,
        )
        t0 = time.perf_counter()
        report = harness.run(self.golden_path, question_types=self.question_types)
        arm.latency_ms = (time.perf_counter() - t0) * 1000

        agg = report.aggregate
        arm.correctness         = getattr(agg, "mean_correctness", getattr(agg, "avg_correctness", 0.0))
        arm.faithfulness        = getattr(agg, "mean_faithfulness", getattr(agg, "avg_faithfulness", 0.0))
        arm.context_precision   = getattr(agg, "mean_context_precision", getattr(agg, "avg_context_precision", 0.0))
        arm.context_recall      = getattr(agg, "mean_context_recall", getattr(agg, "avg_context_recall", 0.0))
        arm.hallucination_score = getattr(agg, "mean_hallucination_score", getattr(agg, "avg_hallucination_score", 0.0))
        arm.answer_relevancy    = getattr(agg, "mean_answer_relevancy", getattr(agg, "avg_answer_relevancy", 0.0))
        arm.semantic_similarity = getattr(agg, "mean_semantic_similarity", getattr(agg, "avg_semantic_similarity", 0.0))
        arm.mrr                 = getattr(agg, "mean_mrr", getattr(agg, "avg_mrr", 0.0))
        arm.n_questions         = getattr(agg, "n", 0)


    def _fill_synthetic(self, arm: AblationArm) -> None:
        """Fill arm with deterministic synthetic scores (dry-run only)."""
        import hashlib  # noqa: PLC0415
        seed = int(hashlib.md5(arm.arm_id.encode()).hexdigest()[:8], 16)
        rng  = __import__("random").Random(seed)
        arm.correctness         = round(rng.uniform(0.3, 0.8), 4)
        arm.faithfulness        = round(rng.uniform(0.4, 0.9), 4)
        arm.context_precision   = round(rng.uniform(0.3, 0.8), 4)
        arm.context_recall      = round(rng.uniform(0.3, 0.8), 4)
        arm.hallucination_score = round(rng.uniform(0.0, 0.3), 4)
        arm.answer_relevancy    = round(rng.uniform(0.3, 0.8), 4)
        arm.semantic_similarity = round(rng.uniform(0.4, 0.9), 4)
        arm.mrr                 = round(rng.uniform(0.4, 0.9), 4)
        arm.latency_ms          = round(rng.uniform(200, 2000), 1)
        arm.n_questions         = 10

    def _save_arm(self, arm: AblationArm) -> None:
        path = self.reports_dir / f"{arm.arm_id}.json"
        path.write_text(json.dumps(arm.to_dict(), indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def write_markdown(
        self,
        arms: list[AblationArm],
        output_path: str | Path = "eval/ABLATION_RESULTS.md",
    ) -> Path:
        """Write ABLATION_RESULTS.md — sorted by composite score descending."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ranked = sorted(arms, key=lambda a: a.composite_score(), reverse=True)
        lines: list[str] = [
            "# Biome RAG — Ablation Study Results",
            "",
            "> Auto-generated by `eval/ablation_runner.py` · Phase 7",
            f"> Golden dataset: `{self.golden_path}`",
            "",
            "## Summary Table (ranked by composite score ↓)",
            "",
            "| Rank | Arm ID | Mode | top_k | Rerank | Correctness | Faithfulness | Ctx-P | Ctx-R | Hall↓ | AnsRel | SemSim | MRR | Composite | Latency(ms) |",
            "|------|--------|------|-------|--------|-------------|--------------|-------|-------|-------|--------|--------|-----|-----------|-------------|",
        ]
        for rank, arm in enumerate(ranked, 1):
            err_flag = " ⚠" if arm.error else ""
            lines.append(
                f"| {rank} | `{arm.arm_id}`{err_flag} "
                f"| {arm.retrieval_mode} "
                f"| {arm.top_k} "
                f"| {'✓' if arm.rerank else '✗'} "
                f"| {arm.correctness:.3f} "
                f"| {arm.faithfulness:.3f} "
                f"| {arm.context_precision:.3f} "
                f"| {arm.context_recall:.3f} "
                f"| {arm.hallucination_score:.3f} "
                f"| {arm.answer_relevancy:.3f} "
                f"| {arm.semantic_similarity:.3f} "
                f"| {arm.mrr:.3f} "
                f"| **{arm.composite_score():.4f}** "
                f"| {arm.latency_ms:.0f} |"
            )
        lines += [
            "",
            "## Axis Analysis",
            "",
            self._axis_section(arms, "retrieval_mode", ["dense", "sparse", "hybrid"]),
            "",
            self._axis_section(arms, "top_k", [3, 5, 10]),
            "",
            self._axis_section(arms, "rerank", [True, False]),
            "",
            "## Best Configuration",
            "",
        ]
        if ranked:
            best = ranked[0]
            lines += [
                f"**Winner:** `{best.arm_id}`",
                "",
                f"| Metric | Value |",
                f"|--------|-------|",
                f"| Retrieval mode | {best.retrieval_mode} |",
                f"| Top-K | {best.top_k} |",
                f"| Reranking | {'Yes' if best.rerank else 'No'} |",
                f"| Correctness | {best.correctness:.4f} |",
                f"| Faithfulness | {best.faithfulness:.4f} |",
                f"| Context Precision | {best.context_precision:.4f} |",
                f"| Context Recall | {best.context_recall:.4f} |",
                f"| Hallucination Score | {best.hallucination_score:.4f} |",
                f"| Answer Relevancy | {best.answer_relevancy:.4f} |",
                f"| Semantic Similarity | {best.semantic_similarity:.4f} |",
                f"| MRR | {best.mrr:.4f} |",
                f"| **Composite Score** | **{best.composite_score():.4f}** |",
                f"| Avg latency | {best.latency_ms:.0f} ms |",
            ]
        lines += [
            "",
            "## Composite Score Formula",
            "",
            "```",
            "composite = 0.30 × correctness",
            "           + 0.20 × faithfulness",
            "           + 0.15 × context_precision",
            "           + 0.10 × context_recall",
            "           + 0.10 × answer_relevancy",
            "           + 0.10 × semantic_similarity",
            "           − 0.05 × hallucination_score",
            "```",
            "",
            "Weights chosen to prioritise factual correctness and faithfulness, "
            "while penalising hallucination.",
            "",
            "## Errors",
        ]
        failed = [a for a in arms if a.error]
        if failed:
            for a in failed:
                lines.append(f"- `{a.arm_id}`: {a.error}")
        else:
            lines.append("_No errors._")
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info("Ablation report written -> %s", output_path)
        return output_path

    def write_json(
        self,
        arms: list[AblationArm],
        output_path: str | Path = "eval/ablation_results.json",
    ) -> Path:
        """Write machine-readable JSON results."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps([a.to_dict() for a in arms], indent=2),
            encoding="utf-8",
        )
        return output_path

    def _axis_section(
        self,
        arms: list[AblationArm],
        axis: str,
        values: list[Any],
    ) -> str:
        """Build a mini comparison table for a single axis (others averaged)."""
        lines = [
            f"### Effect of `{axis}`",
            "",
            f"| {axis} | Avg Correctness | Avg Faithfulness | Avg Composite |",
            f"|--------|-----------------|-----------------|---------------|",
        ]
        for val in values:
            cohort = [a for a in arms if getattr(a, axis) == val and not a.error]
            if not cohort:
                lines.append(f"| {val} | — | — | — |")
                continue
            avg_corr  = sum(a.correctness for a in cohort) / len(cohort)
            avg_faith = sum(a.faithfulness for a in cohort) / len(cohort)
            avg_comp  = sum(a.composite_score() for a in cohort) / len(cohort)
            lines.append(
                f"| {val} | {avg_corr:.3f} | {avg_faith:.3f} | {avg_comp:.4f} |"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Phase 7 — Biome RAG Ablation Runner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--golden",       default="eval/golden_qa.jsonl",        help="Path to JSONL/JSON golden dataset")
    p.add_argument("--processed",    default="data/processed",               help="Processed chunks directory")
    p.add_argument("--storage",      default="data/index",                   help="Index storage directory")
    p.add_argument("--reports-dir",  default="eval/reports/ablation",        help="Per-arm report directory")
    p.add_argument("--output-md",    default="eval/ABLATION_RESULTS.md",     help="Markdown output path")
    p.add_argument("--output-json",  default="eval/ablation_results.json",   help="JSON output path")
    p.add_argument("--axes",         nargs="+", default=list(_DEFAULT_AXES), help="Axes to sweep (subset of default keys)")
    p.add_argument("--retrieval-modes", nargs="+", default=["dense", "sparse", "hybrid"])
    p.add_argument("--top-k-values",    nargs="+", type=int, default=[3, 5, 10])
    p.add_argument("--no-rerank",    action="store_true",    help="Only test without reranking")
    p.add_argument("--question-types", nargs="*",            help="Filter golden dataset by question type")
    p.add_argument("--dry-run",      action="store_true",    help="Fill results with synthetic scores (no real inference)")
    p.add_argument("--arm",          nargs="*",              help="Run only these arm IDs (for partial re-runs)")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        stream=sys.stderr,
    )

    # Build axes dict from CLI args
    axes: dict[str, list[Any]] = {}
    if "retrieval_mode" in args.axes:
        axes["retrieval_mode"] = args.retrieval_modes
    if "top_k" in args.axes:
        axes["top_k"] = args.top_k_values
    if "rerank" in args.axes:
        rerank_vals: list[Any] = [False] if args.no_rerank else ([True] if len(args.top_k_values) == 1 else [True, False])
        axes["rerank"] = rerank_vals

    runner = AblationRunner(
        golden_path   = args.golden,
        processed_dir = args.processed,
        storage_dir   = args.storage,
        reports_dir   = args.reports_dir,
        axes          = axes or None,
        question_types= args.question_types,
    )

    all_arms = runner.enumerate_arms()

    # Filter to requested arms if --arm specified
    if args.arm:
        all_arms = [a for a in all_arms if a.arm_id in args.arm]
        if not all_arms:
            logger.error("No arms matched --arm filter: %s", args.arm)
            return 1

    results = runner.run(all_arms, dry_run=args.dry_run)

    md_path   = runner.write_markdown(results,  args.output_md)
    json_path = runner.write_json(results,       args.output_json)

    # Print summary to stdout
    ranked = sorted(results, key=lambda a: a.composite_score(), reverse=True)
    print(f"\n{'='*60}")
    print(f"Ablation complete - {len(results)} arms evaluated")
    print(f"{'='*60}")
    print(f"{'Rank':<5} {'Arm ID':<35} {'Composite':>10} {'Latency':>10}")
    print("-" * 62)
    for rank, arm in enumerate(ranked[:10], 1):
        err = "  [ERROR]" if arm.error else ""
        print(f"{rank:<5} {arm.arm_id:<35} {arm.composite_score():>10.4f} {arm.latency_ms:>9.0f}ms{err}")
    if len(ranked) > 10:
        print(f"  ... {len(ranked)-10} more arms (see {md_path})")
    print(f"\nReport  -> {md_path}")
    print(f"JSON    -> {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

