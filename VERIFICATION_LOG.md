# Verification Log — Biome RAG Backend Audit

Branch: `chore/backend-verify-and-connect`
Auditor: Automated via coding agent (Antigravity)
Hardware: Windows 11, Intel Core i5, Intel Iris Xe (no discrete GPU), 16 GB RAM
Python: 3.12.6 (satisfies 3.11+ requirement)

---

## Phase 0 — Recon

| Timestamp | Step | Command | Result | Decision |
|---|---|---|---|---|
| 2026-11-13 09:30 | Read README, DECISIONS.md, AUDIT_REPORT.md, SETUP_INTEGRATIONS.md | read_file | Understood architecture: BGE-M3 + BM25 + RRF + CrossEncoder + Ollama | — |
| 2026-11-13 09:35 | Read config.py, app.py, router.py, engine.py, session.py, langfuse_tracer.py | read_file | Built dependency map and env-var matrix | — |
| 2026-11-13 09:45 | Read frontend/src/services/api.js | read_file | FOUND: Every API function has hardcoded mock fallback | FINDING-001 |
| 2026-11-13 09:46 | Checked docker-compose.yml for Postgres | read_file | No app-level Postgres service found (only langfuse-db) | INT-002 filed |
| 2026-11-13 09:47 | Checked Langfuse in compose | read_file | Langfuse containers present but not in default startup; LANGFUSE_ENABLED=false | INT-005 noted |
| 2026-11-13 09:50 | Checked ACL flow access_scope → requester_scope | read_file | router.py:263 `if not requester_scope: return sql` — ACL FAILS OPEN | FINDING-002 (CRITICAL) |
| 2026-11-13 09:52 | Checked RRF implementation | read_file | Weighted RRF via `score = w_dense/(k+rank_d) + w_sparse/(k+rank_s)` — matches DECISIONS.md intent | Confirmed |
| 2026-11-13 09:55 | Checked ablation defaults | read_file | `rerank=True`, `top_k=5`, `retrieval_mode=hybrid` — consistent with documented intent | Confirmed |
| 2026-11-13 09:57 | Checked /v1/evaluate and /v1/index/files protection | read_file | UNAUTHENTICATED — no API key or auth check | FINDING-003 |
| 2026-11-13 09:58 | Checked Ollama model name | ollama list | llama3.2:3b and llama3.1:latest available; .env says llama3.2:3b, config default says llama3.1:8b | INT-003 filed |
| 2026-11-13 10:02 | Checked CrossEncoder cold start | code review | Loaded at HybridRetriever.__init__() — no lazy loading | FINDING-004 |
| 2026-11-13 10:05 | Checked CORS config | read_file | allow_origins=["*"] + allow_credentials=True — invalid per CORS spec | FINDING-005 (CRITICAL) |

## Phase 1 — Environment & Infrastructure

| Timestamp | Step | Command | Result | Decision |
|---|---|---|---|---|
| 2026-11-13 10:10 | Python version check | `python --version` | 3.12.6 ✓ (3.11+ satisfied) | — |
| 2026-11-13 10:11 | Create .venv | `python -m venv .venv --system-site-packages` | Created. Inherits system torch, sentence_transformers, etc. | — |
| 2026-11-13 10:12 | Install deps | `pip install -e . -q` | qdrant-client==1.20.0, redis==8.1.0 installed. sse-starlette conflict (non-blocking). | — |
| 2026-11-13 10:15 | pip check | `pip check` | `sse-starlette 3.3.3 requires starlette>=0.49.1; have 0.38.6`. Not used in biome_rag. LOW. | NOTED |
| 2026-11-13 10:17 | docker compose config | `docker compose config` | Validates cleanly ✓ | — |
| 2026-11-13 10:18 | Docker Desktop status | `docker ps` | FAILED — daemon not running | INT-001 BLOCKER |
| 2026-11-13 10:20 | Start Ollama | `ollama serve` | Running on localhost:11434 (host process) | ✓ |
| 2026-11-13 10:22 | Create llama3.1:8b alias | `ollama cp llama3.1:latest llama3.1:8b` | Success. Both llama3.2:3b and llama3.1:8b available | ✓ |
| 2026-11-13 10:25 | Ollama generate test | `curl localhost:11434/api/generate` | 200 OK; cold-start 21.5s, warm 5.5s | FINDING-006 (cold-start) |
| 2026-11-13 10:28 | Hardware assessment | system info | 16GB RAM, Intel Iris Xe (CPU-only). llama3.1:8b+BGE-M3+CrossEncoder co-exist but cold-start is slow. | INT-003 noted |

## Phase 2 — Static Analysis

| Timestamp | Step | Command | Result | Decision |
|---|---|---|---|---|
| 2026-11-13 10:35 | Compile check | `python -m compileall biome_rag` | FAILED: SyntaxError in biome_rag/ingestion/base.py (stray `-`) | FIXED (commit b85ad76) |
| 2026-11-13 10:40 | Ruff check | `ruff check biome_rag` | 33 errors; F821: json undefined in app.py:548 (CRITICAL). 30 auto-fixable. | FIXED (commit fc55b43) |
| 2026-11-13 10:45 | Manual review: ACL | read_file router.py | CRITICAL: apply_acl fails open when scope=None or scope=['internal'] | FIXED (commit 3540f21) |
| 2026-11-13 10:50 | Manual review: SQL injection via scope | read_file router.py | Scope values embedded without sanitisation via f-string | FIXED (commit 3540f21) |
| 2026-11-13 10:55 | Manual review: CORS | read_file app.py | allow_origins=["*"] + credentials=True — browsers reject this | FIXED (commit 3540f21) |
| 2026-11-13 11:00 | Manual review: path traversal | read_file app.py | /v1/index/files and /v1/ingest/directory accept arbitrary paths | FIXED (commit 3540f21) |
| 2026-11-13 11:05 | Manual review: input limits | read_file app.py | AskRequest.question has no max_length | FIXED (commit 3540f21) |
| 2026-11-13 11:10 | Manual review: async/sync | read_file | Routes are sync def (run in threadpool by uvicorn). Blocking requests.post() inside sync route — acceptable. | NOTED |
| 2026-11-13 11:12 | Manual review: error handling | read_file | No stack traces leaked to clients. Errors returned as {"detail":"..."} ✓ | ✓ |

## Phase 3 — Test Suite

| Timestamp | Test File | Command | Result |
|---|---|---|---|
| 2026-11-13 11:30 | test_phase8_nl2sql.py | pytest -q | 42 passed → after fixes: **46 passed** ✓ |
| 2026-11-13 11:45 | test_api.py | pytest -q | 2 passed ✓ |
| 2026-11-13 12:00 | test_phase1_ingesters.py | pytest -q | 29 passed, 2 skipped ✓ |
| 2026-11-13 12:15 | test_phase2_chunking.py | pytest -q | 54 passed ✓ |
| 2026-11-13 12:30 | test_phase3_embeddings.py | pytest -q | 35 passed, 4 warnings ✓ |
| 2026-11-13 13:00 | test_phase4_indexbuilder.py + test_phase5_memory_observability.py | pytest -q | 66 passed, 16 warnings ✓ |
| 2026-11-13 13:30 | test_phase6_evaluation.py + test_phase7_ablation.py | pytest -q | 74 passed, 1 failed (stale version: 0.6.0→0.7.0) → FIXED: 75 passed |
| 2026-11-13 14:00 | Full suite (minus ablation) | pytest -q | IN PROGRESS — results in VERIFICATION_REPORT.md |

## Phase 4 — Live API Smoke Tests

| Timestamp | Endpoint | Command | Result |
|---|---|---|---|
| 2026-11-13 14:45 | GET /v1/health | curl | 200 `{"status":"ok","chunks_indexed":351}` ✓ |
| 2026-11-13 14:46 | POST /v1/ask (semantic) | curl + JSON file | 200, 5 chunks retrieved, INSUFFICIENT_CONTEXT (BGE-M3 fallback active) ✓ |
| 2026-11-13 14:47 | POST /v1/ask (structured, scope=["*"]) | curl | 200, SQL executed, 0 tickets in SQLite in-memory DB ✓ |
| 2026-11-13 14:47 | POST /v1/ask (structured, no scope) | curl | 403 `apply_acl: requester_scope must be provided` ✓ |
| 2026-11-13 14:47 | POST /v1/ingest/directory (path traversal) | curl | 400 `Path '../../Windows/System32' is outside the allowed ingest root` ✓ |
| 2026-11-13 14:47 | POST /v1/ask (question > 2000 chars) | curl | 422 `String should have at most 2000 characters` ✓ |
| 2026-11-13 14:48 | GET /v1/documents | curl | 200, 351 chunks across 10+ source files ✓ |

## Commits Made

| Hash | Message |
|---|---|
| b85ad76 | fix(ingestion): remove stray leading character in base.py causing SyntaxError |
| fc55b43 | fix(static): add missing json import in app.py and clean unused imports |
| 3540f21 | fix(security): ACL fail-closed, CORS wildcard, path traversal guard, input limits |
