from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from .models import NormalizedDocument


class BaseLoader:
    def load(self, path: Path) -> NormalizedDocument:
        raise NotImplementedError


class MarkdownLoader(BaseLoader):
    def load(self, path: Path) -> NormalizedDocument:
        text = path.read_text(encoding="utf-8")
        heading = self._extract_heading(text)
        return NormalizedDocument(text=text, source=str(path), section_heading=heading)

    def _extract_heading(self, text: str) -> str | None:
        for line in text.splitlines():
            if line.startswith("#"):
                return line.lstrip("#").strip()
        return None


class PlainTextLoader(BaseLoader):
    def load(self, path: Path) -> NormalizedDocument:
        text = path.read_text(encoding="utf-8")
        return NormalizedDocument(text=text, source=str(path))


class HtmlLoader(BaseLoader):
    def load(self, path: Path) -> NormalizedDocument:
        text = path.read_text(encoding="utf-8")
        cleaned = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
        cleaned = re.sub(r"<style.*?</style>", " ", cleaned, flags=re.S | re.I)
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return NormalizedDocument(text=cleaned.strip(), source=str(path))


class PdfLoader(BaseLoader):
    def load(self, path: Path) -> NormalizedDocument:
        text = path.read_text(encoding="utf-8")
        page_number = self._extract_page_number(path.name)
        return NormalizedDocument(text=text, source=str(path), page_number=page_number)

    def _extract_page_number(self, name: str) -> int | None:
        match = re.search(r"p(?:age)?[-_ ]?(\d+)", name, flags=re.I)
        if match:
            return int(match.group(1))
        return None


def load_documents(paths: Iterable[Path]) -> list[NormalizedDocument]:
    loaders = {
        ".md": MarkdownLoader(),
        ".markdown": MarkdownLoader(),
        ".txt": PlainTextLoader(),
        ".html": HtmlLoader(),
        ".htm": HtmlLoader(),
        ".pdf": PdfLoader(),
    }
    docs: list[NormalizedDocument] = []
    for path in paths:
        loader = loaders.get(path.suffix.lower())
        if loader is None:
            continue
        docs.append(loader.load(path))
    return docs
