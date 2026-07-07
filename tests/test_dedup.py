from biome_rag.ingestion.dedup import Deduplicator
from biome_rag.ingestion.models import Chunk


def test_deduplicator_detects_near_duplicate():
    dedup = Deduplicator(threshold=0.95)
    candidate = Chunk(text="alpha beta gamma", source="a.md", section_heading=None, page_number=None, chunk_index=0, chunking_strategy="fixed", character_count=16)
    existing = [Chunk(text="alpha beta gamma", source="b.md", section_heading=None, page_number=None, chunk_index=0, chunking_strategy="fixed", character_count=16)]
    assert dedup.is_duplicate(candidate, existing) is True
