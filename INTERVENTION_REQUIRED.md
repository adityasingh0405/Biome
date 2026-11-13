# Intervention Required

**Blocking items that require human decision or external action before this system can be fully production-ready.**

---

## INT-001 — Docker Desktop not running (BLOCKER)

| Field | Detail |
|---|---|
| Severity | BLOCKER — Qdrant and Redis unavailable |
| Affects | Hybrid vector search, session memory, full E2E flow |
| Root Cause | Docker Desktop daemon not started on host |
| Evidence | `docker ps` → `failed to connect to …dockerDesktopLinuxEngine` |
| Required Action | **User must start Docker Desktop**, then run: `docker compose up -d qdrant redis` |
| Workaround | App degrades gracefully: simple in-memory dense adapter, in-memory session store |
| Status | ⏳ OPEN — awaiting user action |

---

## INT-002 — PostgreSQL for `enterprise_tickets` not in docker-compose (DECISION)

| Field | Detail |
|---|---|
| Severity | DECISION — NL2SQL works with SQLite in-memory fallback |
| Affects | NL2SQL data persistence between restarts |
| Root Cause | `docker-compose.yml` has no `postgres` service for the app DB (only `langfuse-db` for Langfuse). `NL2SQLEngine` falls back to SQLite in-memory when Postgres DSN is unreachable. |
| Evidence | `docker compose config` — no `postgres` app service. `config.py` default: `postgresql://localhost:5432/enterprise_rag`. On connection failure, engine creates `sqlite:///enterprise_tickets.db`. |
| README Claim | "seeds PostgreSQL with enterprise_tickets fixture data" |
| Decision Needed | **A) Add postgres service to docker-compose.yml** (persistent, matches README intent) OR **B) Document SQLite fallback as official and update README** |
| Status | ⏳ OPEN — awaiting user decision |

---

## INT-003 — Model choice mismatch: `.env` vs README vs `config.py` default (DECISION)

| Field | Detail |
|---|---|
| Severity | DECISION — both models are available; it's a config question |
| Affects | LLM generation quality and RAM usage |
| Root Cause | `.env` sets `OLLAMA_MODEL=llama3.2:3b`; README and `config.py` default say `llama3.1:8b`; both models pulled |
| Hardware | 16GB RAM, Intel Iris Xe (no GPU) — `llama3.1:8b` cold-start ~21s, warm ~5.5s; `llama3.2:3b` is faster |
| Decision Needed | **A) Keep `llama3.2:3b` (faster, less RAM, lower quality)** OR **B) Change to `llama3.1:8b` (README intent, higher quality, slower)** |
| Recommendation | Confirm choice, then update `.env.example` to match. For production keep `llama3.1:8b` unless latency budget is tight. |
| Status | ⏳ OPEN — awaiting user decision |

---

## INT-004 — FlagEmbedding not installed in `.venv` (INFORMATION)

| Field | Detail |
|---|---|
| Severity | LOW — app runs with fallback adapter |
| Affects | BGE-M3 dense embedding quality (falls back to `SimpleDenseEmbeddingAdapter`) |
| Root Cause | `FlagEmbedding` requires Rust toolchain to build; not in `.venv` pip install |
| Evidence | Server startup: `FlagEmbedding not installed. BGE-M3 encoder unavailable; dense retrieval will use the fallback adapter.` |
| Required Action | Optionally install: `pip install FlagEmbedding` (may require Rust/C++ build tools) OR use system-installed version if available |
| Workaround | App degrades gracefully; `SimpleDenseEmbeddingAdapter` used automatically |
| Status | ℹ️ INFORMATIONAL — no action required for local dev |

---

## INT-005 — Langfuse not in docker-compose main services (INFORMATION)

| Field | Detail |
|---|---|
| Severity | LOW — app degrades gracefully |
| Affects | Observability / tracing |
| Root Cause | Langfuse containers (`langfuse-db`, `langfuse`) exist in compose but are not started by default. `LANGFUSE_ENABLED=false` in `.env.example`. |
| Evidence | `config.py`: `langfuse_enabled: bool = False`. `langfuse_tracer.py`: no-op when disabled. |
| Required Action | To enable: (1) set `LANGFUSE_ENABLED=true` and add real keys to `.env`, (2) run `docker compose up -d langfuse-db langfuse` |
| Status | ℹ️ INFORMATIONAL — documented, no action required |
