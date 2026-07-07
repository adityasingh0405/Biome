from pathlib import Path

from biome_rag.ingestion.chunkers import FixedSizeChunker, SemanticChunker, StructureAwareChunker


def test_fixed_size_chunker_splits_text():
    chunker = FixedSizeChunker(chunk_size=10, chunk_overlap=3)
    chunks = chunker.chunk("abcdefghijklmno", source="sample.md")
    assert len(chunks) >= 2
    assert chunks[0].chunking_strategy == "fixed"


def test_structure_aware_chunker_splits_on_headers():
    chunker = StructureAwareChunker(chunk_size=40, chunk_overlap=0)
    text = "# Intro\nFirst paragraph about onboarding.\n\n# API\nSecond paragraph about configuration."
    chunks = chunker.chunk(text, source="sample.md")
    assert len(chunks) >= 2


def test_semantic_chunker_creates_chunks_from_sentences():
    chunker = SemanticChunker(chunk_size=80, chunk_overlap=0)
    text = "This is the first sentence. This is the second sentence. This is the third sentence."
    chunks = chunker.chunk(text, source="sample.md")
    assert len(chunks) >= 1
