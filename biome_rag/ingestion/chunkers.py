from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod

from .models import Chunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Separators used by the recursive splitter (ordered from coarsest to finest)
# ---------------------------------------------------------------------------
_RECURSIVE_SEPARATORS: list[str] = ["\n\n", "\n", ". ", " ", ""]


class Chunker(ABC):
    name: str

    @abstractmethod
    def chunk(
        self,
        text: str,
        source: str,
        section_heading: str | None = None,
        page_number: int | None = None,
    ) -> list[Chunk]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Strategy 1: Fixed-size with overlap
# ---------------------------------------------------------------------------


class FixedSizeChunker(Chunker):
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 120):
        self.name = "fixed"
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(
        self,
        text: str,
        source: str,
        section_heading: str | None = None,
        page_number: int | None = None,
    ) -> list[Chunk]:
        if len(text) <= self.chunk_size:
            return [
                Chunk(
                    text=text,
                    source=source,
                    section_heading=section_heading,
                    page_number=page_number,
                    chunk_index=0,
                    chunking_strategy=self.name,
                    character_count=len(text),
                )
            ]

        chunks: list[Chunk] = []
        start = 0
        index = 0
        while start < len(text):
            end = min(len(text), start + self.chunk_size)
            piece = text[start:end]
            chunks.append(
                Chunk(
                    text=piece,
                    source=source,
                    section_heading=section_heading,
                    page_number=page_number,
                    chunk_index=index,
                    chunking_strategy=self.name,
                    character_count=len(piece),
                )
            )
            if end >= len(text):
                break
            start = max(0, end - self.chunk_overlap)
            index += 1
        return chunks


# ---------------------------------------------------------------------------
# Strategy 2: Recursive character splitting (structure-aware)
# ---------------------------------------------------------------------------


class StructureAwareChunker(Chunker):
    """Recursive character splitter inspired by LangChain's RecursiveCharacterTextSplitter.

    Splitting priority:
      1. Markdown headings (``#``, ``##``, …) — preserves document sections.
      2. Double newlines (paragraph boundaries).
      3. Single newlines.
      4. Sentence endings ('`. `').
      5. Spaces.
      6. Characters (hard cut — last resort).

    For each section, if the text still exceeds *chunk_size* after the primary
    heading split, the same separator hierarchy is applied recursively until the
    piece fits or the finest separator (character-level) is reached.
    """

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 120):
        self.name = "structure"
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(
        self,
        text: str,
        source: str,
        section_heading: str | None = None,
        page_number: int | None = None,
    ) -> list[Chunk]:
        pieces = self._recursive_split(text, _RECURSIVE_SEPARATORS)
        merged = self._merge_with_overlap(pieces)
        return [
            Chunk(
                text=piece,
                source=source,
                section_heading=section_heading,
                page_number=page_number,
                chunk_index=idx,
                chunking_strategy=self.name,
                character_count=len(piece),
            )
            for idx, piece in enumerate(merged)
        ]

    # ------------------------------------------------------------------
    # Core recursive split logic
    # ------------------------------------------------------------------

    def _recursive_split(self, text: str, separators: list[str]) -> list[str]:
        """Recursively split *text* using the first separator that divides it."""
        if len(text) <= self.chunk_size:
            return [text]

        for sep in separators:
            if sep == "":
                # Last resort: hard character split
                return self._hard_split(text)

            # First try Markdown heading split before other separators
            if sep == "\n\n":
                heading_parts = self._split_on_headings(text)
                if len(heading_parts) > 1:
                    result: list[str] = []
                    for part in heading_parts:
                        result.extend(self._recursive_split(part, separators))
                    return result

            parts = text.split(sep)
            if len(parts) <= 1:
                continue  # Separator not found, try next

            # Re-join short adjacent pieces to avoid tiny fragments
            result = []
            current = ""
            for part in parts:
                candidate = (current + sep + part).lstrip(sep) if current else part
                if len(candidate) <= self.chunk_size:
                    current = candidate
                else:
                    if current:
                        result.extend(self._recursive_split(current, separators[separators.index(sep) + 1:]))
                    current = part
            if current:
                result.extend(self._recursive_split(current, separators[separators.index(sep) + 1:]))
            return result

        return [text]

    def _split_on_headings(self, text: str) -> list[str]:
        """Split *text* on Markdown heading lines (lines starting with `#`)."""
        parts: list[str] = []
        current: list[str] = []
        for line in text.splitlines():
            if line.startswith("#") and current:
                parts.append("\n".join(current).strip())
                current = []
            current.append(line)
        if current:
            parts.append("\n".join(current).strip())
        return [p for p in parts if p]

    def _hard_split(self, text: str) -> list[str]:
        """Hard character split with overlap as an absolute last resort."""
        pieces: list[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + self.chunk_size)
            pieces.append(text[start:end])
            if end >= len(text):
                break
            start = max(0, end - self.chunk_overlap)
        return pieces

    def _merge_with_overlap(self, pieces: list[str]) -> list[str]:
        """Re-merge tiny pieces and apply overlap between adjacent chunks."""
        if not pieces:
            return []

        merged: list[str] = []
        current = pieces[0]
        for next_piece in pieces[1:]:
            if len(current) + len(next_piece) + 1 <= self.chunk_size:
                current = current + " " + next_piece
            else:
                merged.append(current.strip())
                # Carry overlap from the end of current into the start of next
                overlap_text = current[-self.chunk_overlap:] if len(current) > self.chunk_overlap else current
                current = (overlap_text + " " + next_piece).strip()
        if current.strip():
            merged.append(current.strip())
        return merged


# ---------------------------------------------------------------------------
# Strategy 3: Semantic chunking (topic-boundary via sentence embeddings)
# ---------------------------------------------------------------------------


class SemanticChunker(Chunker):
    """Topic-boundary chunker using sentence-level cosine similarity.

    Algorithm:
      1. Split text into sentences (regex-based).
      2. Encode each sentence with a ``sentence-transformers`` model.
      3. Compute cosine similarity between consecutive sentence embeddings.
      4. A new chunk boundary is declared where similarity drops below
         *similarity_threshold* (default 0.5) — indicating a topic shift.
      5. Chunks that exceed *chunk_size* are further split using the
         recursive strategy as a safety net.

    Falls back to sentence-length accumulation (no model needed) if
    ``sentence-transformers`` is not installed or model loading fails.
    """

    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 120,
        similarity_threshold: float = 0.5,
        model_name: str = "all-MiniLM-L6-v2",
    ):
        self.name = "semantic"
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.similarity_threshold = similarity_threshold
        self.model_name = model_name
        self._model = None  # Lazy-loaded

    # ------------------------------------------------------------------
    # Lazy model loader
    # ------------------------------------------------------------------

    def _get_model(self):
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._model = SentenceTransformer(self.model_name)
            logger.info("SemanticChunker loaded model: %s", self.model_name)
        except Exception as exc:
            logger.warning(
                "SemanticChunker: could not load '%s' (%s). Falling back to length-based splitting.",
                self.model_name,
                exc,
            )
            self._model = None
        return self._model

    # ------------------------------------------------------------------
    # Sentence tokenisation
    # ------------------------------------------------------------------

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Split text into sentences using punctuation boundaries."""
        # Split on sentence-ending punctuation followed by whitespace
        raw = re.split(r"(?<=[.!?])\s+", text.strip())
        sentences: list[str] = []
        for s in raw:
            s = s.strip()
            if s:
                sentences.append(s)
        return sentences

    # ------------------------------------------------------------------
    # Embedding-based boundary detection
    # ------------------------------------------------------------------

    def _find_boundaries_with_embeddings(self, sentences: list[str]) -> list[int]:
        """Return indices of sentences that start a new semantic chunk."""
        import numpy as np  # type: ignore  # numpy ships with sentence-transformers

        model = self._get_model()
        if model is None or len(sentences) <= 1:
            return []

        embeddings = model.encode(sentences, show_progress_bar=False, convert_to_numpy=True)

        # Normalise for cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        normalised = embeddings / norms

        boundaries: list[int] = []
        for i in range(1, len(sentences)):
            sim = float(np.dot(normalised[i - 1], normalised[i]))
            if sim < self.similarity_threshold:
                boundaries.append(i)
        return boundaries

    # ------------------------------------------------------------------
    # Fallback: length-based accumulation (no model)
    # ------------------------------------------------------------------

    def _split_by_length(
        self,
        sentences: list[str],
        source: str,
        section_heading: str | None,
        page_number: int | None,
    ) -> list[Chunk]:
        chunks: list[Chunk] = []
        current: list[str] = []
        current_len = 0
        for sentence in sentences:
            if current_len + len(sentence) > self.chunk_size and current:
                piece = ". ".join(current)
                chunks.append(
                    Chunk(
                        text=piece,
                        source=source,
                        section_heading=section_heading,
                        page_number=page_number,
                        chunk_index=len(chunks),
                        chunking_strategy=self.name,
                        character_count=len(piece),
                    )
                )
                # Overlap: carry last sentence forward
                current = [current[-1], sentence]
                current_len = len(current[-2]) + len(sentence)
            else:
                current.append(sentence)
                current_len += len(sentence)
        if current:
            piece = ". ".join(current)
            chunks.append(
                Chunk(
                    text=piece,
                    source=source,
                    section_heading=section_heading,
                    page_number=page_number,
                    chunk_index=len(chunks),
                    chunking_strategy=self.name,
                    character_count=len(piece),
                )
            )
        return chunks

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def chunk(
        self,
        text: str,
        source: str,
        section_heading: str | None = None,
        page_number: int | None = None,
    ) -> list[Chunk]:
        sentences = self._split_sentences(text)
        if not sentences:
            return []

        model = self._get_model()
        if model is None:
            # Graceful fallback — no embeddings available
            return self._split_by_length(sentences, source, section_heading, page_number)

        boundaries = self._find_boundaries_with_embeddings(sentences)

        # Group sentences into chunks using detected boundaries
        groups: list[list[str]] = []
        start = 0
        for boundary in boundaries:
            groups.append(sentences[start:boundary])
            start = boundary
        groups.append(sentences[start:])

        chunks: list[Chunk] = []
        for group in groups:
            if not group:
                continue
            piece = " ".join(group)

            # Safety: if a group is oversized, further split it
            if len(piece) > self.chunk_size:
                sub_splitter = StructureAwareChunker(self.chunk_size, self.chunk_overlap)
                sub_chunks = sub_splitter.chunk(piece, source, section_heading, page_number)
                for sc in sub_chunks:
                    chunks.append(
                        Chunk(
                            text=sc.text,
                            source=source,
                            section_heading=section_heading,
                            page_number=page_number,
                            chunk_index=len(chunks),
                            chunking_strategy=self.name,
                            character_count=len(sc.text),
                        )
                    )
            else:
                chunks.append(
                    Chunk(
                        text=piece,
                        source=source,
                        section_heading=section_heading,
                        page_number=page_number,
                        chunk_index=len(chunks),
                        chunking_strategy=self.name,
                        character_count=len(piece),
                    )
                )

        logger.debug(
            "SemanticChunker produced %d chunks from %d sentences (%d boundaries detected).",
            len(chunks),
            len(sentences),
            len(boundaries),
        )
        return chunks
