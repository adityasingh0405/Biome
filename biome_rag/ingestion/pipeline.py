from __future__ import annotations

import hashlib
import json
import logging
import pickle
from pathlib import Path
from typing import Sequence

from .chunkers import Chunker, FixedSizeChunker, SemanticChunker, StructureAwareChunker
from .dedup import Deduplicator
from .loaders import load_documents
from .models import Chunk, IngestionConfig, IngestionSummary, NormalizedDocument
from ..retrieval.bm25 import BM25Index
from ..retrieval.dense import DenseEmbeddingAdapter, SimpleDenseEmbeddingAdapter, ChromaDenseEmbeddingAdapter

logger = logging.getLogger(__name__)


class IngestionPipeline:
    def __init__(
        self,
        config: IngestionConfig | None = None,
        dense_adapter: DenseEmbeddingAdapter | None = None,
    ):
        self.config = config or IngestionConfig()
        self.chunkers: list[Chunker] = [
            FixedSizeChunker(self.config.chunk_size, self.config.chunk_overlap),
            StructureAwareChunker(self.config.chunk_size, self.config.chunk_overlap),
            SemanticChunker(self.config.chunk_size, self.config.chunk_overlap),
        ]
        self.deduplicator = Deduplicator(self.config.dedup_threshold)

        if dense_adapter is not None:
            self.dense_adapter = dense_adapter
        else:
            try:
                self.dense_adapter = ChromaDenseEmbeddingAdapter(self.config.storage_dir)
                logger.info("ChromaDenseEmbeddingAdapter initialised for ingestion.")
            except Exception as exc:
                logger.warning(
                    "ChromaDenseEmbeddingAdapter unavailable (%s). Falling back to SimpleDenseEmbeddingAdapter.",
                    exc,
                )
                self.dense_adapter = SimpleDenseEmbeddingAdapter()

        self.config.processed_dir.mkdir(parents=True, exist_ok=True)
        self.config.storage_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(self, paths: Sequence[Path] | None = None) -> tuple[list[Chunk], IngestionSummary]:
        input_paths = list(paths or self._discover_paths())
        logger.info("Starting ingestion. Discovered %d input files.", len(input_paths))

        documents = load_documents(input_paths)
        logger.info("Loaded %d documents.", len(documents))

        chunks, summary = self._chunk_and_dedup(documents)
        self._persist(chunks, summary)

        logger.info(
            "Ingestion complete. chunks=%d, duplicates_skipped=%d, strategies=%s",
            summary.chunks_created,
            summary.duplicates_skipped,
            json.dumps(summary.chunks_per_strategy),
        )
        return chunks, summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _discover_paths(self) -> list[Path]:
        if not self.config.raw_dir.exists():
            return []
        return sorted(p for p in self.config.raw_dir.glob("**/*") if p.is_file())

    def _chunk_and_dedup(
        self, documents: list[NormalizedDocument]
    ) -> tuple[list[Chunk], IngestionSummary]:
        """Chunk all documents, remove exact + near-duplicates, return chunks + summary."""
        chunks: list[Chunk] = []
        dedup_skipped = 0
        exact_hashes: set[str] = set()
        summary = IngestionSummary(
            documents_processed=len(documents), chunks_per_strategy={}
        )

        # Reset cosine deduplicator for this ingestion run
        self.deduplicator.reset()

        for document in documents:
            for chunker in self.chunkers:
                generated = chunker.chunk(
                    document.text,
                    document.source,
                    document.section_heading,
                    document.page_number,
                )
                for chunk in generated:
                    # Step 1: exact hash dedup (fast path)
                    chunk_hash = hashlib.md5(
                        chunk.text.strip().lower().encode()
                    ).hexdigest()
                    if chunk_hash in exact_hashes:
                        dedup_skipped += 1
                        logger.debug(
                            "Exact duplicate skipped: source=%s, strategy=%s",
                            chunk.source,
                            chunk.chunking_strategy,
                        )
                        continue
                    exact_hashes.add(chunk_hash)

                    # Step 2: cosine near-duplicate dedup
                    if self.deduplicator.is_duplicate(chunk.text):
                        dedup_skipped += 1
                        logger.debug(
                            "Near-duplicate skipped (cosine): source=%s, strategy=%s",
                            chunk.source,
                            chunk.chunking_strategy,
                        )
                        continue

                    chunks.append(chunk)

        summary.chunks_created = len(chunks)
        summary.duplicates_skipped = dedup_skipped
        for chunker in self.chunkers:
            summary.chunks_per_strategy[chunker.name] = sum(
                1 for c in chunks if c.chunking_strategy == chunker.name
            )

        return chunks, summary

    def _persist(self, chunks: list[Chunk], summary: IngestionSummary) -> None:
        # 1. Write processed chunks JSON
        self.config.processed_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.config.processed_dir / "chunks.json"
        payload = {
            "chunks": [self._chunk_to_dict(c) for c in chunks],
            "summary": {
                "documents_processed": summary.documents_processed,
                "chunks_created": summary.chunks_created,
                "chunks_per_strategy": summary.chunks_per_strategy,
                "duplicates_skipped": summary.duplicates_skipped,
            },
        }
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Processed chunks written to %s", output_path)

        # 2. Build and save BM25 index
        bm25_path = self.config.storage_dir / "bm25_index.pkl"
        bm25_index = BM25Index(bm25_path)
        bm25_index.build([c.text for c in chunks])
        bm25_index.save()
        logger.info("BM25 index saved: %d documents.", len(bm25_index.documents))

        # 3. Index into dense vector store
        self.dense_adapter.index_documents(chunks)

        # 4. Sync check: verify both indexes have matching chunk counts
        self._verify_index_sync(chunks, bm25_index)

    def _verify_index_sync(self, chunks: list[Chunk], bm25_index: BM25Index) -> None:
        """Assert that BM25 and dense indexes contain the same number of chunks.

        Logs an error (E3002) if they diverge, but does not raise — the API can
        still serve partial results and the operator can re-run ingestion.
        """
        bm25_count = len(bm25_index.documents)
        chunk_count = len(chunks)

        if bm25_count != chunk_count:
            logger.error(
                "E3002 — Index out of sync: BM25 has %d documents, chunks JSON has %d. "
                "Re-run ingestion with --force-reindex to rebuild both indexes.",
                bm25_count,
                chunk_count,
            )
        else:
            logger.info(
                "Index sync check passed: BM25 and dense indexes both contain %d chunks.",
                chunk_count,
            )

    @staticmethod
    def _chunk_to_dict(chunk: Chunk) -> dict[str, object]:
        return {
            "text": chunk.text,
            "source": chunk.source,
            "section_heading": chunk.section_heading,
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
            "chunking_strategy": chunk.chunking_strategy,
            "character_count": chunk.character_count,
        }
