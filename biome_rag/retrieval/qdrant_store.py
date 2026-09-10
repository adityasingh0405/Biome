"""Qdrant vector store adapter for Phase 3.

Implements the ``DenseEmbeddingAdapter`` interface so it slots into the
existing ``HybridRetriever`` without changing call sites.

Architecture:
    Each chunk is stored as a Qdrant point with two vector fields:
    - ``dense``:  1024-dim float32 vector from BGE-M3 dense encoder.
    - ``sparse``: SparseVector of (indices, values) from BGE-M3 lexical encoder.

    At query time:
    1. Query is encoded by BGE-M3 into dense + sparse vectors.
    2. Qdrant performs native hybrid search using Prefetch + fusion.
    3. Results are returned as (chunk, score) tuples, compatible with the
       existing HybridRetriever's dense_search_results contract.

Fallback chain (if Qdrant is not running or qdrant-client is not installed):
    QdrantAdapter → ChromaDenseEmbeddingAdapter → SimpleDenseEmbeddingAdapter

Access control at query time:
    If ``access_scope`` is provided to ``search()``, Qdrant's payload filter
    ``{"must": [{"key": "access_scope", "match": {"any": access_scope}}]}``
    is applied before ranking. This enforces row-level ACL.

Design decisions: DECISIONS.md D018
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from .dense import DenseEmbeddingAdapter, SimpleDenseEmbeddingAdapter
from .embeddings import BGE_M3Encoder

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# qdrant-client is optional — graceful degradation
try:
    from qdrant_client import QdrantClient  # type: ignore
    from qdrant_client.http import models as qmodels  # type: ignore
    _QDRANT_AVAILABLE = True
except ImportError:
    QdrantClient = None  # type: ignore
    qmodels = None  # type: ignore
    _QDRANT_AVAILABLE = False
    logger.warning(
        "qdrant-client not installed (`pip install qdrant-client`). "
        "QdrantAdapter will fall back to SimpleDenseEmbeddingAdapter."
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DENSE_DIM = 1024          # BGE-M3 dense vector dimensionality
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"


# ---------------------------------------------------------------------------
# QdrantAdapter
# ---------------------------------------------------------------------------

class QdrantAdapter(DenseEmbeddingAdapter):
    """Dense + sparse retrieval adapter backed by Qdrant.

    Implements the ``DenseEmbeddingAdapter`` interface so it's a drop-in
    replacement for ``ChromaDenseEmbeddingAdapter`` in ``HybridRetriever``.

    The adapter stores BGE-M3 dense AND sparse vectors in a single Qdrant
    collection and performs a two-stage hybrid search at query time.

    Args:
        url: Qdrant server URL (default: ``QDRANT_URL`` env var or localhost:6333).
        collection_name: Qdrant collection name.
        encoder: A ``BGE_M3Encoder`` instance. If None, one is created lazily.
        top_k_per_vector: Number of candidates to fetch per vector type before fusion.
        timeout: Qdrant client request timeout in seconds.
    """

    def __init__(
        self,
        url: str | None = None,
        collection_name: str | None = None,
        encoder: BGE_M3Encoder | None = None,
        top_k_per_vector: int = 20,
        timeout: float = 30.0,
    ) -> None:
        # Resolve URL: explicit arg → QDRANT_URL env → Settings host/port
        if url:
            self.url = url
        elif os.getenv("QDRANT_URL"):
            self.url = os.getenv("QDRANT_URL")
        else:
            try:
                from biome_rag.config import get_settings  # noqa: PLC0415
                s = get_settings()
                self.url = f"http://{s.qdrant_host}:{s.qdrant_port}"
            except Exception:
                self.url = "http://localhost:6333"

        # Resolve collection: explicit arg → QDRANT_COLLECTION env → Settings
        if collection_name:
            self.collection_name = collection_name
        elif os.getenv("QDRANT_COLLECTION"):
            self.collection_name = os.getenv("QDRANT_COLLECTION")
        else:
            try:
                from biome_rag.config import get_settings  # noqa: PLC0415
                self.collection_name = get_settings().qdrant_collection
            except Exception:
                self.collection_name = "biome-chunks-bge-m3"

        self.encoder = encoder or BGE_M3Encoder()
        self.top_k_per_vector = top_k_per_vector
        self.timeout = timeout
        self._client: Any = None
        self._available = _QDRANT_AVAILABLE and self.encoder.is_available
        self._fallback: DenseEmbeddingAdapter = SimpleDenseEmbeddingAdapter()


    # ------------------------------------------------------------------
    # Client management
    # ------------------------------------------------------------------

    def _get_client(self) -> Any | None:
        """Return a cached QdrantClient, or None if unavailable."""
        if self._client is not None:
            return self._client
        if not _QDRANT_AVAILABLE:
            return None
        try:
            self._client = QdrantClient(url=self.url, timeout=self.timeout)
            # Quick connectivity check
            self._client.get_collections()
            logger.info("QdrantClient connected to %s", self.url)
        except Exception as exc:
            logger.warning(
                "Cannot connect to Qdrant at %s: %s. "
                "Falling back to SimpleDenseEmbeddingAdapter.",
                self.url, exc,
            )
            self._client = None
            self._available = False
        return self._client

    def _ensure_collection(self, client: Any) -> None:
        """Create the collection with dense + sparse vector configs if missing."""
        try:
            collections = [c.name for c in client.get_collections().collections]
            if self.collection_name in collections:
                return

            client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    DENSE_VECTOR_NAME: qmodels.VectorParams(
                        size=DENSE_DIM,
                        distance=qmodels.Distance.COSINE,
                        on_disk=False,
                    ),
                },
                sparse_vectors_config={
                    SPARSE_VECTOR_NAME: qmodels.SparseVectorParams(
                        index=qmodels.SparseIndexParams(on_disk=False),
                    ),
                },
            )
            logger.info(
                "Created Qdrant collection '%s' with dense (%d-dim) + sparse vectors.",
                self.collection_name, DENSE_DIM,
            )
        except Exception as exc:
            logger.error("Failed to create Qdrant collection: %s", exc, exc_info=True)

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_documents(self, chunks: list[Any]) -> None:
        """Index a list of chunks into Qdrant with BGE-M3 vectors.

        Each chunk is upserted with:
        - ``dense`` vector from BGE-M3 dense encoder.
        - ``sparse`` vector from BGE-M3 lexical encoder.
        - Payload fields: source, chunk_index, section_heading, page_number,
          source_type, token_count, access_scope (for ACL filtering).

        If Qdrant is unavailable, the call is silently skipped (the fallback
        adapter handles retrieval without an index).
        """
        if not chunks:
            return

        client = self._get_client()
        if client is None:
            logger.info("QdrantAdapter: Qdrant unavailable — skipping indexing.")
            return

        self._ensure_collection(client)

        texts = [str(getattr(c, "text", c)) for c in chunks]
        logger.info("QdrantAdapter: encoding %d chunks with BGE-M3…", len(texts))
        encoded = self.encoder.encode_corpus(texts, show_progress=True)

        if not encoded["available"]:
            logger.warning(
                "BGE-M3 encoding failed; QdrantAdapter will not index these chunks."
            )
            return

        dense_vecs = encoded["dense_vecs"]          # shape (N, 1024)
        sparse_vecs = encoded["lexical_weights"]    # list of {token: weight}

        points = []
        for i, chunk in enumerate(chunks):
            sparse_dict = sparse_vecs[i] if i < len(sparse_vecs) else {}
            indices, values = self._sparse_dict_to_qdrant(sparse_dict)

            payload = self._chunk_to_payload(chunk)

            points.append(
                qmodels.PointStruct(
                    id=str(uuid4()),
                    vector={
                        DENSE_VECTOR_NAME: dense_vecs[i].tolist(),
                        SPARSE_VECTOR_NAME: qmodels.SparseVector(
                            indices=indices, values=values
                        ),
                    },
                    payload=payload,
                )
            )

        # Batch upsert to Qdrant
        batch_size = 64
        for start in range(0, len(points), batch_size):
            batch = points[start : start + batch_size]
            try:
                client.upsert(collection_name=self.collection_name, points=batch)
            except Exception as exc:
                logger.error(
                    "QdrantAdapter: upsert failed for batch %d-%d: %s",
                    start, start + len(batch), exc,
                    exc_info=True,
                )

        logger.info(
            "QdrantAdapter: indexed %d points into collection '%s'.",
            len(points), self.collection_name,
        )

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        chunks: list[Any],
        top_k: int = 5,
        access_scope: list[str] | None = None,
    ) -> list[tuple[Any, float]]:
        """Hybrid search: BGE-M3 dense + sparse, fused by Qdrant.

        Args:
            query: User query string.
            chunks: Full list of chunks (used for identifier lookup + fallback).
            top_k: Number of results to return.
            access_scope: If provided, only chunks with matching ``access_scope``
                          in their Qdrant payload are returned (ACL enforcement).

        Returns:
            List of (chunk, score) tuples, score in [0, 1].
        """
        client = self._get_client()
        if client is None:
            logger.debug("QdrantAdapter: no Qdrant — using fallback adapter.")
            return self._fallback.search(query, chunks, top_k=top_k)

        # Encode query
        q_encoded = self.encoder.encode_query(query)
        if not q_encoded["available"]:
            return self._fallback.search(query, chunks, top_k=top_k)

        q_dense = q_encoded["dense_vecs"][0].tolist()
        q_sparse_dict = q_encoded["lexical_weights"][0] if q_encoded["lexical_weights"] else {}
        q_sparse_indices, q_sparse_values = self._sparse_dict_to_qdrant(q_sparse_dict)

        # Build optional ACL payload filter
        query_filter = self._build_acl_filter(access_scope)

        try:
            # Qdrant hybrid search: Prefetch from both vectors, fuse with RRF
            results = client.query_points(
                collection_name=self.collection_name,
                prefetch=[
                    qmodels.Prefetch(
                        query=q_dense,
                        using=DENSE_VECTOR_NAME,
                        limit=self.top_k_per_vector,
                        filter=query_filter,
                    ),
                    qmodels.Prefetch(
                        query=qmodels.SparseVector(
                            indices=q_sparse_indices, values=q_sparse_values
                        ),
                        using=SPARSE_VECTOR_NAME,
                        limit=self.top_k_per_vector,
                        filter=query_filter,
                    ),
                ],
                query=qmodels.FusionQuery(fusion=qmodels.Fusion.RRF),
                limit=top_k,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exc:
            logger.error("Qdrant hybrid search failed: %s. Using fallback.", exc)
            return self._fallback.search(query, chunks, top_k=top_k)

        # Map Qdrant results back to chunk objects using source+chunk_index as key
        chunk_by_id = {self._chunk_key(c): c for c in chunks}
        ranked: list[tuple[Any, float]] = []

        for point in results.points:
            payload = point.payload or {}
            key = f"{payload.get('source', '')}:{payload.get('chunk_index', 0)}"
            chunk = chunk_by_id.get(key)
            if chunk is None:
                # Try to match by source alone (chunk_index might differ across re-ingests)
                source = payload.get("source", "")
                chunk = next(
                    (c for c in chunks if getattr(c, "source", "") == source), None
                )
            if chunk is not None:
                score = max(0.0, min(1.0, float(point.score)))
                ranked.append((chunk, score))

        logger.debug(
            "QdrantAdapter hybrid search: %d results for query '%s'",
            len(ranked), query[:60],
        )
        return ranked

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    def collection_exists(self) -> bool:
        """Return True if the Qdrant collection exists and is non-empty."""
        client = self._get_client()
        if client is None:
            return False
        try:
            info = client.get_collection(self.collection_name)
            return info.points_count > 0
        except Exception:
            return False

    def delete_collection(self) -> None:
        """Delete the Qdrant collection (used in tests / reset workflows)."""
        client = self._get_client()
        if client is None:
            return
        try:
            client.delete_collection(self.collection_name)
            logger.info("Deleted Qdrant collection '%s'.", self.collection_name)
        except Exception as exc:
            logger.warning("Could not delete Qdrant collection: %s", exc)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sparse_dict_to_qdrant(
        sparse_dict: dict[str | int, float],
    ) -> tuple[list[int], list[float]]:
        """Convert a BGE-M3 lexical weight dict to Qdrant sparse vector format.

        BGE-M3 returns ``{token_str: weight}`` or ``{token_id_int: weight}``.
        Qdrant needs parallel ``(indices: list[int], values: list[float])``.
        Token strings are hashed to stable non-negative integers if needed.
        """
        indices: list[int] = []
        values: list[float] = []
        for token, weight in sparse_dict.items():
            if isinstance(token, int):
                idx = token
            else:
                # Hash the token string to a positive 32-bit int
                import hashlib  # noqa: PLC0415
                idx = int(hashlib.md5(token.encode()).hexdigest(), 16) % (2**31)
            indices.append(idx)
            values.append(float(weight))
        return indices, values

    @staticmethod
    def _chunk_key(chunk: Any) -> str:
        return f"{getattr(chunk, 'source', 'unknown')}:{getattr(chunk, 'chunk_index', 0)}"

    @staticmethod
    def _chunk_to_payload(chunk: Any) -> dict[str, Any]:
        """Build a Qdrant payload dict from a Chunk / SimpleNamespace."""
        payload: dict[str, Any] = {
            "source": str(getattr(chunk, "source", "unknown")),
            "chunk_index": int(getattr(chunk, "chunk_index", 0)),
            "source_type": str(getattr(chunk, "source_type", "unknown")),
            "token_count": int(getattr(chunk, "token_count", 0)),
        }
        heading = getattr(chunk, "section_heading", None)
        if heading is not None:
            payload["section_heading"] = str(heading)
        page = getattr(chunk, "page_number", None)
        if page is not None:
            payload["page_number"] = int(page)

        # ACL: access_scope list for payload filtering
        meta = getattr(chunk, "metadata", {}) or {}
        if isinstance(meta, dict):
            scope = meta.get("access_scope", [])
        else:
            scope = getattr(meta, "access_scope", [])
        if scope:
            payload["access_scope"] = list(scope)

        return payload

    @staticmethod
    def _build_acl_filter(access_scope: list[str] | None) -> Any | None:
        """Build a Qdrant payload filter for access_scope ACL enforcement."""
        if not access_scope or qmodels is None:
            return None
        return qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="access_scope",
                    match=qmodels.MatchAny(any=access_scope),
                )
            ]
        )
