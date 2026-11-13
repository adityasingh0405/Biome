# Biome RAG — Verification Report

**Branch:** `chore/backend-verify-and-connect`
**Date:** 2026-11-13
**Auditor:** Automated production-readiness audit
**Verdict:** ⚠️ **CONDITIONAL PASS** — All critical security bugs fixed; 3 infrastructure items need human action.

---

## Executive Summary

The Biome Enterprise RAG backend is architecturally sound and test-covered. Three **critical security bugs** were found and fixed on this branch. The system can run in a degraded but functional state without Docker (Qdrant/Redis down), and the full hybrid-search + session-memory path requires Docker Desktop to be started. The frontend mock fallbacks have been removed so the UI now reflects real backend state.

---

## Service Health Table

| Service | Status | Evidence |
|---|---|---|
| **FastAPI server** | ✅ RUNNING | `GET /v1/health → 200, chunks_indexed: 351` |
| **Ollama** | ✅ RUNNING | `GET localhost:11434/api/tags → llama3.1:8b, llama3.2:3b present` |
| **Qdrant** | ❌ DOWN | Docker Desktop not started — INT-001 |
| **Redis** | ❌ DOWN | Docker Desktop not started — INT-001 |
| **PostgreSQL (app)** | ⚠️ NOT PROVISIONED | Falls back to in-memory SQLite — INT-002 |
| **Langfuse** | ℹ️ DISABLED | `LANGFUSE_ENABLED=false` — graceful no-op |
| **BGE-M3 (FlagEmbedding)** | ⚠️ FALLBACK | FlagEmbedding not in .venv; ChromaDenseEmbeddingAdapter used |
| **CrossEncoder** | ✅ LOADED | `cross-encoder/ms-marco-MiniLM-L-6-v2` downloaded and loaded |
| **BM25** | ✅ LOADED | In-memory BM25 built from 351 indexed chunks |

---

## Test Results

> Tests run without Qdrant/Redis (using in-memory fallbacks). Qdrant warnings are expected.

| Test File | Passed | Skipped | Failed | Notes |
|---|---|---|---|---|
| test_api.py | 2 | 0 | 0 | ✅ |
| test_phase1_ingesters.py | 29 | 2 | 0 | ✅ Skips require Slack token |
| test_phase2_chunking.py | 54 | 0 | 0 | ✅ |
| test_phase3_embeddings.py | 35 | 0 | 0 | ✅ |
| test_phase4_indexbuilder.py | ~40 | 0 | 0 | ✅ (66 total with phase5) |
| test_phase5_memory_observability.py | ~26 | 0 | 0 | ✅ |
| test_phase6_evaluation.py | 75 | 0 | 0 | ✅ (1 stale version fixed) |
| test_phase7_ablation.py | — | — | — | Excluded from full run (slow; passes individually) |
| test_phase8_nl2sql.py | 46 | 0 | 0 | ✅ (after ACL fix) |
| **TOTAL** | **~287** | **2** | **0** | |

---

## Findings

### 🔴 CRITICAL (Fixed)

#### FINDING-001: ACL fails open — `apply_acl()` returned unfiltered SQL when scope=None

- **File:** `biome_rag/retrieval/router.py:263`
- **Before:** `if not requester_scope: return sql` — any caller omitting scope gets all rows
- **Also:** Scope values used directly in f-string SQL without sanitisation → SQL injection vector
- **Also:** Sentinel-only scopes (`["internal"]`) silently bypassed ACL
- **Fix:** `apply_acl()` now raises `ValueError` when scope is None/empty. Admin bypass tokens (`*`, `admin`, `all`, `superuser`) checked **before** the injection-character guard. Department values validated against `['";\-]|--|/\*` regex. Sentinel-only scopes raise `ValueError`. `execute()` re-raises `ValueError` (not swallows). `app.py` surfaces it as HTTP 403.
- **Commit:** `3540f21`
- **Verified:** `curl -d '{"question":"...","route_override":"structured"}' → HTTP 403`

#### FINDING-002: CORS wildcard + credentials — browsers reject all cross-origin requests

- **File:** `biome_rag/api/app.py:113-114`
- **Before:** `allow_origins=["*"]` with `allow_credentials=True` — browsers reject this per CORS spec §3.2.5
- **Fix:** Origins now read from `CORS_ALLOW_ORIGINS` env var (default: `localhost:5173, 127.0.0.1:5173`)
- **Commit:** `3540f21`

#### FINDING-003: Path traversal in `/v1/ingest/directory` and `/v1/index/files`

- **File:** `biome_rag/api/app.py:433,477`
- **Before:** `dir_path = Path(request.directory_path)` — no base-directory restriction; `../../etc/passwd` accepted
- **Fix:** `_resolve_safe_dir()` validates resolved path is under `INGEST_BASE_DIR` (default: `data/`) using `Path.relative_to()`
- **Commit:** `3540f21`
- **Verified:** `curl -d '{"directory_path":"../../Windows/System32"}' → HTTP 400`

---

### 🟡 HIGH (Fixed)

#### FINDING-004: Missing `import json` in `app.py` — NameError at runtime

- **File:** `biome_rag/api/app.py:548` — `json.dumps(rec)` without `import json`
- **Fix:** Added `import json`
- **Commit:** `fc55b43`

#### FINDING-005: SyntaxError in `biome_rag/ingestion/base.py`

- **Before:** Stray `-` character before docstring — `python -m compileall` fails
- **Fix:** Removed stray character
- **Commit:** `b85ad76`

#### FINDING-006: Frontend mock fallbacks hide backend failures

- **File:** `frontend/src/services/api.js` — every function had `catch(err) → return hardcoded_data`
- **Impact:** App appeared to work even with backend completely offline; bugs invisible
- **Fix:** All mock fallbacks removed. Errors propagate. `SqlView.jsx` now shows error banner. Added `VITE_API_BASE_URL` env var support, abort-controller timeout.
- **Commit:** `3540f21`

---

### 🟡 MEDIUM (Noted, not fixed — by design or low risk)

#### FINDING-007: AskRequest.question had no length limit

- **Fix:** `max_length=2000` added via Pydantic `Field`
- **Commit:** `3540f21`
- **Verified:** `HTTP 422` for 2001-char question

#### FINDING-008: Protected endpoints unauthenticated (`/v1/evaluate`, `/v1/index/files`)

- **Status:** No authentication layer added (would require new auth system design)
- **Mitigation:** Path traversal blocked; evaluate only reads existing golden files
- **Recommendation:** Add `X-API-Key` header validation via FastAPI `Depends` for production. See `INTERVENTION_REQUIRED.md`.

#### FINDING-009: `sse-starlette` requires `starlette>=0.49.1`, have `0.38.6`

- **Status:** sse-starlette not imported anywhere in biome_rag — non-blocking
- **Classification:** LOW

#### FINDING-010: Ollama model mismatch `.env` vs README

- **`.env`** sets `OLLAMA_MODEL=llama3.2:3b`; **README** and `config.py` default say `llama3.1:8b`
- **Status:** Both models pulled and working. See INT-003.

---

### ℹ️ INFORMATIONAL (Architecture confirmed)

#### FINDING-011: RRF weights — non-standard but intentional

- Standard RRF has no weights; Biome uses `score = 0.7/(k+r_d) + 0.3/(k+r_s)` — documented in DECISIONS.md, implemented correctly in `engine.py`

#### FINDING-012: CrossEncoder blocks startup — no lazy loading

- `HybridRetriever.__init__()` downloads ~300 MB cross-encoder on first cold start
- Blocks startup for 30-60s on first run. After download is cached, startup is ~2-3s.
- **Recommendation:** Move to FastAPI lifespan event for explicit startup sequencing

#### FINDING-013: PostgreSQL not in docker-compose

- NL2SQL falls back to in-memory SQLite. See INT-002.

---

## Security Battery Results (Live, with real HTTP evidence)

| Test | Method | Expected | Got | Status |
|---|---|---|---|---|
| Structured query without scope | POST /v1/ask (no access_scope) | 403 | 403 | ✅ PASS |
| Structured query with admin scope | POST /v1/ask (scope=["*"]) | 200 | 200 | ✅ PASS |
| SQL injection via scope | apply_acl(sql, ["eng') OR 1=1 --"]) | ValueError | ValueError | ✅ PASS |
| Path traversal via directory_path | POST /v1/ingest/directory (../../Windows) | 400 | 400 | ✅ PASS |
| Oversized question | POST /v1/ask (2001 chars) | 422 | 422 | ✅ PASS |
| SQL DROP blocked | validate_sql("DROP TABLE enterprise_tickets") | ValueError | ValueError | ✅ PASS |
| SQL comments blocked | validate_sql("SELECT * -- bypass") | ValueError | ValueError | ✅ PASS |
| Sentinel-only scope denied | apply_acl(sql, ["internal"]) | ValueError | ValueError | ✅ PASS |

---

## "Run Everything" Commands

```powershell
# 1. Ensure Ollama is running (host process)
ollama serve

# 2. Start Docker services (requires Docker Desktop)
docker compose up -d qdrant redis

# 3. Activate venv and start backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn biome_rag.api.app:app --host 0.0.0.0 --port 8000

# 4. Run test suite
python -m pytest tests/ -q --tb=short

# 5. Run frontend dev server (new terminal)
cd frontend
npm install
npm run dev  # → http://localhost:5173
```

---

## Intervention Required

See [INTERVENTION_REQUIRED.md](INTERVENTION_REQUIRED.md) for the full table. Headlines:

| ID | Severity | Item |
|---|---|---|
| INT-001 | 🔴 BLOCKER | Start Docker Desktop → `docker compose up -d qdrant redis` |
| INT-002 | 🟡 DECISION | Add Postgres to docker-compose.yml OR document SQLite fallback |
| INT-003 | 🟡 DECISION | Confirm model: `llama3.2:3b` (fast) vs `llama3.1:8b` (README intent) |
| INT-004 | ℹ️ INFO | Install FlagEmbedding for real BGE-M3 (optional) |
| INT-005 | ℹ️ INFO | Start Langfuse containers if tracing needed |
