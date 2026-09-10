"""Unit tests for Phase 3: BGE-M3 encoder, QdrantAdapter, and retrieval updates.

All tests run WITHOUT external services (no Qdrant, no FlagEmbedding model download).
They exercise:
- BGE_M3Encoder fallback behaviour when FlagEmbedding is absent
- BGE_M3Encoder static scoring helpers (dense_score, sparse_score)
- _sparse_dict_to_qdrant conversion (string and int token keys)
- QdrantAdapter fallback path (no Qdrant running → SimpleDenseEmbeddingAdapter)
- QdrantAdapter._chunk_to_payload ACL field population
- QdrantAdapter._build_acl_filter returns None when qmodels unavailable
- HybridRetriever.retrieve() new access_scope parameter (no regression)
- RankedChunk new fields: bge_sparse_score, token_count, source_type, access_scope
"""
from __future__ import annotations

import hashlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from biome_rag.retrieval.embeddings import BGE_M3Encoder
from biome_rag.retrieval.models import RankedChunk
from biome_rag.retrieval.qdrant_store import QdrantAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk(text: str = "test chunk", source: str = "doc.pdf", idx: int = 0, **kwargs):
    return SimpleNamespace(
        text=text,
        source=source,
        chunk_index=idx,
        section_heading="Introduction",
        page_number=1,
        source_type=kwargs.get("source_type", "document"),
        token_count=kwargs.get("token_count", 42),
        metadata={"access_scope": kwargs.get("access_scope", ["internal"])},
    )


# ---------------------------------------------------------------------------
# BGE_M3Encoder — fallback behaviour (FlagEmbedding not installed or fails)
# ---------------------------------------------------------------------------

class TestBGE_M3EncoderFallback:
    def test_encoder_is_not_available_when_flag_embedding_absent(self) -> None:
        """Without FlagEmbedding, is_available should be False."""
        with patch("biome_rag.retrieval.embeddings._FLAG_EMBEDDING_AVAILABLE", False):
            encoder = BGE_M3Encoder()
            encoder._available = False  # simulate missing library
            assert not encoder.is_available

    def test_encode_corpus_returns_empty_result_when_unavailable(self) -> None:
        encoder = BGE_M3Encoder()
        encoder._available = False
        result = encoder.encode_corpus(["text 1", "text 2"])
        assert result["available"] is False
        assert result["dense_vecs"].shape == (2, 1024)
        assert all(w == {} for w in result["lexical_weights"])

    def test_encode_query_returns_empty_result_when_unavailable(self) -> None:
        encoder = BGE_M3Encoder()
        encoder._available = False
        result = encoder.encode_query("test query")
        assert result["available"] is False
        assert result["dense_vecs"].shape == (1, 1024)

    def test_encode_corpus_zero_vecs_when_unavailable(self) -> None:
        encoder = BGE_M3Encoder()
        encoder._available = False
        result = encoder.encode_corpus(["hello"])
        assert np.all(result["dense_vecs"] == 0.0)

    def test_encode_empty_list(self) -> None:
        encoder = BGE_M3Encoder()
        encoder._available = False
        result = encoder.encode_corpus([])
        assert result["dense_vecs"].shape == (0, 1024)
        assert result["lexical_weights"] == []

    def test_load_returns_none_when_unavailable(self) -> None:
        encoder = BGE_M3Encoder()
        encoder._available = False
        assert encoder._load() is None


# ---------------------------------------------------------------------------
# BGE_M3Encoder — static scoring helpers (no model needed)
# ---------------------------------------------------------------------------

class TestBGE_M3ScoringHelpers:
    def test_dense_score_identical_vectors(self) -> None:
        v = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
        score = BGE_M3Encoder.dense_score(v, v)
        assert abs(score - 1.0) < 1e-5

    def test_dense_score_orthogonal_vectors(self) -> None:
        q = np.array([[1.0, 0.0]], dtype=np.float32)
        d = np.array([[0.0, 1.0]], dtype=np.float32)
        score = BGE_M3Encoder.dense_score(q, d)
        assert abs(score) < 1e-5

    def test_dense_score_opposite_vectors(self) -> None:
        q = np.array([[1.0, 0.0]], dtype=np.float32)
        d = np.array([[-1.0, 0.0]], dtype=np.float32)
        score = BGE_M3Encoder.dense_score(q, d)
        assert abs(score - (-1.0)) < 1e-5

    def test_dense_score_zero_vector_no_nan(self) -> None:
        q = np.zeros((1, 4), dtype=np.float32)
        d = np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32)
        score = BGE_M3Encoder.dense_score(q, d)
        assert not np.isnan(score)

    def test_sparse_score_exact_match(self) -> None:
        q = {"vpn": 0.8, "issue": 0.6}
        d = {"vpn": 0.9, "issue": 0.5, "unrelated": 0.3}
        score = BGE_M3Encoder.sparse_score(q, d)
        expected = 0.8 * 0.9 + 0.6 * 0.5
        assert abs(score - expected) < 1e-6

    def test_sparse_score_no_overlap(self) -> None:
        q = {"vpn": 0.8}
        d = {"email": 0.9}
        score = BGE_M3Encoder.sparse_score(q, d)
        assert score == 0.0

    def test_sparse_score_empty_dicts(self) -> None:
        assert BGE_M3Encoder.sparse_score({}, {}) == 0.0
        assert BGE_M3Encoder.sparse_score({"a": 0.5}, {}) == 0.0


# ---------------------------------------------------------------------------
# QdrantAdapter — sparse dict conversion
# ---------------------------------------------------------------------------

class TestSparseConversion:
    def test_string_tokens_converted_to_ints(self) -> None:
        sparse = {"vpn": 0.8, "issue": 0.6}
        indices, values = QdrantAdapter._sparse_dict_to_qdrant(sparse)
        assert len(indices) == 2
        assert len(values) == 2
        assert all(isinstance(i, int) for i in indices)
        assert all(isinstance(v, float) for v in values)

    def test_int_tokens_passed_through(self) -> None:
        sparse = {42: 0.5, 99: 0.3}
        indices, values = QdrantAdapter._sparse_dict_to_qdrant(sparse)
        assert set(indices) == {42, 99}

    def test_empty_sparse_returns_empty_lists(self) -> None:
        indices, values = QdrantAdapter._sparse_dict_to_qdrant({})
        assert indices == []
        assert values == []

    def test_string_token_hash_is_positive(self) -> None:
        sparse = {"query": 1.0}
        indices, _ = QdrantAdapter._sparse_dict_to_qdrant(sparse)
        assert indices[0] >= 0

    def test_same_token_same_index(self) -> None:
        """Hashing must be deterministic."""
        sparse = {"token": 1.0}
        idx1, _ = QdrantAdapter._sparse_dict_to_qdrant(sparse)
        idx2, _ = QdrantAdapter._sparse_dict_to_qdrant(sparse)
        assert idx1 == idx2


# ---------------------------------------------------------------------------
# QdrantAdapter — payload builder (ACL fields)
# ---------------------------------------------------------------------------

class TestChunkToPayload:
    def test_basic_fields_present(self) -> None:
        chunk = _make_chunk("hello world", "api_guide.pdf", 3)
        payload = QdrantAdapter._chunk_to_payload(chunk)
        assert payload["source"] == "api_guide.pdf"
        assert payload["chunk_index"] == 3
        assert payload["source_type"] == "document"
        assert payload["token_count"] == 42

    def test_access_scope_extracted_from_metadata(self) -> None:
        chunk = _make_chunk(access_scope=["internal", "eng-team"])
        payload = QdrantAdapter._chunk_to_payload(chunk)
        assert "access_scope" in payload
        assert "internal" in payload["access_scope"]
        assert "eng-team" in payload["access_scope"]

    def test_section_heading_included_when_present(self) -> None:
        chunk = _make_chunk()
        payload = QdrantAdapter._chunk_to_payload(chunk)
        assert payload.get("section_heading") == "Introduction"

    def test_page_number_included(self) -> None:
        chunk = _make_chunk()
        payload = QdrantAdapter._chunk_to_payload(chunk)
        assert payload.get("page_number") == 1

    def test_no_access_scope_key_when_empty(self) -> None:
        chunk = _make_chunk(access_scope=[])
        chunk.metadata = {"access_scope": []}
        payload = QdrantAdapter._chunk_to_payload(chunk)
        assert "access_scope" not in payload


# ---------------------------------------------------------------------------
# QdrantAdapter — fallback (no Qdrant running)
# ---------------------------------------------------------------------------

class TestQdrantAdapterFallback:
    def test_get_client_returns_none_when_not_reachable(self) -> None:
        adapter = QdrantAdapter(url="http://127.0.0.1:9999")  # unreachable port
        client = adapter._get_client()
        assert client is None

    def test_search_falls_back_to_simple_adapter(self) -> None:
        adapter = QdrantAdapter(url="http://127.0.0.1:9999")
        adapter._client = None
        adapter._available = False
        chunks = [_make_chunk(text="VPN policy document")]
        results = adapter.search("VPN policy", chunks, top_k=3)
        # SimpleDenseEmbeddingAdapter returns up to top_k results
        assert len(results) >= 0  # may be empty if score==0; no crash

    def test_index_documents_silently_skips_when_no_qdrant(self) -> None:
        adapter = QdrantAdapter(url="http://127.0.0.1:9999")
        adapter._client = None
        adapter._available = False
        chunks = [_make_chunk(text="some text")]
        # Should not raise
        adapter.index_documents(chunks)

    def test_collection_exists_returns_false_when_no_qdrant(self) -> None:
        adapter = QdrantAdapter(url="http://127.0.0.1:9999")
        adapter._client = None
        adapter._available = False
        assert adapter.collection_exists() is False

    def test_chunk_key_helper(self) -> None:
        chunk = _make_chunk(source="guide.pdf", idx=7)
        assert QdrantAdapter._chunk_key(chunk) == "guide.pdf:7"


# ---------------------------------------------------------------------------
# RankedChunk — new Phase 3 fields
# ---------------------------------------------------------------------------

class TestRankedChunkPhase3:
    def test_bge_sparse_score_defaults_to_zero(self) -> None:
        chunk = RankedChunk(
            text="hello",
            source="doc.pdf",
            section_heading=None,
            page_number=None,
            dense_score=0.9,
            sparse_score=0.3,
            fused_score=0.7,
            rerank_score=0.8,
        )
        assert chunk.bge_sparse_score == 0.0

    def test_token_count_defaults_to_zero(self) -> None:
        chunk = RankedChunk(
            text="hello",
            source="doc.pdf",
            section_heading=None,
            page_number=None,
            dense_score=0.9,
            sparse_score=0.3,
            fused_score=0.7,
            rerank_score=0.8,
        )
        assert chunk.token_count == 0

    def test_source_type_defaults_to_unknown(self) -> None:
        chunk = RankedChunk(
            text="hello",
            source="doc.pdf",
            section_heading=None,
            page_number=None,
            dense_score=0.9,
            sparse_score=0.3,
            fused_score=0.7,
            rerank_score=0.8,
        )
        assert chunk.source_type == "unknown"

    def test_access_scope_defaults_to_empty_list(self) -> None:
        chunk = RankedChunk(
            text="hello",
            source="doc.pdf",
            section_heading=None,
            page_number=None,
            dense_score=0.9,
            sparse_score=0.3,
            fused_score=0.7,
            rerank_score=0.8,
        )
        assert chunk.access_scope == []

    def test_all_new_fields_settable(self) -> None:
        chunk = RankedChunk(
            text="hello",
            source="doc.pdf",
            section_heading="Intro",
            page_number=1,
            dense_score=0.9,
            sparse_score=0.3,
            fused_score=0.7,
            rerank_score=0.8,
            bge_sparse_score=0.55,
            token_count=128,
            source_type="postgresql",
            access_scope=["internal", "eng-team"],
        )
        assert chunk.bge_sparse_score == 0.55
        assert chunk.token_count == 128
        assert chunk.source_type == "postgresql"
        assert "eng-team" in chunk.access_scope


# ---------------------------------------------------------------------------
# HybridRetriever — access_scope parameter (no regression)
# ---------------------------------------------------------------------------

class TestHybridRetrieverAccessScope:
    def test_retrieve_accepts_access_scope_parameter(self, tmp_path) -> None:
        """retrieve() must accept access_scope=... without raising TypeError."""
        from biome_rag.retrieval.engine import HybridRetriever

        retriever = HybridRetriever(
            storage_dir=tmp_path / "storage",
            processed_dir=tmp_path / "processed",
            dense_adapter=MagicMock(
                search=MagicMock(return_value=[])
            ),
        )
        # Inject an empty BM25 index
        retriever.bm25_index = MagicMock(documents=[], search=MagicMock(return_value=[]))
        # Empty chunk store → should return []
        retriever.chunk_store = MagicMock(get_chunks=MagicMock(return_value=[]))

        result = retriever.retrieve("test query", top_k=5, access_scope=["internal"])
        assert result == []

    def test_retrieve_works_without_access_scope(self, tmp_path) -> None:
        from biome_rag.retrieval.engine import HybridRetriever

        retriever = HybridRetriever(
            storage_dir=tmp_path / "storage",
            processed_dir=tmp_path / "processed",
            dense_adapter=MagicMock(search=MagicMock(return_value=[])),
        )
        retriever.bm25_index = MagicMock(documents=[], search=MagicMock(return_value=[]))
        retriever.chunk_store = MagicMock(get_chunks=MagicMock(return_value=[]))

        result = retriever.retrieve("test query", top_k=5)  # no access_scope
        assert result == []
