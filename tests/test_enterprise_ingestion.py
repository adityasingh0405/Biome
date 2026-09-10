from __future__ import annotations

import json
from pathlib import Path
import pytest

from biome_rag.ingestion.dedup import (
    SQLiteStateTracker,
    compute_file_sha256,
    compute_payload_sha256,
)
from biome_rag.ingestion.loaders import (
    DocxLoader,
    PdfLoader,
    PlainTextLoader,
    PostgreSQLLoader,
    PptxLoader,
    UnstructuredBucketLoader,
)
from biome_rag.ingestion.models import (
    DocumentMetadata,
    DocumentNode,
    IngestionConfig,
)
from biome_rag.ingestion.pipeline import IngestionPipeline


def test_document_node_validation_and_serialization(tmp_path: Path):
    meta = DocumentMetadata(
        source_type="unstructured",
        source_name="annual_report.pdf",
        primary_key=None,
        file_hash="abcdef1234567890",
        access_level="confidential",
        file_path=str(tmp_path / "annual_report.pdf"),
        file_extension=".pdf",
    )
    node = DocumentNode(page_content="Executive summary text.", metadata=meta)

    # Duck-typing properties
    assert node.text == "Executive summary text."
    assert "annual_report.pdf" in node.source

    # Serialization round-trip
    d = node.to_dict()
    assert d["metadata"]["source_type"] == "unstructured"
    assert d["metadata"]["access_level"] == "confidential"

    restored = DocumentNode.from_dict(d)
    assert restored.page_content == node.page_content
    assert restored.metadata.file_hash == "abcdef1234567890"


def test_sha256_hash_functions(tmp_path: Path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("Unique Enterprise Content 123", encoding="utf-8")

    h1 = compute_file_sha256(file_path)
    h2 = compute_file_sha256(file_path)
    assert len(h1) == 64
    assert h1 == h2

    # Different content produces different hash
    file_path.write_text("Modified Content", encoding="utf-8")
    h3 = compute_file_sha256(file_path)
    assert h1 != h3

    # Deterministic payload hashing (dict key ordering independence)
    payload_a = {"b": 2, "a": 1, "nested": {"y": 20, "x": 10}}
    payload_b = {"a": 1, "b": 2, "nested": {"x": 10, "y": 20}}
    assert compute_payload_sha256(payload_a) == compute_payload_sha256(payload_b)


def test_sqlite_state_tracker(tmp_path: Path):
    db_path = tmp_path / "test_state.db"
    tracker = SQLiteStateTracker(db_path)

    hash1 = "hash_alpha_123"
    hash2 = "hash_beta_456"

    assert tracker.is_indexed(hash1) is False
    assert tracker.count() == 0

    tracker.mark_indexed(
        content_hash=hash1,
        source_type="unstructured",
        source_name="doc1.txt",
        metadata={"user": "admin"},
    )
    assert tracker.is_indexed(hash1) is True
    assert tracker.is_indexed(hash2) is False
    assert tracker.count() == 1

    # Batch check
    found = tracker.batch_check_indexed([hash1, hash2, "hash_gamma_789"])
    assert found == {hash1}

    # Batch mark
    tracker.batch_mark_indexed([
        {"content_hash": hash2, "source_type": "postgresql", "source_name": "tickets", "primary_key": "TK-1"}
    ])
    assert tracker.count() == 2
    assert tracker.is_indexed(hash2) is True

    # Reset state
    tracker.reset_state()
    assert tracker.count() == 0
    assert tracker.is_indexed(hash1) is False


def test_unstructured_bucket_loader(tmp_path: Path):
    bucket_dir = tmp_path / "bucket"
    bucket_dir.mkdir()

    (bucket_dir / "policy.txt").write_text("Work from home rules.", encoding="utf-8")
    (bucket_dir / "confidential_memo.txt").write_text("Private audit report.", encoding="utf-8")

    loader = UnstructuredBucketLoader(bucket_dir)
    nodes = loader.load()

    assert len(nodes) == 2
    by_name = {n.metadata.source_name: n for n in nodes}

    assert "Work from home rules." in by_name["policy.txt"].page_content
    assert by_name["confidential_memo.txt"].metadata.access_level == "confidential"
    assert by_name["policy.txt"].metadata.file_hash is not None


def test_postgres_row_semantic_serialization():
    loader = PostgreSQLLoader()
    sample_row = {
        "ticket_id": "9999-uuid",
        "department": "Engineering",
        "route_or_system": "SYS-001",
        "priority_level": "Critical",
        "resolved": False,
        "created_at": "2026-09-04 10:00:00",
        "issue_summary": "Database latency spike on primary replica",
        "detailed_description": "Connection pool exhausted during night batch run.",
    }

    node = loader._serialize_row_to_node("enterprise_tickets", sample_row)

    assert "Support Ticket [ID: 9999-uuid]" in node.page_content
    assert "Department: Engineering" in node.page_content
    assert "Database latency spike on primary replica" in node.page_content
    assert node.metadata.source_type == "postgresql"
    assert node.metadata.source_name == "enterprise_tickets"
    assert node.metadata.primary_key == "9999-uuid"
    assert node.metadata.access_level == "restricted"  # Engineering maps to restricted


def test_pipeline_deduplication_orchestration(tmp_path: Path):
    bucket = tmp_path / "bucket"
    bucket.mkdir()
    silver = tmp_path / "silver"
    state_db = tmp_path / "state.db"

    (bucket / "doc1.txt").write_text("First document content", encoding="utf-8")

    config = IngestionConfig(
        bucket_dir=bucket,
        silver_dir=silver,
        state_db_path=state_db,
    )
    pipeline = IngestionPipeline(config)

    # First run: should persist 1 document
    nodes, summary1 = pipeline.run_pipeline(source="files")
    assert summary1.documents_processed == 1
    assert summary1.duplicates_skipped == 0
    assert (silver / "documents.jsonl").exists()

    # Second run without changes: should detect duplicate and skip
    nodes2, summary2 = pipeline.run_pipeline(source="files")
    assert summary2.documents_processed == 0
    assert summary2.duplicates_skipped == 1
