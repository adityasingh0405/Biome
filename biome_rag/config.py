"""Central configuration module — single source of truth for all settings.

BUG-003 fix: migrated from a frozen @dataclass + os.getenv factory to
pydantic BaseSettings, which provides:
  - Automatic .env file loading
  - Field-level type coercion and validation
  - Env-var prefix support for namespacing
  - A clean, self-documenting settings class

All existing field names are preserved for backward compatibility.
The old `get_runtime_settings()` factory is kept as a compatibility shim.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    _PYDANTIC_SETTINGS = True
except ImportError:
    # Graceful fallback if pydantic-settings is not yet installed
    from pydantic import BaseModel as BaseSettings  # type: ignore[assignment]
    _PYDANTIC_SETTINGS = False


class Settings(BaseSettings):
    """All runtime settings read from environment variables / .env file.

    Pydantic BaseSettings automatically reads from:
      1. Environment variables (highest priority)
      2. .env file in the project root
      3. The default values defined here

    Every credential and connection string lives here and NOWHERE else.
    Never hardcode secrets in source files — put them in .env only.
    """

    if _PYDANTIC_SETTINGS:
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="ignore",
        )

    # ------------------------------------------------------------------ #
    # Retrieval                                                            #
    # ------------------------------------------------------------------ #
    dense_top_k: int = 5
    rrf_dense_weight: float = 0.7
    rrf_sparse_weight: float = 0.3
    rrf_k: int = 60  # RRF smoothing constant (Cormack et al., 2009)

    # ------------------------------------------------------------------ #
    # LLM providers                                                        #
    # ------------------------------------------------------------------ #
    llm_provider: Literal["local", "ollama", "openai", "anthropic", "groq"] = "local"

    # Ollama
    ollama_model: str = "llama3.1:8b"
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout: int = 60

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"

    # Groq (Phase 5 fallback)
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"

    # ------------------------------------------------------------------ #
    # Embeddings                                                           #
    # ------------------------------------------------------------------ #
    embedding_provider: str = "sentence-transformers"
    embedding_model_name: str = "BAAI/bge-m3"  # Phase 3 target
    embedding_collection_name: str = "enterprise_kb"
    embedding_device: str = "cpu"  # "cuda" for GPU

    # ------------------------------------------------------------------ #
    # Vector database (Qdrant — Phase 3+)                                 #
    # ------------------------------------------------------------------ #
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "enterprise_kb"
    qdrant_api_key: str = ""

    # ------------------------------------------------------------------ #
    # Storage (PostgreSQL)                                                 #
    # ------------------------------------------------------------------ #
    postgres_uri: str = "postgresql://localhost:5432/enterprise_rag"
    postgres_table: str = "enterprise_tickets"

    # ------------------------------------------------------------------ #
    # Redis (Phase 5 — session memory)                                    #
    # ------------------------------------------------------------------ #
    redis_url: str = "redis://localhost:6379/0"
    redis_session_ttl: int = 3600  # seconds
    redis_window_size: int = 10    # max messages in sliding window

    # ------------------------------------------------------------------ #
    # Slack ingestion (Phase 1)                                            #
    # ------------------------------------------------------------------ #
    slack_bot_token: str = ""
    slack_app_token: str = ""
    slack_workspace_id: str = ""

    # ------------------------------------------------------------------ #
    # Langfuse observability (Phase 5)                                    #
    # ------------------------------------------------------------------ #
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"
    langfuse_enabled: bool = False

    # ------------------------------------------------------------------ #
    # Chunking                                                             #
    # ------------------------------------------------------------------ #
    chunk_size: int = 800          # characters (legacy default)
    chunk_overlap: int = 120       # characters
    dedup_threshold: float = 0.95
    # Token-count targets (Phase 2 — Docling / Chonkie):
    pdf_chunk_max_tokens: int = 600
    pdf_chunk_min_tokens: int = 400
    slack_chunk_max_tokens: int = 400
    slack_chunk_min_tokens: int = 256
    pg_chunk_max_tokens: int = 256
    pg_chunk_min_tokens: int = 128
    table_split_max_tokens: int = 600  # oversized-table row-split threshold

    # ------------------------------------------------------------------ #
    # Citation & confidence                                                #
    # ------------------------------------------------------------------ #
    citation_verification_enabled: bool = True
    insufficient_confidence_threshold: float = 0.5
    sensitive_fields: str = "salary,ssn,tax_id,password,secret"  # comma-separated

    # ------------------------------------------------------------------ #
    # Context window                                                       #
    # ------------------------------------------------------------------ #
    max_context_chunks: int = 5
    max_context_tokens: int = 1500

    # ------------------------------------------------------------------ #
    # Misc                                                                 #
    # ------------------------------------------------------------------ #
    fallback_keyword_threshold: float = 0.5
    retry_attempts: int = 2
    log_level: str = "INFO"

    @property
    def sensitive_field_list(self) -> list[str]:
        """Return the sensitive_fields string as a parsed list."""
        return [f.strip().lower() for f in self.sensitive_fields.split(",") if f.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton Settings instance.

    Uses @lru_cache so the .env file is read only once per process.
    Call `get_settings.cache_clear()` in tests to reset between test runs.
    """
    return Settings()


# ---------------------------------------------------------------------------
# Backward-compatibility shim — existing code uses get_runtime_settings()
# ---------------------------------------------------------------------------

def get_runtime_settings() -> Settings:
    """Backward-compatible alias for get_settings().

    All new code should use get_settings() directly.
    """
    return get_settings()
