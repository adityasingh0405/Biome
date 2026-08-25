# Configuration Reference

## Environment Variables

All configuration is managed through environment variables. Copy `.env.example` to `.env` to start.

### Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `BIOME_API_KEY` | — | Required. API authentication token |
| `BIOME_DEPLOY_TARGET` | `dev` | Deployment environment: `dev`, `staging`, `production` |

### Embedding

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_PROVIDER` | `sentence-transformers` | `sentence-transformers` or `openai` |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Model name for sentence-transformers |
| `OPENAI_API_KEY` | — | Required if `EMBEDDING_PROVIDER=openai` |
| `EMBEDDING_COLLECTION_NAME` | `biome-chunks` | ChromaDB collection name |

### Chunking

| Variable | Default | Description |
|----------|---------|-------------|
| `CHUNK_SIZE` | `800` | Maximum characters per chunk |
| `CHUNK_OVERLAP` | `120` | Overlap between consecutive chunks |
| `DEDUP_THRESHOLD` | `0.95` | Cosine similarity threshold for near-duplicate detection |

### Retrieval

| Variable | Default | Description |
|----------|---------|-------------|
| `DENSE_TOP_K` | `5` | Number of candidates from dense retrieval |
| `RRF_DENSE_WEIGHT` | `0.7` | Weight given to dense ranks in RRF fusion |
| `RRF_SPARSE_WEIGHT` | `0.3` | Weight given to sparse (BM25) ranks in RRF fusion |
| `MAX_CONTEXT_CHUNKS` | `5` | Maximum chunks passed to LLM as context |
| `MAX_CONTEXT_TOKENS` | `1500` | Maximum total tokens in context window |
| `FALLBACK_KEYWORD_THRESHOLD` | `0.5` | Minimum keyword overlap ratio for smart fallback |

### Language Model

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `local` | `local`, `ollama`, `openai`, or `anthropic` |
| `OLLAMA_MODEL` | `llama3.2:3b` | Ollama model name |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_TIMEOUT` | `60` | Timeout in seconds for Ollama requests |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model name |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-5` | Anthropic model name |
| `ANTHROPIC_API_KEY` | — | Required if `LLM_PROVIDER=anthropic` |

### Citation & Confidence

| Variable | Default | Description |
|----------|---------|-------------|
| `CITATION_VERIFICATION_ENABLED` | `true` | Enable LLM-as-judge citation verification |
| `INSUFFICIENT_CONFIDENCE_THRESHOLD` | `0.5` | Below this composite score, return "I don't know" |
| `RETRY_ATTEMPTS` | `2` | Number of retries for LLM calls |

## Chunking Strategy Selection

The pipeline runs all three chunking strategies (fixed, structure-aware, semantic) by default. To restrict to a single strategy during evaluation, set `CHUNKING_STRATEGY` to `fixed`, `structure`, or `semantic`. Default is `all` (runs all three and deduplicates).

## Logging

Set `LOG_LEVEL` to `DEBUG`, `INFO`, `WARNING`, or `ERROR`. Default is `INFO`. In Docker, logs are streamed to stdout.

## Storage Layout

```
data/
├── raw/            # Original uploaded documents
├── processed/
│   └── chunks.json # All processed chunks with metadata
└── index/
    ├── bm25_index.pkl    # BM25 sparse index (pickle)
    └── chroma/           # ChromaDB vector store (directory)
```
