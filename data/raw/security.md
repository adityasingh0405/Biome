# Security Guide

## Authentication Model

Biome uses token-based authentication. Every API request must include the `BIOME_API_KEY` in the `Authorization` header:

```
Authorization: Bearer <BIOME_API_KEY>
```

Tokens are 64-character alphanumeric strings. They do not encode permissions; all token holders have full API access within their plan's rate limits.

## Secret Management

### Never hardcode secrets

All secrets must be loaded from environment variables. The `.env` file is excluded from version control via `.gitignore`. Use `.env.example` as the template.

### Required secrets

| Secret | Storage recommendation |
|--------|----------------------|
| `BIOME_API_KEY` | Environment variable or secrets manager |
| `OPENAI_API_KEY` | Environment variable or secrets manager |
| `ANTHROPIC_API_KEY` | Environment variable or secrets manager |

### Docker secrets

In Docker Compose, mount secrets via environment variables, not hardcoded values in `docker-compose.yml`:

```yaml
env_file:
  - .env
```

In Kubernetes, use `Secret` resources and mount them as environment variables — never as config maps.

## Data Security

### Data at rest

ChromaDB vector embeddings and BM25 index files are stored in `data/index/`. These files contain document embeddings but not the original plaintext. Original documents are stored in `data/raw/` and processed chunks in `data/processed/chunks.json`.

For sensitive corpora, encrypt the `data/` directory at the filesystem level (e.g., with LUKS on Linux or BitLocker on Windows).

### Data in transit

All API calls between the dashboard and API use HTTP. For production deployments, place both services behind a TLS-terminating reverse proxy (e.g., nginx or Caddy).

### LLM data privacy

When using `LLM_PROVIDER=openai` or `LLM_PROVIDER=anthropic`, document chunks are sent to third-party APIs as part of the prompt. Ensure your data use agreement with OpenAI or Anthropic covers your use case. For sensitive internal documentation, prefer `LLM_PROVIDER=ollama` to keep all data local.

## Input Validation

The API validates all inputs with Pydantic schemas. Empty questions are rejected before retrieval. Document text submitted via `POST /v1/ingest` is sanitised by the loader (HTML tags stripped, encoding normalised) before storage.

## Rate Limiting

The API enforces per-key rate limits. Exceeding limits returns E1002 with a `Retry-After` header. Implement exponential backoff in clients to handle rate limit responses gracefully.

## Audit Logging

All API requests are logged at `INFO` level including the endpoint, response status, and timestamp. Question text is logged at `INFO` level. Document content is not logged. Set `LOG_LEVEL=WARNING` in production to reduce log volume.

## Vulnerability Disclosure

Report security vulnerabilities to the project maintainer. Do not open public GitHub issues for security concerns.
