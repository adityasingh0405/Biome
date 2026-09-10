"""Document ingester using IBM Docling for layout-aware parsing.

Phase 1 implementation:
- PDF / DOCX / PPTX / HTML parsed by Docling — preserves tables, headings, and page layout.
- Falls back to the existing file loaders (PyMuPDF, python-docx, etc.) if Docling is
  unavailable OR if the format is not natively supported by Docling.
- Incremental ingestion: file mtime compared against ``since`` watermark.
- ACL groundwork: ``access_scope`` list populated from filename-based inference rules.
- The Docling document object is preserved in ``DocumentNode.docling_doc`` (not serialized)
  so the Phase 2 HybridChunker can consume it directly without re-parsing.

Design decisions:
- Docling is a hard import wrapped in try/except so the pipeline still works without it.
- Fallback loader selection mirrors the existing ``UnstructuredBucketLoader`` routing.
- One ``DocumentConverter`` instance is shared across all files in a single ingest() call
  (Docling initialises models once, which is expensive).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .base import Ingester, IngestResult
from .dedup import compute_file_sha256
from .models import DocumentMetadata, DocumentNode, IngestionSummary

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Format routing
# ---------------------------------------------------------------------------

#: Extensions that Docling can parse with full layout awareness
DOCLING_FORMATS: frozenset[str] = frozenset({".pdf", ".docx", ".pptx", ".html", ".htm"})

#: Extensions routed to the existing fallback loaders
FALLBACK_FORMATS: frozenset[str] = frozenset({
    ".txt", ".md", ".markdown", ".json", ".jsonl",
    ".csv", ".py", ".sql", ".yaml", ".yml", ".rst",
})

ALL_SUPPORTED = DOCLING_FORMATS | FALLBACK_FORMATS


# ---------------------------------------------------------------------------
# ACL inference
# ---------------------------------------------------------------------------

def _infer_access_scope(path: Path, extra_scopes: list[str] | None = None) -> list[str]:
    """Derive an ``access_scope`` list from filename / directory name hints.

    This is a heuristic — for a real deployment, scopes would come from a
    document management system or an explicit metadata sidecar.

    Args:
        path: Absolute or relative path to the document.
        extra_scopes: Caller-supplied scopes to append (e.g. team-specific tags).

    Returns:
        A deduplicated list starting with the inferred scope.
    """
    name_lower = path.name.lower()
    parent_lower = path.parent.name.lower()

    if any(k in name_lower or k in parent_lower for k in ("secret", "confidential", "salary", "audit", "payroll")):
        primary = "confidential"
    elif any(k in name_lower or k in parent_lower for k in ("private", "hr_", "security", "personal", "restricted")):
        primary = "restricted"
    elif any(k in name_lower or k in parent_lower for k in ("public", "readme", "guide", "overview", "external")):
        primary = "public"
    else:
        primary = "internal"

    scopes: list[str] = [primary]
    if extra_scopes:
        for s in extra_scopes:
            if s not in scopes:
                scopes.append(s)
    return scopes


# ---------------------------------------------------------------------------
# DocumentIngester
# ---------------------------------------------------------------------------

class DocumentIngester(Ingester):
    """Layout-aware document ingester using IBM Docling.

    Supported formats:
    - **Docling path**: PDF, DOCX, PPTX, HTML — preserves headings, tables, lists.
    - **Fallback path**: TXT, Markdown, JSON, CSV, code files — plain text extraction.

    Incremental ingestion:
        Files with ``mtime <= since`` are skipped. On the first run (``since=None``),
        all files are ingested.

    ACL:
        ``access_scope`` is inferred from the filename. Pass ``default_scope`` to
        inject team-specific scopes (e.g. ``["eng-team", "internal"]``).
    """

    source_type = "document"

    def __init__(
        self,
        source_dir: Path | str,
        default_scope: list[str] | None = None,
        recursive: bool = True,
        use_docling: bool = True,
    ) -> None:
        """
        Args:
            source_dir: Directory to scan for documents.
            default_scope: Extra ACL scopes added to every document.
            recursive: If True, scan subdirectories recursively.
            use_docling: If False, skip Docling and use fallback loaders only
                         (useful for tests or when Docling models are not cached).
        """
        self.source_dir = Path(source_dir)
        self.default_scope: list[str] = default_scope or []
        self.recursive = recursive
        self.use_docling = use_docling
        self._converter: Any = None   # Lazy-loaded on first call

    # ------------------------------------------------------------------
    # Docling lazy initialisation
    # ------------------------------------------------------------------

    def _get_converter(self) -> Any | None:
        """Return a cached Docling DocumentConverter, or None if unavailable."""
        if self._converter is not None:
            return self._converter
        if not self.use_docling:
            return None
        try:
            from docling.document_converter import DocumentConverter  # noqa: PLC0415
            self._converter = DocumentConverter()
            logger.info("Docling DocumentConverter initialised.")
        except ImportError:
            logger.warning(
                "Docling not installed (`pip install docling`). "
                "Falling back to legacy file loaders for all formats."
            )
            self._converter = None
        return self._converter

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def ingest(self, since: datetime | None = None) -> IngestResult:
        """Ingest all supported documents from ``source_dir``.

        Args:
            since: Re-ingest only files modified after this timestamp (mtime-based).
                   ``None`` means ingest all files (full run).

        Returns:
            ``IngestResult`` with one ``DocumentNode`` per successfully parsed file.
        """
        since = self._normalize_ts(since)
        result = IngestResult()

        if not self.source_dir.exists():
            logger.warning("DocumentIngester: source dir not found: %s", self.source_dir)
            return result

        glob_pattern = "**/*" if self.recursive else "*"
        candidate_files = sorted(
            p for p in self.source_dir.glob(glob_pattern)
            if p.is_file() and p.suffix.lower() in ALL_SUPPORTED
        )

        logger.info(
            "DocumentIngester: scanning %d candidate files in '%s' (since=%s)",
            len(candidate_files),
            self.source_dir,
            since.isoformat() if since else "None",
        )

        for path in candidate_files:
            # ---- Incremental filter ----
            if since is not None:
                mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                if mtime <= since:
                    logger.debug("Skipping unchanged: %s (mtime=%s)", path.name, mtime.isoformat())
                    continue

            try:
                node = self._parse_file(path)
                if node is not None and node.page_content.strip():
                    result.documents.append(node)
                    result.summary.documents_processed += 1
                else:
                    logger.debug("Skipping empty document: %s", path.name)
            except Exception as exc:
                msg = f"Error ingesting '{path}': {exc}"
                logger.error(msg, exc_info=True)
                result.errors.append(msg)

        logger.info(
            "DocumentIngester: finished — %d documents, %d errors.",
            result.summary.documents_processed,
            len(result.errors),
        )
        return result

    # ------------------------------------------------------------------
    # Per-file routing
    # ------------------------------------------------------------------

    def _parse_file(self, path: Path) -> DocumentNode | None:
        """Route to Docling or fallback parser based on file extension."""
        if path.suffix.lower() in DOCLING_FORMATS and self.use_docling:
            return self._parse_with_docling(path)
        return self._parse_with_fallback(path)

    def _build_metadata(
        self,
        path: Path,
        parser: str,
        extra: dict[str, Any] | None = None,
    ) -> DocumentMetadata:
        """Construct a ``DocumentMetadata`` object with all ACL fields populated."""
        access_scope = _infer_access_scope(path, self.default_scope)
        return DocumentMetadata(
            source_type="document",
            source_name=path.name,
            file_path=str(path.resolve()),
            file_extension=path.suffix.lower(),
            file_hash=compute_file_sha256(path),
            access_level=access_scope[0] if access_scope else "internal",
            access_scope=access_scope,
            extra={
                "parser": parser,
                "file_size_bytes": path.stat().st_size,
                "section_heading": path.stem,
                **(extra or {}),
            },
        )

    # ------------------------------------------------------------------
    # Docling path
    # ------------------------------------------------------------------

    def _parse_with_docling(self, path: Path) -> DocumentNode | None:
        """Parse using IBM Docling — layout-aware, table-preserving."""
        converter = self._get_converter()
        if converter is None:
            # Docling unavailable; use fallback transparently
            return self._parse_with_fallback(path)

        try:
            conversion_result = converter.convert(str(path))
            docling_doc = conversion_result.document

            # Export to Markdown for the text representation used in the Silver Layer
            text = docling_doc.export_to_markdown()
            if not text.strip():
                logger.debug("Docling returned empty output for %s — trying fallback.", path.name)
                return self._parse_with_fallback(path)

            node = DocumentNode(
                page_content=text.strip(),
                metadata=self._build_metadata(path, parser="docling"),
            )
            # Attach the Docling document object for Phase 2 HybridChunker.
            # This field is excluded from serialization (Field(exclude=True)).
            node.docling_doc = docling_doc
            return node

        except Exception as exc:
            logger.warning(
                "Docling failed on '%s' (%s). Falling back to legacy parser.", path.name, exc
            )
            return self._parse_with_fallback(path)

    # ------------------------------------------------------------------
    # Fallback path (existing loaders)
    # ------------------------------------------------------------------

    def _parse_with_fallback(self, path: Path) -> DocumentNode | None:
        """Use existing file loaders for non-Docling formats or when Docling fails."""
        from .loaders import (  # noqa: PLC0415
            CodeLoader,
            CsvLoader,
            DocxLoader,
            HtmlLoader,
            JsonLoader,
            MarkdownLoader,
            PdfLoader,
            PlainTextLoader,
            PptxLoader,
        )

        _EXTENSION_LOADER_MAP: dict[str, Any] = {
            ".pdf":      PdfLoader(),
            ".docx":     DocxLoader(),
            ".pptx":     PptxLoader(),
            ".html":     HtmlLoader(),
            ".htm":      HtmlLoader(),
            ".md":       MarkdownLoader(),
            ".markdown": MarkdownLoader(),
            ".json":     JsonLoader(),
            ".jsonl":    JsonLoader(),
            ".csv":      CsvLoader(),
            ".py":       CodeLoader(),
            ".sql":      CodeLoader(),
            ".yaml":     CodeLoader(),
            ".yml":      CodeLoader(),
        }

        loader = _EXTENSION_LOADER_MAP.get(path.suffix.lower(), PlainTextLoader())
        try:
            node = loader.load(path)
            # Override source_type: legacy loaders set "unstructured" by default,
            # but this node came through DocumentIngester so it should read "document".
            node.metadata.source_type = "document"
            # Graft access_scope onto the legacy node's metadata
            if not node.metadata.access_scope:
                node.metadata.access_scope = _infer_access_scope(path, self.default_scope)
            node.metadata.extra["parser"] = "fallback"
            return node
        except Exception as exc:
            logger.error("Fallback loader failed for '%s': %s", path, exc, exc_info=True)
            return None
