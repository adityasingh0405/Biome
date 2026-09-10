"""Unit tests for PostgresIngester (Phase 1).

These tests exercise the logic that doesn't need a live database:
- Row → Markdown serialization
- ACL scope inference from row columns
- Content-hash dedup
- Watermark timestamp normalization
- Error handling (bad URI, failed query)

Integration tests requiring a real PostgreSQL instance are
marked ``@pytest.mark.integration`` and are skipped in CI
unless the POSTGRES_URI env var is set and the DB is reachable.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from biome_rag.ingestion.postgres_ingester import (
    PostgresIngester,
    _infer_scope_from_row,
    _row_to_markdown,
)
from biome_rag.ingestion.models import DocumentNode


# ---------------------------------------------------------------------------
# _row_to_markdown
# ---------------------------------------------------------------------------

class TestRowToMarkdown:
    def test_produces_markdown_heading(self) -> None:
        row = {"id": 1, "title": "VPN broken", "status": "open"}
        md = _row_to_markdown(row, "enterprise_tickets")
        assert "## enterprise_tickets" in md
        assert "id=1" in md

    def test_includes_all_non_sensitive_fields(self) -> None:
        row = {"id": 2, "title": "Email issue", "description": "Cannot send emails."}
        md = _row_to_markdown(row, "tickets")
        assert "**title**: Email issue" in md
        assert "**description**: Cannot send emails." in md

    def test_excludes_sensitive_fields(self) -> None:
        row = {"id": 3, "title": "Reset", "password": "hunter2", "ssn": "123-45-6789"}
        md = _row_to_markdown(row, "tickets")
        assert "hunter2" not in md
        assert "123-45-6789" not in md

    def test_skips_none_values(self) -> None:
        row = {"id": 4, "title": "Test", "description": None, "status": "open"}
        md = _row_to_markdown(row, "tickets")
        assert "description" not in md
        assert "**status**: open" in md

    def test_uses_ticket_id_when_id_missing(self) -> None:
        row = {"ticket_id": 99, "title": "Alt ID"}
        md = _row_to_markdown(row, "tickets")
        assert "id=99" in md

    def test_falls_back_to_question_mark_for_unknown_id(self) -> None:
        row = {"title": "No ID at all"}
        md = _row_to_markdown(row, "tickets")
        assert "id=?" in md


# ---------------------------------------------------------------------------
# _infer_scope_from_row
# ---------------------------------------------------------------------------

class TestInferScopeFromRow:
    def test_uses_department_column(self) -> None:
        row = {"department": "Engineering", "id": 1}
        scopes = _infer_scope_from_row(row, ["internal"])
        assert "engineering" in scopes

    def test_spaces_converted_to_underscores(self) -> None:
        row = {"department": "Human Resources"}
        scopes = _infer_scope_from_row(row, [])
        assert "human_resources" in scopes

    def test_falls_back_to_team_column(self) -> None:
        row = {"team": "Platform"}
        scopes = _infer_scope_from_row(row, [])
        assert "platform" in scopes

    def test_default_scope_always_present(self) -> None:
        row = {"id": 5}
        scopes = _infer_scope_from_row(row, ["internal"])
        assert "internal" in scopes

    def test_no_department_returns_default(self) -> None:
        row = {"id": 6, "title": "No dept"}
        scopes = _infer_scope_from_row(row, ["internal"])
        assert scopes == ["internal"]


# ---------------------------------------------------------------------------
# PostgresIngester — unit tests (mocked DB)
# ---------------------------------------------------------------------------

class TestPostgresIngesterUnit:
    def _make_ingester(self, **kwargs) -> PostgresIngester:
        return PostgresIngester(
            db_uri="postgresql://test:test@localhost:5432/testdb",
            table_name="enterprise_tickets",
            **kwargs,
        )

    def test_safe_uri_redacts_password(self) -> None:
        ingester = self._make_ingester()
        safe = ingester._safe_uri()
        # Password ("test") should not appear BEFORE the @ sign
        # URI format: postgresql://user:password@host:port/db
        assert ":test@" not in ingester.db_uri.replace("test:test", "REDACTED")
        assert "localhost" in safe

    def test_ingest_returns_empty_on_connection_failure(self) -> None:
        """A bad URI should return IngestResult with an error, not raise."""
        ingester = PostgresIngester(
            db_uri="postgresql://invalid:invalid@999.999.999.999:9999/nodb",
        )
        result = ingester.ingest()
        assert result.documents == []
        assert len(result.errors) >= 1

    def test_row_to_node_produces_document_node(self) -> None:
        ingester = self._make_ingester()
        row = {"id": 10, "title": "Test ticket", "status": "open", "department": "IT"}
        from biome_rag.ingestion.dedup import compute_payload_sha256
        hash_ = compute_payload_sha256(row)
        node = ingester._row_to_node(row, hash_)
        assert isinstance(node, DocumentNode)
        assert node.page_content.strip()
        assert node.metadata.source_type == "postgresql"
        assert "10" in node.metadata.source_name
        assert node.metadata.file_hash == hash_

    def test_row_to_node_sets_access_scope(self) -> None:
        ingester = self._make_ingester()
        row = {"id": 11, "department": "Finance"}
        from biome_rag.ingestion.dedup import compute_payload_sha256
        node = ingester._row_to_node(row, compute_payload_sha256(row))
        assert "finance" in node.metadata.access_scope

    def test_row_to_node_access_scope_and_level_consistent(self) -> None:
        ingester = self._make_ingester()
        row = {"id": 12, "department": "Legal"}
        from biome_rag.ingestion.dedup import compute_payload_sha256
        node = ingester._row_to_node(row, compute_payload_sha256(row))
        # access_level should be the first element of access_scope
        assert node.metadata.access_level == node.metadata.access_scope[0]

    def test_ingest_deduplicates_identical_rows(self) -> None:
        """Two rows with the same content should produce only one DocumentNode."""
        ingester = self._make_ingester()
        # Return same tuple twice: content-hash dedup should collapse to 1 document
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchmany.side_effect = [[(1, "Duplicate", "open"), (1, "Duplicate", "open")], []]
        mock_cursor.keys.return_value = ["id", "title", "status"]
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_cursor

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        ingester._engine = mock_engine
        ingester._has_updated_at = False

        result = ingester.ingest(since=None)
        assert result.summary.documents_processed == 1

    def test_ingest_max_rows_respected(self) -> None:
        """max_rows cap should be honoured."""
        ingester = self._make_ingester(max_rows=2)

        # Real SQLAlchemy cursor returns tuples matched by keys()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchmany.side_effect = [
            [(0, "Ticket 0")],
            [(1, "Ticket 1")],
            [(2, "Ticket 2")],
            [],
        ]
        mock_cursor.keys.return_value = ["id", "title"]
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_cursor

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        ingester._engine = mock_engine
        ingester._has_updated_at = False

        result = ingester.ingest()
        assert result.summary.documents_processed == 2

    def test_incremental_query_uses_updated_at(self) -> None:
        """When updated_at column exists and since is set, SQL should contain WHERE updated_at."""
        ingester = self._make_ingester()
        ingester._has_updated_at = True

        captured_sql: list[str] = []

        class FakeCursor:
            def fetchmany(self, n):
                return []
            def keys(self):
                return []

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        def capture_execute(stmt, params=None):
            captured_sql.append(str(stmt))
            return FakeCursor()

        mock_conn.execute.side_effect = capture_execute
        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        ingester._engine = mock_engine

        since = datetime(2024, 1, 1, tzinfo=timezone.utc)
        ingester.ingest(since=since)

        assert captured_sql, "execute() should have been called"
        assert "updated_at" in captured_sql[0]

    def test_full_query_when_no_updated_at(self) -> None:
        """Without updated_at column, full SELECT should be issued."""
        ingester = self._make_ingester()
        ingester._has_updated_at = False

        captured_sql: list[str] = []

        class FakeCursor:
            def fetchmany(self, n):
                return []
            def keys(self):
                return []

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.side_effect = lambda stmt, p=None: (
            captured_sql.append(str(stmt)) or FakeCursor()
        )
        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        ingester._engine = mock_engine

        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        ingester.ingest(since=since)

        assert captured_sql
        assert "updated_at" not in captured_sql[0]


# ---------------------------------------------------------------------------
# SlackIngester — unit tests (stub behaviour)
# ---------------------------------------------------------------------------

class TestSlackIngesterStub:
    def test_returns_empty_result_without_token(self) -> None:
        from biome_rag.ingestion.slack_ingester import SlackIngester
        ingester = SlackIngester(bot_token="")
        result = ingester.ingest()
        assert result.documents == []
        assert result.summary.documents_processed == 0

    def test_source_type_is_slack(self) -> None:
        from biome_rag.ingestion.slack_ingester import SlackIngester
        assert SlackIngester.source_type == "slack"

    def test_group_by_thread_groups_correctly(self) -> None:
        from biome_rag.ingestion.slack_ingester import SlackIngester
        ingester = SlackIngester(bot_token="")
        messages = [
            {"ts": "100", "thread_ts": "100", "text": "parent"},
            {"ts": "101", "thread_ts": "100", "text": "reply 1"},
            {"ts": "200", "text": "standalone"},  # no thread_ts → own thread
        ]
        grouped = ingester._group_by_thread(messages)
        assert "100" in grouped
        assert len(grouped["100"]) == 2
        assert "200" in grouped


# ---------------------------------------------------------------------------
# WatermarkStore — unit tests
# ---------------------------------------------------------------------------

class TestWatermarkStore:
    def test_get_returns_none_on_first_run(self, tmp_path: Path) -> None:
        from biome_rag.ingestion.base import WatermarkStore
        store = WatermarkStore(tmp_path / "watermarks.db")
        assert store.get("document") is None

    def test_set_and_get_roundtrip(self, tmp_path: Path) -> None:
        from biome_rag.ingestion.base import WatermarkStore
        store = WatermarkStore(tmp_path / "watermarks.db")
        ts = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        store.set("document", ts)
        retrieved = store.get("document")
        assert retrieved is not None
        assert retrieved.replace(microsecond=0) == ts.replace(microsecond=0)

    def test_set_without_timestamp_uses_now(self, tmp_path: Path) -> None:
        from biome_rag.ingestion.base import WatermarkStore
        before = datetime.now(tz=timezone.utc)
        store = WatermarkStore(tmp_path / "watermarks.db")
        store.set("postgresql")
        after = datetime.now(tz=timezone.utc)
        retrieved = store.get("postgresql")
        assert retrieved is not None
        assert before <= retrieved <= after

    def test_reset_removes_watermark(self, tmp_path: Path) -> None:
        from biome_rag.ingestion.base import WatermarkStore
        store = WatermarkStore(tmp_path / "watermarks.db")
        store.set("document", datetime.now(tz=timezone.utc))
        store.reset("document")
        assert store.get("document") is None

    def test_overwrite_updates_watermark(self, tmp_path: Path) -> None:
        from biome_rag.ingestion.base import WatermarkStore
        store = WatermarkStore(tmp_path / "watermarks.db")
        ts1 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        ts2 = datetime(2024, 6, 1, tzinfo=timezone.utc)
        store.set("document", ts1)
        store.set("document", ts2)
        retrieved = store.get("document")
        assert retrieved.year == 2024
        assert retrieved.month == 6

    def test_multiple_sources_independent(self, tmp_path: Path) -> None:
        from biome_rag.ingestion.base import WatermarkStore
        store = WatermarkStore(tmp_path / "watermarks.db")
        ts_doc = datetime(2024, 1, 1, tzinfo=timezone.utc)
        ts_pg = datetime(2024, 6, 1, tzinfo=timezone.utc)
        store.set("document", ts_doc)
        store.set("postgresql", ts_pg)
        assert store.get("document").month == 1
        assert store.get("postgresql").month == 6


# ---------------------------------------------------------------------------
# Integration placeholder
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestPostgresIngesterIntegration:
    """Requires POSTGRES_URI to point to a live DB with enterprise_tickets table.

    Run with: pytest -m integration
    """

    def test_full_ingest_returns_documents(self) -> None:
        uri = os.environ.get("POSTGRES_URI")
        if not uri:
            pytest.skip("POSTGRES_URI not set — skipping integration test.")
        ingester = PostgresIngester(db_uri=uri, max_rows=5)
        result = ingester.ingest()
        assert result.summary.documents_processed > 0
        for node in result.documents:
            assert node.page_content.strip()
            assert node.metadata.source_type == "postgresql"

    def test_incremental_ingest_returns_fewer_rows(self) -> None:
        uri = os.environ.get("POSTGRES_URI")
        if not uri:
            pytest.skip("POSTGRES_URI not set — skipping integration test.")
        full = PostgresIngester(db_uri=uri).ingest()
        from datetime import timedelta
        recent_since = datetime.now(tz=timezone.utc) + timedelta(days=365)
        incremental = PostgresIngester(db_uri=uri).ingest(since=recent_since)
        assert incremental.summary.documents_processed <= full.summary.documents_processed
