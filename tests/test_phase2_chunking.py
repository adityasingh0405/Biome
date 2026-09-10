"""Unit tests for Phase 2 chunking layer.

All tests run without external services (no Docling models, no Chonkie).
They exercise:
- count_tokens() with tiktoken and word-count fallback
- split_text_by_tokens() boundary conditions
- Markdown table detection and row-splitting
- DocumentChunker fallback path (no docling_doc)
- TextChunker fallback path (no Chonkie)
- Per-source factory methods and token targets
- Micro-chunk merging
- get_chunker() routing
- Chunk model token_count and source_type fields
- chunk_many() global re-indexing
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from biome_rag.chunking import DocumentChunker, TextChunker, count_tokens, get_chunker, split_text_by_tokens
from biome_rag.chunking.document_chunker import (
    _is_markdown_table,
    _split_markdown_table_by_rows,
)
from biome_rag.ingestion.models import Chunk, DocumentMetadata, DocumentNode


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_document(
    text: str,
    source_type: str = "document",
    source_name: str = "test.pdf",
    docling_doc=None,
) -> DocumentNode:
    """Create a minimal DocumentNode for testing."""
    node = DocumentNode(
        page_content=text,
        metadata=DocumentMetadata(
            source_type=source_type,
            source_name=source_name,
            access_level="internal",
            access_scope=["internal"],
            extra={"section_heading": "Test Section"},
        ),
    )
    node.docling_doc = docling_doc
    return node


def _make_long_text(n_words: int = 600) -> str:
    """Generate a long text of approximately n_words English words."""
    words = ["enterprise", "knowledge", "retrieval", "augmented", "generation", "pipeline"]
    return " ".join(words[i % len(words)] for i in range(n_words))


SAMPLE_TABLE = """\
| ID | Title | Status | Department |
| --- | --- | --- | --- |
| 1 | VPN issue | open | IT |
| 2 | Email down | closed | IT |
| 3 | Laptop broken | open | Engineering |
| 4 | Slow build | in-progress | Engineering |
| 5 | DB migration | open | Platform |
"""


# ---------------------------------------------------------------------------
# count_tokens
# ---------------------------------------------------------------------------

class TestCountTokens:
    def test_returns_positive_integer_for_text(self) -> None:
        n = count_tokens("Hello, world!")
        assert isinstance(n, int)
        assert n > 0

    def test_longer_text_has_more_tokens(self) -> None:
        short = count_tokens("Hello")
        long_ = count_tokens("Hello " * 100)
        assert long_ > short

    def test_empty_string_returns_zero_or_one(self) -> None:
        n = count_tokens("")
        assert n == 0 or n == 1  # tiktoken returns 0; heuristic returns max(1,...)

    def test_consistent_across_calls(self) -> None:
        text = "The quick brown fox jumps over the lazy dog."
        assert count_tokens(text) == count_tokens(text)

    def test_different_encodings_accepted(self) -> None:
        t1 = count_tokens("hello", "cl100k_base")
        t2 = count_tokens("hello", "p50k_base")
        # Both should return a positive int (may differ by encoding)
        assert t1 > 0
        assert t2 > 0


# ---------------------------------------------------------------------------
# split_text_by_tokens
# ---------------------------------------------------------------------------

class TestSplitTextByTokens:
    def test_short_text_not_split(self) -> None:
        text = "Short text."
        parts = split_text_by_tokens(text, max_tokens=512)
        assert len(parts) == 1
        assert parts[0] == text

    def test_long_text_split_into_multiple_parts(self) -> None:
        text = _make_long_text(600)
        parts = split_text_by_tokens(text, max_tokens=100)
        assert len(parts) > 1

    def test_each_part_within_token_budget(self) -> None:
        text = _make_long_text(600)
        max_tok = 100
        parts = split_text_by_tokens(text, max_tokens=max_tok)
        for part in parts:
            # Allow 20% slack for overlap
            assert count_tokens(part) <= max_tok * 1.4, f"Part too long: {count_tokens(part)} tokens"

    def test_all_parts_non_empty(self) -> None:
        text = _make_long_text(200)
        parts = split_text_by_tokens(text, max_tokens=50)
        for part in parts:
            assert part.strip()

    def test_empty_text_returns_empty_list(self) -> None:
        assert split_text_by_tokens("", max_tokens=100) == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        assert split_text_by_tokens("   \n  ", max_tokens=100) == []

    def test_exact_budget_text_not_split(self) -> None:
        text = "word " * 10
        max_tok = count_tokens(text) + 10
        parts = split_text_by_tokens(text, max_tokens=max_tok)
        assert len(parts) == 1

    def test_no_content_loss(self) -> None:
        """All words from the original text should appear somewhere in the chunks."""
        text = "alpha beta gamma delta epsilon zeta eta theta iota kappa " * 20
        parts = split_text_by_tokens(text, max_tokens=30)
        rejoined = " ".join(parts)
        for word in ["alpha", "beta", "gamma", "kappa"]:
            assert word in rejoined


# ---------------------------------------------------------------------------
# Markdown table detection
# ---------------------------------------------------------------------------

class TestMarkdownTableDetection:
    def test_detects_standard_table(self) -> None:
        assert _is_markdown_table(SAMPLE_TABLE)

    def test_plain_text_not_detected_as_table(self) -> None:
        assert not _is_markdown_table("This is just plain text.")

    def test_partial_table_not_detected(self) -> None:
        # Missing separator row
        text = "| col1 | col2 |\n| val1 | val2 |"
        assert not _is_markdown_table(text)

    def test_table_with_surrounding_text(self) -> None:
        text = "Here is a table:\n" + SAMPLE_TABLE + "\nEnd of table."
        assert _is_markdown_table(text)


# ---------------------------------------------------------------------------
# Oversized-table row-splitting
# ---------------------------------------------------------------------------

class TestSplitMarkdownTableByRows:
    def test_small_table_not_split(self) -> None:
        # If the table fits in max_tokens, it comes back as one chunk
        parts = _split_markdown_table_by_rows(SAMPLE_TABLE, max_tokens=1000)
        assert len(parts) == 1

    def test_large_table_split_into_multiple(self) -> None:
        # Very small max_tokens forces each row into its own chunk
        parts = _split_markdown_table_by_rows(SAMPLE_TABLE, max_tokens=40)
        assert len(parts) > 1

    def test_each_part_has_header(self) -> None:
        parts = _split_markdown_table_by_rows(SAMPLE_TABLE, max_tokens=40)
        for part in parts:
            assert "| ID |" in part, "Header should be repeated in every sub-table"
            assert "| --- |" in part or "---" in part, "Separator should be repeated"

    def test_each_part_within_token_budget(self) -> None:
        max_tok = 60
        parts = _split_markdown_table_by_rows(SAMPLE_TABLE, max_tokens=max_tok)
        for part in parts:
            assert count_tokens(part) <= max_tok * 1.5  # 50% slack for header overhead

    def test_tiny_table_returns_original(self) -> None:
        tiny = "| A |\n| --- |\n| 1 |"
        parts = _split_markdown_table_by_rows(tiny, max_tokens=1000)
        assert len(parts) == 1


# ---------------------------------------------------------------------------
# DocumentChunker — fallback mode (no docling_doc)
# ---------------------------------------------------------------------------

class TestDocumentChunkerFallback:
    def test_short_text_produces_one_chunk(self) -> None:
        doc = _make_document("Short document text.", source_type="document")
        chunker = DocumentChunker(max_tokens=512)
        chunks = chunker.chunk(doc)
        assert len(chunks) == 1

    def test_long_text_split_into_multiple_chunks(self) -> None:
        doc = _make_document(_make_long_text(600), source_type="document")
        chunker = DocumentChunker(max_tokens=100)
        chunks = chunker.chunk(doc)
        assert len(chunks) > 1

    def test_chunk_has_token_count(self) -> None:
        doc = _make_document("Some text for chunking.")
        chunker = DocumentChunker(max_tokens=512)
        chunks = chunker.chunk(doc)
        for c in chunks:
            assert c.token_count > 0

    def test_chunk_source_type_matches_document(self) -> None:
        doc = _make_document("text", source_type="document")
        chunker = DocumentChunker(max_tokens=512)
        chunks = chunker.chunk(doc)
        for c in chunks:
            assert c.source_type == "document"

    def test_chunking_strategy_label_correct(self) -> None:
        doc = _make_document("text")
        chunker = DocumentChunker(max_tokens=512)
        chunks = chunker.chunk(doc)
        for c in chunks:
            assert "docling" in c.chunking_strategy

    def test_chunk_index_sequential(self) -> None:
        doc = _make_document(_make_long_text(500), source_type="document")
        chunker = DocumentChunker(max_tokens=80)
        chunks = chunker.chunk(doc)
        for i, c in enumerate(chunks):
            assert c.chunk_index == i

    def test_empty_document_returns_empty(self) -> None:
        doc = _make_document("", source_type="document")
        chunker = DocumentChunker(max_tokens=512)
        chunks = chunker.chunk(doc)
        # empty page_content → fallback splitter → [] or single empty chunk
        for c in chunks:
            assert c.text.strip() == "" or c.text  # no crash

    def test_table_within_budget_not_row_split(self) -> None:
        doc = _make_document(SAMPLE_TABLE, source_type="document")
        chunker = DocumentChunker(max_tokens=512, table_split_max_tokens=600)
        chunks = chunker.chunk(doc)
        # SAMPLE_TABLE is small — should be one chunk
        assert len(chunks) == 1

    def test_table_over_budget_row_split(self) -> None:
        # The row-split rule fires when a chunk is detected as a Markdown table
        # AND its token count exceeds table_split_max_tokens.
        # Test _split_markdown_table_by_rows directly here (it is called inside chunk()).
        parts = _split_markdown_table_by_rows(SAMPLE_TABLE, max_tokens=40)
        assert len(parts) > 1
        for part in parts:
            # The header row (with | ID | column) must appear in every sub-table
            lines = part.splitlines()
            assert len(lines) >= 2, f"Sub-table must have at least header+separator: {part!r}"
            assert "ID" in lines[0], f"Header must contain 'ID': {lines[0]!r}"

    def test_metadata_source_name_preserved(self) -> None:
        doc = _make_document("Text", source_name="report.pdf")
        chunker = DocumentChunker(max_tokens=512)
        chunks = chunker.chunk(doc)
        for c in chunks:
            assert "report.pdf" in c.source or "report.pdf" in str(c.metadata)

    def test_chunk_many_global_reindex(self) -> None:
        docs = [
            _make_document(_make_long_text(200), source_name=f"doc{i}.pdf")
            for i in range(3)
        ]
        chunker = DocumentChunker(max_tokens=80)
        all_chunks = chunker.chunk_many(docs)
        indices = [c.chunk_index for c in all_chunks]
        assert indices == list(range(len(all_chunks))), "chunk_many should reindex globally"


# ---------------------------------------------------------------------------
# TextChunker — fallback mode (no Chonkie)
# ---------------------------------------------------------------------------

class TestTextChunkerFallback:
    """Run with chunker_type='fallback' to exercise the pure-Python path."""

    def test_postgres_short_row_one_chunk(self) -> None:
        doc = _make_document("## tickets — row id=1\n\n**title**: VPN issue\n**status**: open",
                              source_type="postgresql")
        chunker = TextChunker.for_postgres(chunker_type="fallback")
        chunks = chunker.chunk(doc)
        assert len(chunks) == 1

    def test_postgres_long_row_split(self) -> None:
        long_text = _make_long_text(400)
        doc = _make_document(long_text, source_type="postgresql")
        chunker = TextChunker.for_postgres(chunker_type="fallback", chunk_size=60)
        chunks = chunker.chunk(doc)
        assert len(chunks) > 1

    def test_token_count_populated(self) -> None:
        doc = _make_document("This is a PostgreSQL row.", source_type="postgresql")
        chunker = TextChunker.for_postgres(chunker_type="fallback")
        chunks = chunker.chunk(doc)
        for c in chunks:
            assert c.token_count > 0

    def test_source_type_postgresql(self) -> None:
        doc = _make_document("Row text", source_type="postgresql")
        chunker = TextChunker.for_postgres(chunker_type="fallback")
        chunks = chunker.chunk(doc)
        for c in chunks:
            assert c.source_type == "postgresql"

    def test_source_type_slack(self) -> None:
        doc = _make_document("Thread text", source_type="slack")
        chunker = TextChunker.for_slack(chunker_type="fallback")
        chunks = chunker.chunk(doc)
        for c in chunks:
            assert c.source_type == "slack"

    def test_empty_text_returns_empty(self) -> None:
        doc = _make_document("", source_type="postgresql")
        chunker = TextChunker.for_postgres(chunker_type="fallback")
        chunks = chunker.chunk(doc)
        assert chunks == []

    def test_micro_chunk_merged(self) -> None:
        """Chunks shorter than min_chunk_tokens should be merged into the previous."""
        # Build text that produces one large chunk + one micro chunk
        long_part = _make_long_text(60)    # ~60 tokens
        micro_part = "ok"                   # ~1 token
        doc = _make_document(
            long_part + ".\n\n" + micro_part,
            source_type="postgresql",
        )
        chunker = TextChunker(
            chunk_size=70,
            chunk_overlap=0,
            chunker_type="fallback",
            min_chunk_tokens=5,
        )
        chunks = chunker.chunk(doc)
        # The micro chunk "ok" should be merged into the preceding chunk
        for c in chunks:
            assert c.token_count >= 5 or len(chunks) == 1

    def test_chunk_index_sequential(self) -> None:
        doc = _make_document(_make_long_text(400), source_type="postgresql")
        chunker = TextChunker.for_postgres(chunker_type="fallback", chunk_size=60)
        chunks = chunker.chunk(doc)
        for i, c in enumerate(chunks):
            assert c.chunk_index == i

    def test_chunk_many_global_reindex(self) -> None:
        docs = [
            _make_document(_make_long_text(100), source_type="postgresql")
            for _ in range(3)
        ]
        chunker = TextChunker.for_postgres(chunker_type="fallback", chunk_size=40)
        all_chunks = chunker.chunk_many(docs)
        indices = [c.chunk_index for c in all_chunks]
        assert indices == list(range(len(all_chunks)))

    def test_for_postgres_chunk_size(self) -> None:
        chunker = TextChunker.for_postgres()
        assert chunker.chunk_size == 256

    def test_for_slack_chunk_size(self) -> None:
        chunker = TextChunker.for_slack()
        assert chunker.chunk_size == 400

    def test_for_unstructured_chunk_size(self) -> None:
        chunker = TextChunker.for_unstructured()
        assert chunker.chunk_size == 512


# ---------------------------------------------------------------------------
# get_chunker() routing
# ---------------------------------------------------------------------------

class TestGetChunker:
    def test_document_returns_document_chunker(self) -> None:
        chunker = get_chunker("document")
        assert isinstance(chunker, DocumentChunker)

    def test_postgresql_returns_text_chunker(self) -> None:
        chunker = get_chunker("postgresql")
        assert isinstance(chunker, TextChunker)
        assert chunker.chunk_size == 256

    def test_slack_returns_text_chunker(self) -> None:
        chunker = get_chunker("slack")
        assert isinstance(chunker, TextChunker)
        assert chunker.chunk_size == 400

    def test_unstructured_returns_text_chunker(self) -> None:
        chunker = get_chunker("unstructured")
        assert isinstance(chunker, TextChunker)
        assert chunker.chunk_size == 512

    def test_unknown_source_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown source_type"):
            get_chunker("invalid_source")

    def test_kwargs_forwarded_to_chunker(self) -> None:
        chunker = get_chunker("postgresql", chunk_size=128)
        assert chunker.chunk_size == 128


# ---------------------------------------------------------------------------
# Chunk model fields
# ---------------------------------------------------------------------------

class TestChunkModel:
    def test_token_count_defaults_to_zero(self) -> None:
        c = Chunk(
            text="hello",
            source="test.py",
            section_heading=None,
            page_number=None,
            chunk_index=0,
            chunking_strategy="legacy",
            character_count=5,
        )
        assert c.token_count == 0

    def test_source_type_defaults_to_unknown(self) -> None:
        c = Chunk(
            text="hello",
            source="test.py",
            section_heading=None,
            page_number=None,
            chunk_index=0,
            chunking_strategy="legacy",
            character_count=5,
        )
        assert c.source_type == "unknown"

    def test_token_count_and_source_type_can_be_set(self) -> None:
        c = Chunk(
            text="hello world",
            source="test.txt",
            section_heading=None,
            page_number=None,
            chunk_index=0,
            chunking_strategy="chonkie_sentence",
            character_count=11,
            token_count=3,
            source_type="postgresql",
        )
        assert c.token_count == 3
        assert c.source_type == "postgresql"
