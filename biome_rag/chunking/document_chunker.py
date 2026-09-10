"""Document chunker using IBM Docling's HybridChunker.

Phase 2 implementation for documents that went through Docling in Phase 1:
- If ``DocumentNode.docling_doc`` is present → use Docling HybridChunker, which
  respects headings, tables, lists, and column layout.
- If Docling is unavailable or ``docling_doc`` is None → fall back to the
  token-budget sentence splitter from ``base.py``.

Oversized-table rule (target architecture spec):
    If a chunk contains a Markdown table AND its token count exceeds
    ``table_split_max_tokens``, split the table into chunks of at most
    ``max_tokens`` tokens by adding rows one at a time.

Token targets (from Settings / .env):
    PDF: 400–600 tokens  (default max_tokens=512)
    HTML: 400–600 tokens (same)
    DOCX/PPTX: 400–600 tokens (same)

Design:
- One ``DocumentConverter`` instance is never held here — Docling is only
  called at chunk time, using the ``docling_doc`` already stored on the node.
- The ``HybridChunker`` is lazy-loaded and cached (it downloads a tokenizer
  on first call; subsequent calls are fast).
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from .base import Chunker, count_tokens, split_text_by_tokens
from biome_rag.ingestion.models import Chunk

if TYPE_CHECKING:
    from biome_rag.ingestion.models import DocumentNode

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Markdown table detection
# ---------------------------------------------------------------------------

_TABLE_SEPARATOR_RE = re.compile(r"^\|[-| :]+\|$", re.MULTILINE)


def _is_markdown_table(text: str) -> bool:
    """Return True if text appears to be a Markdown table (has | --- | rows)."""
    return bool(_TABLE_SEPARATOR_RE.search(text))


def _split_markdown_table_by_rows(
    table_text: str,
    max_tokens: int,
    header_tokens_budget: int = 60,
    encoding: str = "cl100k_base",
) -> list[str]:
    """Split an oversized Markdown table into sub-tables, each ≤ ``max_tokens`` tokens.

    The header row (and separator row) are repeated at the top of every sub-table
    so each chunk is a self-contained, readable table.

    Args:
        table_text: Full Markdown table text (may have preceding/following text).
        max_tokens: Token budget per chunk.
        header_tokens_budget: Token budget reserved for the header + separator rows.
        encoding: tiktoken encoding name.

    Returns:
        List of Markdown table strings, each fitting the token budget.
    """
    lines = table_text.strip().splitlines()
    if len(lines) < 3:  # header + separator + at least one row
        return [table_text]

    header = lines[0]
    separator = lines[1]
    data_rows = lines[2:]

    header_block = f"{header}\n{separator}\n"
    header_tokens = count_tokens(header_block, encoding)
    row_budget = max(max_tokens - header_tokens, 50)

    chunks: list[str] = []
    current_rows: list[str] = []
    current_tokens = 0

    for row in data_rows:
        row_tokens = count_tokens(row + "\n", encoding)
        if current_tokens + row_tokens > row_budget and current_rows:
            chunks.append(header_block + "\n".join(current_rows))
            current_rows = []
            current_tokens = 0
        current_rows.append(row)
        current_tokens += row_tokens

    if current_rows:
        chunks.append(header_block + "\n".join(current_rows))

    return chunks or [table_text]


# ---------------------------------------------------------------------------
# DocumentChunker
# ---------------------------------------------------------------------------

class DocumentChunker(Chunker):
    """Chunks PDF / DOCX / PPTX / HTML documents using Docling's HybridChunker.

    Routing:
    1. ``document.docling_doc`` is not None → Docling HybridChunker path.
    2. ``document.docling_doc`` is None (fallback parser was used) → token-budget
       sentence splitter.

    Oversized-table rule:
        Any chunk that is a Markdown table AND exceeds ``table_split_max_tokens``
        tokens is row-split into sub-tables.
    """

    strategy_name = "docling_hybrid"

    def __init__(
        self,
        max_tokens: int = 512,
        merge_peers: bool = True,
        table_split_max_tokens: int = 600,
        overlap_tokens: int = 0,          # Docling handles overlap internally
        tiktoken_encoding: str = "cl100k_base",
        fallback_overlap_tokens: int = 50,
    ) -> None:
        """
        Args:
            max_tokens: Maximum tokens per chunk (Docling ``max_tokens`` param).
            merge_peers: Ask Docling to merge small adjacent chunks of the same type.
            table_split_max_tokens: Chunks containing tables larger than this are
                                    row-split further.
            overlap_tokens: Token overlap between adjacent chunks (0 = Docling default).
            tiktoken_encoding: Encoding for tiktoken-based token counting.
            fallback_overlap_tokens: Overlap used by the fallback sentence splitter.
        """
        self.max_tokens = max_tokens
        self.merge_peers = merge_peers
        self.table_split_max_tokens = table_split_max_tokens
        self.overlap_tokens = overlap_tokens
        self.tiktoken_encoding = tiktoken_encoding
        self.fallback_overlap_tokens = fallback_overlap_tokens
        self._hybrid_chunker: Any = None   # Lazy-loaded

    # ------------------------------------------------------------------
    # Docling HybridChunker
    # ------------------------------------------------------------------

    def _get_hybrid_chunker(self) -> Any | None:
        """Return a cached Docling HybridChunker, or None if unavailable."""
        if self._hybrid_chunker is not None:
            return self._hybrid_chunker
        try:
            from docling.chunking import HybridChunker as DoclingHybridChunker  # noqa: PLC0415
            self._hybrid_chunker = DoclingHybridChunker(
                tokenizer="BAAI/bge-m3",
                max_tokens=self.max_tokens,
                merge_peers=self.merge_peers,
            )
            logger.info("Docling HybridChunker initialised (max_tokens=%d).", self.max_tokens)
        except ImportError:
            logger.warning(
                "Docling not installed (`pip install docling`). "
                "DocumentChunker will use the fallback token-budget splitter."
            )
            self._hybrid_chunker = None
        except Exception as exc:
            logger.warning("Docling HybridChunker init failed: %s. Using fallback.", exc)
            self._hybrid_chunker = None
        return self._hybrid_chunker

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk(self, document: "DocumentNode") -> list[Chunk]:
        """Chunk a document into Chunk objects.

        Routes to Docling HybridChunker if ``document.docling_doc`` is set,
        otherwise uses the token-budget fallback.
        """
        if document.docling_doc is not None:
            raw_chunks = self._chunk_with_docling(document)
        else:
            raw_chunks = self._chunk_text_fallback(document)

        # Apply oversized-table row-split rule
        final_chunks: list[Chunk] = []
        index = 0
        for chunk in raw_chunks:
            if (
                _is_markdown_table(chunk.text)
                and self._count(chunk.text) > self.table_split_max_tokens
            ):
                sub_tables = _split_markdown_table_by_rows(
                    chunk.text,
                    self.max_tokens,
                    encoding=self.tiktoken_encoding,
                )
                for sub in sub_tables:
                    final_chunks.append(self._make_chunk(sub, document, index, "docling_table_split"))
                    index += 1
            else:
                chunk.chunk_index = index
                final_chunks.append(chunk)
                index += 1

        return final_chunks

    # ------------------------------------------------------------------
    # Docling path
    # ------------------------------------------------------------------

    def _chunk_with_docling(self, document: "DocumentNode") -> list[Chunk]:
        """Use Docling HybridChunker on the stored DoclingDocument object."""
        chunker = self._get_hybrid_chunker()
        if chunker is None:
            return self._chunk_text_fallback(document)

        try:
            docling_chunks = list(chunker.chunk(document.docling_doc))
        except Exception as exc:
            logger.warning(
                "Docling HybridChunker failed for '%s': %s. Using fallback.",
                document.metadata.source_name, exc,
            )
            return self._chunk_text_fallback(document)

        if not docling_chunks:
            return self._chunk_text_fallback(document)

        result: list[Chunk] = []
        for idx, dc in enumerate(docling_chunks):
            text = dc.text.strip() if hasattr(dc, "text") else str(dc)
            if not text:
                continue

            # Extract heading from Docling metadata if available
            heading: str | None = None
            page_num: int | None = None
            try:
                meta = dc.meta
                if hasattr(meta, "headings") and meta.headings:
                    heading = meta.headings[-1]  # deepest heading
                if hasattr(meta, "origin") and meta.origin:
                    page_num = getattr(meta.origin, "page_no", None)
            except Exception:
                pass

            result.append(
                Chunk(
                    text=text,
                    source=document.metadata.file_path or document.metadata.source_name,
                    section_heading=heading or document.metadata.extra.get("section_heading"),
                    page_number=page_num,
                    chunk_index=idx,
                    chunking_strategy=self.strategy_name,
                    character_count=len(text),
                    token_count=self._count(text),
                    source_type=document.metadata.source_type,
                    metadata={
                        **document.metadata.model_dump(),
                        "docling_chunk_index": idx,
                    },
                )
            )
        return result

    # ------------------------------------------------------------------
    # Fallback path
    # ------------------------------------------------------------------

    def _chunk_text_fallback(self, document: "DocumentNode") -> list[Chunk]:
        """Token-budget sentence splitter used when Docling is unavailable."""
        texts = split_text_by_tokens(
            document.page_content,
            max_tokens=self.max_tokens,
            overlap_tokens=self.fallback_overlap_tokens,
            encoding=self.tiktoken_encoding,
        )
        return [
            self._make_chunk(text, document, idx, f"{self.strategy_name}_fallback")
            for idx, text in enumerate(texts)
        ]

    def _make_chunk(
        self,
        text: str,
        document: "DocumentNode",
        index: int,
        strategy: str,
    ) -> Chunk:
        """Construct a Chunk from a text string and source document."""
        return Chunk(
            text=text.strip(),
            source=document.metadata.file_path or document.metadata.source_name,
            section_heading=document.metadata.extra.get("section_heading"),
            page_number=document.metadata.extra.get("page_number"),
            chunk_index=index,
            chunking_strategy=strategy,
            character_count=len(text),
            token_count=self._count(text),
            source_type=document.metadata.source_type,
            metadata=document.metadata.model_dump(),
        )
