"""Chunker ABC and token-counting utilities for Phase 2.

All Phase 2 chunkers inherit from ``Chunker`` and produce ``Chunk`` objects
with ``token_count`` populated (using tiktoken, falling back to a word-count
heuristic if tiktoken is not installed).

Design principles:
- One ``Chunker`` per source type keeps the logic focused and testable.
- Token counting is centralised here so every chunker uses the same formula.
- Chunkers are stateless (no model weights loaded at init) unless they need
  an embedding model (SemanticChunker).

Chunker routing by source_type:
    document   → DocumentChunker  (Docling HybridChunker + text fallback)
    postgresql → TextChunker      (Chonkie SentenceChunker, pg_chunk targets)
    slack      → TextChunker      (Chonkie SentenceChunker, slack_chunk targets)
    unstructured → TextChunker    (legacy path, internal_chunk targets)
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from biome_rag.ingestion.models import Chunk, DocumentNode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

@lru_cache(maxsize=4)
def _get_tiktoken_encoding(encoding_name: str) -> "object | None":
    """Return a cached tiktoken encoding, or None if tiktoken is not installed."""
    try:
        import tiktoken  # noqa: PLC0415
        return tiktoken.get_encoding(encoding_name)
    except ImportError:
        logger.warning(
            "tiktoken not installed (`pip install tiktoken`). "
            "Falling back to word-count heuristic for token counting."
        )
        return None
    except Exception as exc:
        logger.warning("tiktoken encoding '%s' failed: %s", encoding_name, exc)
        return None


def count_tokens(text: str, encoding: str = "cl100k_base") -> int:
    """Count the number of tokens in ``text`` using tiktoken.

    Args:
        text: The text to count tokens for.
        encoding: The tiktoken encoding name (default ``cl100k_base``, used by
                  GPT-4 / GPT-3.5-turbo and compatible with most modern LLMs).
                  Use ``"o200k_base"`` for GPT-4o or ``"p50k_base"`` for Codex.

    Returns:
        Exact token count if tiktoken is available; otherwise
        ``int(len(text.split()) * 1.3)`` as a word-count heuristic.
    """
    enc = _get_tiktoken_encoding(encoding)
    if enc is not None:
        return len(enc.encode(text, disallowed_special=()))
    # Heuristic: ~1.3 tokens per whitespace-delimited word (English text)
    return max(1, int(len(text.split()) * 1.3))


# ---------------------------------------------------------------------------
# Token-budget text splitter (pure Python, no dependencies)
# ---------------------------------------------------------------------------

def split_text_by_tokens(
    text: str,
    max_tokens: int,
    overlap_tokens: int = 0,
    encoding: str = "cl100k_base",
) -> list[str]:
    """Split ``text`` into chunks of at most ``max_tokens`` tokens.

    Used as the innermost fallback when neither Docling HybridChunker nor
    Chonkie SentenceChunker is available.  Splits by sentences first (on
    ''. '' / '\n'), then by words if a single sentence is too long.

    Args:
        text: Input text to split.
        max_tokens: Maximum tokens per chunk.
        overlap_tokens: Number of tokens to repeat at the start of the next chunk.
        encoding: tiktoken encoding name (passed to ``count_tokens``).

    Returns:
        List of text strings, each ≤ ``max_tokens`` tokens.
    """
    if not text.strip():
        return []

    if count_tokens(text, encoding) <= max_tokens:
        return [text]

    # Split into sentence-like units
    import re  # noqa: PLC0415
    sentences = re.split(r"(?<=[.!?])\s+|\n{2,}", text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks: list[str] = []
    current_parts: list[str] = []
    current_tokens = 0
    overlap_text = ""

    for sent in sentences:
        sent_tokens = count_tokens(sent, encoding)

        if sent_tokens > max_tokens:
            # A single sentence exceeds the budget — split by words
            if current_parts:
                chunks.append(overlap_text + " ".join(current_parts))
                overlap_text = _compute_overlap(current_parts, overlap_tokens, encoding)
            words = sent.split()
            buf: list[str] = []
            buf_tokens = count_tokens(overlap_text, encoding) if overlap_text else 0
            for word in words:
                w_tokens = count_tokens(word, encoding)
                if buf_tokens + w_tokens > max_tokens and buf:
                    chunks.append(overlap_text + " ".join(buf))
                    overlap_text = _compute_overlap(buf, overlap_tokens, encoding)
                    buf_tokens = count_tokens(overlap_text, encoding) if overlap_text else 0
                    buf = []
                buf.append(word)
                buf_tokens += w_tokens
            if buf:
                current_parts = buf
                current_tokens = buf_tokens
            else:
                current_parts = []
                current_tokens = 0
            continue

        if current_tokens + sent_tokens > max_tokens and current_parts:
            chunks.append(overlap_text + " ".join(current_parts))
            overlap_text = _compute_overlap(current_parts, overlap_tokens, encoding)
            current_parts = []
            current_tokens = count_tokens(overlap_text, encoding) if overlap_text else 0

        current_parts.append(sent)
        current_tokens += sent_tokens

    if current_parts:
        chunks.append(overlap_text + " ".join(current_parts))

    return [c for c in chunks if c.strip()] or [text[:500]]


def _compute_overlap(parts: list[str], overlap_tokens: int, encoding: str) -> str:
    """Return a suffix of ``parts`` that fits within ``overlap_tokens`` tokens."""
    if overlap_tokens <= 0:
        return ""
    collected: list[str] = []
    total = 0
    for part in reversed(parts):
        t = count_tokens(part, encoding)
        if total + t > overlap_tokens:
            break
        collected.insert(0, part)
        total += t
    return " ".join(collected) + " " if collected else ""


# ---------------------------------------------------------------------------
# Abstract Chunker
# ---------------------------------------------------------------------------

class Chunker(ABC):
    """Abstract base class for all Phase 2 chunkers.

    All concrete chunkers must implement ``chunk(document)``, which takes a
    ``DocumentNode`` and returns a list of ``Chunk`` objects with ``token_count``
    set.

    The ``chunk_many`` convenience method processes a list of documents,
    re-indexing ``chunk_index`` across the whole corpus.
    """

    #: Human-readable name, used in ``Chunk.chunking_strategy``
    strategy_name: str = "unknown"

    #: tiktoken encoding used for all token counting in this chunker
    tiktoken_encoding: str = "cl100k_base"

    @abstractmethod
    def chunk(self, document: "DocumentNode") -> "list[Chunk]":
        """Chunk a single document into a list of ``Chunk`` objects.

        Args:
            document: A ``DocumentNode`` from Phase 1 ingestion.

        Returns:
            Ordered list of ``Chunk`` objects with ``chunk_index``, ``token_count``,
            ``source_type``, and ``chunking_strategy`` all populated.
        """
        raise NotImplementedError

    def chunk_many(self, documents: "list[DocumentNode]") -> "list[Chunk]":
        """Chunk a list of documents and re-index chunks sequentially.

        Args:
            documents: List of ``DocumentNode`` objects from Phase 1.

        Returns:
            Flat list of all chunks, with ``chunk_index`` running from 0
            across the entire corpus.
        """
        all_chunks: list[Chunk] = []
        global_index = 0
        for doc in documents:
            doc_chunks = self.chunk(doc)
            for chunk in doc_chunks:
                chunk.chunk_index = global_index
                all_chunks.append(chunk)
                global_index += 1
        return all_chunks

    def _count(self, text: str) -> int:
        """Convenience wrapper for ``count_tokens`` using this chunker's encoding."""
        return count_tokens(text, self.tiktoken_encoding)
