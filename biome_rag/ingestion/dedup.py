from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# SHA-256 Content Hash Utilities
# ----------------------------------------------------------------------

def compute_file_sha256(file_path: str | Path, chunk_size: int = 65536) -> str:
    """Compute SHA-256 content hash of a local file via streaming chunks."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found for hash calculation: {path}")

    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_payload_sha256(payload: str | bytes | dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash for a row payload or text content."""
    hasher = hashlib.sha256()
    if isinstance(payload, dict):
        # Deterministic canonical JSON serialization with sorted keys
        canonical_str = json.dumps(payload, sort_keys=True, default=str)
        hasher.update(canonical_str.encode("utf-8"))
    elif isinstance(payload, str):
        hasher.update(payload.strip().encode("utf-8"))
    elif isinstance(payload, bytes):
        hasher.update(payload)
    else:
        hasher.update(str(payload).encode("utf-8"))
    return hasher.hexdigest()


# ----------------------------------------------------------------------
# Enterprise SQLite State Tracker
# ----------------------------------------------------------------------

class SQLiteStateTracker:
    """Enterprise-grade local state tracker backed by SQLite.

    Maintains a persistent ledger of processed content hashes across runs
    to prevent duplicate indexing and vector store inflation.
    """

    def __init__(self, db_path: str | Path = "data/ingestion_state.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for high concurrency & speed
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_state (
                    content_hash TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    primary_key TEXT,
                    indexed_at TIMESTAMP NOT NULL,
                    metadata TEXT
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_state_source 
                ON ingestion_state (source_type, source_name);
                """
            )
            conn.commit()

    def is_indexed(self, content_hash: str) -> bool:
        """Check if a single content hash has already been indexed."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM ingestion_state WHERE content_hash = ? LIMIT 1;",
                (content_hash,),
            )
            return cursor.fetchone() is not None

    def filter_unseen_hashes(self, hashes: list[str]) -> list[str]:
        """Return the subset of hashes that have NOT yet been indexed."""
        if not hashes:
            return []

        indexed_set = self.batch_check_indexed(hashes)
        return [h for h in hashes if h not in indexed_set]

    def batch_check_indexed(self, hashes: Sequence[str]) -> set[str]:
        """Check a batch of hashes and return the set of hashes that already exist."""
        if not hashes:
            return set()

        unique_hashes = list(set(hashes))
        indexed = set()
        chunk_size = 900  # SQLite variable limit safety

        with self._get_connection() as conn:
            for i in range(0, len(unique_hashes), chunk_size):
                chunk = unique_hashes[i : i + chunk_size]
                placeholders = ",".join("?" for _ in chunk)
                query = f"SELECT content_hash FROM ingestion_state WHERE content_hash IN ({placeholders});"
                cursor = conn.execute(query, chunk)
                indexed.update(row["content_hash"] for row in cursor.fetchall())

        return indexed

    def mark_indexed(
        self,
        content_hash: str,
        source_type: str,
        source_name: str,
        primary_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an indexed item in the state database."""
        now = datetime.now(timezone.utc).isoformat()
        meta_json = json.dumps(metadata or {}, default=str)
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO ingestion_state 
                (content_hash, source_type, source_name, primary_key, indexed_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (content_hash, source_type, source_name, primary_key, now, meta_json),
            )
            conn.commit()

    def batch_mark_indexed(
        self,
        records: Iterable[dict[str, Any]],
    ) -> int:
        """Batch record indexed items.

        Each dict in records must contain:
        - content_hash (str)
        - source_type (str)
        - source_name (str)
        Optional: primary_key (str), metadata (dict)
        """
        now = datetime.now(timezone.utc).isoformat()
        rows_to_insert = []
        for r in records:
            meta_json = json.dumps(r.get("metadata") or {}, default=str)
            rows_to_insert.append(
                (
                    r["content_hash"],
                    r["source_type"],
                    r["source_name"],
                    r.get("primary_key"),
                    now,
                    meta_json,
                )
            )

        if not rows_to_insert:
            return 0

        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO ingestion_state 
                (content_hash, source_type, source_name, primary_key, indexed_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                rows_to_insert,
            )
            conn.commit()

        return len(rows_to_insert)

    def count(self) -> int:
        """Total number of tracked records in the state database."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) AS total FROM ingestion_state;")
            row = cursor.fetchone()
            return int(row["total"]) if row else 0

    def reset_state(self) -> None:
        """Reset and wipe the state table."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM ingestion_state;")
            conn.commit()
        logger.info("Ingestion state tracker database has been reset.")


# ----------------------------------------------------------------------
# Legacy TF-IDF Near-Duplicate Detector (preserved for chunk-level dedup)
# ----------------------------------------------------------------------

_tfidf = None


def _get_tfidf():
    global _tfidf
    if _tfidf is None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        _tfidf = TfidfVectorizer(
            analyzer="word",
            token_pattern=r"[a-zA-Z0-9_]+",
            max_features=5000,
            sublinear_tf=True,
        )
    return _tfidf


class Deduplicator:
    """Near-duplicate detector using cosine similarity on TF-IDF vectors.

    Fast pre-filter: exact string equality is checked first.
    Slow path: TF-IDF cosine similarity for near-duplicates above *threshold*.
    """

    def __init__(self, threshold: float = 0.95):
        self.threshold = threshold
        self._seen_vectors: list = []
        self._seen_texts: list[str] = []

    def is_duplicate(self, item: str | object, existing_chunks: Sequence[object] | None = None) -> bool:
        """Return True if item (str or Chunk) is a near-duplicate of existing content."""
        text = str(getattr(item, "text", item))

        if existing_chunks is not None:
            for ex in existing_chunks:
                ex_text = str(getattr(ex, "text", ex))
                if text.strip().lower() == ex_text.strip().lower():
                    return True

        if not self._seen_texts:
            self._seen_texts.append(text)
            return False

        try:
            from sklearn.metrics.pairwise import cosine_similarity
            vectorizer = _get_tfidf()
            all_texts = self._seen_texts + [text]
            matrix = vectorizer.fit_transform(all_texts)
            new_vec = matrix[-1]
            existing = matrix[:-1]
            sims = cosine_similarity(new_vec, existing).flatten()
            if sims.max() >= self.threshold:
                logger.debug(
                    "Near-duplicate detected (max_sim=%.4f >= %.4f). Skipping chunk.",
                    sims.max(),
                    self.threshold,
                )
                return True
        except Exception as exc:
            logger.warning("Cosine dedup failed (%s); skipping similarity check.", exc)

        self._seen_texts.append(text)
        return False

    def reset(self) -> None:
        self._seen_texts = []


def filter_duplicates(texts: Sequence[str], threshold: float = 0.95) -> list[int]:
    """Return indices of non-duplicate texts from *texts*."""
    if not texts:
        return []

    kept: list[int] = []
    dedup = Deduplicator(threshold=threshold)

    for idx, text in enumerate(texts):
        if not dedup.is_duplicate(text):
            kept.append(idx)

    return kept
