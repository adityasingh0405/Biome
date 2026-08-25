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
