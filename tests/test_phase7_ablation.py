"""Unit tests for Phase 7: Ablation Runner and Study.

All tests run without external services (no LLM API, no network calls).
Tests exercise:
- AblationArm dataclass and composite score calculation
- AblationRunner axis enumeration and arm ID generation
- AblationRunner synthetic dry-run generation
- AblationRunner markdown & JSON report generation
- AblationRunner axis comparison table construction
- CLI argument parsing and execution with --dry-run and --arm filters
- AblationRunner integration with mocked EvaluationHarness
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from eval.ablation_runner import AblationArm, AblationRunner, _build_parser, main


# ---------------------------------------------------------------------------
# AblationArm Tests
# ---------------------------------------------------------------------------

class TestAblationArm:
    def test_default_fields(self) -> None:
        arm = AblationArm(arm_id="test_arm")
        assert arm.arm_id == "test_arm"
        assert arm.retrieval_mode == "hybrid"
        assert arm.top_k == 5
        assert arm.rerank is True
        assert arm.chunk_strategy == "default"
        assert arm.correctness == 0.0
        assert arm.error == ""

    def test_composite_score_calculation(self) -> None:
        arm = AblationArm(
            arm_id="test_score",
            correctness=0.8,
            faithfulness=0.9,
            context_precision=0.7,
            context_recall=0.6,
            hallucination_score=0.1,
            answer_relevancy=0.75,
            semantic_similarity=0.85,
        )
        expected = (
            0.30 * 0.8
            + 0.20 * 0.9
            + 0.15 * 0.7
            + 0.10 * 0.6
            + 0.10 * 0.75
            + 0.10 * 0.85
            - 0.05 * 0.1
        )
        assert pytest.approx(arm.composite_score(), 1e-6) == expected

    def test_composite_score_penalizes_hallucination(self) -> None:
        arm_clean = AblationArm(arm_id="clean", correctness=0.8, hallucination_score=0.0)
        arm_hallucinating = AblationArm(arm_id="hallucinating", correctness=0.8, hallucination_score=0.8)
        assert arm_clean.composite_score() > arm_hallucinating.composite_score()

    def test_to_dict(self) -> None:
        arm = AblationArm(arm_id="dict_test", retrieval_mode="dense", top_k=3, rerank=False)
        d = arm.to_dict()
        assert d["arm_id"] == "dict_test"
        assert d["retrieval_mode"] == "dense"
        assert d["top_k"] == 3
        assert d["rerank"] is False
        assert "composite_score" in d
        assert isinstance(d["composite_score"], float)


# ---------------------------------------------------------------------------
# AblationRunner Axis Enumeration Tests
# ---------------------------------------------------------------------------

class TestAblationRunnerAxes:
    def test_default_axes_enumeration(self, tmp_path: Path) -> None:
        runner = AblationRunner(
            golden_path="eval/golden_qa.jsonl",
            reports_dir=tmp_path / "reports",
        )
        arms = runner.enumerate_arms()
        # 3 retrieval modes * 3 top_k * 2 rerank = 18 arms
        assert len(arms) == 18

    def test_custom_axes_enumeration(self, tmp_path: Path) -> None:
        custom_axes = {
            "retrieval_mode": ["dense", "hybrid"],
            "top_k": [3, 10],
        }
        runner = AblationRunner(
            golden_path="eval/golden_qa.jsonl",
            reports_dir=tmp_path / "reports",
            axes=custom_axes,
        )
        arms = runner.enumerate_arms()
        assert len(arms) == 4
        ids = [a.arm_id for a in arms]
        assert "dense_k3" in ids
        assert "dense_k10" in ids
        assert "hybrid_k3" in ids
        assert "hybrid_k10" in ids

    def test_arm_id_naming_convention(self, tmp_path: Path) -> None:
        runner = AblationRunner(
            golden_path="eval/golden_qa.jsonl",
            reports_dir=tmp_path / "reports",
            axes={
                "retrieval_mode": ["dense"],
                "top_k": [5],
                "rerank": [True, False],
            },
        )
        arms = runner.enumerate_arms()
        assert len(arms) == 2
        assert arms[0].arm_id == "dense_k5_rerank"
        assert arms[1].arm_id == "dense_k5_no_rerank"


# ---------------------------------------------------------------------------
# AblationRunner Dry Run Tests
# ---------------------------------------------------------------------------

class TestAblationRunnerDryRun:
    def test_dry_run_populates_all_arms(self, tmp_path: Path) -> None:
        runner = AblationRunner(
            golden_path="eval/golden_qa.jsonl",
            reports_dir=tmp_path / "reports",
        )
        arms = runner.run(dry_run=True)
        assert len(arms) == 18
        for arm in arms:
            assert arm.correctness > 0.0
            assert arm.faithfulness > 0.0
            assert arm.context_precision > 0.0
            assert arm.context_recall > 0.0
            assert arm.answer_relevancy > 0.0
            assert arm.semantic_similarity > 0.0
            assert arm.composite_score() > 0.0
            assert arm.error == ""

    def test_dry_run_is_deterministic(self, tmp_path: Path) -> None:
        runner1 = AblationRunner(reports_dir=tmp_path / "r1")
        runner2 = AblationRunner(reports_dir=tmp_path / "r2")
        arms1 = runner1.run(dry_run=True)
        arms2 = runner2.run(dry_run=True)
        for a1, a2 in zip(arms1, arms2):
            assert a1.arm_id == a2.arm_id
            assert a1.composite_score() == a2.composite_score()


# ---------------------------------------------------------------------------
# Report Writing Tests
# ---------------------------------------------------------------------------

class TestAblationReports:
    def test_write_markdown_report(self, tmp_path: Path) -> None:
        runner = AblationRunner(reports_dir=tmp_path / "reports")
        arms = runner.run(dry_run=True)
        md_file = tmp_path / "ABLATION_RESULTS.md"
        out_path = runner.write_markdown(arms, md_file)

        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert "# Biome RAG — Ablation Study Results" in content
        assert "## Summary Table (ranked by composite score" in content
        assert "## Axis Analysis" in content
        assert "### Effect of `retrieval_mode`" in content
        assert "### Effect of `top_k`" in content
        assert "### Effect of `rerank`" in content
        assert "## Best Configuration" in content
        assert "## Composite Score Formula" in content

    def test_write_json_report(self, tmp_path: Path) -> None:
        runner = AblationRunner(reports_dir=tmp_path / "reports")
        arms = runner.run(dry_run=True)
        json_file = tmp_path / "ablation_results.json"
        out_path = runner.write_json(arms, json_file)

        assert out_path.exists()
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == 18
        assert "arm_id" in data[0]
        assert "composite_score" in data[0]

    def test_markdown_with_errors(self, tmp_path: Path) -> None:
        runner = AblationRunner(reports_dir=tmp_path / "reports")
        arm_ok = AblationArm(arm_id="ok_arm", correctness=0.8)
        arm_fail = AblationArm(arm_id="fail_arm", error="Index not found")
        md_file = tmp_path / "err_report.md"
        runner.write_markdown([arm_ok, arm_fail], md_file)

        content = md_file.read_text(encoding="utf-8")
        assert "`fail_arm`: Index not found" in content

    def test_axis_section_averages(self, tmp_path: Path) -> None:
        runner = AblationRunner(reports_dir=tmp_path / "reports")
        arms = [
            AblationArm(arm_id="d1", retrieval_mode="dense", correctness=0.6, faithfulness=0.8),
            AblationArm(arm_id="d2", retrieval_mode="dense", correctness=0.8, faithfulness=0.8),
            AblationArm(arm_id="s1", retrieval_mode="sparse", correctness=0.4, faithfulness=0.6),
        ]
        table = runner._axis_section(arms, "retrieval_mode", ["dense", "sparse"])
        assert "### Effect of `retrieval_mode`" in table
        assert "| dense | 0.700 | 0.800 |" in table
        assert "| sparse | 0.400 | 0.600 |" in table


# ---------------------------------------------------------------------------
# Mocked Evaluation Harness Integration Tests
# ---------------------------------------------------------------------------

class TestAblationMockHarness:
    def test_run_arm_with_mock_harness(self, tmp_path: Path) -> None:
        runner = AblationRunner(
            golden_path="eval/golden_qa.jsonl",
            reports_dir=tmp_path / "reports",
        )
        arm = AblationArm(arm_id="hybrid_k5_rerank", retrieval_mode="hybrid", top_k=5, rerank=True)

        mock_agg = MagicMock(
            mean_correctness=0.75,
            mean_faithfulness=0.88,
            mean_context_precision=0.90,
            mean_context_recall=0.80,
            mean_hallucination_score=0.05,
            mean_answer_relevancy=0.82,
            mean_semantic_similarity=0.78,
            mean_mrr=0.85,
            n=10,
        )
        mock_report = MagicMock(aggregate=mock_agg)

        with patch("biome_rag.evaluation.harness.EvaluationHarness") as MockHarness:
            instance = MockHarness.return_value
            instance.run.return_value = mock_report

            runner._run_arm(arm)

        assert arm.correctness == 0.75
        assert arm.faithfulness == 0.88
        assert arm.context_precision == 0.90
        assert arm.context_recall == 0.80
        assert arm.hallucination_score == 0.05
        assert arm.answer_relevancy == 0.82
        assert arm.semantic_similarity == 0.78
        assert arm.mrr == 0.85
        assert arm.n_questions == 10
        assert arm.error == ""
        assert arm.latency_ms >= 0.0


# ---------------------------------------------------------------------------
# CLI Tests
# ---------------------------------------------------------------------------

class TestAblationCLI:
    def test_parser_defaults(self) -> None:
        parser = _build_parser()
        args = parser.parse_args([])
        assert args.golden == "eval/golden_qa.jsonl"
        assert args.output_md == "eval/ABLATION_RESULTS.md"
        assert args.output_json == "eval/ablation_results.json"
        assert "retrieval_mode" in args.axes
        assert args.dry_run is False

    def test_cli_dry_run_success(self, tmp_path: Path) -> None:
        md_path = tmp_path / "out.md"
        json_path = tmp_path / "out.json"
        ret = main(["--dry-run", "--output-md", str(md_path), "--output-json", str(json_path)])
        assert ret == 0
        assert md_path.exists()
        assert json_path.exists()

    def test_cli_arm_filtering(self, tmp_path: Path) -> None:
        md_path = tmp_path / "out.md"
        json_path = tmp_path / "out.json"
        ret = main([
            "--dry-run",
            "--arm", "dense_k3_rerank",
            "--output-md", str(md_path),
            "--output-json", str(json_path),
        ])
        assert ret == 0
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["arm_id"] == "dense_k3_rerank"

    def test_cli_invalid_arm_filter_returns_1(self) -> None:
        ret = main(["--dry-run", "--arm", "non_existent_arm_id_12345"])
        assert ret == 1
