from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from biome_rag.generation.answering import AnswerBuilder
from biome_rag.ingestion.models import IngestionConfig
from biome_rag.ingestion.pipeline import IngestionPipeline
from biome_rag.retrieval.engine import HybridRetriever
from biome_rag.retrieval.models import RankedChunk


class AskRequest(BaseModel):
    question: str


class IngestRequest(BaseModel):
    documents: list[dict[str, Any]]


class DocumentItem(BaseModel):
    text: str
    source: str


def create_app(raw_dir: Path | str | None = None, processed_dir: Path | str | None = None, storage_dir: Path | str | None = None) -> FastAPI:
    app = FastAPI(title="Biome RAG", version="0.1.0")
    raw_dir = Path(raw_dir or "data/raw")
    processed_dir = Path(processed_dir or "data/processed")
    storage_dir = Path(storage_dir or "data/index")

    config = IngestionConfig(raw_dir=raw_dir, processed_dir=processed_dir, storage_dir=storage_dir)
    pipeline = IngestionPipeline(config)
    retriever = HybridRetriever(storage_dir=storage_dir, processed_dir=processed_dir)
    answer_builder = AnswerBuilder()

    @app.post("/v1/ask")
    def ask(request: AskRequest):
        retrieved = retriever.retrieve(request.question)
        answer = answer_builder.answer(request.question, retrieved)
        return {
            "answer": answer.answer,
            "citations": [{"chunk_index": citation.chunk_index, "text": citation.text, "verified": citation.verified} for citation in answer.citations],
            "confidence": {
                "retrieval_confidence": answer.confidence.retrieval_confidence if answer.confidence else 0.0,
                "citation_coverage": answer.confidence.citation_coverage if answer.confidence else 0.0,
                "completeness": answer.confidence.completeness if answer.confidence else 0.0,
                "composite": answer.confidence.composite if answer.confidence else 0.0,
            },
            "retrieved_chunks": [
                {
                    "text": chunk.text,
                    "source": chunk.source,
                    "section_heading": chunk.section_heading,
                    "page_number": chunk.page_number,
                    "dense_score": chunk.dense_score,
                    "sparse_score": chunk.sparse_score,
                    "fused_score": chunk.fused_score,
                    "rerank_score": chunk.rerank_score,
                }
                for chunk in answer.retrieved_chunks
            ],
        }

    @app.get("/v1/documents")
    def documents():
        return {"documents": [
            {"source": chunk.get("source", "unknown")} for chunk in retriever.chunk_store.get_chunks()
        ]}

    @app.post("/v1/ingest")
    def ingest(request: IngestRequest):
        for document in request.documents:
            source = document.get("source", "uploaded")
            text = document.get("text", "")
            path = raw_dir / source
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        pipeline.ingest(list(raw_dir.glob("**/*")))
        return {"status": "ok"}

    return app


app = create_app()
