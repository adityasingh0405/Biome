from pathlib import Path

from biome_rag.ingestion.loaders import MarkdownLoader, PdfLoader


def test_markdown_loader_extracts_heading(tmp_path: Path):
    path = tmp_path / "guide.md"
    path.write_text("# Setup\n\nInstall the tool first.\n", encoding="utf-8")

    document = MarkdownLoader().load(path)

    assert document.section_heading == "Setup"
    assert "Install" in document.text


def test_pdf_loader_extracts_page_number_from_filename(tmp_path: Path):
    path = tmp_path / "architecture-page-7.pdf"
    path.write_text("sample pdf content", encoding="utf-8")

    document = PdfLoader().load(path)

    assert document.page_number == 7
