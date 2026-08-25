from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from biome_rag.generation.answering import AnswerBuilder
from biome_rag.ingestion.models import IngestionConfig
from biome_rag.ingestion.pipeline import IngestionPipeline
from biome_rag.retrieval.engine import HybridRetriever
from biome_rag.retrieval.models import RankedChunk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str
    retrieval_mode: str = "hybrid"


class IngestRequest(BaseModel):
    documents: list[dict[str, Any]]


class CompareRequest(BaseModel):
    question: str


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(
    raw_dir: Path | str | None = None,
    processed_dir: Path | str | None = None,
    storage_dir: Path | str | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Biome RAG",
        version="0.3.0",
        description=(
            "Production RAG pipeline with hybrid search (BM25 + dense), "
            "RRF fusion, cross-encoder reranking, and cited grounded answers."
        ),
    )
    raw_dir = Path(raw_dir or "data/raw")
    processed_dir = Path(processed_dir or "data/processed")
    storage_dir = Path(storage_dir or "data/index")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    config = IngestionConfig(raw_dir=raw_dir, processed_dir=processed_dir, storage_dir=storage_dir)
    pipeline = IngestionPipeline(config)
    retriever = HybridRetriever(storage_dir=storage_dir, processed_dir=processed_dir)
    answer_builder = AnswerBuilder()

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _chunk_to_dict(chunk: RankedChunk) -> dict:
        return {
            "text": chunk.text,
            "source": chunk.source,
            "section_heading": chunk.section_heading,
            "page_number": chunk.page_number,
            "dense_score": round(chunk.dense_score, 4),
            "sparse_score": round(chunk.sparse_score, 4),
            "fused_score": round(chunk.fused_score, 4),
            "rerank_score": round(chunk.rerank_score, 4),
        }

    def _build_answer_payload(question: str, mode: str) -> dict:
        if not question.strip():
            return {
                "answer": "Please provide a question.",
                "citations": [],
                "confidence": {"retrieval_confidence": 0.0, "citation_coverage": 0.0, "completeness": 0.0, "composite": 0.0},
                "retrieved_chunks": [],
            }
        retrieved = retriever.retrieve(question, retrieval_mode=mode)
        ans = answer_builder.answer(question, retrieved)
        return {
            "answer": ans.answer,
            "citations": [
                {"chunk_index": c.chunk_index, "text": c.text, "verified": c.verified}
                for c in ans.citations
            ],
            "confidence": {
                "retrieval_confidence": round(ans.confidence.retrieval_confidence, 4) if ans.confidence else 0.0,
                "citation_coverage": round(ans.confidence.citation_coverage, 4) if ans.confidence else 0.0,
                "completeness": round(ans.confidence.completeness, 4) if ans.confidence else 0.0,
                "composite": round(ans.confidence.composite, 4) if ans.confidence else 0.0,
            },
            "retrieved_chunks": [_chunk_to_dict(c) for c in ans.retrieved_chunks],
        }

    # -----------------------------------------------------------------------
    # Routes
    # -----------------------------------------------------------------------

    @app.get("/", tags=["meta"])
    def root():
        return {
            "service": "Biome RAG",
            "version": "0.3.0",
            "status": "ok",
            "endpoints": ["ask", "/v1/ask", "documents", "/v1/documents", "ingest", "/v1/ingest", "health", "/health"],
            "docs": "/docs",
        }

    @app.get("/health", tags=["meta"])
    @app.get("/v1/health", tags=["meta"])
    def health():
        chunks = retriever.chunk_store.get_chunks()
        return {
            "status": "ok",
            "chunks_indexed": len(chunks),
            "storage_dir": str(storage_dir),
            "processed_dir": str(processed_dir),
        }

    @app.post("/v1/ask", tags=["query"])
    def ask(request: AskRequest):
        """Answer a question using the RAG pipeline.

        Returns the answer text, inline citations with verification status,
        a four-dimensional confidence breakdown, and the ranked retrieved chunks.
        """
        return _build_answer_payload(request.question, request.retrieval_mode)

    @app.post("/v1/compare", tags=["query"])
    def compare(request: CompareRequest):
        """Run the same question through hybrid and dense-only retrieval side by side.

        Useful for demonstrating the advantage of hybrid search over dense-only.
        """
        hybrid_result = _build_answer_payload(request.question, "hybrid")
        dense_result = _build_answer_payload(request.question, "dense")
        return {
            "question": request.question,
            "hybrid": hybrid_result,
            "dense": dense_result,
        }

    @app.get("/v1/documents", tags=["index"])
    def documents():
        """List all indexed documents with their source paths."""
        chunks = retriever.chunk_store.get_chunks()
        seen: dict[str, int] = {}
        for chunk in chunks:
            src = chunk.get("source", "unknown")
            seen[src] = seen.get(src, 0) + 1
        return {
            "total_chunks": len(chunks),
            "documents": [{"source": src, "chunk_count": count} for src, count in sorted(seen.items())],
        }

    @app.post("/v1/ingest", tags=["index"])
    def ingest(request: IngestRequest):
        """Ingest new documents into the pipeline.

        Accepts a list of {source, text} objects. Each document is written to
        raw_dir before triggering a full re-ingestion.
        """
        for document in request.documents:
            source = document.get("source", "uploaded.txt")
            text = document.get("text", "")
            path = raw_dir / source
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        chunks, summary = pipeline.ingest(list(raw_dir.glob("**/*")))
        return {
            "status": "ok",
            "chunks_created": summary.chunks_created,
            "duplicates_skipped": summary.duplicates_skipped,
        }

    return app


app = create_app()
