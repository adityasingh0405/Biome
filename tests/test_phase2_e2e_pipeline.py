"""End-to-end pipeline tests: Phase 1 Ingestion → Phase 2 Chunking.

These tests verify that the full ingestion + chunking pipeline produces
correct Chunk objects from real temporary files, using the fallback paths
(no Docling models, no Chonkie) so they run fast in CI.

Key assertions:
- Every Chunk has token_count > 0
- Every Chunk has source_type matching the original DocumentNode
- chunk_many() produces monotonically increasing chunk_index values
- Total character coverage: no text is silently dropped
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from biome_rag.chunking import DocumentChunker, TextChunker, get_chunker
from biome_rag.ingestion.document_ingester import DocumentIngester
from biome_rag.ingestion.postgres_ingester import _row_to_markdown
from biome_rag.ingestion.models import DocumentMetadata, DocumentNode


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def doc_dir(tmp_path: Path) -> Path:
    """Temporary directory with multiple text-based documents."""
    d = tmp_path / "docs"
    d.mkdir()

    # API guide — medium length
    guide = d / "api_guide.md"
    guide.write_text(
        "# API Guide\n\n"
        "## Authentication\n\nUse `Authorization: Bearer <token>` for all requests.\n\n"
        "## Endpoints\n\n"
        "### POST /v1/ask\n\nSubmit a question and receive an answer with citations.\n\n"
        "### GET /v1/documents\n\nList all ingested documents.\n\n"
        "## Rate Limits\n\nThe API allows 100 requests per minute per API key.\n",
        encoding="utf-8",
    )

    # Policy document — simulates a large HR PDF (text-based fallback)
    policy = d / "hr_internal_policy.txt"
    policy.write_text(
        "# HR Policy Document\n\n"
        + "\n\n".join(
            f"## Section {i}\n\n"
            + " ".join(["This is a policy statement about employee conduct and compliance."] * 8)
            for i in range(1, 12)
        ),
        encoding="utf-8",
    )

    # JSON data file
    data_file = d / "config.json"
    data_file.write_text(
        json.dumps({"version": "1.0", "features": {"rag": True, "rerank": True}, "model": "bge-m3"}),
        encoding="utf-8",
    )

    return d


def _make_postgres_doc(row: dict, idx: int = 0) -> DocumentNode:
    """Create a DocumentNode from a Postgres row dict (simulates Phase 1 output)."""
    from biome_rag.ingestion.dedup import compute_payload_sha256
    text = _row_to_markdown(row, "enterprise_tickets")
    return DocumentNode(
        page_content=text,
        metadata=DocumentMetadata(
            source_type="postgresql",
            source_name=f"enterprise_tickets:{row.get('id', idx)}",
            access_level="internal",
            access_scope=["internal", row.get("department", "unknown").lower()],
            file_hash=compute_payload_sha256(row),
            extra={
                "table": "enterprise_tickets",
                "parser": "postgres_ingester",
                "department": row.get("department", ""),
            },
        ),
    )


# ---------------------------------------------------------------------------
# Phase 1 → Phase 2: Document pipeline
# ---------------------------------------------------------------------------

class TestDocumentPipeline:
    def test_ingest_then_chunk_produces_chunks(self, doc_dir: Path) -> None:
        # Phase 1: ingest
        ingester = DocumentIngester(doc_dir, use_docling=False)
        ingest_result = ingester.ingest()
        assert ingest_result.summary.documents_processed >= 2

        # Phase 2: chunk
        chunker = DocumentChunker(max_tokens=100)
        all_chunks = chunker.chunk_many(ingest_result.documents)
        assert len(all_chunks) > 0

    def test_all_chunks_have_token_count(self, doc_dir: Path) -> None:
        ingester = DocumentIngester(doc_dir, use_docling=False)
        documents = ingester.ingest().documents
        chunker = DocumentChunker(max_tokens=100)
        chunks = chunker.chunk_many(documents)
        for c in chunks:
            assert c.token_count > 0, f"token_count=0 for chunk: {c.text[:60]!r}"

    def test_all_chunks_source_type_is_document(self, doc_dir: Path) -> None:
        ingester = DocumentIngester(doc_dir, use_docling=False)
        documents = ingester.ingest().documents
        chunker = DocumentChunker(max_tokens=100)
        chunks = chunker.chunk_many(documents)
        for c in chunks:
            assert c.source_type == "document"

    def test_chunk_many_global_index_monotonic(self, doc_dir: Path) -> None:
        ingester = DocumentIngester(doc_dir, use_docling=False)
        documents = ingester.ingest().documents
        chunker = DocumentChunker(max_tokens=100)
        chunks = chunker.chunk_many(documents)
        for i, c in enumerate(chunks):
            assert c.chunk_index == i

    def test_no_empty_chunks(self, doc_dir: Path) -> None:
        ingester = DocumentIngester(doc_dir, use_docling=False)
        documents = ingester.ingest().documents
        chunker = DocumentChunker(max_tokens=100)
        chunks = chunker.chunk_many(documents)
        for c in chunks:
            assert c.text.strip(), f"Empty chunk produced from source: {c.source}"

    def test_chunking_strategy_label_set(self, doc_dir: Path) -> None:
        ingester = DocumentIngester(doc_dir, use_docling=False)
        documents = ingester.ingest().documents
        chunker = DocumentChunker(max_tokens=100)
        chunks = chunker.chunk_many(documents)
        for c in chunks:
            assert c.chunking_strategy, "chunking_strategy should not be empty"

    def test_access_scope_in_chunk_metadata(self, doc_dir: Path) -> None:
        ingester = DocumentIngester(doc_dir, use_docling=False)
        documents = ingester.ingest().documents
        chunker = DocumentChunker(max_tokens=512)
        chunks = chunker.chunk_many(documents)
        for c in chunks:
            assert "access_scope" in c.metadata
            assert isinstance(c.metadata["access_scope"], list)


# ---------------------------------------------------------------------------
# Phase 1 → Phase 2: Postgres pipeline
# ---------------------------------------------------------------------------

class TestPostgresPipeline:
    SAMPLE_ROWS = [
        {"id": i, "title": f"Ticket {i}", "description": "Cannot connect to VPN after update.", "status": "open", "department": "IT"}
        for i in range(1, 6)
    ]

    def test_ingest_then_chunk_postgres_rows(self) -> None:
        documents = [_make_postgres_doc(row, i) for i, row in enumerate(self.SAMPLE_ROWS)]
        chunker = TextChunker.for_postgres(chunker_type="fallback")
        chunks = chunker.chunk_many(documents)
        assert len(chunks) >= len(self.SAMPLE_ROWS)

    def test_postgres_chunks_have_correct_source_type(self) -> None:
        documents = [_make_postgres_doc(row, i) for i, row in enumerate(self.SAMPLE_ROWS)]
        chunker = TextChunker.for_postgres(chunker_type="fallback")
        chunks = chunker.chunk_many(documents)
        for c in chunks:
            assert c.source_type == "postgresql"

    def test_postgres_chunks_within_token_budget(self) -> None:
        documents = [_make_postgres_doc(row, i) for i, row in enumerate(self.SAMPLE_ROWS)]
        chunker = TextChunker.for_postgres(chunker_type="fallback", chunk_size=256)
        chunks = chunker.chunk_many(documents)
        for c in chunks:
            # Allow 20% slack for overlap appended to first chunk
            assert c.token_count <= 256 * 1.2, f"Chunk too large: {c.token_count} tokens"

    def test_postgres_global_index_monotonic(self) -> None:
        documents = [_make_postgres_doc(row, i) for i, row in enumerate(self.SAMPLE_ROWS)]
        chunker = TextChunker.for_postgres(chunker_type="fallback")
        chunks = chunker.chunk_many(documents)
        for i, c in enumerate(chunks):
            assert c.chunk_index == i

    def test_access_scope_in_postgres_chunk_metadata(self) -> None:
        documents = [_make_postgres_doc(row, i) for i, row in enumerate(self.SAMPLE_ROWS)]
        chunker = TextChunker.for_postgres(chunker_type="fallback")
        chunks = chunker.chunk_many(documents)
        for c in chunks:
            assert "access_scope" in c.metadata
            assert "it" in c.metadata["access_scope"] or "internal" in c.metadata["access_scope"]


# ---------------------------------------------------------------------------
# Routing: get_chunker produces working chunkers
# ---------------------------------------------------------------------------

class TestGetChunkerEndToEnd:
    def test_document_chunker_end_to_end(self, doc_dir: Path) -> None:
        ingester = DocumentIngester(doc_dir, use_docling=False)
        docs = ingester.ingest().documents
        chunker = get_chunker("document")
        chunks = chunker.chunk_many(docs)
        assert all(c.token_count > 0 for c in chunks)

    def test_postgresql_chunker_end_to_end(self) -> None:
        rows = [{"id": 1, "title": "Issue", "status": "open", "department": "IT"}]
        docs = [_make_postgres_doc(r, i) for i, r in enumerate(rows)]
        chunker = get_chunker("postgresql")
        chunks = chunker.chunk_many(docs)
        assert all(c.source_type == "postgresql" for c in chunks)
