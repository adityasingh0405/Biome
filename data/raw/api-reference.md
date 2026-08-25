# Biome API Reference

## Authentication

All API requests must include the `BIOME_API_KEY` environment variable set in your environment before calling the API. Pass the key in the `Authorization` header as `Bearer <BIOME_API_KEY>`.

```
Authorization: Bearer <your-api-key>
```

If the key is missing or invalid, the API returns HTTP 401 with error code `E1001`.

## Error Codes

### E1001 — Invalid Credentials
Returned when the API key is missing, malformed, or revoked. Resolution: verify the `BIOME_API_KEY` environment variable is set and the token has not expired.

### E1002 — Rate Limit Exceeded
Returned when a client exceeds 100 requests per minute. Resolution: implement exponential backoff. Retry after the number of seconds indicated in the `Retry-After` header.

### E2001 — Resource Not Found
The requested document, chunk, or collection does not exist. Resolution: verify the resource ID and ensure the corpus has been indexed.

### E2002 — Missing Deployment Target
Returned when a deployment operation is initiated without specifying a target environment. Resolution: set the `BIOME_DEPLOY_TARGET` environment variable to `staging`, `production`, or `dev`.

### E3001 — Chunking Failed
Ingestion succeeded but chunking produced zero chunks. Resolution: verify the document is not empty and uses a supported format (Markdown, TXT, HTML, PDF).

### E3002 — Index Out of Sync
The BM25 index and vector store contain a different number of chunks. Resolution: re-run ingestion with `--force-reindex` to rebuild both indexes from scratch.

## Endpoints

### POST /v1/ask
Submit a question to the RAG pipeline.

**Request body:**
```json
{
  "question": "string",
  "retrieval_mode": "hybrid | dense | sparse"
}
```

**Response:**
```json
{
  "answer": "string",
  "citations": [{"chunk_index": 0, "text": "string", "verified": true}],
  "confidence": {
    "retrieval_confidence": 0.85,
    "citation_coverage": 0.9,
    "completeness": 0.7,
    "composite": 0.83
  },
  "retrieved_chunks": [...]
}
```

### GET /v1/documents
List all indexed documents with their source paths and chunk counts.

### POST /v1/ingest
Upload new documents for indexing. Accepts a JSON array of `{source, text}` objects.

### GET /v1/health
Returns system health including indexed chunk count and storage paths.

### GET /v1/compare
Run the same query in both hybrid and dense-only mode. Returns both result sets for comparison.

## Rate Limits

| Plan | Requests/minute | Requests/day |
|------|----------------|-------------|
| Free | 20 | 500 |
| Pro | 100 | 10,000 |
| Enterprise | Unlimited | Unlimited |

## Versioning

The API is versioned with `/v1/` prefix. Breaking changes are introduced in new versions. The current stable version is `v1`.
