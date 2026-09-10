"""Unit tests for Phase 4: IndexBuilder and IndexingResult.

All tests run without external services (no Qdrant, no Docling models).
Tests exercise:
- IndexingResult dataclass fields and backward-compat properties
- PhaseStats dataclass
- IndexBuilder._count_by utility
- IndexBuilder._persist_chunks_json writes valid chunks.json
- IndexBuilder._phase3_bm25 builds a loadable BM25 index
- IndexBuilder.run() end-to-end on temp files (fallback paths only)
- IndexBuilder.run() with no files returns empty result
- IndexBuilder.run() with Qdrant disabled
- app.py: /v1/index/* routes return correct schema
- app.py: res.sub bug is fixed (re.sub now used)
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from biome_rag.indexing import IndexBuilder, IndexingResult, PhaseStats
from biome_rag.ingestion.models import Chunk
from biome_rag.retrieval.bm25 import BM25Index


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_chunk(text: str = "test chunk", source: str = "doc.pdf", idx: int = 0) -> Chunk:
    return Chunk(
        text=text,
        source=source,
        section_heading="Intro",
        page_number=1,
        chunk_index=idx,
        chunking_strategy="chonkie_sentence",
        character_count=len(text),
        token_count=len(text.split()),
        source_type="document",
    )


@pytest.fixture()
def tmp_dirs(tmp_path: Path):
    raw = tmp_path / "raw"
    proc = tmp_path / "processed"
    stor = tmp_path / "storage"
    raw.mkdir(); proc.mkdir(); stor.mkdir()
    return raw, proc, stor


@pytest.fixture()
def doc_files(tmp_dirs):
    raw, proc, stor = tmp_dirs
    (raw / "guide.md").write_text(
        "# API Guide\n\nThis guide covers authentication and endpoints.\n" * 10,
        encoding="utf-8",
    )
    (raw / "policy.txt").write_text(
        "## HR Policy\n\nAll employees must follow the code of conduct.\n" * 8,
        encoding="utf-8",
    )
    return raw, proc, stor


# ---------------------------------------------------------------------------
# IndexingResult
# ---------------------------------------------------------------------------

class TestIndexingResult:
    def test_default_fields(self) -> None:
        r = IndexingResult()
        assert r.documents_ingested == 0
        assert r.total_chunks == 0
        assert r.errors == []
        assert r.success is True

    def test_success_false_when_errors(self) -> None:
        r = IndexingResult(errors=["phase1: something went wrong"])
        assert r.success is False

    def test_backward_compat_chunks_created(self) -> None:
        r = IndexingResult(total_chunks=42)
        assert r.chunks_created == 42

    def test_backward_compat_duplicates_skipped(self) -> None:
        r = IndexingResult(documents_skipped=7)
        assert r.duplicates_skipped == 7

    def test_to_dict_has_all_required_keys(self) -> None:
        r = IndexingResult(total_chunks=10, documents_ingested=3)
        d = r.to_dict()
        for key in [
            "documents_ingested", "total_chunks", "chunks_per_strategy",
            "bm25_docs_indexed", "qdrant_points_upserted", "errors",
            "total_elapsed_seconds", "success",
        ]:
            assert key in d, f"Missing key: {key}"

    def test_to_dict_success_true(self) -> None:
        r = IndexingResult()
        assert r.to_dict()["success"] is True

    def test_to_dict_success_false(self) -> None:
        r = IndexingResult(errors=["oops"])
        assert r.to_dict()["success"] is False


# ---------------------------------------------------------------------------
# PhaseStats
# ---------------------------------------------------------------------------

class TestPhaseStats:
    def test_defaults(self) -> None:
        s = PhaseStats()
        assert s.elapsed_seconds == 0.0
        assert s.items_processed == 0
        assert s.errors == 0

    def test_settable(self) -> None:
        s = PhaseStats(elapsed_seconds=1.23, items_processed=10, errors=2)
        assert s.elapsed_seconds == 1.23
        assert s.items_processed == 10
        assert s.errors == 2


# ---------------------------------------------------------------------------
# IndexBuilder utilities
# ---------------------------------------------------------------------------

class TestIndexBuilderUtils:
    def test_count_by(self, tmp_dirs) -> None:
        raw, proc, stor = tmp_dirs
        builder = IndexBuilder(raw, proc, stor, use_qdrant=False)
        chunks = [
            _make_chunk("a"), _make_chunk("b"),
            _make_chunk("c"),
        ]
        chunks[0].chunking_strategy = "docling_hybrid_fallback"
        chunks[1].chunking_strategy = "chonkie_sentence"
        chunks[2].chunking_strategy = "chonkie_sentence"
        counts = builder._count_by(chunks, lambda c: c.chunking_strategy)
        assert counts["chonkie_sentence"] == 2
        assert counts["docling_hybrid_fallback"] == 1

    def test_chunk_to_dict_has_token_count(self, tmp_dirs) -> None:
        raw, proc, stor = tmp_dirs
        builder = IndexBuilder(raw, proc, stor, use_qdrant=False)
        chunk = _make_chunk("hello world", idx=5)
        d = builder._chunk_to_dict(chunk)
        assert d["token_count"] == chunk.token_count
        assert d["source_type"] == "document"
        assert d["chunk_index"] == 5

    def test_discover_paths_empty_dir(self, tmp_dirs) -> None:
        raw, proc, stor = tmp_dirs
        builder = IndexBuilder(raw, proc, stor, use_qdrant=False)
        assert builder._discover_paths() == []

    def test_discover_paths_finds_files(self, doc_files) -> None:
        raw, proc, stor = doc_files
        builder = IndexBuilder(raw, proc, stor, use_qdrant=False)
        paths = builder._discover_paths()
        assert len(paths) == 2
        assert any("guide.md" in str(p) for p in paths)


# ---------------------------------------------------------------------------
# _persist_chunks_json
# ---------------------------------------------------------------------------

class TestPersistChunksJson:
    def test_writes_valid_json(self, tmp_dirs) -> None:
        raw, proc, stor = tmp_dirs
        builder = IndexBuilder(raw, proc, stor, use_qdrant=False)
        chunks = [_make_chunk(f"chunk {i}", idx=i) for i in range(3)]
        builder._persist_chunks_json(chunks)
        out = proc / "chunks.json"
        assert out.exists()
        payload = json.loads(out.read_text())
        assert "chunks" in payload
        assert len(payload["chunks"]) == 3

    def test_chunk_json_has_token_count(self, tmp_dirs) -> None:
        raw, proc, stor = tmp_dirs
        builder = IndexBuilder(raw, proc, stor, use_qdrant=False)
        chunk = _make_chunk("hello world enterprise")
        builder._persist_chunks_json([chunk])
        payload = json.loads((proc / "chunks.json").read_text())
        assert payload["chunks"][0]["token_count"] > 0

    def test_chunk_json_has_source_type(self, tmp_dirs) -> None:
        raw, proc, stor = tmp_dirs
        builder = IndexBuilder(raw, proc, stor, use_qdrant=False)
        builder._persist_chunks_json([_make_chunk()])
        payload = json.loads((proc / "chunks.json").read_text())
        assert payload["chunks"][0]["source_type"] == "document"


# ---------------------------------------------------------------------------
# _phase3_bm25
# ---------------------------------------------------------------------------

class TestPhase3BM25:
    def test_bm25_index_persisted(self, tmp_dirs) -> None:
        raw, proc, stor = tmp_dirs
        builder = IndexBuilder(raw, proc, stor, use_qdrant=False)
        chunks = [_make_chunk(f"VPN issue report {i}") for i in range(5)]
        n = builder._phase3_bm25(chunks)
        assert n == 5
        bm25_path = stor / "bm25_index.pkl"
        assert bm25_path.exists()

    def test_bm25_index_searchable(self, tmp_dirs) -> None:
        raw, proc, stor = tmp_dirs
        builder = IndexBuilder(raw, proc, stor, use_qdrant=False)
        chunks = [
            _make_chunk("VPN connectivity problem"),
            _make_chunk("Email delivery failure"),
        ]
        builder._phase3_bm25(chunks)
        bm25 = BM25Index(stor / "bm25_index.pkl")
        results = bm25.search("VPN")
        assert len(results) > 0
        assert results[0][0] == 0  # first chunk should rank highest


# ---------------------------------------------------------------------------
# IndexBuilder.run() — end-to-end (fallback paths, no Docker)
# ---------------------------------------------------------------------------

class TestIndexBuilderRun:
    def test_run_empty_dir_returns_empty_result(self, tmp_dirs) -> None:
        raw, proc, stor = tmp_dirs
        builder = IndexBuilder(raw, proc, stor, use_qdrant=False)
        result = builder.run()
        assert result.total_chunks == 0
        assert result.errors == []

    def test_run_with_files_produces_chunks(self, doc_files) -> None:
        raw, proc, stor = doc_files
        builder = IndexBuilder(raw, proc, stor, use_qdrant=False, bm25_enabled=True)
        result = builder.run()
        assert result.total_chunks > 0

    def test_run_writes_chunks_json(self, doc_files) -> None:
        raw, proc, stor = doc_files
        builder = IndexBuilder(raw, proc, stor, use_qdrant=False)
        builder.run()
        assert (proc / "chunks.json").exists()

    def test_run_builds_bm25(self, doc_files) -> None:
        raw, proc, stor = doc_files
        builder = IndexBuilder(raw, proc, stor, use_qdrant=False, bm25_enabled=True)
        result = builder.run()
        assert result.bm25_docs_indexed > 0
        assert (stor / "bm25_index.pkl").exists()

    def test_run_phase_stats_populated(self, doc_files) -> None:
        raw, proc, stor = doc_files
        builder = IndexBuilder(raw, proc, stor, use_qdrant=False)
        result = builder.run()
        assert "phase1_ingest" in result.phase_stats
        assert "phase2_chunk" in result.phase_stats

    def test_run_qdrant_skipped_when_disabled(self, doc_files) -> None:
        raw, proc, stor = doc_files
        builder = IndexBuilder(raw, proc, stor, use_qdrant=False)
        result = builder.run()
        # Qdrant disabled → 0 points, no qdrant error
        assert result.qdrant_points_upserted == 0
        assert all("qdrant" not in e for e in result.errors)

    def test_run_qdrant_graceful_fallback(self, doc_files) -> None:
        """Qdrant enabled but not reachable → non-fatal error, pipeline continues."""
        raw, proc, stor = doc_files
        builder = IndexBuilder(raw, proc, stor, use_qdrant=True)
        result = builder.run()
        # Chunks still produced even if Qdrant upsert fails
        assert result.total_chunks > 0

    def test_run_result_to_dict_serializable(self, doc_files) -> None:
        raw, proc, stor = doc_files
        builder = IndexBuilder(raw, proc, stor, use_qdrant=False)
        result = builder.run()
        d = result.to_dict()
        # Must be JSON-serializable
        assert json.dumps(d)  # no TypeError

    def test_run_with_explicit_paths(self, doc_files) -> None:
        raw, proc, stor = doc_files
        builder = IndexBuilder(raw, proc, stor, use_qdrant=False)
        paths = [raw / "guide.md"]
        result = builder.run(paths=paths, source_type="document")
        assert result.total_chunks > 0


# ---------------------------------------------------------------------------
# FastAPI /v1/index/* routes
# ---------------------------------------------------------------------------

@pytest.fixture()
def test_client(tmp_path):
    """Create a TestClient with isolated directories."""
    from biome_rag.api.app import create_app
    application = create_app(
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
        storage_dir=tmp_path / "storage",
    )
    return TestClient(application, raise_server_exceptions=False)


class TestIndexRoutes:
    def test_index_text_returns_200(self, test_client) -> None:
        resp = test_client.post(
            "/v1/index/text",
            json={"title": "Test Document", "content": "This is a test document about VPN issues."}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "total_chunks" in body
        assert "document" in body

    def test_index_text_document_field(self, test_client) -> None:
        resp = test_client.post(
            "/v1/index/text",
            json={"title": "My Report!", "content": "Report content here."}
        )
        assert resp.status_code == 200
        # Title special chars should be sanitized
        assert "My_Report_" in resp.json()["document"]

    def test_index_files_missing_dir_returns_400(self, test_client) -> None:
        resp = test_client.post(
            "/v1/index/files",
            json={"directory_path": "/nonexistent/path/xyz", "recursive": True}
        )
        assert resp.status_code == 400

    def test_ingest_text_legacy_route_still_works(self, test_client) -> None:
        """The old /v1/ingest/text route must still respond (backward compat)."""
        resp = test_client.post(
            "/v1/ingest/text",
            json={"title": "Legacy Doc", "content": "Legacy content."}
        )
        # Should return 200 (may have 0 chunks if pipeline hits dedup)
        assert resp.status_code == 200

    def test_root_lists_index_endpoints(self, test_client) -> None:
        resp = test_client.get("/")
        assert resp.status_code == 200
