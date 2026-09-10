"""Unit tests for Phase 5: session memory, Langfuse tracer, Prefect flow, API.

All tests run WITHOUT external services (no Redis, no Langfuse, no Prefect).
Tests exercise:
- InMemorySessionStore: append, get_history, clear, sliding window
- RedisSessionStore: graceful fallback when Redis unavailable
- SessionStore.build_prompt_messages: history interleaving
- LangfuseTracer: no-op when langfuse disabled
- RAGTrace: span methods are no-ops when trace is None
- biome_index_pipeline: importable, run_pipeline_direct available
- FastAPI /v1/chat: multi-turn response schema and session_id
- FastAPI /v1/session/{id} DELETE: clear endpoint
- FastAPI /v1/ask: now accepts session_id and access_scope fields
- FastAPI /v1/ask: trace_id in response (None when Langfuse disabled)
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from biome_rag.memory.session import InMemorySessionStore, RedisSessionStore, get_session_store
from biome_rag.observability.langfuse_tracer import LangfuseTracer, RAGTrace, get_tracer


# ---------------------------------------------------------------------------
# InMemorySessionStore
# ---------------------------------------------------------------------------

class TestInMemorySessionStore:
    def test_append_and_get_history(self) -> None:
        store = InMemorySessionStore()
        store.append("s1", "user", "Hello")
        store.append("s1", "assistant", "Hi there!")
        h = store.get_history("s1")
        assert len(h) == 2
        assert h[0]["role"] == "user"
        assert h[0]["content"] == "Hello"
        assert h[1]["role"] == "assistant"

    def test_sliding_window_trims_oldest(self) -> None:
        store = InMemorySessionStore(window_size=4)
        for i in range(6):
            store.append("s2", "user", f"msg{i}")
        h = store.get_history("s2")
        assert len(h) == 4
        assert h[0]["content"] == "msg2"  # oldest 2 trimmed

    def test_clear_removes_session(self) -> None:
        store = InMemorySessionStore()
        store.append("s3", "user", "test")
        store.clear("s3")
        assert store.get_history("s3") == []

    def test_empty_session_returns_empty_list(self) -> None:
        store = InMemorySessionStore()
        assert store.get_history("nonexistent") == []

    def test_multiple_sessions_isolated(self) -> None:
        store = InMemorySessionStore()
        store.append("a", "user", "session A")
        store.append("b", "user", "session B")
        assert store.get_history("a")[0]["content"] == "session A"
        assert store.get_history("b")[0]["content"] == "session B"

    def test_clear_only_affects_target_session(self) -> None:
        store = InMemorySessionStore()
        store.append("x", "user", "keep")
        store.append("y", "user", "delete me")
        store.clear("y")
        assert len(store.get_history("x")) == 1
        assert store.get_history("y") == []


# ---------------------------------------------------------------------------
# SessionStore.build_prompt_messages
# ---------------------------------------------------------------------------

class TestBuildPromptMessages:
    def test_no_history_returns_just_user_message(self) -> None:
        store = InMemorySessionStore()
        messages = store.build_prompt_messages("fresh", "What is VPN?")
        assert messages == [{"role": "user", "content": "What is VPN?"}]

    def test_system_prompt_prepended(self) -> None:
        store = InMemorySessionStore()
        messages = store.build_prompt_messages("s", "Q?", system_prompt="You are helpful.")
        assert messages[0] == {"role": "system", "content": "You are helpful."}
        assert messages[-1] == {"role": "user", "content": "Q?"}

    def test_history_interleaved(self) -> None:
        store = InMemorySessionStore()
        store.append("s", "user", "first question")
        store.append("s", "assistant", "first answer")
        messages = store.build_prompt_messages("s", "second question")
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["content"] == "second question"


# ---------------------------------------------------------------------------
# RedisSessionStore — fallback path (no Redis running)
# ---------------------------------------------------------------------------

class TestRedisSessionStoreFallback:
    def test_falls_back_to_memory_when_unreachable(self) -> None:
        store = RedisSessionStore(redis_url="redis://127.0.0.1:9999")
        store.append("r1", "user", "hello")
        h = store.get_history("r1")
        assert len(h) == 1
        assert h[0]["content"] == "hello"

    def test_clear_works_in_fallback(self) -> None:
        store = RedisSessionStore(redis_url="redis://127.0.0.1:9999")
        store.append("r2", "user", "data")
        store.clear("r2")
        assert store.get_history("r2") == []

    def test_sliding_window_in_fallback(self) -> None:
        store = RedisSessionStore(redis_url="redis://127.0.0.1:9999", window_size=3)
        for i in range(5):
            store.append("r3", "user", f"msg{i}")
        h = store.get_history("r3")
        assert len(h) == 3

    def test_get_session_store_returns_something(self) -> None:
        # get_session_store() is cached — reset cache to avoid cross-test pollution
        get_session_store.cache_clear()
        store = get_session_store()
        assert store is not None


# ---------------------------------------------------------------------------
# LangfuseTracer — no-op when disabled
# ---------------------------------------------------------------------------

class TestLangfuseTracerNoOp:
    def test_tracer_disabled_by_default(self) -> None:
        get_tracer.cache_clear()
        tracer = LangfuseTracer()
        assert not tracer.is_enabled

    def test_trace_context_yields_rag_trace(self) -> None:
        tracer = LangfuseTracer()
        with tracer.trace(query="test query", session_id="abc") as t:
            assert isinstance(t, RAGTrace)
            assert t.query == "test query"
            assert t.session_id == "abc"

    def test_trace_id_is_none_when_disabled(self) -> None:
        tracer = LangfuseTracer()
        with tracer.trace(query="q") as t:
            assert t.trace_id is None

    def test_span_methods_are_no_ops(self) -> None:
        """All span methods must not raise when Langfuse is disabled."""
        tracer = LangfuseTracer()
        with tracer.trace(query="q") as t:
            t.span_retrieval([], latency_ms=10.0)
            t.span_reranking([], latency_ms=5.0)
            t.span_generation(None, latency_ms=50.0)
            t.update_output("answer", 0.7)

    def test_no_op_trace_returns_rag_trace(self) -> None:
        tracer = LangfuseTracer()
        t = tracer.no_op_trace("q", session_id="xyz")
        assert isinstance(t, RAGTrace)
        assert t.trace_id is None


# ---------------------------------------------------------------------------
# RAGTrace — span helpers with mock objects
# ---------------------------------------------------------------------------

class TestRAGTraceSpans:
    def _make_chunk(self, score: float = 0.8):
        from types import SimpleNamespace  # noqa: PLC0415
        return SimpleNamespace(
            source="doc.pdf",
            fused_score=score,
            dense_score=score,
            sparse_score=0.3,
            rerank_score=score,
        )

    def test_span_retrieval_no_crash_with_none_trace(self) -> None:
        t = RAGTrace(lf_trace=None, query="q", session_id=None)
        t.span_retrieval([self._make_chunk()], latency_ms=20.0)

    def test_span_reranking_no_crash_with_none_trace(self) -> None:
        t = RAGTrace(lf_trace=None, query="q", session_id=None)
        t.span_reranking([self._make_chunk()], latency_ms=5.0)

    def test_span_generation_no_crash_with_none_trace(self) -> None:
        from types import SimpleNamespace  # noqa: PLC0415
        t = RAGTrace(lf_trace=None, query="q", session_id=None)
        resp = SimpleNamespace(answer="hello", confidence=None, citations=[])
        t.span_generation(resp, latency_ms=100.0)

    def test_update_output_no_crash_with_none_trace(self) -> None:
        t = RAGTrace(lf_trace=None, query="q", session_id=None)
        t.update_output("The answer is 42.", 0.88)


# ---------------------------------------------------------------------------
# Prefect flow — importable, shim decorators work without Prefect
# ---------------------------------------------------------------------------

class TestPrefectFlow:
    def test_biome_index_pipeline_importable(self) -> None:
        from biome_rag.flows.index_flow import biome_index_pipeline  # noqa: PLC0415
        assert callable(biome_index_pipeline)

    def test_run_pipeline_direct_importable(self) -> None:
        from biome_rag.flows.index_flow import run_pipeline_direct  # noqa: PLC0415
        assert callable(run_pipeline_direct)

    def test_run_pipeline_direct_empty_dir(self, tmp_path) -> None:
        from biome_rag.flows.index_flow import run_pipeline_direct  # noqa: PLC0415
        result = run_pipeline_direct(
            raw_dir=str(tmp_path / "raw"),
            processed_dir=str(tmp_path / "processed"),
            storage_dir=str(tmp_path / "storage"),
            use_docling=False,
            use_qdrant=False,
        )
        assert result.total_chunks == 0

    def test_run_pipeline_direct_with_files(self, tmp_path) -> None:
        from biome_rag.flows.index_flow import run_pipeline_direct  # noqa: PLC0415
        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "notes.txt").write_text(
            "Security policy: All employees must use MFA.\n" * 10, encoding="utf-8"
        )
        result = run_pipeline_direct(
            raw_dir=str(raw),
            processed_dir=str(tmp_path / "processed"),
            storage_dir=str(tmp_path / "storage"),
            use_docling=False,
            use_qdrant=False,
        )
        assert result.total_chunks > 0
        assert result.bm25_docs_indexed > 0


# ---------------------------------------------------------------------------
# FastAPI — Phase 5 endpoints
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(tmp_path):
    from biome_rag.api.app import create_app  # noqa: PLC0415
    # Reset singletons so each test gets a fresh InMemorySessionStore
    from biome_rag.memory.session import get_session_store  # noqa: PLC0415
    from biome_rag.observability.langfuse_tracer import get_tracer  # noqa: PLC0415
    get_session_store.cache_clear()
    get_tracer.cache_clear()
    app = create_app(
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
        storage_dir=tmp_path / "storage",
    )
    return TestClient(app, raise_server_exceptions=False)


class TestPhase5APIEndpoints:
    def test_ask_accepts_session_id(self, client) -> None:
        resp = client.post("/v1/ask", json={
            "question": "What is the VPN policy?",
            "session_id": "test-session-001",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "answer" in body
        assert "trace_id" in body       # Phase 5 field (None when Langfuse off)

    def test_ask_accepts_access_scope(self, client) -> None:
        resp = client.post("/v1/ask", json={
            "question": "What is MFA?",
            "access_scope": ["internal"],
        })
        assert resp.status_code == 200

    def test_chat_returns_correct_schema(self, client) -> None:
        resp = client.post("/v1/chat", json={
            "message": "What is the onboarding process?",
            "session_id": "chat-session-001",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "answer" in body
        assert "session_id" in body
        assert body["session_id"] == "chat-session-001"
        assert "citations" in body
        assert "confidence" in body
        assert "history_length" in body
        assert body["history_length"] >= 1  # at least this turn stored

    def test_chat_multi_turn_increments_history(self, client) -> None:
        sid = "multi-turn-test"
        r1 = client.post("/v1/chat", json={"message": "First question", "session_id": sid})
        r2 = client.post("/v1/chat", json={"message": "Follow up question", "session_id": sid})
        assert r1.status_code == 200
        assert r2.status_code == 200
        h1 = r1.json()["history_length"]
        h2 = r2.json()["history_length"]
        assert h2 > h1   # second turn has more history

    def test_session_clear_returns_200(self, client) -> None:
        sid = "to-be-cleared"
        client.post("/v1/chat", json={"message": "Hello", "session_id": sid})
        resp = client.delete(f"/v1/session/{sid}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "cleared"
        assert body["session_id"] == sid

    def test_session_clear_then_chat_starts_fresh(self, client) -> None:
        sid = "fresh-after-clear"
        client.post("/v1/chat", json={"message": "Turn 1", "session_id": sid})
        client.delete(f"/v1/session/{sid}")
        r = client.post("/v1/chat", json={"message": "Turn 2", "session_id": sid})
        # After clear, history should only have the new turn
        assert r.json()["history_length"] == 2   # user + assistant for this turn

    def test_root_lists_chat_endpoint(self, client) -> None:
        resp = client.get("/")
        body = resp.json()
        endpoints = body.get("endpoints", [])
        assert any("chat" in e for e in endpoints)

    def test_root_version_is_0_5_or_higher(self, client) -> None:
        resp = client.get("/")
        version = resp.json()["version"]
        assert version >= "0.5.0"

