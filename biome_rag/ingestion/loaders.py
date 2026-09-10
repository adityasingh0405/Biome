from __future__ import annotations

import csv
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from .dedup import compute_file_sha256, compute_payload_sha256
from .models import DocumentMetadata, DocumentNode, NormalizedDocument

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Base Loader & Unstructured File Loaders
# ----------------------------------------------------------------------

class BaseLoader:
    """Base class for individual file loaders."""

    def load(self, path: Path) -> DocumentNode:
        raise NotImplementedError


class PlainTextLoader(BaseLoader):
    """Loader for plain text and log files with encoding fallback."""

    def load(self, path: Path) -> DocumentNode:
        content = self._read_text(path)
        file_hash = compute_file_sha256(path)
        access_level = _infer_access_level(path.name)

        return DocumentNode(
            page_content=content.strip(),
            metadata=DocumentMetadata(
                source_type="unstructured",
                source_name=path.name,
                file_path=str(path.resolve()),
                file_extension=path.suffix.lower(),
                file_hash=file_hash,
                access_level=access_level,
                extra={"section_heading": path.stem},
            ),
        )

    def _read_text(self, path: Path) -> str:
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                return path.read_text(encoding=enc)
            except UnicodeDecodeError:
                continue
        return path.read_text(encoding="utf-8", errors="replace")


class MarkdownLoader(BaseLoader):
    """Loader for Markdown documents extracting primary headings."""

    def load(self, path: Path) -> DocumentNode:
        text = PlainTextLoader()._read_text(path)
        heading = self._extract_heading(text)
        file_hash = compute_file_sha256(path)
        access_level = _infer_access_level(path.name)

        return DocumentNode(
            page_content=text.strip(),
            metadata=DocumentMetadata(
                source_type="unstructured",
                source_name=path.name,
                file_path=str(path.resolve()),
                file_extension=path.suffix.lower(),
                file_hash=file_hash,
                access_level=access_level,
                extra={"section_heading": heading or path.stem},
            ),
        )

    def _extract_heading(self, text: str) -> str | None:
        for line in text.splitlines():
            line_str = line.strip()
            if line_str.startswith("#"):
                return line_str.lstrip("#").strip()
        return None


class PdfLoader(BaseLoader):
    """Fast-path PDF loader using PyMuPDF (fitz) with fallback to pypdf."""

    def load(self, path: Path) -> DocumentNode:
        text, page_count = self._extract_pdf_text(path)
        page_num_from_name = self._extract_page_number(path.name)
        file_hash = compute_file_sha256(path)
        access_level = _infer_access_level(path.name)

        return DocumentNode(
            page_content=text.strip(),
            metadata=DocumentMetadata(
                source_type="unstructured",
                source_name=path.name,
                file_path=str(path.resolve()),
                file_extension=path.suffix.lower(),
                file_hash=file_hash,
                access_level=access_level,
                extra={
                    "section_heading": path.stem,
                    "page_number": page_num_from_name,
                    "page_count": page_count,
                },
            ),
        )

    def _extract_pdf_text(self, path: Path) -> tuple[str, int]:
        # Fast path: PyMuPDF (fitz)
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(path))
            pages_text: list[str] = []
            for idx, page in enumerate(doc, start=1):
                page_text = page.get_text() or ""
                if page_text.strip():
                    pages_text.append(f"[Page {idx}]\n{page_text.strip()}")
            page_count = len(doc)
            doc.close()
            return "\n\n".join(pages_text), page_count
        except ImportError:
            logger.debug("PyMuPDF (fitz) not available. Falling back to pypdf.")
        except Exception as e:
            logger.warning("fitz extraction failed for %s (%s). Attempting fallback.", path, e)

        # Fallback path: pypdf / PyPDF2
        try:
            try:
                from pypdf import PdfReader
            except ImportError:
                from PyPDF2 import PdfReader  # type: ignore

            with path.open("rb") as fh:
                reader = PdfReader(fh)
                pages_text = []
                for idx, page in enumerate(reader.pages, start=1):
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        pages_text.append(f"[Page {idx}]\n{page_text.strip()}")
                return "\n\n".join(pages_text), len(reader.pages)
        except Exception as e:
            logger.warning("PDF extraction failed completely for %s: %s", path, e)
            return "", 0

    def _extract_page_number(self, name: str) -> int | None:
        match = re.search(r"p(?:age)?[-_ ]?(\d+)", name, flags=re.I)
        if match:
            return int(match.group(1))
        return None


class DocxLoader(BaseLoader):
    """Loader for Word (.docx) documents using python-docx."""

    def load(self, path: Path) -> DocumentNode:
        try:
            from docx import Document
            doc = Document(str(path))
            blocks: list[str] = []

            for paragraph in doc.paragraphs:
                text = paragraph.text.strip()
                if text:
                    blocks.append(text)

            for table in doc.tables:
                for row in table.rows:
                    row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_cells:
                        blocks.append(" | ".join(row_cells))

            content = "\n\n".join(blocks)
        except Exception as e:
            logger.warning("Failed to extract DOCX text from %s: %s", path, e)
            content = PlainTextLoader()._read_text(path)

        file_hash = compute_file_sha256(path)
        access_level = _infer_access_level(path.name)

        return DocumentNode(
            page_content=content.strip(),
            metadata=DocumentMetadata(
                source_type="unstructured",
                source_name=path.name,
                file_path=str(path.resolve()),
                file_extension=path.suffix.lower(),
                file_hash=file_hash,
                access_level=access_level,
                extra={"section_heading": path.stem},
            ),
        )


class PptxLoader(BaseLoader):
    """Loader for PowerPoint (.pptx) presentations using python-pptx."""

    def load(self, path: Path) -> DocumentNode:
        try:
            from pptx import Presentation
            prs = Presentation(str(path))
            slides_text: list[str] = []

            for idx, slide in enumerate(prs.slides, start=1):
                slide_lines: list[str] = []
                # Extract title if present
                if slide.shapes.title and slide.shapes.title.text.strip():
                    slide_lines.append(f"Title: {slide.shapes.title.text.strip()}")

                # Extract shape text
                for shape in slide.shapes:
                    if shape == slide.shapes.title:
                        continue
                    if shape.has_text_frame:
                        for paragraph in shape.text_frame.paragraphs:
                            line = paragraph.text.strip()
                            if line:
                                slide_lines.append(line)

                # Extract slide notes if available
                if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                    notes = slide.notes_slide.notes_text_frame.text.strip()
                    if notes:
                        slide_lines.append(f"Notes: {notes}")

                if slide_lines:
                    slides_text.append(f"[Slide {idx}]\n" + "\n".join(slide_lines))

            content = "\n\n".join(slides_text)
        except Exception as e:
            logger.warning("Failed to extract PPTX text from %s: %s", path, e)
            content = PlainTextLoader()._read_text(path)

        file_hash = compute_file_sha256(path)
        access_level = _infer_access_level(path.name)

        return DocumentNode(
            page_content=content.strip(),
            metadata=DocumentMetadata(
                source_type="unstructured",
                source_name=path.name,
                file_path=str(path.resolve()),
                file_extension=path.suffix.lower(),
                file_hash=file_hash,
                access_level=access_level,
                extra={"section_heading": path.stem},
            ),
        )


class HtmlLoader(BaseLoader):
    """Loader for HTML documents stripping tags and scripts."""

    def load(self, path: Path) -> DocumentNode:
        text = PlainTextLoader()._read_text(path)
        cleaned = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
        cleaned = re.sub(r"<style.*?</style>", " ", cleaned, flags=re.S | re.I)
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        title_match = re.search(r"<title>(.*?)</title>", text, re.I)
        heading = title_match.group(1).strip() if title_match else path.stem
        file_hash = compute_file_sha256(path)
        access_level = _infer_access_level(path.name)

        return DocumentNode(
            page_content=cleaned.strip(),
            metadata=DocumentMetadata(
                source_type="unstructured",
                source_name=path.name,
                file_path=str(path.resolve()),
                file_extension=path.suffix.lower(),
                file_hash=file_hash,
                access_level=access_level,
                extra={"section_heading": heading},
            ),
        )


class JsonLoader(BaseLoader):
    """Loader for structured JSON text documents."""

    def load(self, path: Path) -> DocumentNode:
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
            data = json.loads(raw)
            if isinstance(data, dict):
                lines = [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in data.items()]
                text = "\n".join(lines)
            elif isinstance(data, list):
                lines = [json.dumps(item, ensure_ascii=False) for item in data]
                text = "\n".join(lines)
            else:
                text = str(data)
        except Exception as e:
            logger.warning("JSON parse failed for %s (%s); reading raw text.", path, e)
            text = PlainTextLoader()._read_text(path)

        file_hash = compute_file_sha256(path)
        access_level = _infer_access_level(path.name)

        return DocumentNode(
            page_content=text.strip(),
            metadata=DocumentMetadata(
                source_type="unstructured",
                source_name=path.name,
                file_path=str(path.resolve()),
                file_extension=path.suffix.lower(),
                file_hash=file_hash,
                access_level=access_level,
                extra={"section_heading": path.stem},
            ),
        )


class CsvLoader(BaseLoader):
    """Loader for CSV files formatting rows with header context."""

    def load(self, path: Path) -> DocumentNode:
        try:
            text_lines = []
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                reader = csv.reader(fh)
                header = next(reader, None)
                if header:
                    text_lines.append(f"Columns: {', '.join(header)}")
                    for idx, row in enumerate(reader, start=1):
                        formatted = ", ".join(f"{h}: {val}" for h, val in zip(header, row) if val.strip())
                        text_lines.append(f"Row {idx}: {formatted}")
                else:
                    text_lines.append(PlainTextLoader()._read_text(path))
            text = "\n".join(text_lines)
        except Exception as e:
            logger.warning("CSV parse failed for %s: %s", path, e)
            text = PlainTextLoader()._read_text(path)

        file_hash = compute_file_sha256(path)
        access_level = _infer_access_level(path.name)

        return DocumentNode(
            page_content=text.strip(),
            metadata=DocumentMetadata(
                source_type="unstructured",
                source_name=path.name,
                file_path=str(path.resolve()),
                file_extension=path.suffix.lower(),
                file_hash=file_hash,
                access_level=access_level,
                extra={"section_heading": path.stem},
            ),
        )


class CodeLoader(BaseLoader):
    """Loader for code and config files formatted in fenced code blocks."""

    def load(self, path: Path) -> DocumentNode:
        text = PlainTextLoader()._read_text(path)
        lang = path.suffix.lstrip(".").lower()
        formatted = f"```{lang}\n// Source: {path.name}\n{text}\n```"
        file_hash = compute_file_sha256(path)
        access_level = _infer_access_level(path.name)

        return DocumentNode(
            page_content=formatted.strip(),
            metadata=DocumentMetadata(
                source_type="unstructured",
                source_name=path.name,
                file_path=str(path.resolve()),
                file_extension=path.suffix.lower(),
                file_hash=file_hash,
                access_level=access_level,
                extra={"section_heading": f"Code: {path.name}"},
            ),
        )


def _infer_access_level(filename: str) -> str:
    """Infer RBAC access level from file name and directory naming cues."""
    name_lower = filename.lower()
    if any(k in name_lower for k in ("secret", "confidential", "compliance", "salary", "audit")):
        return "confidential"
    if any(k in name_lower for k in ("security", "private", "internal_only", "hr_")):
        return "restricted"
    if any(k in name_lower for k in ("public", "readme", "guide", "overview")):
        return "public"
    return "internal"


# ----------------------------------------------------------------------
# Unstructured Bucket Loader
# ----------------------------------------------------------------------

class UnstructuredBucketLoader:
    """Discovers, loads, and normalizes unstructured files from local folder."""

    SUPPORTED_EXTENSIONS = {
        ".pdf": PdfLoader(),
        ".docx": DocxLoader(),
        ".pptx": PptxLoader(),
        ".txt": PlainTextLoader(),
        ".md": MarkdownLoader(),
        ".markdown": MarkdownLoader(),
        ".html": HtmlLoader(),
        ".htm": HtmlLoader(),
        ".json": JsonLoader(),
        ".csv": CsvLoader(),
        ".py": CodeLoader(),
        ".sql": CodeLoader(),
        ".yaml": CodeLoader(),
        ".yml": CodeLoader(),
    }

    def __init__(self, bucket_dir: str | Path = "local_data_bucket/unstructured"):
        self.bucket_dir = Path(bucket_dir)

    def discover_files(self) -> list[Path]:
        """Scan bucket directory for all supported file types."""
        if not self.bucket_dir.exists():
            logger.warning("Bucket directory does not exist: %s", self.bucket_dir)
            return []

        files: list[Path] = []
        for path in sorted(self.bucket_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                files.append(path)
        return files

    def load(self, files: Sequence[Path] | None = None) -> list[DocumentNode]:
        """Load files into standard DocumentNode objects."""
        target_files = list(files if files is not None else self.discover_files())
        nodes: list[DocumentNode] = []

        for path in target_files:
            loader = self.SUPPORTED_EXTENSIONS.get(path.suffix.lower(), PlainTextLoader())
            try:
                node = loader.load(path)
                if node.page_content.strip():
                    nodes.append(node)
                else:
                    logger.debug("Skipping empty document: %s", path)
            except Exception as e:
                logger.error("Failed to ingest unstructured file %s: %s", path, e, exc_info=True)

        return nodes


# ----------------------------------------------------------------------
# PostgreSQL Structured Database Loader
# ----------------------------------------------------------------------

class PostgreSQLLoader:
    """Connects to local PostgreSQL using SQLAlchemy and converts rows

    into rich, natural-language sentence blocks suitable for semantic embedding.
    """

    def __init__(
        self,
        db_uri: str | None = None,
        table_name: str | None = None,
    ):
        import os
        self.db_uri = db_uri or os.getenv("POSTGRES_URI", "postgresql://localhost:5432/enterprise_rag")
        self.table_name = table_name or os.getenv("POSTGRES_TABLE", "enterprise_tickets")

    def load(
        self,
        table_name: str | None = None,
        limit: int | None = None,
    ) -> list[DocumentNode]:
        """Query target table and serialize rows into DocumentNode objects."""
        from sqlalchemy import create_engine, text

        target_table = table_name or self.table_name
        engine = create_engine(self.db_uri, pool_pre_ping=True)
        nodes: list[DocumentNode] = []

        query_str = f"SELECT * FROM {target_table}"
        if limit is not None and limit > 0:
            query_str += f" LIMIT {int(limit)}"

        try:
            with engine.connect() as conn:
                result = conn.execute(text(query_str))
                for row_mapping in result.mappings():
                    row_dict = dict(row_mapping)
                    node = self._serialize_row_to_node(target_table, row_dict)
                    nodes.append(node)
        except Exception as e:
            logger.error("PostgreSQL query failed on table '%s': %s", target_table, e, exc_info=True)
            raise
        finally:
            engine.dispose()

        return nodes

    def _serialize_row_to_node(self, table_name: str, row: dict[str, Any]) -> DocumentNode:
        """Convert relational row dict to rich natural language DocumentNode."""
        # Detect primary key
        pk = (
            row.get("ticket_id")
            or row.get("id")
            or row.get("uuid")
            or row.get("pk")
        )
        pk_str = str(pk) if pk is not None else None

        # Compute deterministic row payload hash
        file_hash = compute_payload_sha256(row)

        # Department & RBAC access level
        department = str(row.get("department", "General"))
        access_level = self._determine_rbac_level(department)

        # Natural language semantic serialization
        if "ticket_id" in row or "issue_summary" in row:
            page_content = self._format_ticket_nl(row)
        else:
            page_content = self._format_generic_nl(table_name, row)

        created_at_val = row.get("created_at")
        if isinstance(created_at_val, datetime):
            created_iso = created_at_val.isoformat()
        elif created_at_val:
            created_iso = str(created_at_val)
        else:
            created_iso = datetime.now(timezone.utc).isoformat()

        # Sanitize extra row dictionary for JSON serialization
        sanitized_extra: dict[str, Any] = {}
        for k, v in row.items():
            if isinstance(v, (datetime, Path)):
                sanitized_extra[k] = v.isoformat() if isinstance(v, datetime) else str(v)
            else:
                sanitized_extra[k] = str(v) if hasattr(v, "hex") else v

        metadata = DocumentMetadata(
            source_type="postgresql",
            source_name=table_name,
            primary_key=pk_str,
            file_hash=file_hash,
            access_level=access_level,
            department=department,
            created_at=created_iso,
            extra=sanitized_extra,
        )

        return DocumentNode(page_content=page_content, metadata=metadata)

    def _determine_rbac_level(self, department: str) -> str:
        """Map organizational department to RBAC sensitivity level."""
        dept_upper = department.upper()
        if "HR" in dept_upper or "HUMAN RESOURCES" in dept_upper or "LEGAL" in dept_upper:
            return "confidential"
        if "ENGINEERING" in dept_upper or "SECURITY" in dept_upper:
            return "restricted"
        return "internal"

    def _format_ticket_nl(self, row: dict[str, Any]) -> str:
        """Format an enterprise support ticket into rich, natural-language context."""
        ticket_id = row.get("ticket_id", "N/A")
        dept = row.get("department", "General")
        system = row.get("route_or_system", "Unspecified System")
        priority = row.get("priority_level", "Medium")
        resolved = row.get("resolved")
        status_text = "Resolved" if resolved is True else "Open / Unresolved"
        created_at = row.get("created_at", "Unknown Date")
        summary = row.get("issue_summary", "").strip()
        description = row.get("detailed_description", "").strip()

        return (
            f"Support Ticket [ID: {ticket_id}]\n"
            f"Department: {dept}\n"
            f"Target System / Route: {system}\n"
            f"Priority Level: {priority} | Operational Status: {status_text}\n"
            f"Logged At: {created_at}\n"
            f"Issue Summary: {summary}\n"
            f"Detailed Description: {description}"
        )

    def _format_generic_nl(self, table_name: str, row: dict[str, Any]) -> str:
        """Dynamic narrative serialization for arbitrary database tables."""
        lines = [f"Record from database table '{table_name}':"]
        for col, val in row.items():
            if val is not None and str(val).strip():
                formatted_col = col.replace("_", " ").title()
                lines.append(f"- {formatted_col}: {val}")
        return "\n".join(lines)


# ----------------------------------------------------------------------
# Legacy Compatibility Helper
# ----------------------------------------------------------------------

def load_documents(paths: Iterable[Path]) -> list[NormalizedDocument]:
    """Legacy helper returning NormalizedDocument list for backward compatibility."""
    bucket_loader = UnstructuredBucketLoader()
    docs: list[NormalizedDocument] = []
    for p in paths:
        path = Path(p)
        if not path.is_file():
            continue
        loader = bucket_loader.SUPPORTED_EXTENSIONS.get(path.suffix.lower(), PlainTextLoader())
        try:
            node = loader.load(path)
            docs.append(node.to_normalized_document())
        except Exception as e:
            logger.warning("Failed to load legacy document %s: %s", path, e)
    return docs