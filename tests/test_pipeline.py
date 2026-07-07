from pathlib import Path

from biome_rag.ingestion.models import IngestionConfig
from biome_rag.ingestion.pipeline import IngestionPipeline


def test_pipeline_ingests_documents_and_persists_summary(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "sample.md").write_text("# Setup\n\nInstall the tool.\n", encoding="utf-8")

    config = IngestionConfig(raw_dir=raw_dir, processed_dir=tmp_path / "processed", storage_dir=tmp_path / "index")
    pipeline = IngestionPipeline(config)
    chunks, summary = pipeline.ingest()

    assert summary.documents_processed == 1
    assert summary.chunks_created >= 1
    assert (config.processed_dir / "chunks.json").exists()
    assert (config.storage_dir / "bm25_index.pkl").exists()
