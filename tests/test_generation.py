from pathlib import Path

from biome_rag.generation.answering import AnswerBuilder, AnswerResponse, ConfidenceScores
from biome_rag.retrieval.models import RankedChunk


def test_answer_builder_returns_insufficient_context_when_confidence_is_low(tmp_path: Path):
    builder = AnswerBuilder(confidence_threshold=0.5)
    chunks = [
        RankedChunk(
            text="Authentication requires a valid API token.",
            source="onboarding.md",
            section_heading="Setup",
            page_number=None,
            dense_score=0.1,
            sparse_score=0.1,
            fused_score=0.1,
            rerank_score=0.1,
        )
    ]

    response = builder.answer("What is the password?", chunks)

    assert response.answer.startswith("I don't know")
    assert response.confidence.retrieval_confidence < 0.5
    assert response.citations[0].verified is False
