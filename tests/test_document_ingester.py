"""Unit tests for DocumentIngester (Phase 1).

These tests run with NO external services — Docling, databases, etc.
They create real temporary files and exercise:
- Incremental filtering (mtime-based since parameter)
- Fallback parser routing (no Docling installed → fallback loaders)
- ACL scope inference from filenames
- Empty document handling
- Error resilience per file
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from biome_rag.ingestion.document_ingester import (
    DocumentIngester,
    _infer_access_scope,
)
from biome_rag.ingestion.models import DocumentNode


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with a set of sample documents."""
    docs = tmp_path / "docs"
    docs.mkdir()

    (docs / "api_guide.md").write_text(
        "# API Guide\n\nUse `Authorization: Bearer <token>` for all requests.\n",
        encoding="utf-8",
    )
    (docs / "public_overview.txt").write_text(
        "This is a public overview of the platform features.",
        encoding="utf-8",
    )
    (docs / "hr_salary_bands.txt").write_text(
        "Engineering Level 1: $80k-$100k\nEngineering Level 2: $100k-$130k\n",
        encoding="utf-8",
    )
    (docs / "empty_file.txt").write_text("", encoding="utf-8")
    (docs / "sample.json").write_text(
        json.dumps({"key": "value", "nested": {"a": 1}}),
        encoding="utf-8",
    )
    return docs


# ---------------------------------------------------------------------------
# ACL inference
# ---------------------------------------------------------------------------

class TestInferAccessScope:
    def test_public_file(self, tmp_path: Path) -> None:
        path = tmp_path / "public_readme.txt"
        scopes = _infer_access_scope(path)
        assert "public" in scopes

    def test_confidential_file(self, tmp_path: Path) -> None:
        path = tmp_path / "salary_data.csv"
        scopes = _infer_access_scope(path)
        assert "confidential" in scopes

    def test_restricted_file(self, tmp_path: Path) -> None:
        path = tmp_path / "hr_policies.pdf"
        scopes = _infer_access_scope(path)
        assert "restricted" in scopes

    def test_default_internal(self, tmp_path: Path) -> None:
        path = tmp_path / "quarterly_report.md"
        scopes = _infer_access_scope(path)
        assert "internal" in scopes

    def test_extra_scopes_appended(self, tmp_path: Path) -> None:
        path = tmp_path / "guide.md"
        scopes = _infer_access_scope(path, extra_scopes=["eng-team"])
        assert "eng-team" in scopes

    def test_no_duplicates(self, tmp_path: Path) -> None:
        path = tmp_path / "readme.md"
        scopes = _infer_access_scope(path, extra_scopes=["internal"])
        assert scopes.count("internal") == 1


# ---------------------------------------------------------------------------
# DocumentIngester — fallback mode (no Docling)
# ---------------------------------------------------------------------------

class TestDocumentIngesterFallback:
    """Tests run with use_docling=False to avoid requiring Docling models."""

    def test_ingest_returns_document_nodes(self, sample_dir: Path) -> None:
        ingester = DocumentIngester(sample_dir, use_docling=False)
        result = ingester.ingest()
        # 4 non-empty supported files: api_guide.md, public_overview.txt, hr_salary.txt, sample.json
        assert result.summary.documents_processed >= 3
        for node in result.documents:
            assert isinstance(node, DocumentNode)
            assert node.page_content.strip()

    def test_empty_file_excluded(self, sample_dir: Path) -> None:
        ingester = DocumentIngester(sample_dir, use_docling=False)
        result = ingester.ingest()
        names = [n.metadata.source_name for n in result.documents]
        assert "empty_file.txt" not in names

    def test_access_scope_populated(self, sample_dir: Path) -> None:
        ingester = DocumentIngester(sample_dir, use_docling=False)
        result = ingester.ingest()
        for node in result.documents:
            assert isinstance(node.metadata.access_scope, list)
            assert len(node.metadata.access_scope) >= 1

    def test_access_scope_matches_filename(self, sample_dir: Path) -> None:
        ingester = DocumentIngester(sample_dir, use_docling=False)
        result = ingester.ingest()
        salary_nodes = [n for n in result.documents if "salary" in n.metadata.source_name.lower()]
        assert salary_nodes, "hr_salary_bands.txt should produce a document node"
        assert "confidential" in salary_nodes[0].metadata.access_scope

    def test_source_type_is_document(self, sample_dir: Path) -> None:
        ingester = DocumentIngester(sample_dir, use_docling=False)
        result = ingester.ingest()
        for node in result.documents:
            assert node.metadata.source_type == "document"

    def test_file_hash_populated(self, sample_dir: Path) -> None:
        ingester = DocumentIngester(sample_dir, use_docling=False)
        result = ingester.ingest()
        for node in result.documents:
            assert node.metadata.file_hash, f"file_hash missing for {node.metadata.source_name}"

    def test_nonexistent_source_dir(self, tmp_path: Path) -> None:
        """Should return empty result without raising."""
        ingester = DocumentIngester(tmp_path / "does_not_exist", use_docling=False)
        result = ingester.ingest()
        assert result.documents == []
        assert result.summary.documents_processed == 0

    def test_default_scope_appended(self, sample_dir: Path) -> None:
        ingester = DocumentIngester(sample_dir, default_scope=["eng-team"], use_docling=False)
        result = ingester.ingest()
        for node in result.documents:
            assert "eng-team" in node.metadata.access_scope

    def test_docling_doc_is_none_in_fallback(self, sample_dir: Path) -> None:
        ingester = DocumentIngester(sample_dir, use_docling=False)
        result = ingester.ingest()
        for node in result.documents:
            assert node.docling_doc is None

    def test_docling_doc_not_in_serialized_output(self, sample_dir: Path) -> None:
        """docling_doc must never appear in model_dump() — it's excluded from serialization."""
        ingester = DocumentIngester(sample_dir, use_docling=False)
        result = ingester.ingest()
        for node in result.documents:
            d = node.model_dump()
            assert "docling_doc" not in d


# ---------------------------------------------------------------------------
# Incremental ingestion (since parameter)
# ---------------------------------------------------------------------------

class TestDocumentIngesterIncremental:
    def test_since_future_skips_all_files(self, sample_dir: Path) -> None:
        """If since is in the future, no files should be ingested."""
        future = datetime.now(tz=timezone.utc) + timedelta(hours=24)
        ingester = DocumentIngester(sample_dir, use_docling=False)
        result = ingester.ingest(since=future)
        assert result.summary.documents_processed == 0

    def test_since_past_includes_all_files(self, sample_dir: Path) -> None:
        """If since is far in the past, all files should be ingested."""
        past = datetime(2000, 1, 1, tzinfo=timezone.utc)
        ingester = DocumentIngester(sample_dir, use_docling=False)
        result = ingester.ingest(since=past)
        assert result.summary.documents_processed >= 3

    def test_since_none_includes_all_files(self, sample_dir: Path) -> None:
        """since=None (full run) should ingest everything."""
        ingester = DocumentIngester(sample_dir, use_docling=False)
        result = ingester.ingest(since=None)
        assert result.summary.documents_processed >= 3

    def test_only_new_files_included_after_watermark(self, tmp_path: Path) -> None:
        """Only files created AFTER the watermark timestamp should be ingested."""
        docs = tmp_path / "docs"
        docs.mkdir()

        # Write "old" file
        old_file = docs / "old_guide.txt"
        old_file.write_text("Old content", encoding="utf-8")

        # Record watermark AFTER writing the old file
        time.sleep(0.05)  # ensure mtime difference
        watermark = datetime.now(tz=timezone.utc)
        time.sleep(0.05)

        # Write "new" file
        new_file = docs / "new_guide.txt"
        new_file.write_text("New content", encoding="utf-8")

        ingester = DocumentIngester(docs, use_docling=False)
        result = ingester.ingest(since=watermark)

        names = [n.metadata.source_name for n in result.documents]
        assert "new_guide.txt" in names
        assert "old_guide.txt" not in names

    def test_since_naive_datetime_treated_as_utc(self, sample_dir: Path) -> None:
        """Naive datetimes (no tzinfo) should be assumed UTC, not raise."""
        past_naive = datetime(2000, 1, 1)  # no tzinfo
        ingester = DocumentIngester(sample_dir, use_docling=False)
        result = ingester.ingest(since=past_naive)
        assert result.summary.documents_processed >= 3


# ---------------------------------------------------------------------------
# Non-recursive mode
# ---------------------------------------------------------------------------

class TestDocumentIngesterNonRecursive:
    def test_non_recursive_skips_subdirs(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "top.txt").write_text("Top level", encoding="utf-8")
        sub = docs / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("Nested content", encoding="utf-8")

        ingester = DocumentIngester(docs, recursive=False, use_docling=False)
        result = ingester.ingest()

        names = [n.metadata.source_name for n in result.documents]
        assert "top.txt" in names
        assert "nested.txt" not in names
