"""Chunking router — selects the correct chunker for each source type.

Routing table (also used by the Prefect flow in Phase 5):

    source_type="document"      → DocumentChunker (Docling HybridChunker)
    source_type="postgresql"    → TextChunker.for_postgres()
    source_type="slack"         → TextChunker.for_slack()
    source_type="unstructured"  → TextChunker.for_unstructured()

Usage::

    from biome_rag.chunking import get_chunker, DocumentChunker, TextChunker

    chunker = get_chunker("postgresql")
    chunks  = chunker.chunk_many(documents)
"""

from biome_rag.chunking.base import Chunker, count_tokens, split_text_by_tokens
from biome_rag.chunking.document_chunker import DocumentChunker
from biome_rag.chunking.text_chunker import TextChunker

__all__ = [
    "Chunker",
    "DocumentChunker",
    "TextChunker",
    "count_tokens",
    "split_text_by_tokens",
    "get_chunker",
]


def get_chunker(source_type: str, **kwargs) -> Chunker:
    """Return the appropriate Chunker for a given source_type.

    Args:
        source_type: One of ``"document"``, ``"postgresql"``, ``"slack"``,
                     ``"unstructured"``.
        **kwargs: Forwarded to the Chunker constructor (e.g. ``max_tokens=256``).

    Returns:
        A ``Chunker`` instance configured for the source type.

    Raises:
        ValueError: If ``source_type`` is not recognised.
    """
    match source_type:
        case "document":
            return DocumentChunker(**kwargs)
        case "postgresql":
            return TextChunker.for_postgres(**kwargs)
        case "slack":
            return TextChunker.for_slack(**kwargs)
        case "unstructured":
            return TextChunker.for_unstructured(**kwargs)
        case _:
            raise ValueError(
                f"Unknown source_type '{source_type}'. "
                f"Choose from: 'document', 'postgresql', 'slack', 'unstructured'."
            )
