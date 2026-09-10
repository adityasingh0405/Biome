"""PostgreSQL ingester — Phase 1 implementation using the Ingester ABC.

Refactors the existing ``PostgreSQLLoader`` into a first-class ``Ingester``
with:
- Watermark-based incremental ingestion (``WHERE updated_at > :since``)
- Automatic fallback to content-hash dedup when no ``updated_at`` column exists
- JOIN-based composite entity documents (configurable join query)
- ``access_scope`` list populated from department / source column values
- Markdown serialization of rows for better chunking downstream

Design decisions:
- SQLAlchemy Core is used (not ORM) to avoid schema coupling.
- The ingester reflects the table schema at runtime — no model class needed.
- A ``join_query`` override lets you pass arbitrary SQL for complex JOINs.
- All credential handling goes through the ``POSTGRES_URI`` env var.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from .base import Ingester, IngestResult
from .dedup import compute_payload_sha256
from .models import DocumentMetadata, DocumentNode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper — row → Markdown serializer
# ---------------------------------------------------------------------------

def _row_to_markdown(row: dict[str, Any], table_name: str) -> str:
    """Convert a database row to a readable Markdown document.

    Format example::

        ## enterprise_tickets — row id=42

        **id**: 42
        **title**: VPN not connecting
        **description**: Cannot connect to company VPN since yesterday.
        **status**: open
        **department**: IT
        **created_at**: 2024-01-15 09:32:00

    This format is intentionally verbose so that downstream chunkers and
    LLMs can identify the record type and field names from context alone.
    """
    sensitive = {"password", "secret", "ssn", "tax_id", "token", "api_key"}
    row_id = row.get("id", row.get("ticket_id", "?"))
    lines = [f"## {table_name} — row id={row_id}", ""]
    for key, value in row.items():
        if str(key).lower() in sensitive:
            continue  # Never serialise sensitive fields
        if value is None:
            continue
        lines.append(f"**{key}**: {value}")
    return "\n".join(lines)


def _infer_scope_from_row(row: dict[str, Any], default_scope: list[str]) -> list[str]:
    """Derive ``access_scope`` from a row's department / team / category columns."""
    scopes: list[str] = list(default_scope)
    for col in ("department", "team", "category", "access_level"):
        val = row.get(col)
        if val and isinstance(val, str):
            slug = val.lower().replace(" ", "_")
            if slug not in scopes:
                scopes.append(slug)
            break
    return scopes or ["internal"]


# ---------------------------------------------------------------------------
# PostgresIngester
# ---------------------------------------------------------------------------

class PostgresIngester(Ingester):
    """Ingest rows from a PostgreSQL table as Markdown documents.

    Incremental ingestion strategy:
    1. If the table has an ``updated_at`` column → use ``WHERE updated_at > :since``.
    2. Otherwise → fetch all rows and rely on content-hash dedup (``compute_payload_sha256``)
       to skip rows unchanged since the last run.

    Each row becomes one ``DocumentNode`` with ``source_type="postgresql"``.

    JOIN support:
        Pass a ``join_query`` string with SQLAlchemy bind params (e.g.
        ``SELECT t.*, c.name AS category FROM tickets t JOIN categories c …``).
        When ``join_query`` is provided, ``table_name`` is used only for logging.

    ACL:
        ``access_scope`` is derived from the row's ``department`` / ``team``
        column if present. Falls back to ``default_scope``.
    """

    source_type = "postgresql"

    def __init__(
        self,
        db_uri: str | None = None,
        table_name: str | None = None,
        join_query: str | None = None,
        default_scope: list[str] | None = None,
        batch_size: int = 500,
        max_rows: int | None = None,
    ) -> None:
        """
        Args:
            db_uri: Full SQLAlchemy connection URI. Defaults to ``POSTGRES_URI`` env var.
            table_name: Primary table to SELECT from. Defaults to ``POSTGRES_TABLE`` env var.
            join_query: Optional raw SQL query. If set, overrides the default
                        ``SELECT * FROM table_name`` with a custom JOIN.
            default_scope: Base ``access_scope`` list applied to every row.
            batch_size: Number of rows to fetch per SQLAlchemy chunk.
            max_rows: Hard cap on total rows (useful for development / testing).
        """
        self.db_uri: str = db_uri or os.getenv("POSTGRES_URI", "postgresql://localhost:5432/enterprise_rag")
        self.table_name: str = table_name or os.getenv("POSTGRES_TABLE", "enterprise_tickets")
        self.join_query: str | None = join_query
        self.default_scope: list[str] = default_scope or ["internal"]
        self.batch_size = batch_size
        self.max_rows = max_rows
        self._engine: Any = None   # SQLAlchemy engine, lazy-loaded
        self._has_updated_at: bool | None = None  # Cached after first schema check

    # ------------------------------------------------------------------
    # Engine management
    # ------------------------------------------------------------------

    def _get_engine(self) -> Any:
        """Return a cached SQLAlchemy engine, creating it on first call."""
        if self._engine is not None:
            return self._engine
        try:
            from sqlalchemy import create_engine  # noqa: PLC0415
            self._engine = create_engine(
                self.db_uri,
                pool_size=1,
                max_overflow=0,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 10},
            )
            logger.info("PostgresIngester: engine created for %s", self._safe_uri())
        except Exception as exc:
            raise RuntimeError(
                f"PostgresIngester: cannot create SQLAlchemy engine for {self._safe_uri()}: {exc}"
            ) from exc
        return self._engine

    def _safe_uri(self) -> str:
        """Return the URI with the password redacted for logging."""
        try:
            from urllib.parse import urlparse, urlunparse  # noqa: PLC0415
            parsed = urlparse(self.db_uri)
            safe = parsed._replace(netloc=f"{parsed.hostname}:{parsed.port or 5432}")
            return urlunparse(safe)
        except Exception:
            return "<REDACTED_URI>"

    # ------------------------------------------------------------------
    # Schema introspection
    # ------------------------------------------------------------------

    def _check_updated_at(self, engine: Any) -> bool:
        """Return True if ``updated_at`` column exists in ``table_name``."""
        if self._has_updated_at is not None:
            return self._has_updated_at
        try:
            from sqlalchemy import inspect as sa_inspect  # noqa: PLC0415
            inspector = sa_inspect(engine)
            cols = [c["name"] for c in inspector.get_columns(self.table_name)]
            self._has_updated_at = "updated_at" in cols
            logger.info(
                "PostgresIngester: table '%s' has updated_at=%s",
                self.table_name,
                self._has_updated_at,
            )
        except Exception as exc:
            logger.warning("Schema inspection failed: %s. Assuming no updated_at.", exc)
            self._has_updated_at = False
        return self._has_updated_at  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def ingest(self, since: datetime | None = None) -> IngestResult:
        """Ingest rows from the configured table.

        Args:
            since: Only return rows with ``updated_at > since`` (if column exists).
                   When ``None`` or when ``updated_at`` is absent, all rows are
                   fetched and content-hash dedup is applied instead.

        Returns:
            ``IngestResult`` with one ``DocumentNode`` per row.

        Raises:
            RuntimeError: If the database connection cannot be established.
        """
        since = self._normalize_ts(since)
        result = IngestResult()

        try:
            engine = self._get_engine()
        except RuntimeError as exc:
            result.errors.append(str(exc))
            logger.error("%s", exc)
            return result

        try:
            rows = self._fetch_rows(engine, since)
        except Exception as exc:
            msg = f"PostgresIngester: query failed — {exc}"
            result.errors.append(msg)
            logger.error(msg, exc_info=True)
            return result

        seen_hashes: set[str] = set()
        for row_dict in rows:
            if self.max_rows is not None and result.summary.documents_processed >= self.max_rows:
                break

            # Content-hash dedup (used when no updated_at or as second-pass guard)
            payload_hash = compute_payload_sha256(row_dict)
            if payload_hash in seen_hashes:
                logger.debug("Skipping duplicate row (hash=%s)", payload_hash[:8])
                continue
            seen_hashes.add(payload_hash)

            try:
                node = self._row_to_node(row_dict, payload_hash)
                result.documents.append(node)
                result.summary.documents_processed += 1
            except Exception as exc:
                msg = f"Row serialization failed: {exc} | row={str(row_dict)[:120]}"
                result.errors.append(msg)
                logger.warning(msg)

        logger.info(
            "PostgresIngester: fetched %d documents from '%s', %d errors.",
            result.summary.documents_processed,
            self.table_name,
            len(result.errors),
        )
        return result

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def _fetch_rows(self, engine: Any, since: datetime | None) -> list[dict[str, Any]]:
        """Execute the SELECT query and return rows as dicts."""
        from sqlalchemy import text  # noqa: PLC0415

        has_updated_at = self._check_updated_at(engine)

        if self.join_query:
            # Custom JOIN query — incremental filtering is caller's responsibility
            sql = self.join_query
            params: dict[str, Any] = {}
        elif since is not None and has_updated_at:
            # Watermark-based incremental: only rows modified after `since`
            sql = (
                f"SELECT * FROM {self.table_name} "
                f"WHERE updated_at > :since "
                f"ORDER BY updated_at ASC"
            )
            params = {"since": since.replace(tzinfo=None)}  # naive for psycopg2 compat
            logger.info(
                "PostgresIngester: incremental query (since=%s) on '%s'.",
                since.isoformat(),
                self.table_name,
            )
        else:
            # Full ingest — content-hash dedup will handle duplicates
            sql = f"SELECT * FROM {self.table_name} ORDER BY id"
            params = {}
            if since is not None and not has_updated_at:
                logger.info(
                    "PostgresIngester: table '%s' has no updated_at column — "
                    "full scan with content-hash dedup.",
                    self.table_name,
                )

        rows: list[dict[str, Any]] = []
        with engine.connect() as conn:
            cursor = conn.execute(text(sql), params)
            while True:
                batch = cursor.fetchmany(self.batch_size)
                if not batch:
                    break
                rows.extend(dict(zip(cursor.keys(), row)) for row in batch)

        logger.debug("PostgresIngester: fetched %d raw rows.", len(rows))
        return rows

    # ------------------------------------------------------------------
    # Row → DocumentNode
    # ------------------------------------------------------------------

    def _row_to_node(self, row: dict[str, Any], payload_hash: str) -> DocumentNode:
        """Convert a database row dict into a ``DocumentNode``."""
        row_id = row.get("id", row.get("ticket_id", "unknown"))
        source_name = f"{self.table_name}:{row_id}"

        text = _row_to_markdown(row, self.table_name)
        access_scope = _infer_scope_from_row(row, self.default_scope)
        access_level = access_scope[0] if access_scope else "internal"

        # Extract an updated_at timestamp for the metadata if available
        updated_at_raw = row.get("updated_at") or row.get("created_at")
        updated_at_str: str | None = None
        if updated_at_raw is not None:
            try:
                if isinstance(updated_at_raw, datetime):
                    updated_at_str = updated_at_raw.isoformat()
                else:
                    updated_at_str = str(updated_at_raw)
            except Exception:
                pass

        return DocumentNode(
            page_content=text,
            metadata=DocumentMetadata(
                source_type="postgresql",
                source_name=source_name,
                access_level=access_level,
                access_scope=access_scope,
                file_hash=payload_hash,
                extra={
                    "table": self.table_name,
                    "row_id": str(row_id),
                    "updated_at": updated_at_str,
                    "parser": "postgres_ingester",
                    "department": row.get("department", ""),
                },
            ),
        )
