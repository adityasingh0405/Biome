"""Base Ingester ABC with incremental (watermark-based) ingestion support.

Phase 1 requirement: every ingester must accept a ``since: datetime | None``
parameter so that incremental runs can skip already-seen documents without
re-processing the entire corpus.

Design:
- ``Ingester`` is the abstract base class all concrete ingesters implement.
- ``IngestResult`` is the normalized output contract — a list of ``DocumentNode``
  objects with a consistent metadata schema (source_type, source_id, title,
  access_scope, updated_at, raw_content).
- ``WatermarkStore`` provides a simple SQLite-backed watermark store so each
  ingester can persist the timestamp of its last successful run and resume from
  there on the next invocation.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import DocumentNode, IngestionSummary

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ingestion result contract
# ---------------------------------------------------------------------------

@dataclass
class IngestResult:
    """Output contract from a single ingester run."""
    documents: list[DocumentNode] = field(default_factory=list)
    summary: IngestionSummary = field(default_factory=IngestionSummary)
    errors: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.documents)


# ---------------------------------------------------------------------------
# Abstract Base Ingester
# ---------------------------------------------------------------------------

class Ingester(ABC):
    """Abstract base class for all data source ingesters.

    Every concrete ingester MUST implement ``ingest()``.
    The ``since`` parameter enables incremental ingestion:
    - ``since=None``  → full re-ingest (first run or forced refresh)
    - ``since=<ts>``  → only ingest documents modified/created after ``ts``

    Incremental strategy depends on the source:
    - **Files**: compare ``mtime`` against ``since``.
    - **PostgreSQL**: filter ``WHERE updated_at > since`` (or use content-hash
      dedup as fallback when no ``updated_at`` column exists).
    - **Slack**: use the ``oldest`` parameter of the Slack API.
    """

    #: Human-readable name, used in logs and Prefect task names
    source_type: str = "unknown"

    @abstractmethod
    def ingest(self, since: datetime | None = None) -> IngestResult:
        """Ingest documents from this source.

        Args:
            since: If provided, only documents created/modified after this
                   timestamp will be returned. Timezone-aware datetimes are
                   preferred; naive datetimes are assumed to be UTC.

        Returns:
            An ``IngestResult`` containing normalized ``DocumentNode`` objects.
        """
        raise NotImplementedError

    def _normalize_ts(self, ts: datetime | None) -> datetime | None:
        """Ensure the timestamp is timezone-aware (UTC) or None."""
        if ts is None:
            return None
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts

    def _is_after_watermark(
        self, item_ts: datetime | str | None, watermark: datetime | None
    ) -> bool:
        """Return True if ``item_ts`` is newer than ``watermark`` (or if either is None)."""
        if watermark is None or item_ts is None:
            return True
        if isinstance(item_ts, str):
            try:
                item_ts = datetime.fromisoformat(item_ts)
            except ValueError:
                return True  # Cannot parse — include by default
        item_ts = self._normalize_ts(item_ts)
        watermark = self._normalize_ts(watermark)
        return item_ts > watermark  # type: ignore[operator]


# ---------------------------------------------------------------------------
# SQLite-backed Watermark Store
# ---------------------------------------------------------------------------

class WatermarkStore:
    """Persists the last-successful-run timestamp for each ingester.

    Stored in the same SQLite database as the ``SQLiteStateTracker`` for
    simplicity, but in a separate ``watermarks`` table.

    Usage::

        store = WatermarkStore(Path("data/ingestion_state.db"))
        since = store.get("postgres")           # None on first run
        result = ingester.ingest(since=since)
        store.set("postgres", datetime.now(timezone.utc))
    """

    def __init__(self, db_path: str | Path = "data/ingestion_state.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS watermarks (
                    source_type TEXT PRIMARY KEY,
                    last_run_at TEXT NOT NULL,
                    metadata    TEXT
                );
                """
            )
            conn.commit()

    def get(self, source_type: str) -> datetime | None:
        """Return the last successful run timestamp for ``source_type``, or None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT last_run_at FROM watermarks WHERE source_type = ?;",
                (source_type,),
            ).fetchone()
        if row is None:
            return None
        try:
            ts = datetime.fromisoformat(row["last_run_at"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts
        except ValueError:
            logger.warning("Invalid watermark timestamp for '%s': %s", source_type, row["last_run_at"])
            return None

    def set(
        self,
        source_type: str,
        timestamp: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a successful run for ``source_type``."""
        ts = timestamp or datetime.now(timezone.utc)
        ts_str = ts.isoformat()
        meta_json = json.dumps(metadata or {}, default=str)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO watermarks (source_type, last_run_at, metadata)
                VALUES (?, ?, ?);
                """,
                (source_type, ts_str, meta_json),
            )
            conn.commit()
        logger.info("Watermark updated for '%s': %s", source_type, ts_str)

    def reset(self, source_type: str) -> None:
        """Delete the watermark for ``source_type`` (forces full re-ingest next run)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM watermarks WHERE source_type = ?;", (source_type,))
            conn.commit()
        logger.info("Watermark reset for '%s'.", source_type)
