from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Sequence

from .chunkers import Chunker, FixedSizeChunker, SemanticChunker, StructureAwareChunker
from .dedup import Deduplicator
from .loaders import load_documents
from .models import Chunk, IngestionConfig, IngestionSummary, NormalizedDocument
from ..retrieval.bm25 import BM25Index


class IngestionPipeline:
    def __init__(self, config: IngestionConfig | None = None):
        self.config = config or IngestionConfig()
        self.chunkers: list[Chunker] = [
            FixedSizeChunker(self.config.chunk_size, self.config.chunk_overlap),
            StructureAwareChunker(self.config.chunk_size, self.config.chunk_overlap),
            SemanticChunker(self.config.chunk_size, self.config.chunk_overlap),
        ]
        self.deduplicator = Deduplicator(self.config.dedup_threshold)
        self.config.processed_dir.mkdir(parents=True, exist_ok=True)
        self.config.storage_dir.mkdir(parents=True, exist_ok=True)

    def ingest(self, paths: Sequence[Path] | None = None) -> tuple[list[Chunk], IngestionSummary]:
        input_paths = list(paths or self._discover_paths())
        documents = load_documents(input_paths)
        chunks: list[Chunk] = []
        dedup_skipped = 0
        summary = IngestionSummary(documents_processed=len(documents), chunks_per_strategy={})

        for document in documents:
            for chunker in self.chunkers:
                generated = chunker.chunk(document.text, document.source, document.section_heading, document.page_number)
                for chunk in generated:
                    if self.deduplicator.is_duplicate(chunk, chunks):
                        dedup_skipped += 1
                        continue
                    chunks.append(chunk)

        summary.chunks_created = len(chunks)
        summary.duplicates_skipped = dedup_skipped
        for chunker in self.chunkers:
            summary.chunks_per_strategy[chunker.name] = sum(1 for chunk in chunks if chunk.chunking_strategy == chunker.name)

        self._persist(chunks, summary)
        return chunks, summary

    def _discover_paths(self) -> list[Path]:
        return sorted(self.config.raw_dir.glob("**/*")) if self.config.raw_dir.exists() else []

    def _persist(self, chunks: list[Chunk], summary: IngestionSummary) -> None:
        self.config.processed_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "chunks": [self._chunk_to_dict(chunk) for chunk in chunks],
            "summary": {
                "documents_processed": summary.documents_processed,
                "chunks_created": summary.chunks_created,
                "chunks_per_strategy": summary.chunks_per_strategy,
                "duplicates_skipped": summary.duplicates_skipped,
            },
        }
        output_path = self.config.processed_dir / "chunks.json"
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        bm25_path = self.config.storage_dir / "bm25_index.pkl"
        bm25_index = BM25Index(bm25_path)
        bm25_index.build([chunk.text for chunk in chunks])
        bm25_index.save()

    def _chunk_to_dict(self, chunk: Chunk) -> dict[str, object]:
        return {
            "text": chunk.text,
            "source": chunk.source,
            "section_heading": chunk.section_heading,
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
            "chunking_strategy": chunk.chunking_strategy,
            "character_count": chunk.character_count,
        }
