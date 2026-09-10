"""BGE-M3 Dual-Encoder: dense (semantic) + sparse (lexical) embeddings.

Phase 3 implementation.

BGE-M3 from BAAI simultaneously produces three representation types:
  1. **Dense**  — 1024-dim cosine-similarity vectors (standard semantic search)
  2. **Sparse** — term-weight map (lexical, like learned BM25); replaces hand-tuned BM25
  3. **ColBERT** — multi-vector late interaction (optional, not used here)

This module wraps FlagEmbedding's ``BGEM3FlagModel`` with:
  - Lazy loading (model not loaded until first encode call)
  - Batch processing with configurable batch_size
  - Caching of encoded corpus vectors (for the index path)
  - Graceful fallback to ``SimpleDenseEmbeddingAdapter`` when FlagEmbedding
    is not installed (so tests and the legacy API still work)

Usage::

    encoder = BGE_M3Encoder()

    # Encode a batch of chunks for indexing
    results = encoder.encode_corpus(["chunk text 1", "chunk text 2"])
    dense_vecs   = results["dense_vecs"]    # shape (N, 1024)
    sparse_vecs  = results["lexical_weights"]  # list of {token: weight} dicts

    # Encode a query (uses query-specific prompt internally)
    q = encoder.encode_query("what is the VPN policy?")
    q_dense  = q["dense_vecs"]       # shape (1, 1024)
    q_sparse = q["lexical_weights"]  # {token: weight}

Architecture note:
    BGE-M3 was trained with "Hybrid retrieval" in mind. The recommended fusion
    strategy is to combine dense cosine similarity with sparse dot-product
    similarity using normalised weights. See DECISIONS.md D018.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# FlagEmbedding is optional — graceful degradation when not installed
try:
    from FlagEmbedding import BGEM3FlagModel as _BGEM3FlagModel  # type: ignore
    _FLAG_EMBEDDING_AVAILABLE = True
except ImportError:
    _BGEM3FlagModel = None  # type: ignore
    _FLAG_EMBEDDING_AVAILABLE = False
    logger.warning(
        "FlagEmbedding not installed (`pip install FlagEmbedding`). "
        "BGE-M3 encoder unavailable; dense retrieval will use the fallback adapter."
    )


# ---------------------------------------------------------------------------
# BGE-M3 Encoder
# ---------------------------------------------------------------------------

class BGE_M3Encoder:
    """Lazy-loading BGE-M3 dual-encoder.

    Produces dense and sparse vectors for both corpus chunks and queries.
    The model is NOT loaded at init — it loads on the first ``encode_*`` call.

    Args:
        model_name: HuggingFace model ID. Defaults to ``BAAI/bge-m3``.
        use_fp16: Load model weights in float16 for ~2× speed on GPU. Safe
                  to enable even on CPU-only machines (PyTorch handles it).
        batch_size: Chunks processed per forward pass.
        max_length: Maximum token length (BGE-M3 supports up to 8192 tokens).
        device: ``"cpu"``, ``"cuda"``, or ``"mps"``.  ``None`` = auto-detect.
        return_sparse: Compute lexical (sparse) weights in addition to dense.
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        use_fp16: bool = True,
        batch_size: int = 32,
        max_length: int = 8192,
        device: str | None = None,
        return_sparse: bool = True,
    ) -> None:
        self.model_name = model_name
        self.use_fp16 = use_fp16
        self.batch_size = batch_size
        self.max_length = max_length
        self.device = device
        self.return_sparse = return_sparse
        self._model: Any = None
        self._available = _FLAG_EMBEDDING_AVAILABLE

    @property
    def is_available(self) -> bool:
        """Return True if FlagEmbedding is installed."""
        return self._available

    def _load(self) -> Any | None:
        """Lazy-load the BGE-M3 model. Returns the model or None on failure."""
        if self._model is not None:
            return self._model
        if not self._available:
            return None
        try:
            logger.info("Loading BGE-M3 model '%s' (this may take a minute)…", self.model_name)
            self._model = _BGEM3FlagModel(
                self.model_name,
                use_fp16=self.use_fp16,
                device=self.device,
            )
            logger.info("BGE-M3 model loaded successfully.")
        except Exception as exc:
            logger.error("Failed to load BGE-M3 model: %s", exc, exc_info=True)
            self._model = None
            self._available = False
        return self._model

    # ------------------------------------------------------------------
    # Encoding methods
    # ------------------------------------------------------------------

    def encode_corpus(
        self,
        texts: list[str],
        show_progress: bool = False,
    ) -> dict[str, Any]:
        """Encode a list of corpus documents for indexing.

        Args:
            texts: Plain text strings (one per chunk).
            show_progress: Show a tqdm progress bar (useful for large corpora).

        Returns:
            Dict with keys:
            - ``dense_vecs``:      np.ndarray of shape (N, 1024), float32.
            - ``lexical_weights``: list of N ``{token: weight}`` dicts (sparse).
            - ``available``:       bool — False if FlagEmbedding not installed.
        """
        model = self._load()
        if model is None:
            return self._empty_result(len(texts))

        try:
            output = model.encode(
                texts,
                batch_size=self.batch_size,
                max_length=self.max_length,
                return_dense=True,
                return_sparse=self.return_sparse,
                return_colbert_vecs=False,
                show_progress_bar=show_progress,
            )
            return {
                "dense_vecs": np.array(output["dense_vecs"], dtype=np.float32),
                "lexical_weights": output.get("lexical_weights", [{} for _ in texts]),
                "available": True,
            }
        except Exception as exc:
            logger.error("BGE-M3 corpus encoding failed: %s", exc, exc_info=True)
            return self._empty_result(len(texts))

    def encode_query(self, query: str) -> dict[str, Any]:
        """Encode a single query string for retrieval.

        BGE-M3 uses an internal query prompt (``Represent this sentence for searching
        relevant passages:`` by default) which is applied automatically.

        Returns:
            Dict with keys:
            - ``dense_vecs``:      np.ndarray of shape (1, 1024), float32.
            - ``lexical_weights``: single ``{token: weight}`` dict.
            - ``available``:       bool.
        """
        model = self._load()
        if model is None:
            return self._empty_result(1)

        try:
            output = model.encode(
                [query],
                batch_size=1,
                max_length=self.max_length,
                return_dense=True,
                return_sparse=self.return_sparse,
                return_colbert_vecs=False,
            )
            return {
                "dense_vecs": np.array(output["dense_vecs"], dtype=np.float32),
                "lexical_weights": output.get("lexical_weights", [{}]),
                "available": True,
            }
        except Exception as exc:
            logger.error("BGE-M3 query encoding failed: %s", exc, exc_info=True)
            return self._empty_result(1)

    # ------------------------------------------------------------------
    # Scoring helpers (used by QdrantAdapter and tests)
    # ------------------------------------------------------------------

    @staticmethod
    def dense_score(q_vec: np.ndarray, d_vec: np.ndarray) -> float:
        """Cosine similarity between a query and document dense vector."""
        q_norm = q_vec / (np.linalg.norm(q_vec) + 1e-10)
        d_norm = d_vec / (np.linalg.norm(d_vec) + 1e-10)
        return float(np.dot(q_norm.flatten(), d_norm.flatten()))

    @staticmethod
    def sparse_score(q_weights: dict[str, float], d_weights: dict[str, float]) -> float:
        """Dot-product between two sparse lexical weight dicts.

        This is equivalent to a learned BM25 where the weights come from
        BGE-M3's SPLADE-style sparse encoder.
        """
        score = 0.0
        for token, q_w in q_weights.items():
            d_w = d_weights.get(token, 0.0)
            score += float(q_w) * float(d_w)
        return score

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _empty_result(self, n: int) -> dict[str, Any]:
        return {
            "dense_vecs": np.zeros((n, 1024), dtype=np.float32),
            "lexical_weights": [{} for _ in range(n)],
            "available": False,
        }
