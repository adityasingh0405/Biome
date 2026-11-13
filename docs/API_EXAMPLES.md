# Biome RAG — API Examples

Working request/response pairs for every endpoint. All examples assume the server is running at `http://localhost:8000`.

> [!NOTE]
> **During development**, the Vite dev server (`npm run dev`) proxies `/v1/*` to `http://127.0.0.1:8000`, so the frontend never makes cross-origin requests. CORS is only relevant for production or non-proxied access.

> [!IMPORTANT]
> **ACL is fail-closed for structured (SQL) queries.** If you send a structured query without `access_scope`, the server returns `403`. Pass `["*"]` for unrestricted admin access, or a department list for row-level filtering.

---

## GET /v1/health

```bash
curl http://localhost:8000/v1/health
```

```json
{
  "status": "ok",
  "chunks_indexed": 0,
  "storage_dir": "data/index",
  "processed_dir": "data/processed"
}
```

---

## POST /v1/ask — Semantic RAG query

```bash
curl -X POST http://localhost:8000/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How do I authenticate with the Biome API?",
    "retrieval_mode": "hybrid"
  }'
```

**Response** (truncated):
```json
{
  "answer": "Based on the enterprise documentation [1], authentication uses JWT bearer tokens...",
  "citations": [
    {
      "chunk_index": 0,
      "text": "All API clients must attach an Authorization: Bearer token.",
      "verified": true
    }
  ],
  "confidence": {
    "retrieval_confidence": 0.87,
    "citation_coverage": 1.0,
    "completeness": 0.91,
    "composite": 0.93
  },
  "retrieved_chunks": [ ... ],
  "trace_id": null,
  "route": "semantic",
  "sql_query": null
}
```

---

## POST /v1/ask — Structured NL2SQL query (with ACL)

> [!IMPORTANT]
> `access_scope` is **required** for structured queries. Omitting it returns `HTTP 403`.

```bash
# Admin / unrestricted access:
curl -X POST http://localhost:8000/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How many total tickets are in the database?",
    "access_scope": ["*"],
    "route_override": "structured"
  }'
```

```json
{
  "answer": "The Total Tickets is **10** (queried from `enterprise_tickets`).",
  "citations": [
    {
      "chunk_index": 0,
      "text": "SQL Query: SELECT COUNT(*) AS total_tickets FROM enterprise_tickets (Source: enterprise_tickets)",
      "verified": true
    }
  ],
  "confidence": { "retrieval_confidence": 1.0, "citation_coverage": 1.0, "completeness": 1.0, "composite": 1.0 },
  "retrieved_chunks": [],
  "route": "structured",
  "sql_query": "SELECT COUNT(*) AS total_tickets FROM enterprise_tickets LIMIT 50",
  "sql_rows": [{ "total_tickets": 10 }]
}
```

```bash
# Department-scoped access (row-level ACL):
curl -X POST http://localhost:8000/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How many total tickets are in the database?",
    "access_scope": ["logistics"],
    "route_override": "structured"
  }'
```

```json
{
  "answer": "The Total Tickets is **4** (queried from `enterprise_tickets`).",
  "sql_query": "SELECT COUNT(*) AS total_tickets FROM (SELECT * FROM enterprise_tickets WHERE lower(department) IN ('logistics')) AS enterprise_tickets LIMIT 50",
  "sql_rows": [{ "total_tickets": 4 }],
  "route": "structured"
}
```

```bash
# No scope → 403:
curl -X POST http://localhost:8000/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How many total tickets?", "route_override": "structured"}'
# HTTP 403 — {"detail": "apply_acl: requester_scope must be provided..."}
```

---

## POST /v1/chat — Multi-turn with session memory

```bash
# Turn 1
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the company VPN policy?",
    "session_id": "sess-demo-001",
    "retrieval_mode": "hybrid"
  }'
```

```json
{
  "answer": "The VPN policy requires...",
  "session_id": "sess-demo-001",
  "citations": [ ... ],
  "confidence": { ... },
  "retrieved_chunks": [ ... ],
  "trace_id": null,
  "history_length": 2,
  "route": "semantic",
  "sql_query": null
}
```

```bash
# Turn 2 — references previous turn
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "And what are the exceptions to that policy?",
    "session_id": "sess-demo-001"
  }'
```

```bash
# Clear session
curl -X DELETE http://localhost:8000/v1/session/sess-demo-001
```

---

## POST /v1/compare — Retrieval mode ablation

```bash
curl -X POST http://localhost:8000/v1/compare \
  -H "Content-Type: application/json" \
  -d '{"question": "What error code indicates invalid credentials?"}'
```

```json
{
  "question": "What error code indicates invalid credentials?",
  "hybrid": {
    "answer": "According to documentation [1], invalid credentials return ERR-AUTH-401...",
    "confidence": { "composite": 0.95 },
    "citations": [ ... ]
  },
  "dense": {
    "answer": "Authentication errors are returned when...",
    "confidence": { "composite": 0.72 }
  }
}
```

---

## GET /v1/documents — Document registry

```bash
curl http://localhost:8000/v1/documents
```

```json
{
  "documents": [
    { "source": "data/raw/enterprise_security_policy.pdf", "chunk_count": 42 },
    { "source": "data/raw/architecture.md", "chunk_count": 28 }
  ]
}
```

---

## POST /v1/index/upload — Upload and index files

```bash
curl -X POST http://localhost:8000/v1/index/upload \
  -F "files=@enterprise_security_policy.pdf" \
  -F "files=@onboarding.md"
```

```json
{
  "status": "ok",
  "files_uploaded": ["enterprise_security_policy.pdf", "onboarding.md"],
  "total_chunks": 68,
  "duplicates_skipped": 0
}
```

---

## POST /v1/index/text — Ingest raw text

```bash
curl -X POST http://localhost:8000/v1/index/text \
  -H "Content-Type: application/json" \
  -d '{
    "title": "VPN Policy Update 2026",
    "content": "All employees must use the company VPN when accessing internal systems..."
  }'
```

```json
{ "status": "ok", "document": "VPN_Policy_Update_2026.txt", "total_chunks": 3 }
```

---

## POST /v1/ingest/directory — Index a local directory

> [!WARNING]
> Path is validated server-side against `INGEST_BASE_DIR` env var (default: `data/`). Paths outside this root return `HTTP 400` to prevent path traversal.

```bash
curl -X POST http://localhost:8000/v1/ingest/directory \
  -H "Content-Type: application/json" \
  -d '{"directory_path": "data/raw", "recursive": true}'
```

```json
{
  "status": "ok",
  "directory": "data/raw",
  "files_found": 5,
  "total_chunks": 148
}
```

---

## Security Notes

| Concern | Implementation |
|---|---|
| ACL fail-closed | `access_scope=null` on structured queries → `HTTP 403` |
| SQL injection via scope | Scope values validated against forbidden-char regex before SQL embedding |
| SQL mutation guard | Only `SELECT` allowed; `DROP`, `UPDATE`, `INSERT`, `DELETE`, etc. → `HTTP 400` |
| LIMIT cap | Max 50 rows; any higher LIMIT is clamped to 50 |
| Path traversal | Directory endpoints restricted to `INGEST_BASE_DIR` |
| CORS | `allow_origins` set via `CORS_ALLOW_ORIGINS` env var; never `*` with `credentials=true` |
| Stacked statements | Semicolons → rejected |
| SQL comments | `--` and `/* */` → rejected |

---

## Environment Setup

```bash
# Backend
cp .env.example .env
# Edit .env — set OLLAMA_MODEL, optionally CORS_ALLOW_ORIGINS, INGEST_BASE_DIR

# Start services (requires Docker Desktop)
docker compose up -d qdrant redis

# Start API server
python -m uvicorn biome_rag.api.app:app --host 0.0.0.0 --port 8000

# Frontend (dev)
cd frontend
cp .env.example .env
npm install
npm run dev  # → http://localhost:5173, proxied to :8000
```
