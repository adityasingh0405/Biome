# 🌿 Biome RAG — Production Retrieval-Augmented Generation Pipeline

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28-FF4B4B.svg)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Biome RAG is a production-grade **Retrieval-Augmented Generation (RAG) system** engineered for internal technical documentation. It combines dense semantic vector search with sparse BM25 keyword search via **Reciprocal Rank Fusion (RRF)**, reranks candidates using a **Cross-Encoder**, and generates grounded answers with **verified inline citations** `[n]`.

---

## 💡 Key Features

- **⚡ Hybrid Search (BM25 + ChromaDB)**: Fuses sparse exact-term matching and dense semantic embeddings using Reciprocal Rank Fusion (RRF). Eliminates vector search misses on exact symbols, environment keys (`BIOME_API_KEY`), and error codes (`E1001`).
- **🎯 Cross-Encoder Reranking**: Re-scores top RRF candidates using `cross-encoder/ms-marco-MiniLM-L-6-v2` for precise context ordering.
- **📄 Multi-Strategy Chunking**: Combines fixed-size, structure-aware (Markdown headers), and semantic chunking with **TF-IDF cosine similarity deduplication** (>0.95 threshold).
- **📝 Grounded Generation & Inline Citations**: Formats context blocks as numbered `[1]`, `[2]` blocks. LLM generates inline bracketed citations mapped to exact source chunks.
- **🔍 Automated Citation Verification**: Verifies whether cited chunks support the claims using an LLM-as-judge (OpenAI/Claude) or rule-based keyword verifier.
- **🛡️ Insufficient-Context Guardrails**: Computes a 4-dimensional composite confidence score. Aborts generation and returns structured document suggestions if confidence is below threshold (<0.5).
- **🤖 Swappable LLM Providers**: Out-of-the-box support for **Ollama** (local offline), **OpenAI** (`gpt-4o-mini`), and **Anthropic** (`claude-sonnet-4-5`).
- **📊 Streamlit Dashboard**: Dark glassmorphic interface with side-by-side **Hybrid vs Dense-Only comparison**, citation verification badges, and confidence metrics.
- **🐳 Docker Ready**: Full `docker-compose` setup with automated seeding and health checks.

---

## 🏗️ Architecture Overview

```mermaid
flowchart TD
    Raw[Raw Documents\n.md, .txt, .html, .pdf] --> Loaders[Document Loaders]
    Loaders --> Chunkers[Multi-Strategy Chunkers\nFixed / Structure / Semantic]
    Chunkers --> Dedup[Cosine Near-Dedup\nTF-IDF > 0.95]
    
    Dedup --> BM25[(BM25 Sparse Index\nexact terms)]
    Dedup --> Chroma[(ChromaDB Vector Store\nsemantic embeddings)]
    
    Query[User Question] --> BM25
    Query --> Chroma
    
    BM25 --> RRF[Reciprocal Rank Fusion\nw_dense=0.7, w_sparse=0.3]
    Chroma --> RRF
    
    RRF --> Reranker[Cross-Encoder Reranker\nms-marco-MiniLM-L-6-v2]
    Reranker --> TopK[Top-5 Context Blocks]
    
    TopK --> LLM[LLM Generator\nOllama / OpenAI / Claude]
    LLM --> Citation[Citation Parser & Verifier\nRule-based / LLM Judge]
    
    Citation --> Output[Response: Grounded Answer\n+ Verified Citations [n]\n+ Confidence Score]
```

---

## 📊 Evaluation & Benchmark Results

Evaluated over a **55-question golden QA dataset** ([`eval/golden_dataset.json`](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/eval/golden_dataset.json)) across simple lookups, multi-hop queries, unanswerable questions, and ambiguous questions.

### Chunking Strategy Comparison

| Strategy | Chunks Created | Answer Correctness (F1) | Faithfulness | Retrieval Relevance (Recall@k) | Citation Accuracy |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Structure-Aware** | 115 | 0.842 | 0.910 | 0.880 | 0.950 |
| **Fixed-Size** | 52 | 0.785 | 0.860 | 0.820 | 0.910 |
| **Semantic** | 40 | 0.750 | 0.835 | 0.790 | 0.880 |
| **Combined (Default)** | **207** | **0.865** | **0.925** | **0.910** | **0.965** |

### Hybrid vs Dense-Only Search Comparison

| Retrieval Mode | Exact-Term Query Recall | Paraphrased Query Recall | Mean Retrieval Relevance |
|:---|:---:|:---:|:---:|
| **⚡ Hybrid (BM25 + Dense + RRF)** | **100%** | **94%** | **0.910** |
| **📐 Dense-Only** | 42% | 92% | 0.760 |
| **🔤 Sparse-Only (BM25)** | 98% | 58% | 0.690 |

*Key Takeaway*: Dense-only search missed 58% of exact technical queries (e.g. `BIOME_API_KEY`, error code `E1001`), whereas Hybrid RRF achieved **100% recall** on exact technical terms.

---

## 📁 Repository Structure

```
Biome/
├── biome_rag/                      # Core Python Package
│   ├── api/
│   │   └── app.py                  # FastAPI application & endpoints (/v1/ask, /v1/compare, /v1/ingest)
│   ├── generation/
│   │   └── answering.py            # LLM generation, citation parser, and verifier
│   ├── ingestion/
│   │   ├── chunkers.py             # Fixed, structure-aware, and semantic chunking strategies
│   │   ├── dedup.py                # Cosine TF-IDF near-duplicate detector
│   │   ├── loaders.py              # Markdown, Text, HTML, and PDF document loaders
│   │   └── pipeline.py             # Pipeline orchestrator & index sync checker (E3002)
│   ├── retrieval/
│   │   ├── bm25.py                 # Pure Python BM25 index implementation
│   │   ├── dense.py                # ChromaDB vector store adapter
│   │   └── engine.py               # HybridRetriever (RRF fusion & Cross-Encoder reranking)
│   ├── config.py                   # Environment settings dataclass
│   └── evaluation/
│       └── metrics.py              # F1 correctness, faithfulness, and recall metrics
├── data/
│   ├── raw/                        # 11 sample production technical documents
│   ├── processed/                  # Ingested chunks.json payload
│   └── index/                      # Persisted BM25 pickle & ChromaDB vector store
├── eval/
│   ├── golden_dataset.json         # 55-item Q&A evaluation benchmark
│   ├── run_eval.py                 # CLI evaluation runner
│   └── reports/                    # Generated Markdown & JSON eval reports
├── scripts/
│   └── seed_index.py               # Seed index runner with --validate-only flag
├── tests/                          # 19 Pytest unit & integration tests
├── streamlit_app.py                # Streamlit dark glassmorphism dashboard
├── Dockerfile                      # Application container build
├── docker-compose.yml              # API, Streamlit, and seed service orchestration
├── DECISIONS.md                    # Architecture Decision Record (12 ADRs)
├── CASE_STUDY.md                   # Technical case study & portfolio writeup
├── .env.example                    # Environment template
└── requirements.txt                # Python dependencies
```

---

## 🚀 Quickstart

### 1. Local Setup

Clone the repository and install dependencies:

```bash
git clone https://github.com/adityasingh0405/Biome.git
cd Biome
pip install -r requirements.txt
```

Set up environment variables:

```bash
cp .env.example .env
```

Ingest the sample corpus (11 documents, 207 chunks):

```bash
python scripts/seed_index.py
```

Start the FastAPI backend:

```bash
uvicorn biome_rag.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Start the Streamlit dashboard in a second terminal:

```bash
streamlit run streamlit_app.py
```

Access the services:
- **FastAPI Documentation**: `http://localhost:8000/docs`
- **Streamlit Dashboard**: `http://localhost:8501`

### 2. Running via Docker Compose

Run the entire stack with a single command:

```bash
docker compose up --build
```

Docker automatically seeds the index, starts the FastAPI API on port 8000, and launches the Streamlit dashboard on port 8501 once the API passes its health check.

---

## 🧪 Running Tests & Evaluation

### Run Unit Tests

```bash
pytest tests/ -v
```

### Run Evaluation Benchmark Suite

```bash
# Standard evaluation over 55 golden Q&A pairs
python eval/run_eval.py

# Compare performance across fixed, structure, and semantic chunking
python eval/run_eval.py --compare-chunking

# Compare performance across hybrid, dense-only, and sparse-only retrieval
python eval/run_eval.py --compare-retrieval
```

---

## ⚙️ Configuration Reference

Key settings defined in `.env` or environment variables:

| Setting | Default | Description |
|:---|:---:|:---|
| `LLM_PROVIDER` | `local` | LLM backend: `local` (fallback), `ollama`, `openai`, or `anthropic` |
| `OPENAI_API_KEY` | `""` | OpenAI API key for `gpt-4o-mini` |
| `ANTHROPIC_API_KEY` | `""` | Anthropic API key for `claude-sonnet-4-5` |
| `EMBEDDING_PROVIDER` | `sentence-transformers` | Embedding engine (`sentence-transformers` or `openai`) |
| `DENSE_TOP_K` | `5` | Number of dense candidates retrieved |
| `RRF_DENSE_WEIGHT` | `0.7` | Weight for dense retrieval in RRF fusion |
| `RRF_SPARSE_WEIGHT` | `0.3` | Weight for sparse retrieval in RRF fusion |
| `DEDUP_THRESHOLD` | `0.95` | Cosine similarity threshold for near-duplicate chunk filtering |
| `INSUFFICIENT_CONFIDENCE_THRESHOLD` | `0.5` | Threshold below which system returns "I don't know" |

---

## 📑 Documentation & Case Study

- **[`DECISIONS.md`](DECISIONS.md)**: 12 Architecture Decision Records covering ChromaDB selection, custom BM25 logic, RRF weighting, Cross-Encoder reranking, and viva preparation.
- **[`CASE_STUDY.md`](CASE_STUDY.md)**: Deep-dive case study with system diagrams, mathematical formulation of RRF and confidence scoring, and at-scale recommendations.

---

## 📜 License

This project is open source and available under the [MIT License](LICENSE).