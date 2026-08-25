from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class RuntimeSettings:
    dense_top_k: int
    rrf_dense_weight: float
    rrf_sparse_weight: float
    llm_provider: str
    # Ollama settings
    ollama_model: str
    ollama_base_url: str
    ollama_timeout: int
    # OpenAI settings
    openai_model: str
    # Anthropic settings
    anthropic_model: str
    # Embedding settings
    embedding_provider: str
    embedding_collection_name: str
    # Citation & confidence settings
    citation_verification_enabled: bool
    insufficient_confidence_threshold: float
    # Context settings
    max_context_chunks: int
    max_context_tokens: int
    # Misc
    fallback_keyword_threshold: float
    retry_attempts: int


def get_runtime_settings() -> RuntimeSettings:
    def _as_bool(value: str | None, default: bool) -> bool:
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    return RuntimeSettings(
        dense_top_k=int(os.getenv("DENSE_TOP_K", "5")),
        rrf_dense_weight=float(os.getenv("RRF_DENSE_WEIGHT", "0.7")),
        rrf_sparse_weight=float(os.getenv("RRF_SPARSE_WEIGHT", "0.3")),
        llm_provider=os.getenv("LLM_PROVIDER", "local").strip().lower(),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2:3b").strip(),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
        ollama_timeout=int(os.getenv("OLLAMA_TIMEOUT", "60")),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5").strip(),
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", "sentence-transformers").strip().lower(),
        citation_verification_enabled=_as_bool(os.getenv("CITATION_VERIFICATION_ENABLED"), True),
        insufficient_confidence_threshold=float(os.getenv("INSUFFICIENT_CONFIDENCE_THRESHOLD", "0.5")),
        embedding_collection_name=os.getenv("EMBEDDING_COLLECTION_NAME", "biome-chunks"),
        max_context_chunks=int(os.getenv("MAX_CONTEXT_CHUNKS", "5")),
        max_context_tokens=int(os.getenv("MAX_CONTEXT_TOKENS", "1500")),
        fallback_keyword_threshold=float(os.getenv("FALLBACK_KEYWORD_THRESHOLD", "0.5")),
        retry_attempts=int(os.getenv("RETRY_ATTEMPTS", "2")),
    )
