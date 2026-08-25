# Architecture Overview

## System Design

Biome RAG follows a modular pipeline architecture with clear separation between ingestion, retrieval, generation, and evaluation layers.

## Component Diagram

```
Raw Documents (md, txt, html, pdf)
        │
        ▼
  ┌─────────────────────────────────────┐
  │         Ingestion Pipeline           │
  │  Loaders → Chunkers → Deduplication │
  │  Fixed / Structure / Semantic        │
  └───────────────────┬─────────────────┘
                      │
            ┌─────────┴──────────┐
            │                    │
     ┌──────▼──────┐    ┌───────▼──────┐
     │  BM25 Index │    │ Chroma Vector│
     │  (sparse)   │    │  Store (dense)│
     └──────┬──────┘    └───────┬──────┘
            │                    │
            └─────────┬──────────┘
                      │
                      ▼
           ┌──────────────────────┐
           │   Reciprocal Rank    │
           │   Fusion (RRF)       │
           └──────────┬───────────┘
                      │
                      ▼
           ┌──────────────────────┐
           │  Cross-Encoder       │
           │  Reranker            │
           └──────────┬───────────┘
                      │
                      ▼
           ┌──────────────────────┐
           │  Answer Builder      │
           │  LLM + Citations     │
           │  + Confidence Score  │
           └──────────┬───────────┘
                      │
               ┌──────┴──────┐
               │              │
        ┌──────▼──┐    ┌──────▼──────┐
        │ FastAPI  │    │  Streamlit  │
        │  /v1/*   │    │  Dashboard  │
        └──────────┘    └─────────────┘
```

## Design Decisions

### Why ChromaDB?

ChromaDB provides file-based persistence with no external service dependency. It handles embedding storage, cosine similarity search, and metadata filtering out of the box. For a single-machine deployment, it is the simplest path to a fully persistent vector store.

### Why Reciprocal Rank Fusion over score normalisation?

Score normalisation (e.g., min-max scaling) requires knowing the range of both BM25 and cosine similarity scores, which vary unpredictably across corpora. RRF only requires rank order, which is corpus-agnostic and produces consistently good results.

### Why a cross-encoder reranker?

Bi-encoder embeddings (used for initial retrieval) encode query and document independently, sacrificing some accuracy for speed. Cross-encoders attend to both query and document jointly, catching fine-grained relevance signals. Running the cross-encoder over only the top-20 fused candidates keeps latency manageable.

### Why three chunking strategies?

Different documents benefit from different chunking strategies. Markdown documentation benefits from structure-aware chunking that respects headings. Long prose benefits from fixed-size chunking with overlap to avoid losing context at boundaries. Semantic chunking produces more coherent chunks but is more expensive. Running all three and deduplicating covers the strengths of each.

## Data Flow

1. A document enters `data/raw/`
2. The appropriate loader extracts plain text with metadata
3. All three chunkers split the text; near-duplicates are removed
4. Chunks are stored in `data/processed/chunks.json`
5. BM25 index is built and saved as `data/index/bm25_index.pkl`
6. Dense embeddings are stored in ChromaDB at `data/index/chroma/`
7. At query time, the HybridRetriever queries both indexes
8. RRF combines the ranked lists; the cross-encoder reranks the top-20
9. The top-5 chunks are passed to the AnswerBuilder
10. The LLM generates a grounded answer with `[n]` citations
11. Citation verification flags any unsupported claims
12. The response includes a composite confidence score

## Latency Budget (per query, warm start)

| Step | Typical latency |
|------|----------------|
| Dense retrieval (Chroma) | 50–150ms |
| Sparse retrieval (BM25) | <5ms |
| RRF fusion | <1ms |
| Cross-encoder reranking (5 chunks) | 100–300ms |
| LLM generation (Ollama local) | 3–15s |
| LLM generation (GPT-4o-mini API) | 1–3s |
| Citation verification | 50–500ms |
| **Total (Ollama)** | **~5–20s** |
| **Total (API LLM)** | **~2–5s** |
