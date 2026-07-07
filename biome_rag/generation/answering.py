from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from biome_rag.retrieval.models import RankedChunk


@dataclass
class Citation:
    chunk_index: int
    text: str
    verified: bool = False


@dataclass
class ConfidenceScores:
    retrieval_confidence: float
    citation_coverage: float
    completeness: float
    composite: float


@dataclass
class AnswerResponse:
    answer: str
    citations: list[Citation] = field(default_factory=list)
    confidence: ConfidenceScores | None = None
    retrieved_chunks: list[RankedChunk] = field(default_factory=list)


class AnswerBuilder:
    def __init__(self, confidence_threshold: float = 0.5):
        self.confidence_threshold = confidence_threshold

    def answer(self, question: str, chunks: list[RankedChunk]) -> AnswerResponse:
        if not chunks:
            return AnswerResponse(
                answer="I don't know. No supporting context was found.",
                citations=[],
                confidence=ConfidenceScores(0.0, 0.0, 0.0, 0.0),
                retrieved_chunks=[],
            )

        retrieval_confidence = min(1.0, len(chunks) / 3.0)
        citation_coverage = 1.0 if chunks else 0.0
        completeness = 0.4 if retrieval_confidence >= self.confidence_threshold else 0.0
        composite = (retrieval_confidence + citation_coverage + completeness) / 3.0

        if retrieval_confidence < self.confidence_threshold:
            return AnswerResponse(
                answer="I don't know. The retrieved context was insufficient to answer this confidently.",
                citations=[Citation(chunk_index=idx, text=chunk.text, verified=False) for idx, chunk in enumerate(chunks)],
                confidence=ConfidenceScores(retrieval_confidence, citation_coverage, completeness, composite),
                retrieved_chunks=chunks,
            )

        answer_text = f"Based on the retrieved context, the best answer is: {chunks[0].text}"
        citations = [Citation(chunk_index=idx, text=chunk.text, verified=True) for idx, chunk in enumerate(chunks[:2])]
        return AnswerResponse(
            answer=answer_text,
            citations=citations,
            confidence=ConfidenceScores(retrieval_confidence, citation_coverage, completeness, composite),
            retrieved_chunks=chunks,
        )
