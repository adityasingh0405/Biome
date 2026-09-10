"""Langfuse observability tracer — Phase 5.

Wraps every RAG pipeline call in a Langfuse trace with structured spans:
  - ``retrieval``  — BM25 + dense search + RRF fusion timing and top-k scores
  - ``reranking``  — cross-encoder reranking latency and score delta
  - ``generation`` — LLM call latency, token counts, answer length

Design:
  - Graceful no-op: if Langfuse is not installed or ``langfuse_enabled=False``
    in Settings, all trace/span calls are silently skipped. The caller code
    path is identical whether tracing is on or off.
  - Thread-safe: each ``RAGTrace`` object holds a single Langfuse ``trace``
    context and is NOT shared across threads.
  - The trace ID is returned in the API response so it can be linked from the
    Streamlit dashboard to the Langfuse UI.

Usage::

    tracer = get_tracer()              # singleton, reads Settings

    with tracer.trace(session_id="abc123", query="VPN policy") as t:
        chunks = retriever.retrieve(query)
        t.span_retrieval(chunks, latency_ms=42)

        ranked = reranker.rerank(chunks)
        t.span_reranking(ranked, latency_ms=12)

        answer = builder.answer(query, ranked)
        t.span_generation(answer, latency_ms=380)

    print(t.trace_id)   # link to http://localhost:3000

References:
    https://langfuse.com/docs/sdk/python/low-level-sdk
    DECISIONS.md D020
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Generator

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from biome_rag.retrieval.models import RankedChunk
    from biome_rag.generation.answering import AnswerResponse

# langfuse is optional
try:
    from langfuse import Langfuse as _Langfuse  # type: ignore
    _LANGFUSE_AVAILABLE = True
except ImportError:
    _Langfuse = None  # type: ignore
    _LANGFUSE_AVAILABLE = False
    logger.debug("langfuse not installed — observability disabled.")


# ---------------------------------------------------------------------------
# RAGTrace: per-request trace context
# ---------------------------------------------------------------------------

class RAGTrace:
    """Holds a single Langfuse trace for one RAG request.

    All span methods are no-ops when Langfuse is disabled.
    """

    def __init__(
        self,
        lf_trace: Any | None,
        query: str,
        session_id: str | None,
    ) -> None:
        self._trace = lf_trace
        self.query = query
        self.session_id = session_id
        self.trace_id: str | None = getattr(lf_trace, "id", None) if lf_trace else None
        self._spans: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Span helpers
    # ------------------------------------------------------------------

    def span_retrieval(
        self,
        chunks: list[Any],
        latency_ms: float = 0.0,
        retrieval_mode: str = "hybrid",
    ) -> None:
        """Record retrieval span with top-5 chunk scores."""
        if self._trace is None:
            return
        try:
            top_scores = [
                {
                    "source": getattr(c, "source", "?"),
                    "fused_score": round(getattr(c, "fused_score", 0.0), 4),
                    "dense_score": round(getattr(c, "dense_score", 0.0), 4),
                    "sparse_score": round(getattr(c, "sparse_score", 0.0), 4),
                }
                for c in chunks[:5]
            ]
            self._trace.span(
                name="retrieval",
                metadata={
                    "retrieval_mode": retrieval_mode,
                    "chunks_returned": len(chunks),
                    "top_scores": top_scores,
                    "latency_ms": round(latency_ms, 1),
                },
            )
        except Exception as exc:
            logger.debug("Langfuse retrieval span failed: %s", exc)

    def span_reranking(
        self,
        chunks: list[Any],
        latency_ms: float = 0.0,
    ) -> None:
        """Record reranking span with score statistics."""
        if self._trace is None:
            return
        try:
            rerank_scores = [round(getattr(c, "rerank_score", 0.0), 4) for c in chunks[:5]]
            self._trace.span(
                name="reranking",
                metadata={
                    "chunks_reranked": len(chunks),
                    "top_rerank_scores": rerank_scores,
                    "latency_ms": round(latency_ms, 1),
                },
            )
        except Exception as exc:
            logger.debug("Langfuse reranking span failed: %s", exc)

    def span_generation(
        self,
        answer_response: Any,
        latency_ms: float = 0.0,
        model: str = "unknown",
    ) -> None:
        """Record LLM generation span with token estimate and confidence."""
        if self._trace is None:
            return
        try:
            answer_text = getattr(answer_response, "answer", "")
            confidence = getattr(answer_response, "confidence", None)
            composite = round(getattr(confidence, "composite", 0.0), 4) if confidence else 0.0
            # Rough token estimate (word count × 1.3 heuristic)
            token_estimate = int(len(answer_text.split()) * 1.3)
            self._trace.span(
                name="generation",
                metadata={
                    "model": model,
                    "answer_length_chars": len(answer_text),
                    "token_estimate": token_estimate,
                    "confidence_composite": composite,
                    "citations_count": len(getattr(answer_response, "citations", [])),
                    "latency_ms": round(latency_ms, 1),
                },
            )
        except Exception as exc:
            logger.debug("Langfuse generation span failed: %s", exc)

    def update_output(self, answer: str, confidence: float) -> None:
        """Set the trace-level output for Langfuse score tracking."""
        if self._trace is None:
            return
        try:
            self._trace.update(
                output=answer[:500],  # truncate for Langfuse UI
                metadata={"confidence_composite": round(confidence, 4)},
            )
        except Exception as exc:
            logger.debug("Langfuse trace update failed: %s", exc)


# ---------------------------------------------------------------------------
# LangfuseTracer — manages the Langfuse client singleton
# ---------------------------------------------------------------------------

class LangfuseTracer:
    """Creates and manages Langfuse traces.

    Gracefully no-ops when Langfuse is disabled or unreachable.
    """

    def __init__(self) -> None:
        from biome_rag.config import get_settings  # noqa: PLC0415
        self.settings = get_settings()
        self._client: Any = None
        self._enabled = self.settings.langfuse_enabled and _LANGFUSE_AVAILABLE
        if self._enabled:
            self._init_client()

    def _init_client(self) -> None:
        try:
            self._client = _Langfuse(
                public_key=self.settings.langfuse_public_key,
                secret_key=self.settings.langfuse_secret_key,
                host=self.settings.langfuse_host,
            )
            logger.info("Langfuse tracer connected to %s", self.settings.langfuse_host)
        except Exception as exc:
            logger.warning("Langfuse client init failed: %s — tracing disabled.", exc)
            self._client = None
            self._enabled = False

    @property
    def is_enabled(self) -> bool:
        return self._enabled and self._client is not None

    @contextmanager
    def trace(
        self,
        query: str,
        session_id: str | None = None,
        name: str = "rag_pipeline",
    ) -> Generator[RAGTrace, None, None]:
        """Context manager that yields a ``RAGTrace``.

        Example::

            with tracer.trace(query="what is VPN?", session_id="abc") as t:
                chunks = retriever.retrieve(query)
                t.span_retrieval(chunks, latency_ms=50)
            # trace automatically flushed on exit
        """
        lf_trace = None
        if self.is_enabled:
            try:
                lf_trace = self._client.trace(
                    name=name,
                    input=query,
                    session_id=session_id,
                    tags=["rag", "biome"],
                )
            except Exception as exc:
                logger.debug("Failed to create Langfuse trace: %s", exc)

        rag_trace = RAGTrace(lf_trace=lf_trace, query=query, session_id=session_id)
        t0 = time.perf_counter()
        try:
            yield rag_trace
        finally:
            if lf_trace is not None:
                try:
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    lf_trace.update(metadata={"total_latency_ms": round(elapsed_ms, 1)})
                    self._client.flush()
                except Exception as exc:
                    logger.debug("Langfuse trace finalization failed: %s", exc)

    def no_op_trace(self, query: str, session_id: str | None = None) -> RAGTrace:
        """Return a no-op RAGTrace (Langfuse disabled path)."""
        return RAGTrace(lf_trace=None, query=query, session_id=session_id)


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_tracer() -> LangfuseTracer:
    """Return the cached singleton LangfuseTracer."""
    return LangfuseTracer()
