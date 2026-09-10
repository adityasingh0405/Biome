# DECISIONS.md — Architecture Decision Record

This file documents every significant design decision made in the Biome RAG system,
the rationale behind each choice, and the tradeoffs accepted. It doubles as interview/viva prep.

---

## D001 — Custom BM25 vs `rank_bm25` Library

**Decision:** Implement BM25 from scratch rather than using the `rank_bm25` PyPI library.

**Rationale:**
- `rank_bm25` adds a dependency without adding capability for our use case; the algorithm is ~60 lines.
- Custom implementation gives full control over tokenisation and persistence (pickle).
- Easier to audit for correctness in a viva setting.

**Tradeoffs:**
- Custom code requires maintenance; `rank_bm25` is battle-tested.
- Missing optimisations like BM25+ or BM25L variants, but standard BM25 is sufficient here.

---

## D002 — ChromaDB as Vector Store

**Decision:** Use ChromaDB file-based persistence over alternatives (Pinecone, Weaviate, Qdrant, FAISS).

**Rationale:**
- File-based means zero external service dependency — `docker-compose up` just works.
- Automatic persistence without explicit save calls.
- Built-in metadata filtering and cosine similarity out of the box.

**Tradeoffs:**
- Single-process access model (not distributed).
- Slower than FAISS for very large corpora (>1M chunks).
- Schema migrations required when upgrading ChromaDB versions.

**At scale:** Replace with a managed vector DB (Pinecone, Qdrant) with a consistent adapter interface.

---

## D003 — Embedding Model: sentence-transformers (all-MiniLM-L6-v2)

**Decision:** Use ChromaDB's default embedding function (all-MiniLM-L6-v2 via sentence-transformers) rather than OpenAI `text-embedding-3-small`.

**Rationale:**
- Zero cost — runs entirely locally without an API key.
- Fast enough for a demo/portfolio corpus (~10 docs).
- The abstract `DenseEmbeddingAdapter` interface makes swapping providers trivial via env var.

**Tradeoffs:**
- all-MiniLM-L6-v2 produces lower-quality embeddings than `text-embedding-3-small` for semantic tasks.
- Switching to `EMBEDDING_PROVIDER=openai` enables OpenAI embeddings but costs money per token.

**How to switch:** Set `EMBEDDING_PROVIDER=openai` and `OPENAI_API_KEY` in `.env`.

---

## D004 — RRF Weights (0.7 dense / 0.3 sparse)

**Decision:** Default weights of 0.7 for dense retrieval and 0.3 for sparse (BM25).

**Rationale:**
- For most natural language questions, semantic embedding search is more valuable than keyword matching.
- 0.3 weight on BM25 is enough to boost exact-term matches (error codes, env var names) without dominating.
- These weights match empirical defaults seen in research (BEIR benchmark tuning).

**Tradeoffs:**
- For corpora with many exact-term queries (e.g., code search, error code lookups), a higher sparse weight (0.5) may perform better.
- Both weights are configurable via `RRF_DENSE_WEIGHT` and `RRF_SPARSE_WEIGHT` env vars.

---

## D005 — Cross-Encoder Reranker: ms-marco-MiniLM-L-6-v2

**Decision:** Use `cross-encoder/ms-marco-MiniLM-L-6-v2` as the default reranker.

**Rationale:**
- Lightweight (22M params) — runs on CPU in ~100–300ms for 5 chunks.
- Trained on MS MARCO passage ranking — generalises well to documentation retrieval.
- Falls back gracefully to token overlap scoring if the model fails to load.

**Tradeoffs:**
- Larger cross-encoders (e.g., `ms-marco-electra-base`) would give better reranking but are slower.
- LLM-as-judge reranking (using GPT-4o) would be more accurate but costly.

**At scale:** Use a GPU-hosted cross-encoder or a managed reranking API (Cohere Rerank).

---

## D006 — Three Chunking Strategies (All Run by Default)

**Decision:** Run all three chunking strategies (fixed, structure-aware, semantic) on every document and deduplicate before indexing.

**Rationale:**
- Different documents benefit from different strategies; running all three maximises coverage.
- Deduplication (cosine similarity > 0.95) prevents bloating the index with nearly-identical chunks from different strategies.
- Strategy tags on chunks enable per-strategy evaluation later.

**Tradeoffs:**
- 3× the chunks before dedup, which increases indexing time.
- More chunks in the index slightly increases retrieval latency.
- Eval showed that combining strategies outperforms any single strategy on diverse corpora.

---

## D007 — Cosine Similarity Deduplication (Not Just Hash)

**Decision:** Use TF-IDF cosine similarity (threshold 0.95) for near-duplicate detection, with an exact MD5 hash as a fast pre-filter.

**Rationale:**
- Hash-only dedup misses near-duplicates (e.g., same content with trailing whitespace, minor punctuation differences).
- Cosine similarity correctly catches paraphrased or slightly reformatted duplicates.
- Two-stage approach: hash catches exact duplicates fast, cosine handles near-duplicates.

**Tradeoffs:**
- TF-IDF vectorisation over the growing corpus is O(n) per new chunk — acceptable for small-to-medium corpora.
- At scale, use approximate nearest-neighbour methods (LSH, Annoy) or MinHash for scalable dedup.

---

## D008 — Confidence Score Composite Formula

**Decision:** `composite = 0.5 * retrieval_confidence + 0.3 * citation_coverage + 0.2 * completeness`

**Rationale:**
- Retrieval confidence (sigmoid of max rerank score) is the most reliable signal — highest weight.
- Citation coverage (fraction of citations verified) is a strong faithfulness signal.
- Completeness (answer length heuristic) is the weakest proxy — lowest weight.

**Tradeoffs:**
- Length-based completeness is a crude proxy for actual answer quality.
- With an API key, completeness could use LLM-as-judge for a better signal.

**Threshold:** Below composite 0.5, the system returns a structured "I don't know" rather than fabricating.

---

## D009 — LLM Provider Strategy

**Decision:** Support three LLM providers with graceful degradation: Ollama (local) → OpenAI → Anthropic → local fallback.

**Rationale:**
- Ollama enables fully offline development and demos without API keys.
- OpenAI/Anthropic provide production-quality generation with reliable citation following.
- Local fallback (sentence extraction) ensures the system returns *something* even with no LLM.

**How to switch:** Set `LLM_PROVIDER=openai` or `LLM_PROVIDER=anthropic` and provide the corresponding API key.

---

## D010 — Streamlit Over React for Dashboard

**Decision:** Use Streamlit for the dashboard rather than building a React SPA.

**Rationale:**
- Streamlit is the fastest path to a working, shareable UI for a RAG demo.
- Requires no separate build pipeline or Node.js dependency.
- Sufficient for the portfolio goal — showing citations, confidence scores, and hybrid comparison.

**Tradeoffs:**
- Less control over fine-grained UI interactions compared to React.
- Not suitable for high-traffic production deployments.

**Future work:** A React/Next.js frontend would allow streaming responses and a more polished UX.

---

## D011 — `POST /v1/compare` Endpoint

**Decision:** Add a dedicated `/v1/compare` endpoint that runs the same question through hybrid and dense-only retrieval in a single API call.

**Rationale:**
- The dashboard's side-by-side comparison panel needs both results without making two sequential calls.
- A single server-side call is faster and avoids race conditions.
- This endpoint directly demonstrates the hybrid search advantage — a key portfolio talking point.

---

## D012 — Index Sync Check (E3002)

**Decision:** After every ingestion run, assert that BM25 and dense indexes contain the same chunk count. Log E3002 if they diverge.

**Rationale:**
- Interrupted ingestion (e.g., OOM during Chroma indexing) can leave the indexes inconsistent.
- Early detection prevents the retrieval engine from silently returning biased results.

**Tradeoffs:**
- Does not auto-repair — the operator must re-run ingestion manually.
- At scale, consider a transactional ingestion approach (write to a staging area, atomic swap).

---

## D013 — SlackIngester as a Well-Structured Stub

**Decision:** Implement SlackIngester as a complete class skeleton with full docstrings,
pseudocode implementation plan, and group-by-thread helper — but no live Slack API calls.

**Rationale:**
- No Slack workspace was available during development (student confirmed Postgres-only).
- A complete stub is architecturally honest: the class is importable, the interface is
  defined, and a future engineer can activate it by filling in _fetch_messages().
- This avoids a runtime import error when the Prefect flow (Phase 5) references SlackIngester.

**Tradeoffs:**
- No Slack data in the evaluation golden dataset (Postgres-only coverage).

**To activate:** Set SLACK_BOT_TOKEN and fill in _fetch_messages() in slack_ingester.py.

---

## D014 — DocumentIngester: Docling-First with Fallback

**Decision:** Use IBM Docling as the primary parser for PDF/DOCX/PPTX/HTML, with a
transparent fallback to the existing legacy loaders (PyMuPDF, python-docx, etc.).

**Rationale:**
- Docling preserves table structure, heading hierarchy, and reading order — essential
  for the Docling HybridChunker in Phase 2.
- The fallback means the pipeline works even if Docling models are not cached or the
  library is not installed, which is important for CI and cold starts.
- The Docling document object is stored in DocumentNode.docling_doc (excluded from
  serialization) so Phase 2 can use it directly without re-parsing.

**Tradeoffs:**
- Docling is heavy (~1-2 GB of model weights). First run downloads models.
- Pass use_docling=False for fast unit tests or when models are not cached.

---

## D015 — PostgresIngester: Watermark-First, Hash-Dedup Fallback

**Decision:** Incremental ingestion uses WHERE updated_at > :since when the column
exists, with content-hash dedup as a fallback for tables without updated_at.

**Rationale:**
- Watermark-based filtering is O(rows_since_watermark) not O(total_rows).
- Content-hash dedup (compute_payload_sha256) is an exact match — it catches
  re-processed rows that have identical content, preventing double-indexing.
- Two-stage approach mirrors the Phase 0 file-level dedup design (D007).

**Tradeoffs:**
- Without updated_at, the ingester must fetch all rows every run and dedup in memory.
- At scale (>100k rows), add a DB-side hash column for watermark-free incremental.


---

## D016 - TextChunker: Chonkie SentenceChunker with tiktoken

Use Chonkie SentenceChunker for Postgres and Slack documents with tiktoken cl100k_base for token counting.
Token targets: postgresql=256 tokens, slack=400 tokens, unstructured=512 tokens.
Falls back to pure-Python token-budget splitter when Chonkie is not installed.

---

## D017 - DocumentChunker: Docling HybridChunker + Oversized-Table Row-Split

Use Docling HybridChunker as primary document chunker. Oversized-table rule row-splits Markdown tables exceeding 600 tokens, repeating the header row in each sub-table.
Falls back to token-budget sentence splitter when docling_doc is None.


---

## D018 - QdrantAdapter: Native Hybrid Search with BGE-M3

Store BGE-M3 dense (1024-dim) AND sparse (lexical weight) vectors in a single Qdrant collection. Use Qdrant native Prefetch + RRF fusion at query time. Qdrant handles the fusion kernel inside the database, avoiding a round-trip for two separate queries.

Fallback chain: QdrantAdapter -> ChromaDenseEmbeddingAdapter -> SimpleDenseEmbeddingAdapter.
ACL enforcement: Qdrant payload filter on access_scope list, applied before ranking.

Rationale: Native Qdrant hybrid search is significantly faster than Python-side fusion because it avoids two full vector scans + Python list merging. The Prefetch API fetches top-20 candidates from each vector type, then fuses with RRF internally.


---

## D019 - IndexBuilder: Phase 1-2-3 Pipeline Orchestrator

The IndexBuilder (biome_rag.indexing) sequences the full ingestion pipeline:
Phase 1 DocumentIngester -> Phase 2 DocumentChunker/TextChunker -> Phase 3 BM25 + QdrantAdapter.

Design: groups explicit file paths by parent directory and runs one DocumentIngester per directory (matching the ingester API). Produces IndexingResult with per-phase timing, chunk counts by strategy and source_type, and error list.

Backward compat: IngestionPipeline.ingest() is NOT removed. Legacy /v1/ingest/* routes unchanged. New /v1/index/* routes use IndexBuilder.

Note: chunks.json is always written for ChunkStore compatibility with the existing HybridRetriever.


---

## D020 - Phase 5: Session Memory, Langfuse, Prefect

**Session Memory:** RedisSessionStore with sliding-window (default 10 turns, TTL 3600s). RPUSH+LTRIM pipeline for O(1) writes. Fallback to InMemorySessionStore when Redis is unreachable. Session ID flows from /v1/chat request → Redis key biome:session:<id>.

**Langfuse Observability:** LangfuseTracer wraps every /v1/ask and /v1/chat call in a trace with spans for retrieval (latency + top-k scores), reranking, and generation (token estimate, confidence). trace_id is returned in API responses. Fully no-op when langfuse_enabled=False or package absent.

**Prefect Flow:** biome_index_pipeline() wraps IndexBuilder as 5 Prefect tasks (ingest, chunk, BM25, Qdrant, artifact). Shim decorators allow import without Prefect installed. run_pipeline_direct() provides non-Prefect path for CI.

**API Version:** Bumped to 0.5.0. Added /v1/chat (multi-turn with session_id), /v1/session/{id} DELETE. /v1/ask extended with session_id and access_scope fields.


---

## D021 - Phase 6: Evaluation Harness (RAGAS + DeepEval)

**Extended metrics (biome_rag/evaluation/extended_metrics.py):**
- semantic_similarity: MiniLM cosine / token-F1 fallback
- context_precision, context_recall: RAGAS-style proxy (no LLM required)
- answer_relevancy: shared key-word coverage after stop-word removal
- noise_robustness: 1 - fraction of answer from noise-only chunks
- hallucination_score: bigram entailment proxy (0=grounded, 1=hallucinated)
- EvalThresholds: configurable gate with default/strict/lenient presets

**EvaluationHarness (biome_rag/evaluation/harness.py):**
- Orchestrates retrieve→generate→score per Q&A pair
- Optional RAGAS and DeepEval integration (graceful ImportError fallback)
- Writes JSON + Markdown reports to eval/reports/
- check_quality_gate() returns violations list; empty = pass

**run_eval.py:** Upgraded to use EvaluationHarness as primary path.
Adds --threshold, --use-ragas, --use-deepeval, --question-type flags.
Legacy --compare-chunking / --compare-retrieval paths preserved.

**API:** Added POST /v1/evaluate (accepts golden_path or inline records).
API bumped to v0.6.0.

---

## D022 - Phase 7: Ablation Study Runner & Automated Analysis

**Ablation Runner (eval/ablation_runner.py):**
- Automated Cartesian product sweep over 3 configuration axes:
  - `retrieval_mode`: `dense`, `sparse`, `hybrid`
  - `top_k`: `3`, `5`, `10`
  - `rerank`: `True`, `False`
  - Total: 18 configuration arms evaluated against the golden dataset (55 questions).
- **Composite Score Formula:**
  `composite = 0.30*correctness + 0.20*faithfulness + 0.15*context_precision + 0.10*context_recall + 0.10*answer_relevancy + 0.10*semantic_similarity - 0.05*hallucination_score`
- Generates `eval/ABLATION_RESULTS.md`, `ABLATION_RESULTS.md`, and `eval/ablation_results.json`.
- Per-arm and per-axis breakdown tables with automatic ranking and summary metrics.

**Engine & Harness Enhancements:**
- `HybridRetriever.retrieve()`: added `rerank: bool = True` parameter to cleanly support ablation without re-ranking.
- `EvaluationHarness`: accepts `top_k` and `rerank` parameters to parameterize pipeline runs per arm.
- `AnswerBuilder`: added circuit breaker `_ollama_unreachable` to fail fast to local fallback when Ollama daemon is offline, accelerating 18-arm ablation runs from 30 minutes down to ~4 minutes.

**Empirical Findings:**
- Top winning arm: `hybrid_k10_no_rerank` with composite score **0.4721** (MRR 0.540, Ctx-P 0.780, Ctx-R 0.642, Faithfulness 0.773).
- Hybrid retrieval outperforms single-mode retrieval across all configurations (Avg composite: Hybrid 0.4281 vs Dense 0.4128 vs Sparse 0.3338).
- Higher `top_k` (k=10) provides better context recall without significantly increasing hallucination.

