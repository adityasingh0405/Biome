# 🔌 SETUP_INTEGRATIONS.md — Biome Enterprise RAG Integration & Setup Guide

This guide documents the complete infrastructure, external integrations, environment variables, and verification procedures for the **Biome Enterprise RAG Pipeline** built across Phases 0 through 8.

---

## 1. Quickstart (From Clone to Running in 5 Minutes)

### Step 1: Clone and Configure Environment
```bash
# 1. Copy the environment configuration template
cp .env.example .env

# 2. Open .env and customize credentials (or keep local defaults)
```

### Step 2: Spin Up Infrastructure via Docker
```bash
# Start vector database, Redis session cache, and local Ollama
docker compose up -d qdrant redis ollama

# (Optional) If using self-hosted Langfuse for observability:
# Set LANGFUSE_DB_PASSWORD in .env first, then run:
docker compose up -d langfuse-db langfuse
```

### Step 3: Pull Local LLM Model
```bash
# Pull Llama 3.1 8B (or llama3.2:3b for resource-constrained laptops)
docker exec -it biome-ollama ollama pull llama3.1:8b
# Or if running Ollama natively on your host:
ollama pull llama3.1:8b
```

### Step 4: Run Automated Setup Script
```bash
# Idempotently validates environment, seeds sample database, and builds indexes
python scripts/setup_system.py
```

### Step 5: Start the API & Dashboard
```bash
# Terminal 1 — FastAPI Backend (Port 8000)
uvicorn biome_rag.api.app:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Modern React + Vite Frontend (Port 5173)
cd frontend
npm run dev
```

---

## 2. Infrastructure & Docker Services

The complete system infrastructure is codified in [`docker-compose.yml`](docker-compose.yml):

| Service | Container Name | Host Port | Internal Port | Healthcheck Endpoint / Command | Notes |
|---|---|---|---|---|---|
| **Qdrant** | `biome-qdrant` | `6333`, `6334` | `6333`, `6334` | `http://localhost:6333/healthz` | Native hybrid vector DB (dense 1024d + sparse BGE-M3). Dashboard: `http://localhost:6333/dashboard` |
| **Redis** | `biome-redis` | `6379` | `6379` | `redis-cli ping` | Sliding-window session memory (TTL: 3600s, window: 10 turns) |
| **Ollama** | `biome-ollama` | `11434` | `11434` | `http://localhost:11434/` | Local zero-cost LLM inference (`llama3.1:8b`) |
| **Langfuse DB** | `biome-langfuse-db` | *internal* | `5432` | `pg_isready -U langfuse` | PostgreSQL database backing self-hosted Langfuse |
| **Langfuse** | `biome-langfuse` | `3000` | `3000` | `http://localhost:3000/api/public/health` | Observability & tracing dashboard: `http://localhost:3000` |

### Service Management Commands
```bash
# Check status of all containers
docker compose ps

# View service logs
docker compose logs -f qdrant
docker compose logs -f redis
docker compose logs -f ollama

# Stop services without deleting persistent volumes
docker compose stop

# Teardown containers and networks (preserves volumes)
docker compose down
```

---

## 3. External Accounts & API Keys

### 3.1 Groq API (Fast Cloud LLM Fallback)
* **Purpose**: High-speed cloud LLM fallback when local Ollama is offline.
* **Where to obtain**:
  1. Visit [Groq Console](https://console.groq.com/).
  2. Navigate to **API Keys** → **Create API Key**.
  3. Copy the key (starts with `gsk_...`).
* **Configuration (`.env`)**:
  ```ini
  LLM_PROVIDER=groq
  GROQ_API_KEY=gsk_your_actual_key_here
  GROQ_MODEL=llama-3.1-8b-instant
  ```
* **Verification**:
  ```bash
  curl https://api.groq.com/openai/v1/models \
    -H "Authorization: Bearer $GROQ_API_KEY"
  ```

### 3.2 OpenAI (Alternative LLM / Embeddings)
* **Purpose**: Cloud LLM generation (`gpt-4o-mini`) or OpenAI embeddings.
* **Where to obtain**:
  1. Visit [OpenAI Platform](https://platform.openai.com/api-keys).
  2. Create a secret key (`sk-...`).
* **Configuration (`.env`)**:
  ```ini
  LLM_PROVIDER=openai
  OPENAI_API_KEY=sk-your_actual_key_here
  OPENAI_MODEL=gpt-4o-mini
  ```

### 3.3 Anthropic (Claude Sonnet Fallback)
* **Purpose**: High-reasoning generation and citation verification.
* **Where to obtain**:
  1. Visit [Anthropic Console](https://console.anthropic.com/).
  2. Generate an API key (`sk-ant-...`).
* **Configuration (`.env`)**:
  ```ini
  LLM_PROVIDER=anthropic
  ANTHROPIC_API_KEY=sk-ant-your_actual_key_here
  ANTHROPIC_MODEL=claude-sonnet-4-5
  ```

### 3.4 Slack Ingestion Setup
* **Purpose**: Ingestion of enterprise Slack threads with participant/reaction context.
* **Where to obtain**:
  1. Navigate to [Slack API: Your Apps](https://api.slack.com/apps) → **Create New App** (From Scratch).
  2. Under **OAuth & Permissions**, add the following Bot Token Scopes:
     * `channels:history` — Read public channel messages & threads
     * `channels:read` — View basic channel information
     * `groups:history` — Read private channel messages
     * `im:history` — Read direct messages
     * `mpim:history` — Read group direct messages
     * `users:read` — Resolve user IDs to participant names
  3. Click **Install to Workspace** and copy the **Bot User OAuth Token** (`xoxb-...`).
  4. Under **Basic Information** → **App-Level Tokens**, generate an App Token with `connections:write` scope (`xapp-...`).
* **Configuration (`.env`)**:
  ```ini
  SLACK_BOT_TOKEN=xoxb-your-token
  SLACK_APP_TOKEN=xapp-your-token
  SLACK_WORKSPACE_ID=T0123456789
  ```

### 3.5 Langfuse Tracing & Observability
* **Option A: Self-Hosted (Default via Docker)**
  1. Access `http://localhost:3000` after running `docker compose up -d langfuse`.
  2. Create an admin account and a new project called `Biome RAG`.
  3. Navigate to **Settings** → **API Keys** → Generate new API keys.
* **Option B: Langfuse Cloud**
  1. Sign up at [cloud.langfuse.com](https://cloud.langfuse.com).
  2. Create a project and obtain public and secret keys.
* **Configuration (`.env`)**:
  ```ini
  LANGFUSE_ENABLED=true
  LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key
  LANGFUSE_SECRET_KEY=sk-lf-your-secret-key
  LANGFUSE_HOST=http://localhost:3000  # Or https://cloud.langfuse.com
  LANGFUSE_DB_PASSWORD=your_secure_password
  ```

---

## 4. Environment Variables Reference

| Variable | Description | Default | Allowed Values / Example | Phase |
|---|---|---|---|---|
| `LOG_LEVEL` | Application logging verbosity | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | Phase 0 |
| `LLM_PROVIDER` | Active generation provider | `ollama` | `local`, `ollama`, `groq`, `openai`, `anthropic` | Phase 0+ |
| `OLLAMA_MODEL` | Ollama model identifier | `llama3.1:8b` | `llama3.1:8b`, `llama3.2:3b`, `mistral` | Phase 0 |
| `OLLAMA_BASE_URL` | Ollama daemon endpoint | `http://localhost:11434` | URL | Phase 0 |
| `OLLAMA_TIMEOUT` | Ollama timeout in seconds | `60` | Integer | Phase 0 |
| `GROQ_API_KEY` | Groq cloud authentication key | `""` | `gsk_...` | Phase 5 |
| `GROQ_MODEL` | Groq model identifier | `llama-3.1-8b-instant` | Model ID | Phase 5 |
| `OPENAI_API_KEY` | OpenAI authentication key | `""` | `sk-...` | Phase 0 |
| `OPENAI_MODEL` | OpenAI model identifier | `gpt-4o-mini` | `gpt-4o`, `gpt-4o-mini` | Phase 0 |
| `ANTHROPIC_API_KEY` | Anthropic authentication key | `""` | `sk-ant-...` | Phase 0 |
| `ANTHROPIC_MODEL` | Anthropic model identifier | `claude-sonnet-4-5` | Model ID | Phase 0 |
| `EMBEDDING_PROVIDER` | Embedding framework | `sentence-transformers` | `sentence-transformers`, `openai` | Phase 3 |
| `EMBEDDING_MODEL_NAME` | Dual dense+sparse embedding model | `BAAI/bge-m3` | `BAAI/bge-m3`, `all-MiniLM-L6-v2` | Phase 3 |
| `EMBEDDING_COLLECTION_NAME` | Vector collection name | `enterprise_kb` | String | Phase 3 |
| `EMBEDDING_DEVICE` | Hardware acceleration target | `cpu` | `cpu`, `cuda`, `mps` | Phase 3 |
| `QDRANT_HOST` | Qdrant hostname | `localhost` | Hostname / IP | Phase 3 |
| `QDRANT_PORT` | Qdrant REST port | `6333` | Port number | Phase 3 |
| `QDRANT_URL` | Full Qdrant connection URL | `http://localhost:6333` | URL | Phase 3 |
| `QDRANT_COLLECTION` | Qdrant collection name | `enterprise_kb` | String | Phase 3 |
| `QDRANT_API_KEY` | Optional Qdrant auth token | `""` | String | Phase 3 |
| `POSTGRES_URI` | Relational database connection string | `postgresql://localhost:5432/enterprise_rag` | `postgresql://user:pass@host:port/db` | Phase 1 |
| `POSTGRES_TABLE` | Relational table for tickets & NL2SQL | `enterprise_tickets` | Table name | Phase 1 & 8 |
| `REDIS_URL` | Redis session store connection URL | `redis://localhost:6379/0` | `redis://host:port/db` | Phase 5 |
| `REDIS_SESSION_TTL` | Session history expiry in seconds | `3600` | Seconds (e.g. 1 hour) | Phase 5 |
| `REDIS_WINDOW_SIZE` | Max messages in chat sliding window | `10` | Integer (e.g. 10 messages = 5 turns) | Phase 5 |
| `LANGFUSE_ENABLED` | Toggle observability tracing | `false` | `true`, `false` | Phase 5 |
| `LANGFUSE_PUBLIC_KEY` | Langfuse project public key | `""` | `pk-lf-...` | Phase 5 |
| `LANGFUSE_SECRET_KEY` | Langfuse project secret key | `""` | `sk-lf-...` | Phase 5 |
| `LANGFUSE_HOST` | Langfuse instance base URL | `http://localhost:3000` | URL | Phase 5 |
| `LANGFUSE_DB_PASSWORD` | Internal DB password for Langfuse Docker | `""` | String (required for docker compose) | Phase 0 |
| `PDF_CHUNK_MAX_TOKENS` | Maximum tokens per PDF chunk | `600` | Integer (400-600) | Phase 2 |
| `PDF_CHUNK_MIN_TOKENS` | Minimum tokens per PDF chunk | `400` | Integer | Phase 2 |
| `SLACK_CHUNK_MAX_TOKENS` | Maximum tokens per Slack thread | `400` | Integer (256-400) | Phase 2 |
| `PG_CHUNK_MAX_TOKENS` | Maximum tokens per Postgres entity doc | `256` | Integer (128-256) | Phase 2 |
| `TABLE_SPLIT_MAX_TOKENS` | Oversized-table row split threshold | `600` | Integer | Phase 2 |
| `DENSE_TOP_K` | Candidates retrieved per vector type | `5` | Integer | Phase 4 |
| `RRF_DENSE_WEIGHT` | Dense weight in reciprocal rank fusion | `0.7` | Float | Phase 4 |
| `RRF_SPARSE_WEIGHT` | Sparse weight in reciprocal rank fusion | `0.3` | Float | Phase 4 |
| `RRF_K` | RRF constant ($k$) | `60` | Integer | Phase 4 |
| `INSUFFICIENT_CONFIDENCE_THRESHOLD` | Guardrail threshold for "I don't know" | `0.5` | Float (0.0 to 1.0) | Phase 5 |
| `SENSITIVE_FIELDS` | Redacted fields during serialization | `salary,ssn,tax_id,password,secret` | Comma-separated strings | Phase 1 & 5 |
| `NL2SQL_ENABLED` | Toggle structured query router | `true` | `true`, `false` | Phase 8 |
| `NL2SQL_TIMEOUT_SECONDS` | SQL query execution timeout | `5.0` | Seconds | Phase 8 |
| `NL2SQL_MAX_ROWS` | Hard cap on SQL result rows | `50` | Integer | Phase 8 |
| `API_BASE` | Backend URL for frontend proxy | `http://localhost:8000` | URL | Phase 5 & 8 |

---

## 5. End-to-End Verification Procedures

Run these commands to verify that every component is wired correctly:

### 5.1 Verify Docker Stack Connectivity
```bash
# 1. Qdrant Health
curl -s http://localhost:6333/healthz
# Expected output: {"title":"qdrant - vector search engine","version":"..."}

# 2. Redis Ping
docker exec biome-redis redis-cli ping
# Expected output: PONG

# 3. Ollama Tags
curl -s http://localhost:11434/api/tags
# Expected output: JSON listing installed models (including llama3.1)
```

### 5.2 Verify Hybrid Retrieval & Qdrant Collection
```bash
# Check point count in Qdrant enterprise_kb collection
curl -s http://localhost:6333/collections/enterprise_kb
```

### 5.3 Verify API Health & Endpoints
```bash
curl -s http://localhost:8000/v1/health | jq
```
Expected JSON:
```json
{
  "status": "ok",
  "chunks_indexed": 207,
  "storage_dir": "data/index",
  "processed_dir": "data/processed"
}
```

### 5.4 Verify Semantic RAG with Citations
```bash
curl -s -X POST http://localhost:8000/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the policy regarding company equipment security?"}' | jq
```
Verify that the output contains:
* `route`: `"semantic"`
* `answer`: Grounded response text with inline `[1]` citation tags
* `citations`: Non-empty list of source chunks with verified status
* `confidence`: `composite >= 0.5`

### 5.5 Verify Phase 8 NL2SQL & Programmatic ACL
```bash
# Test 1: Unrestricted Aggregate Query
curl -s -X POST http://localhost:8000/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How many total tickets are in the database?"}' | jq

# Expected output:
# route: "structured"
# sql_query: "SELECT COUNT(*) AS total_tickets FROM enterprise_tickets LIMIT 50"
# answer: contains exact ticket count

# Test 2: Programmatic Row-Level ACL (Logistics Scope Only)
curl -s -X POST http://localhost:8000/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How many total tickets are in the database?", "access_scope": ["logistics"]}' | jq

# Expected output:
# sql_query: contains "WHERE lower(department) IN ('logistics')"
# answer: reflects count restricted strictly to Logistics rows
```

### 5.6 Verify Multi-Turn Chat & Redis Memory
```bash
# Turn 1
curl -s -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-session-123", "message": "My department is Logistics."}' | jq

# Turn 2 (Referencing previous turn)
curl -s -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-session-123", "message": "What issues do we have open?"}' | jq
# Verify history_length >= 4 and answer reflects Logistics context.
```

---

## 6. Troubleshooting & Common Pitfalls

| Issue | Root Cause | Solution |
|---|---|---|
| `psycopg2.OperationalError: connection refused` | PostgreSQL daemon is not running on port 5432 | Start local PostgreSQL, or rely on the automatic in-memory SQLite schema fallback for development/testing. |
| `Qdrant connection timeout (30s)` | Docker container `biome-qdrant` is stopped | Run `docker compose up -d qdrant`. If running without Docker, the system falls back to local ChromaDB and Simple adapter. |
| `Ollama connection refused on 11434` | Ollama server is offline | Run `docker compose up -d ollama` or start Ollama desktop. The system automatically engages the circuit breaker and falls back to local sentence extraction. |
| `Redis connection error` | Redis container not running | Run `docker compose up -d redis`. When Redis is unavailable, the pipeline falls back to `InMemorySessionStore`. |
| `UnboundLocalError / ImportErrors` | Missing dependency packages | Run `pip install -r requirements.txt`. |
| `E3002: Index sync mismatch` | Ingestion was interrupted midway | Re-run `python scripts/setup_system.py` to regenerate `chunks.json` and `bm25_index.pkl` in sync. |
