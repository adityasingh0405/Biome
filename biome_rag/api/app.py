from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from biome_rag.generation.answering import AnswerBuilder
from biome_rag.indexing import IndexBuilder
from biome_rag.ingestion.models import IngestionConfig
from biome_rag.ingestion.pipeline import IngestionPipeline
from biome_rag.memory import get_session_store
from biome_rag.observability import get_tracer
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
    session_id: str | None = None      # Phase 5: optional session for memory
    access_scope: list[str] | None = None  # Phase 3: ACL filter


class ChatRequest(BaseModel):
    """Multi-turn chat request (Phase 5)."""
    message: str
    session_id: str                    # required for multi-turn memory
    retrieval_mode: str = "hybrid"
    access_scope: list[str] | None = None


class ChatResponse(BaseModel):
    """Multi-turn chat response (Phase 5)."""
    answer: str
    session_id: str
    citations: list[dict]
    confidence: dict
    retrieved_chunks: list[dict]
    trace_id: str | None = None        # Langfuse trace link
    history_length: int = 0


class IngestRequest(BaseModel):
    documents: list[dict[str, Any]]


class DirectoryIngestRequest(BaseModel):
    directory_path: str
    recursive: bool = True


class DirectTextIngestRequest(BaseModel):
    title: str
    content: str


class CompareRequest(BaseModel):
    question: str


class EvaluateRequest(BaseModel):
    """Phase 6: trigger evaluation via the API (Phase 6)."""
    golden_path: str | None = None      # path to JSONL/JSON on the server
    records: list[dict] | None = None   # inline Q&A records (alternative)
    retrieval_mode: str = "hybrid"
    threshold: str = "default"          # "default" | "strict" | "lenient"
    question_types: list[str] | None = None


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
    index_builder = IndexBuilder(
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        storage_dir=storage_dir,
        use_docling=False,
        use_qdrant=True,
    )
    retriever = HybridRetriever(storage_dir=storage_dir, processed_dir=processed_dir)
    answer_builder = AnswerBuilder()
    session_store = get_session_store()   # Phase 5: Redis-backed sliding window
    tracer = get_tracer()                 # Phase 5: Langfuse observability

    def _refresh_retriever():
        nonlocal retriever
        retriever = HybridRetriever(storage_dir=storage_dir, processed_dir=processed_dir)

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
            "bge_sparse_score": round(chunk.bge_sparse_score, 4),
            "token_count": chunk.token_count,
            "source_type": chunk.source_type,
        }

    def _build_answer_payload(
        question: str,
        mode: str,
        access_scope: list[str] | None = None,
        rag_trace=None,
    ) -> dict:
        import time as _time  # noqa: PLC0415
        if not question.strip():
            return {
                "answer": "Please provide a question.",
                "citations": [],
                "confidence": {"retrieval_confidence": 0.0, "citation_coverage": 0.0, "completeness": 0.0, "composite": 0.0},
                "retrieved_chunks": [],
                "trace_id": None,
            }

        t0 = _time.perf_counter()
        try:
            retrieved = retriever.retrieve(question, retrieval_mode=mode, access_scope=access_scope)
        except TypeError:
            retrieved = retriever.retrieve(question, retrieval_mode=mode)
        retrieval_ms = (_time.perf_counter() - t0) * 1000

        if rag_trace:
            rag_trace.span_retrieval(retrieved, latency_ms=retrieval_ms, retrieval_mode=mode)

        t0 = _time.perf_counter()
        ans = answer_builder.answer(question, retrieved)
        gen_ms = (_time.perf_counter() - t0) * 1000

        if rag_trace:
            rag_trace.span_generation(ans, latency_ms=gen_ms)
            confidence_composite = ans.confidence.composite if ans.confidence else 0.0
            rag_trace.update_output(ans.answer, confidence_composite)

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
            "trace_id": getattr(rag_trace, "trace_id", None) if rag_trace else None,
        }

    # -----------------------------------------------------------------------
    # Routes
    # -----------------------------------------------------------------------

    @app.get("/", tags=["meta"])
    def root():
        return {
            "service": "Biome RAG",
            "version": "0.6.0",
            "status": "ok",
            "endpoints": [
                "POST /v1/ask",
                "POST /v1/chat",
                "POST /v1/compare",
                "GET  /v1/documents",
                "POST /v1/evaluate",        # Phase 6: evaluation harness
                "DELETE /v1/session/{id}",
                "POST /v1/index/files",
                "POST /v1/index/upload",
                "POST /v1/index/text",
                "POST /v1/ingest",
                "POST /v1/ingest/upload",
                "POST /v1/ingest/directory",
                "POST /v1/ingest/text",
                "GET  /v1/health",
            ],
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
        """Answer a question using the RAG pipeline (with optional Langfuse tracing)."""
        with tracer.trace(query=request.question, session_id=request.session_id) as t:
            return _build_answer_payload(
                request.question,
                request.retrieval_mode,
                access_scope=request.access_scope,
                rag_trace=t,
            )

    @app.post("/v1/chat", tags=["query"], response_model=ChatResponse)
    def chat(request: ChatRequest):
        """Multi-turn conversational RAG with Redis session memory (Phase 5).

        The session history is prepended to the LLM context on each turn so the
        model can reference previous exchanges. History is stored in Redis and
        expires after ``REDIS_SESSION_TTL`` seconds of inactivity.
        """
        history = session_store.get_history(request.session_id)

        # Build augmented question from history (last 3 turns for context)
        recent = history[-6:]  # 3 user + 3 assistant turns
        history_ctx = ""
        if recent:
            history_ctx = "\n".join(
                f"{m['role'].upper()}: {m['content']}" for m in recent
            ) + "\n\nCURRENT QUESTION: "
        augmented_q = history_ctx + request.message

        with tracer.trace(query=request.message, session_id=request.session_id, name="chat_pipeline") as t:
            payload = _build_answer_payload(
                augmented_q,
                request.retrieval_mode,
                access_scope=request.access_scope,
                rag_trace=t,
            )

        # Persist this turn to session memory
        session_store.append(request.session_id, "user", request.message)
        session_store.append(request.session_id, "assistant", payload["answer"])
        updated_history = session_store.get_history(request.session_id)

        return ChatResponse(
            answer=payload["answer"],
            session_id=request.session_id,
            citations=payload["citations"],
            confidence=payload["confidence"],
            retrieved_chunks=payload["retrieved_chunks"],
            trace_id=payload.get("trace_id"),
            history_length=len(updated_history),
        )

    @app.delete("/v1/session/{session_id}", tags=["query"])
    def clear_session(session_id: str):
        """Clear conversation history for a session (Phase 5)."""
        session_store.clear(session_id)
        return {"status": "cleared", "session_id": session_id}

    @app.post("/v1/compare", tags=["query"])
    def compare(request: CompareRequest):
        """Run question through hybrid and dense-only retrieval side by side."""
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
            if isinstance(chunk, dict):
                src = chunk.get("source", "unknown")
            else:
                src = getattr(chunk, "source", "unknown")
            seen[src] = seen.get(src, 0) + 1
        return {
            "total_chunks": len(chunks),
            "documents": [{"source": src, "chunk_count": count} for src, count in sorted(seen.items())],
        }

    @app.post("/v1/ingest", tags=["index"])
    def ingest(request: IngestRequest):
        """Ingest new documents into the pipeline."""
        for document in request.documents:
            source = document.get("source", "uploaded.txt")
            text = document.get("text", "")
            path = raw_dir / source
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        all_paths = [p for p in raw_dir.glob("**/*") if p.is_file()]
        chunks, summary = pipeline.ingest(all_paths)
        _refresh_retriever()
        return {
            "status": "ok",
            "chunks_created": summary.chunks_created,
            "duplicates_skipped": summary.duplicates_skipped,
            "chunks_per_strategy": summary.chunks_per_strategy,
        }

    @app.post("/v1/ingest/upload", tags=["index"])
    async def ingest_upload(files: list[UploadFile] = File(...)):
        """Upload and index one or more document files (.pdf, .md, .txt, .html, .json, .csv, code)."""
        uploaded_paths: list[Path] = []
        for file in files:
            safe_name = Path(file.filename or "uploaded_file.txt").name
            dest = raw_dir / safe_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            uploaded_paths.append(dest)

        all_paths = [p for p in raw_dir.glob("**/*") if p.is_file()]
        chunks, summary = pipeline.ingest(all_paths)
        _refresh_retriever()
        return {
            "status": "ok",
            "files_uploaded": [p.name for p in uploaded_paths],
            "total_chunks": summary.chunks_created,
            "duplicates_skipped": summary.duplicates_skipped,
            "chunks_per_strategy": summary.chunks_per_strategy,
        }

    @app.post("/v1/ingest/directory", tags=["index"])
    def ingest_directory(request: DirectoryIngestRequest):
        """Crawl and index any directory on the local system."""
        dir_path = Path(request.directory_path)
        if not dir_path.exists() or not dir_path.is_dir():
            raise HTTPException(status_code=400, detail=f"Directory '{dir_path}' does not exist.")

        pattern = "**/*" if request.recursive else "*"
        found_files = [p for p in dir_path.glob(pattern) if p.is_file()]
        if not found_files:
            raise HTTPException(status_code=400, detail=f"No files found in '{dir_path}'.")

        # Copy or index directly
        chunks, summary = pipeline.ingest(found_files)
        _refresh_retriever()
        return {
            "status": "ok",
            "directory": str(dir_path),
            "files_found": len(found_files),
            "total_chunks": summary.chunks_created,
            "duplicates_skipped": summary.duplicates_skipped,
            "chunks_per_strategy": summary.chunks_per_strategy,
        }

    @app.post("/v1/ingest/text", tags=["index"])
    def ingest_text(request: DirectTextIngestRequest):
        """Ingest raw text directly with a custom document title."""
        safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", request.title.strip()) + ".txt"
        dest = raw_dir / safe_name
        dest.write_text(request.content, encoding="utf-8")
        all_paths = [p for p in raw_dir.glob("**/*") if p.is_file()]
        chunks, summary = pipeline.ingest(all_paths)
        _refresh_retriever()
        return {
            "status": "ok",
            "document": safe_name,
            "total_chunks": summary.chunks_created,
        }

    # -----------------------------------------------------------------------
    # /v1/index/* routes — Phase 4 IndexBuilder-backed endpoints
    # These run Phase 1→2→3 end-to-end and are the preferred ingest path.
    # -----------------------------------------------------------------------

    @app.post("/v1/index/files", tags=["index"])
    def index_files(request: DirectoryIngestRequest):
        """Full Phase 1→2→3 indexing from a local directory (IndexBuilder path)."""
        dir_path = Path(request.directory_path)
        if not dir_path.exists() or not dir_path.is_dir():
            raise HTTPException(status_code=400, detail=f"Directory '{dir_path}' does not exist.")
        pattern = "**/*" if request.recursive else "*"
        found = [p for p in dir_path.glob(pattern) if p.is_file()]
        if not found:
            raise HTTPException(status_code=400, detail=f"No files found in '{dir_path}'.")
        result = index_builder.run(paths=found, source_type="document")
        _refresh_retriever()
        return {"status": "ok", **result.to_dict()}

    @app.post("/v1/index/upload", tags=["index"])
    async def index_upload(files: list[UploadFile] = File(...)):
        """Upload files and run full Phase 1→2→3 indexing (IndexBuilder path)."""
        uploaded: list[Path] = []
        for file in files:
            safe_name = Path(file.filename or "uploaded_file.txt").name
            dest = raw_dir / safe_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as buf:
                shutil.copyfileobj(file.file, buf)
            uploaded.append(dest)
        result = index_builder.run(paths=uploaded, source_type="document")
        _refresh_retriever()
        return {
            "status": "ok",
            "files_uploaded": [p.name for p in uploaded],
            **result.to_dict(),
        }

    @app.post("/v1/index/text", tags=["index"])
    def index_text(request: DirectTextIngestRequest):
        """Ingest raw text via IndexBuilder (Phase 1→2→3)."""
        safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", request.title.strip()) + ".txt"
        dest = raw_dir / safe_name
        dest.write_text(request.content, encoding="utf-8")
        result = index_builder.run(paths=[dest], source_type="document")
        _refresh_retriever()
        return {"status": "ok", "document": safe_name, **result.to_dict()}

    # -----------------------------------------------------------------------
    # /v1/evaluate — Phase 6 evaluation harness
    # -----------------------------------------------------------------------

    @app.post("/v1/evaluate", tags=["evaluation"])
    def evaluate(request: EvaluateRequest):
        """Run the Phase 6 EvaluationHarness and return aggregate + per-question scores.

        Accepts either a server-side golden_path (JSONL/JSON) or inline records.
        """
        import tempfile  # noqa: PLC0415
        from biome_rag.evaluation.harness import EvaluationHarness  # noqa: PLC0415
        from biome_rag.evaluation.extended_metrics import EvalThresholds  # noqa: PLC0415

        threshold_map = {
            "default": EvalThresholds(),
            "strict":  EvalThresholds.strict(),
            "lenient": EvalThresholds.lenient(),
        }
        thresholds = threshold_map.get(request.threshold, EvalThresholds())

        # Resolve golden path
        if request.golden_path:
            golden_path = Path(request.golden_path)
            if not golden_path.exists():
                raise HTTPException(status_code=400, detail=f"golden_path not found: {golden_path}")
        elif request.records:
            # Write inline records to a temp JSONL file
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
            )
            for rec in request.records:
                tmp.write(json.dumps(rec) + "\n")
            tmp.close()
            golden_path = Path(tmp.name)
        else:
            raise HTTPException(status_code=400, detail="Provide golden_path or inline records.")

        try:
            harness = EvaluationHarness(
                processed_dir=processed_dir,
                storage_dir=storage_dir,
                reports_dir=storage_dir / "eval_reports",
                retrieval_mode=request.retrieval_mode,
                thresholds=thresholds,
            )
            report = harness.run(golden_path, question_types=request.question_types)
            _, md_path = harness.write_report(report)
            violations = harness.check_quality_gate(report, thresholds)
        except HTTPException:
            raise  # re-propagate 400s etc. unchanged
        except Exception as exc:
            # Index not built yet, pipeline init failure, or report write failure.
            # Use JSONResponse directly to avoid double-exception issues in test transport.
            from starlette.responses import JSONResponse as _JSONResponse  # noqa: PLC0415
            return _JSONResponse(
                status_code=503,
                content={"detail": f"Evaluation failed — index may not be built yet: {exc}"},
            )

        return {
            "status": "ok",
            "aggregate": report.aggregate.to_dict(),
            "violations": [str(v) for v in violations],
            "gate_passed": len(violations) == 0,
            "report_md": str(md_path),
            "rows_count": len(report.rows),
        }

    return app


app = create_app()
