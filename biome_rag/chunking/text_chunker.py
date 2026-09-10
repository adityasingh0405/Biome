"""Text chunker using Chonkie's SentenceChunker for Postgres / Slack sources.

Phase 2 implementation for text-based ``DocumentNode`` objects that were NOT
processed by Docling (i.e., database rows and — when activated — Slack threads).

Token targets per source type (from Settings / .env):
    postgresql  → 128–256 tokens   (PG_CHUNK_MAX_TOKENS / PG_CHUNK_MIN_TOKENS)
    slack       → 256–400 tokens   (SLACK_CHUNK_MAX_TOKENS / SLACK_CHUNK_MIN_TOKENS)
    unstructured / default → 400–600 tokens

Chunker routing (controlled by ``chunker_type``):
    "sentence"  → Chonkie ``SentenceChunker``:
                  Splits by sentences, respects token budget. Fast; no GPU.
                  Use for Postgres rows and Slack threads.
    "semantic"  → Chonkie ``SemanticChunker``:
                  Groups semantically similar sentences. Slower; loads an
                  embedding model (all-MiniLM-L6-v2 by default).
                  Use when semantic coherence matters more than speed.
    "fallback"  → ``split_text_by_tokens`` from ``base.py``:
                  Pure Python, no extra dependencies.
                  Used automatically when Chonkie is not installed.

Design decisions (see DECISIONS.md D016):
- Chonkie wraps tiktoken / HuggingFace tokenizers transparently; we pass
  ``tokenizer="cl100k_base"`` to force tiktoken-compatible counting.
- The ``chunk_overlap`` is expressed in tokens (not characters) for all
  new chunkers. Legacy chunkers keep character-based overlap.
- Per-source-type factory methods (``for_postgres``, ``for_slack``) set the
  correct token targets so call sites don't need to remember the numbers.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .base import Chunker, count_tokens, split_text_by_tokens
from biome_rag.ingestion.models import Chunk

if TYPE_CHECKING:
    from biome_rag.ingestion.models import DocumentNode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TextChunker
# ---------------------------------------------------------------------------

class TextChunker(Chunker):
    """Token-aware sentence chunker for Postgres rows and Slack threads.

    Uses Chonkie's ``SentenceChunker`` (or ``SemanticChunker``) when available,
    with a pure-Python token-budget fallback when Chonkie is not installed.

    Args:
        chunk_size: Maximum tokens per chunk.
        chunk_overlap: Tokens of context repeated at the start of the next chunk.
        chunker_type: ``"sentence"`` (default), ``"semantic"``, or ``"fallback"``.
        embedding_model: Embedding model name for ``SemanticChunker`` only.
        tiktoken_encoding: Encoding for tiktoken-based token counting.
        min_chunk_tokens: Chunks shorter than this are merged with the previous
                          chunk (prevents stub chunks like a single date string).
    """

    strategy_name = "chonkie_sentence"

    def __init__(
        self,
        chunk_size: int = 256,
        chunk_overlap: int = 32,
        chunker_type: str = "sentence",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        tiktoken_encoding: str = "cl100k_base",
        min_chunk_tokens: int = 20,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunker_type = chunker_type
        self.embedding_model = embedding_model
        self.tiktoken_encoding = tiktoken_encoding
        self.min_chunk_tokens = min_chunk_tokens
        self._chonkie: Any = None   # Lazy-loaded

    # ------------------------------------------------------------------
    # Factory methods for per-source token targets
    # ------------------------------------------------------------------

    @classmethod
    def for_postgres(cls, **kwargs: Any) -> "TextChunker":
        """Create a TextChunker tuned for PostgreSQL row documents.

        Targets: 128–256 tokens, 16-token overlap.
        """
        return cls(
            chunk_size=kwargs.pop("chunk_size", 256),
            chunk_overlap=kwargs.pop("chunk_overlap", 16),
            chunker_type=kwargs.pop("chunker_type", "sentence"),
            **kwargs,
        )

    @classmethod
    def for_slack(cls, **kwargs: Any) -> "TextChunker":
        """Create a TextChunker tuned for Slack thread documents.

        Targets: 256–400 tokens, 32-token overlap.
        """
        return cls(
            chunk_size=kwargs.pop("chunk_size", 400),
            chunk_overlap=kwargs.pop("chunk_overlap", 32),
            chunker_type=kwargs.pop("chunker_type", "sentence"),
            **kwargs,
        )

    @classmethod
    def for_unstructured(cls, **kwargs: Any) -> "TextChunker":
        """Create a TextChunker for legacy unstructured / text file documents.

        Targets: 400–600 tokens, 50-token overlap.
        """
        return cls(
            chunk_size=kwargs.pop("chunk_size", 512),
            chunk_overlap=kwargs.pop("chunk_overlap", 50),
            chunker_type=kwargs.pop("chunker_type", "sentence"),
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Chonkie lazy init
    # ------------------------------------------------------------------

    def _get_chonkie(self) -> Any | None:
        """Return a cached Chonkie chunker, or None if Chonkie is unavailable."""
        if self._chonkie is not None:
            return self._chonkie

        if self.chunker_type == "fallback":
            return None

        try:
            if self.chunker_type == "semantic":
                from chonkie import SemanticChunker  # noqa: PLC0415
                self._chonkie = SemanticChunker(
                    embedding_model=self.embedding_model,
                    chunk_size=self.chunk_size,
                    threshold=0.5,
                )
                self.strategy_name = "chonkie_semantic"
                logger.info("Chonkie SemanticChunker initialised (chunk_size=%d).", self.chunk_size)
            else:
                from chonkie import SentenceChunker  # noqa: PLC0415
                self._chonkie = SentenceChunker(
                    tokenizer_or_token_counter=self.tiktoken_encoding,
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                    min_sentences_per_chunk=1,
                )
                self.strategy_name = "chonkie_sentence"
                logger.info("Chonkie SentenceChunker initialised (chunk_size=%d).", self.chunk_size)
        except ImportError:
            logger.warning(
                "Chonkie not installed (`pip install chonkie`). "
                "TextChunker will use the token-budget fallback splitter."
            )
            self._chonkie = None
        except Exception as exc:
            logger.warning("Chonkie init failed (%s). Using fallback.", exc)
            self._chonkie = None
        return self._chonkie

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk(self, document: "DocumentNode") -> list[Chunk]:
        """Chunk a text document into Chunk objects.

        Routes to Chonkie SentenceChunker/SemanticChunker if available,
        otherwise uses the token-budget fallback splitter.
        """
        text = document.page_content.strip()
        if not text:
            return []

        # If the document is already short enough, return as a single chunk
        if self._count(text) <= self.chunk_size:
            return [self._make_chunk(text, document, 0)]

        chonkie = self._get_chonkie()
        if chonkie is not None:
            raw = self._chunk_with_chonkie(chonkie, text, document)
        else:
            raw = self._chunk_fallback(text, document)

        # Post-process: drop/merge micro-chunks below min_chunk_tokens
        return self._merge_micro_chunks(raw, document)

    # ------------------------------------------------------------------
    # Chonkie path
    # ------------------------------------------------------------------

    def _chunk_with_chonkie(
        self, chonkie: Any, text: str, document: "DocumentNode"
    ) -> list[Chunk]:
        """Use Chonkie to split text and convert to Chunk objects."""
        try:
            chonkie_chunks = chonkie(text)  # Chonkie is callable
        except Exception as exc:
            logger.warning(
                "Chonkie failed for '%s': %s. Using fallback.",
                document.metadata.source_name, exc,
            )
            return self._chunk_fallback(text, document)

        result: list[Chunk] = []
        for idx, cc in enumerate(chonkie_chunks):
            chunk_text = cc.text.strip() if hasattr(cc, "text") else str(cc).strip()
            if not chunk_text:
                continue
            token_cnt = getattr(cc, "token_count", None) or self._count(chunk_text)
            result.append(
                Chunk(
                    text=chunk_text,
                    source=document.metadata.file_path or document.metadata.source_name,
                    section_heading=document.metadata.extra.get("section_heading"),
                    page_number=document.metadata.extra.get("page_number"),
                    chunk_index=idx,
                    chunking_strategy=self.strategy_name,
                    character_count=len(chunk_text),
                    token_count=token_cnt,
                    source_type=document.metadata.source_type,
                    metadata=document.metadata.model_dump(),
                )
            )
        return result

    # ------------------------------------------------------------------
    # Fallback path
    # ------------------------------------------------------------------

    def _chunk_fallback(self, text: str, document: "DocumentNode") -> list[Chunk]:
        """Pure-Python token-budget sentence splitter."""
        texts = split_text_by_tokens(
            text,
            max_tokens=self.chunk_size,
            overlap_tokens=self.chunk_overlap,
            encoding=self.tiktoken_encoding,
        )
        return [
            self._make_chunk(t, document, idx, strategy="token_budget_fallback")
            for idx, t in enumerate(texts)
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_chunk(
        self,
        text: str,
        document: "DocumentNode",
        index: int,
        strategy: str | None = None,
    ) -> Chunk:
        text = text.strip()
        return Chunk(
            text=text,
            source=document.metadata.file_path or document.metadata.source_name,
            section_heading=document.metadata.extra.get("section_heading"),
            page_number=document.metadata.extra.get("page_number"),
            chunk_index=index,
            chunking_strategy=strategy or self.strategy_name,
            character_count=len(text),
            token_count=self._count(text),
            source_type=document.metadata.source_type,
            metadata=document.metadata.model_dump(),
        )

    def _merge_micro_chunks(
        self, chunks: list[Chunk], document: "DocumentNode"
    ) -> list[Chunk]:
        """Merge chunks shorter than ``min_chunk_tokens`` into the previous chunk.

        A Postgres row serialised to Markdown sometimes ends with a short
        field like ``**status**: open`` (~3 tokens). Rather than indexing this
        as a standalone chunk, we append it to the previous one.
        """
        if not chunks:
            return chunks

        merged: list[Chunk] = []
        for chunk in chunks:
            if (
                merged
                and chunk.token_count < self.min_chunk_tokens
                and merged[-1].token_count + chunk.token_count <= self.chunk_size * 1.2
            ):
                prev = merged[-1]
                combined_text = prev.text.rstrip() + "\n" + chunk.text
                prev.text = combined_text
                prev.character_count = len(combined_text)
                prev.token_count = self._count(combined_text)
            else:
                merged.append(chunk)

        # Re-index
        for i, c in enumerate(merged):
            c.chunk_index = i
        return merged
