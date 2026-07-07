from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from .models import Chunk


class Chunker(ABC):
    name: str

    @abstractmethod
    def chunk(self, text: str, source: str, section_heading: str | None = None, page_number: int | None = None) -> list[Chunk]:
        raise NotImplementedError


class FixedSizeChunker(Chunker):
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 120):
        self.name = "fixed"
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, text: str, source: str, section_heading: str | None = None, page_number: int | None = None) -> list[Chunk]:
        if len(text) <= self.chunk_size:
            return [Chunk(text=text, source=source, section_heading=section_heading, page_number=page_number, chunk_index=0, chunking_strategy=self.name, character_count=len(text))]

        chunks: list[Chunk] = []
        start = 0
        index = 0
        while start < len(text):
            end = min(len(text), start + self.chunk_size)
            piece = text[start:end]
            chunks.append(Chunk(text=piece, source=source, section_heading=section_heading, page_number=page_number, chunk_index=index, chunking_strategy=self.name, character_count=len(piece)))
            if end >= len(text):
                break
            start = max(0, end - self.chunk_overlap)
            index += 1
        return chunks


class StructureAwareChunker(Chunker):
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 120):
        self.name = "structure"
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, text: str, source: str, section_heading: str | None = None, page_number: int | None = None) -> list[Chunk]:
        sections = self._split_sections(text)
        chunks: list[Chunk] = []
        for idx, section in enumerate(sections):
            if not section.strip():
                continue
            if len(section) <= self.chunk_size:
                chunks.append(Chunk(text=section, source=source, section_heading=section_heading, page_number=page_number, chunk_index=len(chunks), chunking_strategy=self.name, character_count=len(section)))
                continue
            sub_chunks = self._split_text(section, source, section_heading, page_number, start_index=len(chunks))
            chunks.extend(sub_chunks)
        return chunks

    def _split_sections(self, text: str) -> list[str]:
        parts = []
        current = []
        for line in text.splitlines():
            if line.startswith("#"):
                if current:
                    parts.append("\n".join(current).strip())
                    current = []
            current.append(line)
        if current:
            parts.append("\n".join(current).strip())
        return parts

    def _split_text(self, text: str, source: str, section_heading: str | None, page_number: int | None, start_index: int) -> list[Chunk]:
        chunks: list[Chunk] = []
        start = 0
        index = start_index
        while start < len(text):
            end = min(len(text), start + self.chunk_size)
            piece = text[start:end]
            chunks.append(Chunk(text=piece, source=source, section_heading=section_heading, page_number=page_number, chunk_index=index, chunking_strategy=self.name, character_count=len(piece)))
            if end >= len(text):
                break
            start = max(0, end - self.chunk_overlap)
            index += 1
        return chunks


class SemanticChunker(Chunker):
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 120):
        self.name = "semantic"
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, text: str, source: str, section_heading: str | None = None, page_number: int | None = None) -> list[Chunk]:
        sentences = [segment.strip() for segment in text.split(".") if segment.strip()]
        if not sentences:
            return []
        chunks: list[Chunk] = []
        current = []
        current_len = 0
        for sentence in sentences:
            if current_len + len(sentence) > self.chunk_size and current:
                chunks.append(Chunk(text=". ".join(current), source=source, section_heading=section_heading, page_number=page_number, chunk_index=len(chunks), chunking_strategy=self.name, character_count=len(". ".join(current))))
                current = [sentence]
                current_len = len(sentence)
            else:
                current.append(sentence)
                current_len += len(sentence)
        if current:
            chunks.append(Chunk(text=". ".join(current), source=source, section_heading=section_heading, page_number=page_number, chunk_index=len(chunks), chunking_strategy=self.name, character_count=len(". ".join(current))))
        return chunks
