# Frequently Asked Questions

## General

### What is Biome RAG?

Biome RAG is a retrieval-augmented generation system for internal documentation. It indexes your documents using both dense vector search and sparse keyword (BM25) search, fuses the results using Reciprocal Rank Fusion, reranks with a cross-encoder, and generates grounded answers with cited sources.

### What file formats does Biome support?

Biome supports Markdown (`.md`), plain text (`.txt`), HTML (`.html`, `.htm`), and PDF (`.pdf`). Other formats are silently skipped during ingestion.

### How long does ingestion take?

For a 10-document corpus, ingestion takes approximately 30–60 seconds including embedding and cross-encoder model loading. For 100 documents, expect 5–10 minutes. Ingestion scales roughly linearly with document count.

### Can I add documents without re-running full ingestion?

Yes. Use `POST /v1/ingest` to add new documents. The pipeline incrementally adds new chunks to both indexes. Near-duplicate detection prevents re-inserting content that already exists.

## Retrieval

### What is hybrid retrieval and why is it better than dense-only?

Hybrid retrieval combines dense (semantic embedding) search and sparse (BM25 keyword) search. Dense retrieval finds semantically similar content even when exact terms differ. Sparse retrieval finds documents containing exact query terms. Combining both via Reciprocal Rank Fusion ensures neither signal is ignored. For queries containing exact configuration keys (like `BIOME_API_KEY`) or error codes (like `E1001`), sparse retrieval consistently outperforms dense-only search because embeddings tend to smooth over exact token matches.

### What is Reciprocal Rank Fusion?

RRF combines ranked lists from multiple sources without requiring score normalisation. Each document is scored as the weighted sum of `1/rank` across all lists. The default weights are `0.7` for dense and `0.3` for sparse. These are configurable via `RRF_DENSE_WEIGHT` and `RRF_SPARSE_WEIGHT`.

### What does the reranker do?

After RRF fusion, the top-20 candidates are passed to a cross-encoder reranker (`cross-encoder/ms-marco-MiniLM-L-6-v2`). The cross-encoder scores each (query, document) pair jointly, which is more accurate than embedding-based similarity but too slow to run over the full index. It returns the top-5 results.

### Why does the retrieval sometimes return "I don't know"?

If the composite confidence score (combining retrieval relevance, citation coverage, and answer completeness) falls below the `INSUFFICIENT_CONFIDENCE_THRESHOLD` (default `0.5`), the system returns a structured "insufficient context" response rather than generating a potentially hallucinated answer. You can lower this threshold in `.env` if you prefer the system to attempt answers with lower confidence.

## Generation

### How does citation work?

The system numbers the retrieved context blocks as `[1]`, `[2]`, etc. in the prompt. The language model is instructed to cite sources using these numbers inline. After generation, the system parses the `[n]` markers, pairs each citation with the corresponding chunk, and runs a verification pass to confirm the chunk supports the claim.

### What happens if a citation is unverified?

Unverified citations appear in the response with `verified: false`. The dashboard highlights these in amber to signal they require manual review. The presence of unverified citations does not suppress the answer.

### Can I use a different language model?

Yes. Set `LLM_PROVIDER` to:
- `ollama` — local inference via Ollama (default, requires Ollama running)
- `openai` — OpenAI GPT-4o or GPT-4o-mini (requires `OPENAI_API_KEY`)
- `anthropic` — Anthropic Claude (requires `ANTHROPIC_API_KEY`)

## Troubleshooting

### The API returns 500 errors

Check that ingestion has been run (`data/processed/chunks.json` exists) and that the storage directory is writable.

### Answers are very short or seem truncated

Increase `MAX_CONTEXT_TOKENS` (default 1500) or `MAX_CONTEXT_CHUNKS` (default 5) in `.env`.

### The cross-encoder is slow

The cross-encoder (`ms-marco-MiniLM-L-6-v2`) loads on first use. Subsequent queries are faster. To disable reranking entirely, set the reranker model to an invalid name — it will fall back to token overlap scoring.

### ChromaDB error on startup

Delete `data/index/chroma/` and re-run ingestion. The Chroma schema can change between package versions.
