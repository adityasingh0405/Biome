# Technical Architecture Audit & System Analysis: Biome RAG

> **Document Type:** Technical System Audit & Architecture Analysis  
> **Target System:** Biome Enterprise Retrieval-Augmented Generation (RAG) & NL2SQL Platform  
> **Codebase Version:** `0.6.0` / API Version `0.7.0`  
> **Status:** Production / Portfolio-Grade Hybrid Intelligence Engine  
> **Audit Date:** October 2026  

---

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Tech Stack Inventory](#2-tech-stack-inventory)
3. [Annotated Repository Structure](#3-annotated-repository-structure)
4. [Module-by-Module Breakdown](#4-module-by-module-breakdown)
   - [4.1 Configuration Layer (`biome_rag/config.py`)](#41-configuration-layer-biome_ragconfigpy)
   - [4.2 Ingestion & Loader Subsystem (`biome_rag/ingestion/`)](#42-ingestion--loader-subsystem-biome_ragingestion)
   - [4.3 Layout-Aware Chunking Engine (`biome_rag/chunking/`)](#43-layout-aware-chunking-engine-biome_ragchunking)
   - [4.4 Retrieval & Vector Engine (`biome_rag/retrieval/`)](#44-retrieval--vector-engine-biome_ragretrieval)
   - [4.5 Index Orchestration (`biome_rag/indexing/`)](#45-index-orchestration-biome_ragindexing)
   - [4.6 Grounded Generation & Citation Engine (`biome_rag/generation/`)](#46-grounded-generation--citation-engine-biome_raggeneration)
   - [4.7 Conversational Memory Subsystem (`biome_rag/memory/`)](#47-conversational-memory-subsystem-biome_ragmemory)
   - [4.8 Observability & Distributed Tracing (`biome_rag/observability/`)](#48-observability--distributed-tracing-biome_ragobservability)
   - [4.9 Pipeline Orchestration Flows (`biome_rag/flows/`)](#49-pipeline-orchestration-flows-biome_ragflows)
   - [4.10 Evaluation, Benchmark & Ablation Harness (`biome_rag/evaluation/`, `eval/`)](#410-evaluation-benchmark--ablation-harness-biome_ragevaluation-eval)
   - [4.11 REST API Application Layer (`biome_rag/api/app.py`, `app.py`)](#411-rest-api-application-layer-biome_ragapiapppy-apppy)
   - [4.12 Modern Web Client (`frontend/`)](#412-modern-web-client-frontend)
   - [4.13 Top-Level Wrapper Packages & Automation Scripts](#413-top-level-wrapper-packages--automation-scripts)
5. [Workflows (Step by Step)](#5-workflows-step-by-step)
   - [5.1 Ingestion Workflow](#51-ingestion-workflow)
   - [5.2 Indexing Workflow](#52-indexing-workflow)
   - [5.3 Query / Retrieval Workflow](#53-query--retrieval-workflow)
   - [5.4 Generation Workflow](#54-generation-workflow)
   - [5.5 Secondary Flows: Session Chat, Observability, NL2SQL, Evaluation, and Orchestration](#55-secondary-flows-session-chat-observability-nl2sql-evaluation-and-orchestration)
6. [Data Flow & Persistence](#6-data-flow--persistence)
   - [6.1 Overall System Architecture Diagram](#61-overall-system-architecture-diagram)
   - [6.2 Ingestion & Indexing Pipeline Diagram](#62-ingestion--indexing-pipeline-diagram)
   - [6.3 Query-Time Decision & Execution Flow Diagram](#63-query-time-decision--execution-flow-diagram)
   - [6.4 Stage Data Transformations Matrix](#64-stage-data-transformations-matrix)
   - [6.5 Persistence Layer Architecture](#65-persistence-layer-architecture)
7. [Configuration & Environment](#7-configuration--environment)
8. [Entry Points & Operational Runbook](#8-entry-points--operational-runbook)
9. [External Dependencies & Failure Modes](#9-external-dependencies--failure-modes)
10. [Prompts & Model Parameter Usage](#10-prompts--model-parameter-usage)
11. [Testing, Evaluation & Observability](#11-testing-evaluation--observability)
12. [Risks, Gaps & Code Smells](#12-risks-gaps--code-smells)
13. [Suggested Reading Order](#13-suggested-reading-order)
14. [Domain Glossary](#14-domain-glossary)
15. [Confidence & Coverage Audit Note](#15-confidence--coverage-audit-note)

---

## 1. Executive Summary

Biome RAG is an enterprise-grade dual-path conversational knowledge retrieval platform that merges unstructured documentation retrieval with structured relational analytics. It is designed for enterprise knowledge workers and IT support teams who need exact, cited answers from complex internal handbooks, PDFs, presentations, ticketing systems, and policy manuals without hallucinations.

When a query arrives, a deterministic classifier routes it either to a sandboxed natural language to SQL (NL2SQL) engine running over PostgreSQL with programmatic row-level access control (ACL), or to a hybrid retrieval pipeline. The hybrid pipeline retrieves candidates via dense semantic vectors (BGE-M3 1024-dimensional embeddings stored in Qdrant) and lexical keyword matching (BM25 with inverted index and TF-IDF), fused together through Reciprocal Rank Fusion (RRF, $k=60$). Fused candidates are reranked via a cross-encoder (`ms-marco-MiniLM-L-6-v2`) before being injected into a strict, citation-enforcing LLM context window supporting Ollama, OpenAI, Anthropic, or Groq. Stateful conversations are persisted via Redis sliding-window memory, end-to-end execution spans are traced with Langfuse, and empirical quality is measured via an 18-arm ablation and RAGAS/DeepEval test harness.

---

## 2. Tech Stack Inventory

| Component / Layer | Technology | Version (from lock/config) | Location in Repo | Architectural Purpose |
|---|---|---|---|---|
| **Core Runtime** | Python | `>=3.11` (`3.12` tested) | `pyproject.toml`, `.env.example` | Primary backend execution runtime |
| **API Framework** | FastAPI | `>=0.115.0` | `biome_rag/api/app.py`, `app.py` | Asynchronous REST API routing, OpenAPI docs, file uploads |
| **ASGI Server** | Uvicorn | `>=0.30.6` | `app.py`, `docker-compose.yml` | Production HTTP server process with workers |
| **Data Validation** | Pydantic & Pydantic-Settings | `>=2.9.0` / `>=2.3.0` | `biome_rag/config.py`, `biome_rag/ingestion/models.py` | Type validation, schema coercion, and `.env` loading |
| **Vector Database (Primary)** | Qdrant | `v1.10.1` (Docker) / `client >=1.10.0` | `biome_rag/retrieval/qdrant_store.py`, `docker-compose.yml` | Hybrid vector search (dense cosine + sparse dot-product with native fusion) |
| **Vector Database (Legacy Fallback)** | ChromaDB | `>=0.5.0` | `biome_rag/retrieval/dense.py` | Local disk-based vector collection fallback |
| **Dense Embedding Model** | BAAI/bge-m3 | VIA `FlagEmbedding>=1.2.9` / `sentence-transformers>=3.0.0` | `biome_rag/retrieval/embeddings.py` | 1024-dimensional dense semantic vectors and lexical term weights |
| **Sparse / Lexical Engine** | Custom Inverted Index + rank-bm25 fallback | Pure Python / `rank-bm25>=0.2.2` | `biome_rag/retrieval/bm25.py` | Exact token match, error code (`ERR-401`), and keyword retrieval |
| **Cross-Encoder Reranker** | `cross-encoder/ms-marco-MiniLM-L-6-v2` | VIA `sentence-transformers>=3.0.0` | `biome_rag/retrieval/engine.py -> Reranker` | Deep passage cross-attention reranking of fused candidates |
| **Layout-Aware Doc Parser** | IBM Docling | `>=2.0.0` | `biome_rag/ingestion/document_ingester.py` | PDF/DOCX/PPTX/HTML parsing preserving tables and heading trees |
| **Fallback Parsers** | PyMuPDF (`fitz`), `pypdf`, `python-docx`, `python-pptx`, `beautifulsoup4`, `lxml` | `PyMuPDF>=1.24.0`, `python-docx>=1.1.0`, `python-pptx>=0.6.23` | `biome_rag/ingestion/loaders.py` | Secondary document text extractors when Docling is unavailable |
| **Text Chunking Library** | Chonkie (`chonkie[semantic]`) | `>=0.3.0` | `biome_rag/chunking/text_chunker.py` | Token-budgeted sentence and semantic chunking for DB/Slack text |
| **Docling Hybrid Chunker** | Docling `HybridChunker` | Docling native | `biome_rag/chunking/document_chunker.py` | Heading-prefix and table-aware document chunking |
| **Token Counting** | Tiktoken | `cl100k_base` | `biome_rag/chunking/base.py` | Token estimation and strict window enforcement |
| **Primary Relational DB** | PostgreSQL | `16-alpine` (Docker) / `psycopg2-binary>=2.9.9`, `SQLAlchemy>=2.0.0` | `biome_rag/ingestion/postgres_ingester.py`, `biome_rag/retrieval/router.py` | Relational ticket storage (`enterprise_tickets`) and Langfuse internal DB |
| **Local State Ledger** | SQLite | Python standard library | `biome_rag/ingestion/dedup.py`, `biome_rag/ingestion/base.py` | Content-hash tracking (`ingestion_state.db`) and incremental watermarks |
| **Session Memory & Cache** | Redis | `7-alpine` (Docker) / `redis>=5.0.0` | `biome_rag/memory/session.py` | Sliding-window conversational chat memory (`RPUSH` + `LTRIM`) |
| **LLM Inference (Local)** | Ollama (`llama3.1:8b`) | Latest image (Docker) | `biome_rag/generation/answering.py` | Local zero-cost grounded generation via HTTP API |
| **LLM Providers (Cloud)** | OpenAI (`gpt-4o-mini`), Anthropic (`claude-sonnet-4-5`), Groq (`llama-3.1-8b-instant`) | `openai>=1.40.0`, `anthropic>=0.34.0`, `groq>=0.9.0` | `biome_rag/generation/answering.py` | Production cloud LLM endpoints with graceful degradation |
| **Observability & Tracing** | Langfuse | `v2` (Docker) / `langfuse>=2.35.0` | `biome_rag/observability/langfuse_tracer.py` | Request latency, generation spans, token metrics, trace dashboards |
| **Pipeline Orchestrator** | Prefect | `>=3.0.0` | `biome_rag/flows/index_flow.py` | Scheduled, resilient ingestion pipelines with task state tracking |
| **Evaluation Frameworks** | RAGAS & DeepEval | `ragas>=0.1.21`, `deepeval>=1.0.0` | `biome_rag/evaluation/harness.py`, `eval/` | End-to-end RAG metric calculation and quality gates |
| **Frontend Framework** | React 18 + Vite | `React 18.3.1`, `Vite 5.4.2` | `frontend/` | Dark glassmorphic user copilot, ROI calculator, and arena UI |
| **Frontend Styling** | Tailwind CSS & Lucide Icons | `tailwindcss 3.4.11`, `lucide-react 0.441.0` | `frontend/tailwind.config.js`, `frontend/src/` | Glassmorphism, animations, UI components |
| **Containerization** | Docker & Docker Compose | Compose file version 3.8 schema | `docker-compose.yml`, `Dockerfile`, `frontend/Dockerfile` | Multi-container stack (api, frontend, qdrant, redis, ollama, langfuse) |
| **Testing Harness** | Pytest, pytest-asyncio, HTTPX | `pytest>=8.3.0`, `httpx>=0.27.0` | `tests/` | Unit, integration, ablation, and regression test suites |

---

## 3. Annotated Repository Structure

```
Biome/
├── .env                              # Active local runtime environment variables (untracked)
├── .env.example                      # Documented configuration template for deployment
├── .gitignore                        # Git exclusion rules (virtual environments, caches, DBs)
├── ABLATION_RESULTS.md               # Executive summary of the 18-arm retrieval ablation study
├── AUDIT_REPORT.md                   # Initial security and architectural defect audit
├── CASE_STUDY.md                     # Engineering narrative and business case study
├── DECISIONS.md                      # Architecture Decision Records (ADRs D001 through D024)
├── Dockerfile                        # Multi-stage container build for FastAPI backend
├── README.md                         # Project overview, architectural diagrams, quickstart
├── SETUP_INTEGRATIONS.md             # Integration setup runbook (Slack, Qdrant, Ollama, Langfuse)
├── app.py                            # Root convenience launcher executing Uvicorn on port 8000
├── docker-compose.yml                # Full stack definitions: Qdrant, Redis, Ollama, Langfuse, API, Frontend
├── docker-entrypoint.sh              # Container startup script for backend container
├── generate_mock_files.py            # Generates test DOCX, PPTX, and TXT files for local data bucket
├── pyproject.toml                    # PEP 621 package metadata, phase dependencies, and pytest config
├── requirements.txt                  # Comprehensive pinned Python dependency manifest
├── seed_db.py                        # Standalone script populating enterprise_tickets table with Faker
├── test_pag.docx                     # Sample test binary document for loader testing
├── DOC-20260915-WA0023.pdf           # Sample real-world test PDF document
│
├── biome_rag/                        # Core Python package root
│   ├── __init__.py                   # Package initialization
│   ├── config.py                     # Pydantic BaseSettings: centralized environment & config management
│   │
│   ├── api/                          # FastAPI REST application layer
│   │   ├── __init__.py               # API module initializer
│   │   └── app.py                    # API route definitions, request/response models, app factory
│   │
│   ├── chunking/                     # Phase 2 layout-aware & token-budget chunking
│   │   ├── __init__.py               # Source-type chunking router (get_chunker factory)
│   │   ├── base.py                   # Chunker ABC, tiktoken token counting, split_text_by_tokens
│   │   ├── document_chunker.py       # Docling HybridChunker + Markdown table row-splitting rule
│   │   └── text_chunker.py           # Chonkie SentenceChunker for PostgreSQL and Slack text
│   │
│   ├── evaluation/                   # Phase 6 offline evaluation & metrics
│   │   ├── __init__.py               # Evaluation package exports
│   │   ├── extended_metrics.py       # Deterministic RAGAS proxies, hallucination, similarity, thresholds
│   │   ├── harness.py                # EvaluationHarness: Q&A evaluation runner and quality gate checker
│   │   ├── metrics.py                # Lexical baselines: answer_correctness, faithfulness, MRR, P@k
│   │   └── report.py                 # Markdown and JSON report generator for evaluation runs
│   │
│   ├── flows/                        # Phase 5 workflow orchestration
│   │   ├── __init__.py               # Flows module initializer
│   │   └── index_flow.py             # Prefect flow & tasks for scheduled end-to-end indexing
│   │
│   ├── generation/                   # Grounded generation, citation verification & confidence
│   │   ├── __init__.py               # Generation module initializer
│   │   └── answering.py              # AnswerBuilder: LLM dispatch (Ollama/OpenAI/Anthropic), citations, fallback
│   │
│   ├── indexing/                     # Phase 4 pipeline orchestration
│   │   ├── __init__.py               # Indexing package exports
│   │   └── builder.py                # IndexBuilder: Orchestrates Phase 1 (Ingest) -> 2 (Chunk) -> 3 (Index)
│   │
│   ├── ingestion/                    # Multi-source data ingestion, deduplication & normalization
│   │   ├── __init__.py               # Ingestion package exports
│   │   ├── base.py                   # Ingester ABC, IngestResult contract, SQLite WatermarkStore
│   │   ├── chunkers.py               # Legacy Phase 0 chunkers (Fixed, StructureAware, Semantic)
│   │   ├── cli.py                    # Standalone CLI entry point for ingestion operations
│   │   ├── dedup.py                  # SHA-256 content hashing, SQLiteStateTracker, TF-IDF Deduplicator
│   │   ├── document_ingester.py      # IBM Docling layout parser + fallback to legacy file loaders
│   │   ├── loaders.py                # Format-specific file loaders (PDF, DOCX, PPTX, HTML, CSV, Code)
│   │   ├── models.py                 # DocumentMetadata, DocumentNode, NormalizedDocument, Chunk dataclasses
│   │   ├── pipeline.py               # Legacy IngestionPipeline (Silver layer JSONL output)
│   │   ├── postgres_ingester.py      # SQLAlchemy Core table ingester with watermark & hash dedup
│   │   └── slack_ingester.py         # Slack API thread-level ingester skeleton (structured stub)
│   │
│   ├── memory/                       # Phase 5 conversational session memory
│   │   ├── __init__.py               # Memory package exports (get_session_store factory)
│   │   └── session.py                # RedisSessionStore (RPUSH/LTRIM) + InMemorySessionStore fallback
│   │
│   ├── observability/                # Phase 5 telemetry & distributed tracing
│   │   ├── __init__.py               # Observability package exports (get_tracer factory)
│   │   └── langfuse_tracer.py        # LangfuseTracer & RAGTrace: spans for retrieval, rerank, generation
│   │
│   └── retrieval/                    # Search, vector storage, reranking & routing
│       ├── __init__.py               # Retrieval package exports
│       ├── bm25.py                   # BM25Index: Custom inverted index with term frequency & IDF persistence
│       ├── dense.py                  # DenseEmbeddingAdapter, ChromaDenseEmbeddingAdapter, Simple fallback
│       ├── embeddings.py             # BGE_M3Encoder: FlagEmbedding BAAI/bge-m3 dense + sparse encoder
│       ├── engine.py                 # HybridRetriever (RRF fusion k=60), Reranker (CrossEncoder)
│       ├── models.py                 # RankedChunk dataclass
│       ├── qdrant_store.py           # QdrantAdapter: Native dual-vector storage and hybrid prefetch search
│       ├── router.py                 # QueryRouter (SEMANTIC vs STRUCTURED) & Sandboxed NL2SQLEngine
│       └── stores.py                 # ChunkStore: Loads chunks.json / bm25_index.pkl into memory
│
├── data/                             # File-based runtime data directory
│   ├── index/                        # Persisted search indexes
│   │   ├── bm25_index.pkl            # Serialized BM25 inverted index dictionary
│   │   └── chroma/                   # Legacy ChromaDB sqlite/parquet vector files
│   ├── ingestion_state.db            # SQLite database tracking indexed SHA-256 hashes & watermarks
│   ├── processed/                    # Processed chunk storage
│   │   └── chunks.json               # Serialized JSON array of all active Chunk objects
│   ├── raw/                          # Default local input documents (Markdown, HTML, TXT)
│   │   ├── api-reference.md          # Technical documentation on endpoints and tokens
│   │   ├── architecture.md           # Internal design specification
│   │   ├── changelog.txt             # Historical system revision logs
│   │   ├── configuration.md          # Guide to environment parameters
│   │   ├── deployment-guide.md       # Cluster deployment instructions
│   │   ├── error-codes.html          # HTML reference of enterprise error codes (E1001, etc.)
│   │   ├── evaluation-methodology.txt# Evaluation guidelines
│   │   ├── faq.md                    # Frequently asked internal questions
│   │   ├── onboarding.md             # Employee handbook and setup guide
│   │   ├── security.md               # Security guidelines and password rules
│   │   └── troubleshooting.md        # Operational troubleshooting steps
│   └── silver/                       # Intermediate clean document layer
│       ├── documents.json            # Array of normalized DocumentNode JSON objects
│       └── documents.jsonl           # Line-delimited JSON stream of DocumentNodes
│
├── eval/                             # Evaluation datasets, reports, and ablation runners
│   ├── ABLATION_RESULTS.md           # Copy of ablation findings
│   ├── ablation_results.json         # Raw Cartesian metric results across 18 ablation arms
│   ├── ablation_runner.py            # Cartesian sweep runner across retrieval_mode, top_k, rerank
│   ├── golden_dataset.json           # Comprehensive 55-question golden QA benchmark
│   ├── golden_qa.jsonl               # 10-question compact evaluation dataset
│   ├── reports/                      # Output directory for timestamped markdown/JSON eval runs
│   └── run_eval.py                   # CLI tool to run EvaluationHarness against golden datasets
│
├── frontend/                         # Modern React 18 + Vite Web Application
│   ├── Dockerfile                    # Container definition for frontend
│   ├── package.json                  # Node.js dependencies (React, Lucide, Tailwind, Vite)
│   ├── tailwind.config.js            # Tailwind CSS styling and theme configuration
│   ├── vite.config.js                # Vite build configuration and API reverse proxy
│   └── src/
│       ├── App.jsx                   # Main layout container and tab routing
│       ├── index.css                 # Global glassmorphic styles and custom scrollbars
│       ├── components/
│       │   ├── LandingPage.jsx       # Interactive business landing page, architecture tour & ROI calculator
│       │   ├── Navbar.jsx            # Application header with health check pill and navigation
│       │   ├── Workspace.jsx         # Feature studio tab container
│       │   └── views/
│       │       ├── AblationView.jsx  # Interactive 18-arm ablation matrix and benchmark chart
│       │       ├── ChatView.jsx      # Neural copilot with verified citation pills & confidence radar
│       │       ├── CompareView.jsx   # Side-by-side hybrid vs dense retrieval arena
│       │       ├── KnowledgeBaseView.jsx # Document repository, file uploader, directory crawler
│       │       ├── RoiCalculatorView.jsx # Dedicated business ROI modeler
│       │       └── SqlView.jsx       # Interactive NL2SQL query runner, schema viewer & ACL simulator
│       └── services/
│           └── api.js                # Frontend API client communicating with FastAPI backend
│
├── ingestion/                        # Root wrapper package re-exporting biome_rag.ingestion
│   ├── __init__.py                   # Re-exports loaders, models, dedup, and pipeline
│   ├── cli.py                        # Root CLI alias
│   ├── dedup.py                      # Re-export alias
│   ├── loaders.py                    # Re-export alias
│   ├── models.py                     # Re-export alias
│   └── pipeline.py                   # Re-export alias
│
├── local_data_bucket/                # Mock local object store / shared drive
│   └── unstructured/                 # Test files (Word, PowerPoint, PDF, TXT)
│
├── retrieval/                        # Root wrapper package re-exporting biome_rag.retrieval
│   ├── __init__.py                   # Re-exports HybridRetriever, QueryRouter, NL2SQLEngine
│   └── router.py                     # Root wrapper alias for router module
│
├── scripts/                          # Operational, seeding, and verification scripts
│   ├── seed_index.py                 # Seeds index from data/raw/ and asserts E3002 index sync
│   ├── setup_system.py               # End-to-end zero-to-running bootstrap script
│   └── report_gen/                   # Utility scripts for document analysis
│
└── tests/                            # Automated test suite (21 test modules)
    ├── test_api.py                   # Integration tests for FastAPI endpoints
    ├── test_chunkers.py              # Unit tests for Phase 0 chunkers
    ├── test_dedup.py                 # Tests for TF-IDF and SQLite state deduplication
    ├── test_document_ingester.py     # Tests for Docling layout parser and fallback loaders
    ├── test_enterprise_ingestion.py  # Tests for SQLite state tracker and Silver layer
    ├── test_evaluation.py            # Basic lexical evaluation tests
    ├── test_generation.py            # Tests for AnswerBuilder and citation verification
    ├── test_loaders.py               # Unit tests for PDF, DOCX, PPTX, HTML loaders
    ├── test_phase1_ingesters.py      # Comprehensive tests for Document, Postgres, Slack ingesters
    ├── test_phase2_chunking.py       # Tests for Docling HybridChunker and Chonkie TextChunker
    ├── test_phase2_e2e_pipeline.py   # End-to-end integration tests for Ingestion -> Chunking
    ├── test_phase3_embeddings.py     # Tests for BGE-M3 dual-encoder and QdrantAdapter
    ├── test_phase4_indexbuilder.py   # Tests for IndexBuilder orchestration
    ├── test_phase5_memory_observability.py # Tests for RedisSessionStore and LangfuseTracer
    ├── test_phase6_evaluation.py     # Tests for extended evaluation metrics and harness
    ├── test_phase7_ablation.py       # Tests for AblationRunner Cartesian sweeping
    ├── test_phase8_nl2sql.py         # Tests for QueryRouter, Sandboxed SQL, and row-level ACL
    ├── test_pipeline.py              # Tests for legacy IngestionPipeline
    ├── test_retrieval.py             # Tests for BM25, Chroma, and Reranker
    ├── test_retrieval_hybrid_advantage.py # Regression test proving hybrid superiority over dense
    └── test_retrieval_regression.py  # Regression tests for rank scoring and fusion
```

---

## 4. Module-by-Module Breakdown

### 4.1 Configuration Layer (`biome_rag/config.py`)
- **Purpose & Responsibility:** Acts as the single source of truth for all system configuration, thresholds, timeouts, credentials, and connection strings. Migrated from an older `@dataclass` pattern (fixing `BUG-003`) to `pydantic-settings.BaseSettings`.
- **Technologies Used:** `pydantic`, `pydantic_settings.BaseSettings`, `functools.lru_cache`.
- **Key Classes & Functions:**
  - [Settings](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/config.py#L27-L167): Primary settings class reading from environment variables, `.env` file, and hardcoded defaults. Includes properties like `sensitive_field_list`.
  - [get_settings()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/config.py#L170-L177): Cached singleton factory using `@lru_cache(maxsize=1)`.
  - [get_runtime_settings()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/config.py#L183-L189): Backward-compatibility shim mapping directly to `get_settings()`.
- **Dependencies:** Relies on `.env` file in the project root. Depended on by every other module in `biome_rag`.
- **Notable Quirks & Hardcoded Defaults:** Case-insensitive environment mapping (`case_sensitive=False`). Extra keys in `.env` are silently ignored (`extra="ignore"`). If `pydantic_settings` is missing, it falls back to basic `pydantic.BaseModel`.

### 4.2 Ingestion & Loader Subsystem (`biome_rag/ingestion/`)
- **Purpose & Responsibility:** Ingests heterogeneous data sources (unstructured files, relational databases, Slack threads), applies content-hash and near-duplicate detection, and normalizes inputs into structured `DocumentNode` objects.
- **Technologies Used:** IBM Docling (`docling`), PyMuPDF (`fitz`), `pypdf`, `python-docx`, `python-pptx`, `beautifulsoup4`, `lxml`, `SQLAlchemy`, `psycopg2-binary`, `sqlite3`, `scikit-learn` (TF-IDF vectorizer).
- **File Breakdown:**
  - [models.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/models.py): Defines data schemas. [DocumentMetadata](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/models.py#L14-L62) enforces source types, timestamps, file hashes, and access control lists (`access_level`, `access_scope`). [DocumentNode](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/models.py#L64-L134) represents normalized documents, storing the IBM Docling document object in `docling_doc` (excluded from serialization). [Chunk](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/models.py#L150-L161) holds text, token count, strategy tag, and source tracking.
  - [base.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/base.py): Defines the abstract base class [Ingester](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/base.py#L51-L105) with an `ingest(since: datetime | None)` contract, the [IngestResult](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/base.py#L36-L45) dataclass, and the SQLite-backed [WatermarkStore](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/base.py#L111-L194) for incremental runs.
  - [dedup.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/dedup.py): Provides cryptographic SHA-256 calculation ([compute_file_sha256](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/dedup.py#L17-L28), [compute_payload_sha256](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/dedup.py#L30-L44)), [SQLiteStateTracker](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/dedup.py#L50-L206) (persisting indexed hashes to `data/ingestion_state.db` with WAL mode), and [Deduplicator](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/dedup.py#L228-L291) (TF-IDF cosine similarity near-duplicate detection at threshold `0.95`).
  - [document_ingester.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/document_ingester.py): Implements [DocumentIngester](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/document_ingester.py#L88-L329). Parses `.pdf`, `.docx`, `.pptx`, `.html` with Docling, exporting layout markdown to `page_content` while preserving `docling_doc`. Falls back to legacy loaders for code and text files, or if Docling is missing. Automatically infers `access_scope` via filename heuristics ([_infer_access_scope](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/document_ingester.py#L51-L82)).
  - [loaders.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/loaders.py): Contains legacy file loaders ([PdfLoader](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/loaders.py#L88-L160) using PyMuPDF with pypdf fallback, [DocxLoader](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/loaders.py#L162-L200), [PptxLoader](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/loaders.py#L202-L240), [HtmlLoader](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/loaders.py#L242-L285), [PlainTextLoader](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/loaders.py#L28-L56), [MarkdownLoader](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/loaders.py#L58-L86), [CsvLoader](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/loaders.py#L320-L360), [CodeLoader](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/loaders.py#L362-L395), [PostgreSQLLoader](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/loaders.py#L397-L490)).
  - [postgres_ingester.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/postgres_ingester.py): Implements [PostgresIngester](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/postgres_ingester.py#L81-L345) using SQLAlchemy Core. Uses `WHERE updated_at > :since` for incremental runs; falls back to full scan with row content-hash deduplication when `updated_at` is missing. Formats each row into natural Markdown ([_row_to_markdown](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/postgres_ingester.py#L35-L62)) while redacting sensitive columns (`password`, `ssn`, `tax_id`).
  - [slack_ingester.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/slack_ingester.py): Implements [SlackIngester](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/slack_ingester.py#L33-L208). A structured stub with full interface contracts, channel scope assignment, thread grouping ([_group_by_thread](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/slack_ingester.py#L161-L173)), and conversion to Markdown documents, designed to prevent runtime import failures in Prefect flows.
  - [chunkers.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/chunkers.py): Legacy Phase 0 chunking strategies ([FixedSizeChunker](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/chunkers.py#L36-L84), [StructureAwareChunker](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/chunkers.py#L91-L260), [SemanticChunker](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/chunkers.py#L262-L442)).
  - [pipeline.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/pipeline.py): Legacy [IngestionPipeline](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/pipeline.py#L24-L296) coordinating local data bucket loading, state tracking, and persisting documents to the Silver Layer (`data/silver/documents.jsonl`).
  - [cli.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/cli.py): CLI wrapper providing `python -m biome_rag.ingestion.cli --source all --limit 100`.

### 4.3 Layout-Aware Chunking Engine (`biome_rag/chunking/`)
- **Purpose & Responsibility:** Converts clean `DocumentNode` objects into retrievable `Chunk` units budgeted by token count rather than character count, preserving table integrity and semantic flow.
- **Technologies Used:** `tiktoken` (`cl100k_base`), `chonkie` (`SentenceChunker`), IBM Docling (`HybridChunker`).
- **File Breakdown:**
  - [base.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/chunking/base.py): Base [Chunker](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/chunking/base.py#L176-L229) abstract class. Provides [count_tokens()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/chunking/base.py#L53-L71) with cached tiktoken encoding (falling back to a $1.3 \times \text{words}$ heuristic if tiktoken is missing), and [split_text_by_tokens()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/chunking/base.py#L77-L155) for pure-Python fallback token splitting.
  - [document_chunker.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/chunking/document_chunker.py): Implements [DocumentChunker](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/chunking/document_chunker.py#L106-L309). If `docling_doc` is present on the node, it runs IBM Docling's `HybridChunker` (which prepends parent section headers). Contains an explicit **oversized-table row splitting rule** ([_split_markdown_table_by_rows](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/chunking/document_chunker.py#L51-L99)): any Markdown table chunk exceeding `table_split_max_tokens` (600 tokens) is split into row slices with the table header and separator row repeated across every sub-chunk.
  - [text_chunker.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/chunking/text_chunker.py): Implements [TextChunker](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/chunking/text_chunker.py#L49-L309) using Chonkie's `SentenceChunker`. Provides tuned factory methods:
    - `for_postgres()`: 128–256 token target, 16 token overlap.
    - `for_slack()`: 256–400 token target, 32 token overlap.
    - `for_unstructured()`: 400–600 token target, 50 token overlap.
  - [__init__.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/chunking/__init__.py): Exposes [get_chunker(source_type)](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/chunking/__init__.py#L32-L60) routing dynamically to `DocumentChunker` or `TextChunker`.

### 4.4 Retrieval & Vector Engine (`biome_rag/retrieval/`)
- **Purpose & Responsibility:** Manages candidate search, lexical indexing, dense embedding generation, Qdrant integration, score fusion via RRF, cross-encoder reranking, and natural language query routing.
- **Technologies Used:** `FlagEmbedding` (`BAAI/bge-m3`), `qdrant-client`, `sentence-transformers` (`CrossEncoder`), `scikit-learn`, `pickle`.
- **File Breakdown:**
  - [models.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/models.py): Defines [RankedChunk](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/models.py#L8-L23), recording dense score, sparse score, fused score, rerank score, token count, and access scope.
  - [bm25.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/bm25.py): Implements [BM25Index](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/bm25.py#L9-L63). A lightweight, zero-dependency inverted index with term frequency and IDF math ($\ln((1 + N)/(1 + df))$), serialized to `bm25_index.pkl`.
  - [embeddings.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/embeddings.py): Implements [BGE_M3Encoder](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/embeddings.py#L62-L233). Wraps FlagEmbedding's `BGEM3FlagModel` with lazy model initialization, yielding both 1024-dim dense vectors and lexical weight dictionaries from a single forward pass.
  - [dense.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/dense.py): Declares the [DenseEmbeddingAdapter](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/dense.py#L17-L25) interface. Implements [ChromaDenseEmbeddingAdapter](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/dense.py#L45-L119) and [SimpleDenseEmbeddingAdapter](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/dense.py#L27-L43) (token overlap fallback).
  - [qdrant_store.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/qdrant_store.py): Implements [QdrantAdapter](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/qdrant_store.py#L70-L449). Creates collections with dual vector spaces: `dense` (1024-dim Cosine) and `sparse` (Dot product). Uses Qdrant's `Prefetch` API to retrieve candidates from both spaces and executes Reciprocal Rank Fusion inside the Qdrant daemon. Enforces query-time row-level ACL by injecting a `Filter(must=[FieldCondition(key="access_scope", match=MatchAny(any=access_scope))])`.
  - [stores.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/stores.py): Implements [ChunkStore](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/stores.py#L10-L42). Loads processed chunks from `data/processed/chunks.json` into memory, guaranteeing `chunk_index` presence.
  - [engine.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/engine.py): Contains:
    - [reciprocal_rank_fusion()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/engine.py#L20-L41): Implements canonical Cormack et al. (2009) RRF: $\sum \frac{w}{k + \text{rank}}$ with $k=60$.
    - [Reranker](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/engine.py#L44-L104): Cross-encoder scoring using `cross-encoder/ms-marco-MiniLM-L-6-v2` with fallback to token overlap.
    - [HybridRetriever](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/engine.py#L106-L278): Coordinates dense retrieval (via `QdrantAdapter` or ChromaDB) and sparse retrieval (via `BM25Index`), fuses ranks via RRF, and filters/reranks candidate chunks.
  - [router.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/router.py): Implements:
    - [QueryRouter](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/router.py#L54-L110): Classifies queries into `STRUCTURED` (aggregates, counts, breakdowns, groupings, superlatives) versus `SEMANTIC` (policies, procedural steps).
    - [NL2SQLEngine](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/router.py#L116-L482): Sandboxed execution engine enforcing `SELECT`-only execution, rejecting mutation keywords (`INSERT`, `UPDATE`, `DROP`, `TRUNCATE`), forbidding semicolons and comments (`--`, `/*`), enforcing a 5.0s timeout and a 50-row cap.
    - **Programmatic Row-Level ACL Injection** ([apply_acl](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/router.py#L252-L290)): Injects `FROM (SELECT * FROM enterprise_tickets WHERE lower(department) IN ('dept1', ...)) AS enterprise_tickets` into the generated SQL based on `requester_scope`.

### 4.5 Index Orchestration (`biome_rag/indexing/`)
- **Purpose & Responsibility:** Orchestrates the ingestion, chunking, and dual-indexing pipeline into a unified, reproducible execution pass.
- **Technologies Used:** Python standard library, `biome_rag.chunking`, `biome_rag.retrieval`.
- **File Breakdown:**
  - [builder.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/indexing/builder.py): Implements [IndexBuilder](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/indexing/builder.py#L125-L420) and [IndexingResult](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/indexing/builder.py#L67-L120). Sequences:
    1. Phase 1 Ingestion (`DocumentIngester` / `PostgresIngester`) with file-hash deduplication.
    2. Phase 2 Chunking (`DocumentChunker` / `TextChunker`) populating token counts.
    3. Serializing `data/processed/chunks.json`.
    4. Phase 3a BM25 Inverted Index build and save (`data/index/bm25_index.pkl`).
    5. Phase 3b Qdrant dual-vector upsert.

### 4.6 Grounded Generation & Citation Engine (`biome_rag/generation/`)
- **Purpose & Responsibility:** Builds strict prompt contexts, dispatches inference calls to LLM providers, extracts and validates bracketed inline citations (`[1]`), and calculates a composite confidence score.
- **Technologies Used:** `requests`, `urllib`, standard library `math` and `re`.
- **File Breakdown:**
  - [answering.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/generation/answering.py):
    - [Citation](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/generation/answering.py#L22-L26) & [ConfidenceScores](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/generation/answering.py#L29-L34) dataclasses.
    - [AnswerBuilder](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/generation/answering.py#L76-L550): Primary engine. Computes sigmoid-normalized retrieval confidence from rerank scores:
      $$\text{retrieval\_confidence} = \frac{1}{1 + e^{-\text{max\_rerank}}}$$
      If below `insufficient_confidence_threshold` (default `0.5`), it short-circuits to a structured `INSUFFICIENT_CONTEXT` response.
    - [Composite Confidence Formula](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/generation/answering.py#L170):
      $$\text{composite} = 0.5 \cdot \text{retrieval\_confidence} + 0.3 \cdot \text{citation\_coverage} + 0.2 \cdot \text{completeness}$$
    - Provider handlers: [_generate_with_ollama](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/generation/answering.py#L266-L327) (with `_ollama_unreachable` circuit breaker), [_generate_with_openai](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/generation/answering.py#L329-L380), [_generate_with_anthropic](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/generation/answering.py#L382-L432), and [_fallback_generation](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/generation/answering.py#L434-L465) (deterministic sentence extraction).
    - Citation verification: [_verify_citation](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/generation/answering.py#L485-L514) verifies that key terms from the question and claim exist in the cited passage.

### 4.7 Conversational Memory Subsystem (`biome_rag/memory/`)
- **Purpose & Responsibility:** Stores conversational turns across multi-turn user dialogues, enabling stateful context while bounding memory growth.
- **Technologies Used:** `redis` (Redis lists), Python standard library.
- **File Breakdown:**
  - [session.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/memory/session.py): Implements [SessionStore](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/memory/session.py#L52-L84) abstract interface.
    - [RedisSessionStore](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/memory/session.py#L117-L200): Uses Redis key `biome:session:<id>`. Writes turns atomically via pipeline `RPUSH` + `LTRIM -window_size -1`, resetting TTL (`3600s`).
    - [InMemorySessionStore](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/memory/session.py#L89-L112): In-memory Python list fallback for tests and offline development.
    - [get_session_store()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/memory/session.py#L203-L234): Singleton factory testing Redis connectivity with `PING`.

### 4.8 Observability & Distributed Tracing (`biome_rag/observability/`)
- **Purpose & Responsibility:** Provides fine-grained distributed telemetry for every RAG request, tracking retrieval latency, reranking scores, token usage, and output confidence.
- **Technologies Used:** `langfuse`.
- **File Breakdown:**
  - [langfuse_tracer.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/observability/langfuse_tracer.py): Implements [LangfuseTracer](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/observability/langfuse_tracer.py#L162-L260) and [RAGTrace](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/observability/langfuse_tracer.py#L65-L159). Creates named spans for `retrieval`, `reranking`, and `generation`. If Langfuse is disabled or uninstalled, all methods cleanly no-op with zero runtime overhead.

### 4.9 Pipeline Orchestration Flows (`biome_rag/flows/`)
- **Purpose & Responsibility:** Defines production batch workflows and scheduled indexing jobs.
- **Technologies Used:** `prefect` (`@flow`, `@task`, `create_markdown_artifact`).
- **File Breakdown:**
  - [index_flow.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/flows/index_flow.py): Implements [biome_index_pipeline](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/flows/index_flow.py#L318-L380) with 5 distinct tasks: `ingest_documents`, `chunk_documents`, `build_bm25_index`, `upsert_qdrant`, and `notify_completion`. Includes shim decorators so the file runs cleanly even when Prefect is not installed (`run_pipeline_direct()`).

### 4.10 Evaluation, Benchmark & Ablation Harness (`biome_rag/evaluation/`, `eval/`)
- **Purpose & Responsibility:** Measures end-to-end RAG precision, recall, faithfulness, and hallucination against curated ground-truth datasets, and performs Cartesian ablation sweeps.
- **Technologies Used:** `sentence-transformers`, `scikit-learn`, `ragas` (optional), `deepeval` (optional).
- **File Breakdown:**
  - [metrics.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/evaluation/metrics.py): Pure Python lexical baseline metrics: `answer_correctness` (token F1), `faithfulness` (token overlap), `retrieval_relevance` (Recall@k), `citation_accuracy`, `precision_at_k`, and `mean_reciprocal_rank` (MRR).
  - [extended_metrics.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/evaluation/extended_metrics.py): Deterministic proxy metrics: `semantic_similarity` (MiniLM cosine), `context_precision`, `context_recall`, `answer_relevancy`, `noise_robustness`, `hallucination_score` (bigram non-entailment fraction), and [EvalThresholds](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/evaluation/extended_metrics.py#L224-L290).
  - [harness.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/evaluation/harness.py): [EvaluationHarness](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/evaluation/harness.py#L182-L668) runs queries through the pipeline, scores results, verifies quality gates ([check_quality_gate](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/evaluation/harness.py#L380-L409)), and outputs markdown/JSON reports.
  - [report.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/evaluation/report.py): Generates human-readable evaluation summary tables.
  - [eval/ablation_runner.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/eval/ablation_runner.py): Executes an 18-arm Cartesian product sweep over `retrieval_mode` (`dense`, `sparse`, `hybrid`) $\times$ `top_k` ($3, 5, 10$) $\times$ `rerank` (`True`, `False`), ranking configurations by composite score:
    $$\text{Composite} = 0.30 \cdot \text{Corr} + 0.20 \cdot \text{Faith} + 0.15 \cdot \text{CtxP} + 0.10 \cdot \text{CtxR} + 0.10 \cdot \text{AnsRel} + 0.10 \cdot \text{SemSim} - 0.05 \cdot \text{Hall}$$
  - [eval/run_eval.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/eval/run_eval.py): CLI interface for running evaluations against `eval/golden_dataset.json`.

### 4.11 REST API Application Layer (`biome_rag/api/app.py`, `app.py`)
- **Purpose & Responsibility:** Serves HTTP endpoints for query answering, multi-turn chat, side-by-side comparison, document ingestion, upload, and evaluation triggers.
- **Technologies Used:** `FastAPI`, `Starlette`, `Pydantic`, `Uvicorn`.
- **Key Endpoints:**
  - `POST /v1/ask`: Single-turn question answering with query routing, hybrid retrieval, and citation formatting.
  - `POST /v1/chat`: Multi-turn conversational endpoint with Redis-backed history augmenting the prompt context.
  - `DELETE /v1/session/{id}`: Clears chat history for a given session.
  - `POST /v1/compare`: Executes a query through both hybrid and dense-only retrieval, returning comparative answers and citations.
  - `GET /v1/documents`: Lists all indexed documents and chunk counts.
  - `POST /v1/index/files`, `POST /v1/index/upload`, `POST /v1/index/text`: Modern Phase 4 `IndexBuilder` endpoints.
  - `POST /v1/ingest`, `POST /v1/ingest/upload`, `POST /v1/ingest/directory`, `POST /v1/ingest/text`: Legacy `IngestionPipeline` endpoints.
  - `POST /v1/evaluate`: Triggers an `EvaluationHarness` run over server-side or uploaded Q&A records.
  - `GET /v1/health` & `GET /health`: Cluster health check returning chunk count and storage paths.

### 4.12 Modern Web Client (`frontend/`)
- **Purpose & Responsibility:** Single-page web application providing an enterprise marketing landing page, ROI business calculator, interactive neural chat studio, hybrid retrieval arena, and SQL ACL studio.
- **Technologies Used:** React 18, Vite, Tailwind CSS, Lucide React, Axios/Fetch.
- **Key Views:**
  - `LandingPage.jsx`: Dark glassmorphic landing page featuring animated architecture tours and ROI modeler.
  - `ChatView.jsx`: Conversational copilot rendering verified inline citation pills (`[1✓]`), confidence score meters, and SQL query inspector.
  - `CompareView.jsx`: Split-screen comparison arena highlighting hybrid search precision over dense-only retrieval.
  - `SqlView.jsx`: Sandboxed SQL execution studio displaying table results and simulated department ACL scopes.
  - `KnowledgeBaseView.jsx`: Document catalog, drag-and-drop file uploader, and crawler controls.
  - `AblationView.jsx`: Interactive table displaying all 18 ablation arms and performance metrics.

### 4.13 Top-Level Wrapper Packages & Automation Scripts
- **Top-Level Wrappers:** `ingestion/` and `retrieval/` in the repository root are transparent backward-compatibility packages that re-export from `biome_rag.ingestion` and `biome_rag.retrieval`.
- **Automation Scripts:**
  - `scripts/setup_system.py`: One-command bootstrap validating `.env`, seeding PostgreSQL `enterprise_tickets`, running `IndexBuilder`, asserting index sync (error code `E3002`), and running smoke tests.
  - `scripts/seed_index.py`: CLI seeding script reading `data/raw/` and validating BM25 vs ChunkStore synchronization.
  - `seed_db.py`: Database seeder creating 1,000 synthetic enterprise tickets using Faker.
  - `generate_mock_files.py`: Creates synthetic `.docx`, `.pptx`, and `.txt` files in `local_data_bucket/unstructured/`.

---

## 5. Workflows (Step by Step)

### 5.1 Ingestion Workflow
```
[Raw Sources: Files, DB, Slack]
       │
       ▼
1. Source Discovery & Ingest Routing (DocumentIngester / PostgresIngester / SlackIngester)
       │
       ▼
2. Parsing & Normalization
   ├── Docling Path: PDF/DOCX/PPTX/HTML -> DoclingDocument -> Markdown
   ├── Fallback Path: TXT/MD/JSON/CSV -> Native File Loaders
   └── Relational Path: Postgres Rows -> Markdown serialization (_row_to_markdown)
       │
       ▼
3. Deduplication & State Tracking
   ├── Fast Path: SHA-256 hash check against SQLiteStateTracker (data/ingestion_state.db)
   └── Near-Dup Path: TF-IDF Cosine Similarity (>0.95 threshold) via Deduplicator
       │
       ▼
4. Output: DocumentNode List -> Persisted to Silver Layer (data/silver/documents.jsonl)
```

1. **Intake & Discovery:** [IndexBuilder.run()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/indexing/builder.py#L168-L260) or [IngestionPipeline.run_pipeline()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/pipeline.py#L63-L140) discovers files from `data/raw/` or `local_data_bucket/unstructured/`, or queries PostgreSQL.
2. **Parsing:**
   - Files with extensions `.pdf`, `.docx`, `.pptx`, `.html` pass to [DocumentIngester._parse_with_docling()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/document_ingester.py#L248-L279). Docling parses document layout and exports Markdown into `DocumentNode.page_content`. The internal Docling object is attached to `DocumentNode.docling_doc` (unserialized).
   - If Docling fails or the extension is `.txt`, `.md`, `.json`, `.csv`, or code, it routes to [DocumentIngester._parse_with_fallback()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/document_ingester.py#L284-L329) using loaders from `biome_rag/ingestion/loaders.py`.
   - PostgreSQL rows pass through [PostgresIngester._row_to_node()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/postgres_ingester.py#L307-L345), formatting fields as readable Markdown while excluding sensitive fields (`password`, `ssn`, `tax_id`).
3. **ACL Scope Inference:**
   - In [DocumentIngester._infer_access_scope()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/document_ingester.py#L51-L82), filename tokens (`secret`, `confidential`, `salary`, `private`, `public`) set the `access_level` and `access_scope`.
   - In [PostgresIngester._infer_scope_from_row()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/postgres_ingester.py#L64-L75), department and team columns set the row's scope.
4. **Deduplication:**
   - Exact hash deduplication: [SQLiteStateTracker.batch_check_indexed()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/dedup.py#L109-L126) filters out previously indexed SHA-256 hashes.
   - Near-duplicate detection: [Deduplicator.is_duplicate()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/dedup.py#L240-L291) computes TF-IDF cosine similarity against existing chunks; items exceeding `0.95` similarity are dropped.
5. **Silver Layer Emission:** Validated [DocumentNode](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/models.py#L64-L134) objects are serialized to `data/silver/documents.jsonl`.

---

### 5.2 Indexing Workflow
```
[DocumentNode List]
       │
       ▼
1. Source-Specific Chunking
   ├── DocumentChunker (Docling HybridChunker + Table Row-Splitter)
   └── TextChunker (Chonkie SentenceChunker, 128-400 token targets)
       │
       ▼
2. Chunk Persistence
   └── Serialized to data/processed/chunks.json
       │
       ├────────────────────────────────┐
       ▼                                ▼
3a. Lexical Indexing            3b. Dense & Sparse Dual-Encoding
    BM25 Inverted Index             BGE-M3 Dual Encoder (1024-dim dense + lexical weights)
    Saved to bm25_index.pkl         Upserted to Qdrant (enterprise_kb collection)
       │                                │
       └────────────────┬───────────────┘
                        ▼
4. Synchronization Assertion (E3002 Check)
```

1. **Chunking Dispatch:** [IndexBuilder._phase2_chunk()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/indexing/builder.py#L295-L330) routes nodes to:
   - [DocumentChunker](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/chunking/document_chunker.py#L106-L200) for files. Runs Docling's `HybridChunker` (400–600 tokens). If an output chunk contains a Markdown table exceeding 600 tokens, [_split_markdown_table_by_rows()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/chunking/document_chunker.py#L51-L99) splits the table into sub-tables, repeating the header row in each sub-chunk.
   - [TextChunker](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/chunking/text_chunker.py#L49-L200) for PostgreSQL (128–256 tokens) and Slack (256–400 tokens) using Chonkie sentence boundaries.
2. **Chunk Storage:** Chunks are written to `data/processed/chunks.json` for consumption by `ChunkStore`.
3. **Lexical Indexing:** [BM25Index.build()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/bm25.py#L17-L29) tokenizes all chunk texts, builds an inverted index map (`{token: {doc_id: count}}`), computes document frequencies, and pickles the dictionary to `data/index/bm25_index.pkl`.
4. **Dual Vector Upsert:** [QdrantAdapter.index_documents()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/qdrant_store.py#L160-L245) encodes chunks in batches via [BGE_M3Encoder.encode_corpus()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/embeddings.py#L140-L195), producing 1024-dim dense float32 vectors and sparse lexical weight maps. Points are upserted into Qdrant collection `enterprise_kb` with payload metadata (`source`, `chunk_index`, `access_scope`).
5. **Sync Assertion (E3002):** [scripts/seed_index.py -> validate_only()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/scripts/seed_index.py#L33-L58) verifies that the number of chunks in `chunks.json` exactly matches the document count in `bm25_index.pkl`. If mismatched, it throws error code `E3002`.

---

### 5.3 Query / Retrieval Workflow
```
[User Query: "How do I reset my VPN password?"]
       │
       ▼
1. Query Classification (QueryRouter.classify())
   ├── STRUCTURED -> Divert to NL2SQLEngine (Section 5.5)
   └── SEMANTIC   -> Proceed to Hybrid Retrieval
       │
       ▼
2. Dual Candidate Retrieval (top-20 candidates each)
   ├── Dense Retrieval: BGE-M3 Dense Query Vector -> Qdrant Prefetch / Cosine
   └── Sparse Retrieval: BM25 Term Match -> BM25Index.search()
       │
       ▼
3. Reciprocal Rank Fusion (RRF, k=60)
   Formula: score(d) = 0.7 * (1 / (60 + dense_rank)) + 0.3 * (1 / (60 + sparse_rank))
       │
       ▼
4. Cross-Encoder Reranking
   Candidates (top-20) -> ms-marco-MiniLM-L-6-v2 -> Re-scored top-5 candidates
```

1. **Routing:** Incoming questions hitting `POST /v1/ask` pass through [QueryRouter.classify()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/router.py#L90-L110). If the query matches aggregate/count patterns, it diverts to the NL2SQL engine. Otherwise, it proceeds as a semantic query.
2. **Dense Retrieval:** [QdrantAdapter.search()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/qdrant_store.py#L250-L380) encodes the query with BGE-M3 and issues a prefetch query against Qdrant. If `access_scope` is provided, Qdrant applies a boolean payload match filter before ranking.
3. **Sparse Retrieval:** [BM25Index.search()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/bm25.py#L44-L57) tokenizes the query, scores matching documents using BM25 IDF weights, and returns top candidates.
4. **Fusion:** [reciprocal_rank_fusion()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/engine.py#L20-L41) merges dense and sparse ranked lists using weights `dense_weight=0.7`, `sparse_weight=0.3`, and smoothing constant $k=60$.
5. **Reranking:** The top-20 fused candidates pass to [Reranker.rerank()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/engine.py#L54-L104). The cross-encoder evaluates `(query, passage)` pairs via cross-attention, returning a re-sorted list of [RankedChunk](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/models.py#L8-L23) objects.

---

### 5.4 Generation Workflow
```
[Top-5 Reranked Chunks]
       │
       ▼
1. Retrieval Confidence Calculation
   Formula: confidence = 1 / (1 + exp(-max_rerank_score))
   ├── IF confidence < 0.5 -> Short-circuit with INSUFFICIENT_CONTEXT
   └── ELSE -> Build Context Window
       │
       ▼
2. Context Assembly
   Select chunks within max_context_chunks (5) and max_context_tokens (1500)
   Format: [1] (Source: ...)\nChunk text...
       │
       ▼
3. LLM Generation
   Dispatch to Ollama (llama3.1:8b) / OpenAI / Anthropic / Groq
   System prompt enforces: "Cite sources inline using [n]. If insufficient, state INSUFFICIENT_CONTEXT."
       │
       ▼
4. Citation Parsing & Verification
   Extract [n] tags -> Verify claim tokens against cited chunk text
       │
       ▼
5. Composite Confidence Scoring
   Formula: 0.5 * retrieval_conf + 0.3 * citation_coverage + 0.2 * completeness
       │
       ▼
6. Output: AnswerResponse with verified citations, confidence breakdown, and trace ID
```

1. **Confidence Gating:** [AnswerBuilder.answer()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/generation/answering.py#L92-L182) computes retrieval confidence via a sigmoid over the maximum rerank score. If confidence is below `0.5`, it returns `INSUFFICIENT_CONTEXT` immediately, preventing hallucinations.
2. **Context Assembly:** [_build_context_window()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/generation/answering.py#L191-L218) enforces caps of 5 chunks and 1500 tokens. Excess text in the final chunk is truncated at sentence boundaries. Chunks are formatted as:
   ```
   [1] (Source: deployment-guide.md — Overview)
   Passage text...
   ```
3. **Prompt Dispatch:** [AnswerBuilder._generate()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/generation/answering.py#L224-L235) invokes the configured provider with temperature `0.0`. If Ollama is unreachable, the `_ollama_unreachable` circuit breaker immediately switches to local sentence extraction fallback.
4. **Citation Parsing:** [_parse_citations()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/generation/answering.py#L54-L73) extracts all `[n]` bracket markers using regular expressions and matches them to context chunks.
5. **Verification:** [_verify_citation()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/generation/answering.py#L485-L514) checks that words in the sentence containing `[n]` are present in chunk $n$.
6. **Composite Scoring:** Computes the weighted confidence score and returns an [AnswerResponse](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/generation/answering.py#L37-L42).

---

### 5.5 Secondary Flows: Session Chat, Observability, NL2SQL, Evaluation, and Orchestration

#### Multi-Turn Chat Flow (`POST /v1/chat`)
1. User supplies `session_id` and `message`.
2. [RedisSessionStore.get_history()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/memory/session.py#L162-L178) fetches the last 6 turns (3 exchanges).
3. The query is augmented by prepending historical dialogue.
4. Generation executes, and the new exchange is written via [RedisSessionStore.append()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/memory/session.py#L137-L160) using Redis `RPUSH` + `LTRIM` with a 3600-second TTL.

#### Distributed Tracing Flow
1. [LangfuseTracer.trace()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/observability/langfuse_tracer.py#L197-L235) opens a context manager generating a `trace_id`.
2. As retrieval, reranking, and generation finish, spans are logged: `span_retrieval()`, `span_reranking()`, and `span_generation()`.
3. The `trace_id` is included in the API response and linked in the frontend UI.

#### Sandboxed NL2SQL Execution Flow
1. [QueryRouter.classify()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/router.py#L90-L110) tags a query as `RouteDecision.STRUCTURED`.
2. [NL2SQLEngine.generate_sql()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/router.py#L296-L390) synthesizes a read-only `SELECT` query.
3. [NL2SQLEngine.validate_sql()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/router.py#L199-L246) asserts:
   - Starts with `SELECT` or `WITH`.
   - Contains no mutation keywords (`INSERT`, `UPDATE`, `DROP`, `ALTER`, etc.).
   - Contains no semicolons or comments (`--`, `/*`).
   - Caps row output with `LIMIT 50`.
4. [NL2SQLEngine.apply_acl()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/router.py#L252-L290) injects the user's `requester_scope` as a subquery filter:
   `FROM (SELECT * FROM enterprise_tickets WHERE lower(department) IN ('logistics', ...)) AS enterprise_tickets`.
5. SQLAlchemy executes the query within a 5-second timeout, formatting results into Markdown tables with citations.

#### Offline Evaluation Flow (`POST /v1/evaluate` & `eval/run_eval.py`)
1. [EvaluationHarness.run()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/evaluation/harness.py#L236-L350) iterates over `eval/golden_dataset.json`.
2. For each question, it calls `retriever.retrieve()` and `answer_builder.answer()`.
3. Metrics are evaluated: lexical F1, faithfulness, MRR, P@5, semantic similarity, context precision, context recall, and hallucination score.
4. [EvaluationHarness.check_quality_gate()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/evaluation/harness.py#L380-L409) checks scores against [EvalThresholds](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/evaluation/extended_metrics.py#L224-L290). Reports are written to `eval/reports/`.

---

## 6. Data Flow & Persistence

### 6.1 Overall System Architecture Diagram

```mermaid
graph TB
    subgraph ClientLayer ["Client & Interface Layer"]
        WebClient["React 18 + Vite Frontend<br/>(Port 5173 / Glassmorphic UI)"]
        CLIClient["CLI / Direct Python Scripts<br/>(scripts/setup_system.py)"]
    end

    subgraph APILayer ["FastAPI Gateway (Port 8000)"]
        App["biome_rag/api/app.py"]
        Router["QueryRouter<br/>(SEMANTIC vs STRUCTURED)"]
    end

    subgraph RelationalPath ["Structured Relational Path (Phase 8)"]
        SQLEngine["NL2SQLEngine<br/>(Sandboxed SELECT Guard)"]
        ACLGuard["Programmatic Row-Level ACL<br/>(Scope Filter Injection)"]
        PostgresDB[(PostgreSQL 16<br/>enterprise_tickets)]
    end

    subgraph HybridRAGPath ["Hybrid RAG Pipeline (Phases 1-5)"]
        Retriever["HybridRetriever"]
        BGEEncoder["BGE-M3 Dual-Encoder<br/>(FlagEmbedding)"]
        QdrantDB[(Qdrant Vector DB<br/>Dense + Sparse + Prefetch)]
        BM25[(BM25 Inverted Index<br/>bm25_index.pkl)]
        RRF["Reciprocal Rank Fusion<br/>(k=60, 0.7 Dense / 0.3 Sparse)"]
        Reranker["Cross-Encoder Reranker<br/>(ms-marco-MiniLM-L-6-v2)"]
        AnswerBuilder["AnswerBuilder<br/>(Prompting & Citation Verifier)"]
    end

    subgraph Infrastructure ["State, Memory & Observability"]
        Redis[(Redis 7<br/>Session Memory)]
        Langfuse[Langfuse Observability<br/>Distributed Traces]
        OllamaLocal[Ollama Daemon<br/>llama3.1:8b]
        CloudLLM[OpenAI / Anthropic / Groq]
    end

    WebClient -->|HTTP REST| App
    CLIClient -->|Internal Import| App
    App --> Router

    Router -->|STRUCTURED| SQLEngine
    SQLEngine --> ACLGuard
    ACLGuard --> PostgresDB
    PostgresDB -->|Tabular Result Set| SQLEngine
    SQLEngine -->|Formatted Markdown Table| App

    Router -->|SEMANTIC| Retriever
    Retriever --> BGEEncoder
    BGEEncoder --> QdrantDB
    Retriever --> BM25
    QdrantDB -->|Dense Top-20| RRF
    BM25 -->|Sparse Top-20| RRF
    RRF -->|Top-20 Fused Candidates| Reranker
    Reranker -->|Top-5 Reranked Chunks| AnswerBuilder
    AnswerBuilder --> OllamaLocal
    AnswerBuilder -.->|Fallback / Cloud| CloudLLM
    AnswerBuilder -->|Cited Answer & Confidence| App

    App <-->|Session History RPUSH/LTRIM| Redis
    App -.->|Request Spans & Traces| Langfuse
```

### 6.2 Ingestion & Indexing Pipeline Diagram

```mermaid
graph LR
    subgraph DataSources ["Data Sources"]
        Files["Local Files (data/raw)<br/>PDF, DOCX, PPTX, HTML, TXT"]
        PG["PostgreSQL Database<br/>enterprise_tickets rows"]
        Slack["Slack Channels<br/>(Thread Stub)"]
    end

    subgraph IngestionStage ["Ingestion & Normalization (Phase 1)"]
        DocIngester["DocumentIngester<br/>IBM Docling + Fallback"]
        PGIngester["PostgresIngester<br/>SQLAlchemy + Hash Check"]
        DedupTracker["SQLiteStateTracker<br/>(data/ingestion_state.db)"]
        Silver["Silver Layer JSONL<br/>(data/silver/documents.jsonl)"]
    end

    subgraph ChunkingStage ["Layout-Aware Chunking (Phase 2)"]
        DocChunker["DocumentChunker<br/>HybridChunker + Table Row Split"]
        TextChunker["TextChunker<br/>Chonkie SentenceChunker"]
        ChunksJSON[("data/processed/chunks.json")]
    end

    subgraph IndexingStage ["Indexing & Storage (Phase 3)"]
        BM25Build["BM25 Index Builder"]
        BM25File[("data/index/bm25_index.pkl")]
        BGEM3["BGE-M3 Dual Encoder"]
        QdrantStore[("Qdrant Collection<br/>enterprise_kb")]
    end

    Files --> DocIngester
    PG --> PGIngester
    Slack --> DocIngester
    DocIngester --> DedupTracker
    PGIngester --> DedupTracker
    DedupTracker -->|Unique DocumentNodes| Silver

    Silver -->|Document Nodes| DocChunker
    Silver -->|Postgres / Text Nodes| TextChunker
    DocChunker --> ChunksJSON
    TextChunker --> ChunksJSON

    ChunksJSON --> BM25Build
    BM25Build --> BM25File
    ChunksJSON --> BGEM3
    BGEM3 --> QdrantStore
```

### 6.3 Query-Time Decision & Execution Flow Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Client
    participant API as FastAPI Gateway (/v1/ask or /v1/chat)
    participant Tracer as LangfuseTracer
    participant Memory as RedisSessionStore
    participant Router as QueryRouter
    participant SQL as NL2SQLEngine
    participant Ret as HybridRetriever
    participant Rerank as CrossEncoder
    participant LLM as AnswerBuilder / LLM

    User->>API: POST query (session_id, scope, route_override)
    API->>Tracer: Start trace context (trace_id)
    opt If session_id present
        API->>Memory: get_history(session_id)
        Memory-->>API: Return recent turns
    end

    API->>Router: classify(query)
    
    alt RouteDecision.STRUCTURED (Aggregates, Counts, Group By)
        Router-->>API: STRUCTURED
        API->>SQL: execute(query, requester_scope)
        SQL->>SQL: validate_sql() [SELECT only, no comments/semicolons]
        SQL->>SQL: apply_acl() [Inject department IN (...)]
        SQL->>SQL: Execute query on PostgreSQL (timeout=5s)
        SQL-->>API: Markdown table answer + SQL citation
    else RouteDecision.SEMANTIC (Policies, How-To, Guides)
        Router-->>API: SEMANTIC
        API->>Ret: retrieve(query, access_scope, mode="hybrid")
        par Dense & Sparse Search
            Ret->>Ret: Qdrant search (BGE-M3 Dense + ACL filter)
        and
            Ret->>Ret: BM25Index search (Keyword match)
        end
        Ret->>Ret: reciprocal_rank_fusion(dense, sparse, k=60)
        Ret->>Rerank: rerank(query, top_20_candidates)
        Rerank-->>Ret: Top-5 re-scored RankedChunks
        Ret-->>API: Return RankedChunks

        API->>LLM: answer(query, top_5_chunks)
        LLM->>LLM: Check sigmoid confidence threshold (>= 0.5)
        LLM->>LLM: Dispatch to Ollama / OpenAI (temperature=0.0)
        LLM->>LLM: Parse [n] citations and verify claim tokens
        LLM-->>API: AnswerResponse (answer, citations, confidence)
    end

    opt If session_id present
        API->>Memory: append(user_msg, assistant_ans)
    end
    API->>Tracer: Close trace & record metrics
    API-->>User: JSON response (answer, citations, confidence, trace_id, route)
```

### 6.4 Stage Data Transformations Matrix

| Stage | Input Data Format | Output Data Format | File & Transformation Logic |
|---|---|---|---|
| **Phase 1 Ingestion (Files)** | Raw binary file on disk (`.pdf`, `.docx`, `.pptx`, `.html`) | `DocumentNode` with `page_content: str` (Markdown), `metadata: DocumentMetadata`, `docling_doc` | `biome_rag/ingestion/document_ingester.py -> DocumentIngester._parse_with_docling()` |
| **Phase 1 Ingestion (DB)** | Relational table rows (`dict[str, Any]` via SQLAlchemy) | `DocumentNode` with formatted natural-language Markdown rows | `biome_rag/ingestion/postgres_ingester.py -> PostgresIngester._row_to_node()` |
| **Phase 1 Deduplication** | Candidate `DocumentNode` objects | Filtered subset of `DocumentNode` objects + updated SQLite ledger | `biome_rag/ingestion/dedup.py -> SQLiteStateTracker.batch_check_indexed()` |
| **Phase 2 Chunking (Docs)** | `DocumentNode` (with `docling_doc`) | List of `Chunk` objects (`token_count: int`, `text: str`, `chunk_index: int`) | `biome_rag/chunking/document_chunker.py -> DocumentChunker.chunk()` |
| **Phase 2 Chunking (Tables)** | Markdown table chunk exceeding 600 tokens | List of `Chunk` objects, each with repeated header rows | `biome_rag/chunking/document_chunker.py -> _split_markdown_table_by_rows()` |
| **Phase 2 Chunking (DB/Text)**| `DocumentNode` (plain text) | List of `Chunk` objects budgeted to 128–256 tokens | `biome_rag/chunking/text_chunker.py -> TextChunker.chunk()` |
| **Phase 3a Lexical Index** | List of chunk strings (`list[str]`) | Inverted index `{token: {doc_id: freq}}` and document frequencies | `biome_rag/retrieval/bm25.py -> BM25Index.build()` |
| **Phase 3b Dense Encoding** | List of chunk strings (`list[str]`) | Dense array `float32[N, 1024]` + sparse dicts `list[dict[str, float]]` | `biome_rag/retrieval/embeddings.py -> BGE_M3Encoder.encode_corpus()` |
| **Phase 3b Qdrant Upsert** | Vectors + Chunks | Stored Qdrant points with dual vector names `dense` and `sparse` | `biome_rag/retrieval/qdrant_store.py -> QdrantAdapter.index_documents()` |
| **Phase 4 Fusion & Rerank** | Top-20 dense IDs + Top-20 sparse IDs | Top-5 `RankedChunk` objects with rerank scores | `biome_rag/retrieval/engine.py -> HybridRetriever.retrieve()` |
| **Phase 5 Generation** | Question string + Top-5 `RankedChunk` objects | `AnswerResponse` with parsed `Citation` list and composite confidence | `biome_rag/generation/answering.py -> AnswerBuilder.answer()` |
| **Phase 8 NL2SQL** | Natural language aggregate question string | SQL query string + tabular rows + cited Markdown table answer | `biome_rag/retrieval/router.py -> NL2SQLEngine.execute()` |

### 6.5 Persistence Layer Architecture

| Store / Artifact | Format / Engine | File Path / Port | Lifespan & Update Strategy | Schema / Structure |
|---|---|---|---|---|
| **Deduplication State** | SQLite 3 (WAL mode) | `data/ingestion_state.db` | Persistent across runs; append-only | Table `ingestion_state (content_hash PRIMARY KEY, source_type, source_name, primary_key, indexed_at, metadata)` |
| **Incremental Watermarks**| SQLite 3 (WAL mode) | `data/ingestion_state.db` | Persistent across runs; upsert on success | Table `watermarks (source_type PRIMARY KEY, last_run_at, metadata)` |
| **Silver Document Store** | JSON Lines (`.jsonl`) | `data/silver/documents.jsonl` | Persistent intermediate cache; append-only | One JSON-serialized `DocumentNode` per line |
| **Processed Chunk Store** | JSON (`.json`) | `data/processed/chunks.json` | Overwritten or refreshed on index build | Top-level object `{"chunks": [...]}` holding serialised chunk attributes |
| **BM25 Lexical Store** | Python Pickle (`.pkl`) | `data/index/bm25_index.pkl` | Overwritten on index build | Dict `{"documents": list[str], "index": dict, "doc_freq": dict}` |
| **Vector Store (Primary)**| Qdrant DB | TCP 6333 / 6334 (`qdrant_data` volume)| Persistent daemon storage | Collection `enterprise_kb` with `dense` (1024-dim, Cosine) and `sparse` vectors |
| **Vector Store (Fallback)**| ChromaDB / Parquet | `data/index/chroma/` | Persistent local directory | Collection `enterprise_kb` |
| **Relational DB** | PostgreSQL 16 | TCP 5432 | Persistent production DB | Table `enterprise_tickets (ticket_id PK, department, route_or_system, issue_summary, detailed_description, created_at, priority_level, resolved)` |
| **Session Chat Memory** | Redis 7 | TCP 6379 | In-memory with append-only persistence; TTL 3600s | Redis lists keyed by `biome:session:<uuid>` containing JSON message turn dicts |
| **Observability DB** | PostgreSQL 16 | Internal port 5432 (container only) | Persistent telemetry ledger | Langfuse application data, trace logs, span events, latency metrics |

---

## 7. Configuration & Environment

Configuration is managed centrally in [biome_rag/config.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/config.py) using `pydantic-settings.BaseSettings`. Configuration values are loaded with the following precedence:
1. Active environment variables (highest priority).
2. `.env` file located in the project root directory.
3. Default values declared in `Settings`.

### Environment Variable Inventory

| Environment Variable | Type | Default Value | Description & Impact on Behavior |
|---|---|---|---|
| `LOG_LEVEL` | string | `INFO` | Root logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `LLM_PROVIDER` | string | `local` | Primary generation engine: `local`, `ollama`, `openai`, `anthropic`, `groq`. |
| `OLLAMA_MODEL` | string | `llama3.1:8b` | Model identifier passed to local Ollama server. |
| `OLLAMA_BASE_URL` | string | `http://localhost:11434` | Base HTTP endpoint for Ollama REST API. |
| `OLLAMA_TIMEOUT` | int | `60` | HTTP request timeout in seconds for Ollama generation. |
| `OPENAI_API_KEY` | string | `""` | API key for OpenAI endpoints (used when `LLM_PROVIDER=openai`). |
| `OPENAI_MODEL` | string | `gpt-4o-mini` | OpenAI model ID used for generation. |
| `ANTHROPIC_API_KEY` | string | `""` | API key for Anthropic Claude endpoints. |
| `ANTHROPIC_MODEL` | string | `claude-sonnet-4-5` | Model ID for Anthropic Claude inference. |
| `GROQ_API_KEY` | string | `""` | API key for fast cloud inference via Groq. |
| `GROQ_MODEL` | string | `llama-3.1-8b-instant`| Model ID for Groq inference. |
| `EMBEDDING_PROVIDER` | string | `sentence-transformers` | Embedding engine: `sentence-transformers` or `openai`. |
| `EMBEDDING_MODEL_NAME` | string | `BAAI/bge-m3` | Hugging Face model identifier for dense/sparse dual encoding. |
| `EMBEDDING_COLLECTION_NAME`| string | `enterprise_kb` | Primary collection name in vector database. |
| `EMBEDDING_DEVICE` | string | `cpu` | PyTorch execution device (`cpu`, `cuda`, `mps`). |
| `QDRANT_HOST` | string | `localhost` | Hostname for Qdrant vector database server. |
| `QDRANT_PORT` | int | `6333` | REST port for Qdrant service. |
| `QDRANT_URL` | string | `http://localhost:6333` | Full HTTP URL for Qdrant connection. |
| `QDRANT_COLLECTION` | string | `enterprise_kb` | Collection name inside Qdrant. |
| `QDRANT_API_KEY` | string | `""` | Optional authentication key for managed Qdrant Cloud. |
| `POSTGRES_URI` | string | `postgresql://localhost:5432/enterprise_rag` | Full SQLAlchemy URI for relational ticket storage. |
| `POSTGRES_TABLE` | string | `enterprise_tickets` | Primary relational table for tickets and NL2SQL analytics. |
| `REDIS_URL` | string | `redis://localhost:6379/0` | Connection URI for Redis session memory. |
| `REDIS_SESSION_TTL` | int | `3600` | Inactivity time-to-live in seconds for chat sessions. |
| `REDIS_WINDOW_SIZE` | int | `10` | Maximum number of turns stored in the sliding window. |
| `SLACK_BOT_TOKEN` | string | `""` | Slack Bot OAuth token (`xoxb-...`) for channel history reading. |
| `SLACK_APP_TOKEN` | string | `""` | Slack App-level token (`xapp-...`). |
| `SLACK_WORKSPACE_ID` | string | `""` | Target Slack workspace / team ID. |
| `LANGFUSE_PUBLIC_KEY` | string | `""` | Public API key for Langfuse tracing. |
| `LANGFUSE_SECRET_KEY` | string | `""` | Secret key for Langfuse tracing. |
| `LANGFUSE_HOST` | string | `http://localhost:3000` | Endpoint for Langfuse server dashboard and API. |
| `LANGFUSE_ENABLED` | bool | `False` | Feature flag toggling Langfuse tracing on or off. |
| `CHUNK_SIZE` | int | `800` | Legacy character chunk size. |
| `CHUNK_OVERLAP` | int | `120` | Legacy character chunk overlap. |
| `DEDUP_THRESHOLD` | float | `0.95` | TF-IDF cosine similarity threshold for near-duplicate rejection. |
| `PDF_CHUNK_MAX_TOKENS` | int | `600` | Maximum token budget for document chunks. |
| `PDF_CHUNK_MIN_TOKENS` | int | `400` | Minimum token budget for document chunks. |
| `SLACK_CHUNK_MAX_TOKENS` | int | `400` | Maximum token budget for Slack thread chunks. |
| `SLACK_CHUNK_MIN_TOKENS` | int | `256` | Minimum token budget for Slack thread chunks. |
| `PG_CHUNK_MAX_TOKENS` | int | `256` | Maximum token budget for PostgreSQL row chunks. |
| `PG_CHUNK_MIN_TOKENS` | int | `128` | Minimum token budget for PostgreSQL row chunks. |
| `TABLE_SPLIT_MAX_TOKENS`| int | `600` | Maximum token limit before triggering table row splitting. |
| `DENSE_TOP_K` | int | `5` | Candidate depth fetched from vector store per query. |
| `RRF_DENSE_WEIGHT` | float | `0.7` | Weight assigned to dense vector ranks in RRF fusion. |
| `RRF_SPARSE_WEIGHT` | float | `0.3` | Weight assigned to sparse BM25 ranks in RRF fusion. |
| `RRF_K` | int | `60` | Canonical Cormack smoothing constant for RRF. |
| `MAX_CONTEXT_CHUNKS` | int | `5` | Maximum number of chunks injected into the prompt. |
| `MAX_CONTEXT_TOKENS` | int | `1500` | Hard cap on total context tokens injected into prompt. |
| `FALLBACK_KEYWORD_THRESHOLD` | float | `0.5` | Threshold for keyword fallback scoring. |
| `CITATION_VERIFICATION_ENABLED`| bool| `True` | Toggles claim token verification for inline citations. |
| `INSUFFICIENT_CONFIDENCE_THRESHOLD`| float | `0.5` | Minimum retrieval confidence required before returning an answer. |
| `SENSITIVE_FIELDS` | string | `salary,ssn,tax_id,password,secret` | Comma-separated list of columns redacted during DB ingestion. |
| `NL2SQL_ENABLED` | bool | `True` | Feature flag enabling NL2SQL query routing and execution. |
| `NL2SQL_TIMEOUT_SECONDS`| float | `5.0` | Maximum execution time in seconds for generated SQL queries. |
| `NL2SQL_MAX_ROWS` | int | `50` | Maximum rows returned by generated SQL queries (`LIMIT 50`). |
| `RETRY_ATTEMPTS` | int | `2` | Number of retries for failed network and LLM HTTP calls. |

---

## 8. Entry Points & Operational Runbook

### Primary System Entry Points

1. **FastAPI Application Gateway:**
   - Entry file: [app.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/app.py) or `biome_rag/api/app.py`.
   - Command: `uvicorn biome_rag.api.app:app --host 0.0.0.0 --port 8000 --reload`
2. **React + Vite Frontend Development Server:**
   - Entry directory: `frontend/`
   - Command: `npm run dev` (Runs on `http://localhost:5173`).
3. **Automated System Setup & Bootstrap Script:**
   - Entry file: [scripts/setup_system.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/scripts/setup_system.py)
   - Command: `python scripts/setup_system.py`
4. **Index Seeder & Validation CLI:**
   - Entry file: [scripts/seed_index.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/scripts/seed_index.py)
   - Command: `python scripts/seed_index.py --validate-only`
5. **Standalone Database Seeder:**
   - Entry file: [seed_db.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/seed_db.py)
   - Command: `python seed_db.py`
6. **Ablation Sweep Runner:**
   - Entry file: [eval/ablation_runner.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/eval/ablation_runner.py)
   - Command: `python eval/ablation_runner.py --golden eval/golden_dataset.json`
7. **Offline Evaluation Runner:**
   - Entry file: [eval/run_eval.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/eval/run_eval.py)
   - Command: `python eval/run_eval.py --retrieval-mode hybrid --threshold strict`
8. **Scheduled Prefect Orchestration Flow:**
   - Entry file: [biome_rag/flows/index_flow.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/flows/index_flow.py)
   - Command: `python -m biome_rag.flows.index_flow`

### Step-by-Step Setup Runbook

#### Step 1: Clone and Environment Setup
```bash
git clone https://github.com/adityasingh0405/Biome.git
cd Biome

# Create virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
```

#### Step 2: Start Supporting Infrastructure
```bash
# Start Qdrant, Redis, Ollama, Langfuse, and PostgreSQL
docker compose up -d qdrant redis ollama langfuse-db langfuse

# Pull the default local LLM inside the Ollama container
docker exec -it biome-ollama ollama pull llama3.1:8b
```

#### Step 3: Run Automated Bootstrap & Index Seeding
```bash
python scripts/setup_system.py
```
*What this does:*
- Checks and verifies `.env`.
- Initializes directory structures (`data/raw`, `data/processed`, `data/index`).
- Connects to PostgreSQL and seeds sample tickets.
- Parses raw documents using Docling and fallback loaders.
- Chunks text with token budgets and writes `data/processed/chunks.json`.
- Builds the BM25 inverted index (`data/index/bm25_index.pkl`) and upserts BGE-M3 vectors into Qdrant.
- Asserts index synchronization (validating chunk counts across stores).

#### Step 4: Launch Web Servers
```bash
# Terminal 1: FastAPI Gateway
uvicorn biome_rag.api.app:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: React Frontend
cd frontend
npm install
npm run dev
```

---

## 9. External Dependencies & Failure Modes

| External Service / Dependency | Location Called | Purpose | Failure Mode & System Behavior |
|---|---|---|---|
| **Qdrant Vector DB** (`:6333`) | `biome_rag/retrieval/qdrant_store.py` | Dense vector search and native RRF fusion | **Graceful Degradation:** Falls back to `ChromaDenseEmbeddingAdapter`. If ChromaDB is also unavailable, degrades to `SimpleDenseEmbeddingAdapter` (token overlap). |
| **Redis Cache** (`:6379`) | `biome_rag/memory/session.py` | Sliding-window conversational chat memory | **Graceful Degradation:** Catches connection error and falls back to `InMemorySessionStore`. Multi-turn chat continues in-process (lost on server restart). |
| **PostgreSQL Database** (`:5432`) | `biome_rag/ingestion/postgres_ingester.py`, `biome_rag/retrieval/router.py` | Ingestion of enterprise tickets and NL2SQL execution | **Partial Failure:** Ingestion skips DB and logs an error. `NL2SQLEngine` falls back to an in-memory SQLite schema; queries executing against real DB rows return an error. |
| **Ollama Local Daemon** (`:11434`)| `biome_rag/generation/answering.py` | Local grounded answer generation | **Circuit Breaker:** On connection failure/timeout, sets `_ollama_unreachable = True` and falls back to deterministic extractive sentence generation. |
| **OpenAI / Anthropic APIs** | `biome_rag/generation/answering.py` | Cloud LLM generation | **Graceful Degradation:** If cloud API returns 4xx/5xx or invalid API key, falls back to deterministic extractive sentence generation. |
| **Langfuse Server** (`:3000`) | `biome_rag/observability/langfuse_tracer.py` | Request telemetry and distributed tracing | **Clean No-Op:** If Langfuse server is offline or `LANGFUSE_ENABLED=false`, span calls silently no-op with zero performance penalty. |
| **Slack Web API** | `biome_rag/ingestion/slack_ingester.py` | Ingesting channel message history | **Stub:** Returns an empty `IngestResult` with warning log. Pipeline execution does not break. |
| **Hugging Face Hub** | `biome_rag/retrieval/embeddings.py`, `biome_rag/retrieval/engine.py` | Initial model download for BGE-M3 and cross-encoder | **Model Cache:** Downloads once on first run. If offline without cache, falls back to token overlap adapters. |

---

## 10. Prompts & Model Usage

### Prompts Inventory

#### 1. RAG Answering System Prompt
- **File & Function:** [biome_rag/generation/answering.py -> AnswerBuilder._system_prompt()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/generation/answering.py#L240-L252)
- **Intent:** Establishes a strict, factual persona that answers questions using *only* numbered context blocks and explicitly outputs citation markers (`[n]`), forbidding hallucination.
- **Exact Text:**
  ```text
  You are a precise, factual question-answering assistant. Your task is to answer the user's question using ONLY the numbered context blocks provided below.

  Rules you must follow:
  1. Cite sources inline using the block number in square brackets, e.g. [1] or [2][3].
  2. If the context blocks contain the answer, explain it clearly and concisely with citations.
  3. If the context does NOT contain sufficient information to answer, reply with exactly: "INSUFFICIENT_CONTEXT: I don't know. The provided context does not contain this information."
  4. Never fabricate information. Never use knowledge outside the provided context.
  5. Multiple citations are allowed for a single claim, e.g. [1][3].
  ```

#### 2. RAG User Prompt Template
- **File & Function:** [biome_rag/generation/answering.py -> AnswerBuilder._user_prompt()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/generation/answering.py#L254-L260)
- **Intent:** Injects the formatted numbered context blocks alongside the user question.
- **Template:**
  ```text
  Context blocks:

  {context}

  Question: {question}

  Answer (with inline [n] citations):
  ```

#### 3. Conversational Chat History Augmentation
- **File & Function:** [biome_rag/api/app.py -> chat()](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/api/app.py#L310-L352)
- **Intent:** Formats recent conversational history into the question context for multi-turn coherence.
- **Template:**
  ```text
  USER: {prior_user_message}
  ASSISTANT: {prior_assistant_answer}

  CURRENT QUESTION: {current_message}
  ```

### Models & Key Parameters

| Step | Model Name | Provider | Key Parameters |
|---|---|---|---|
| **Dense Embeddings** | `BAAI/bge-m3` | Hugging Face / FlagEmbedding | `dim=1024`, `max_length=8192`, `use_fp16=True`, `device=cpu/cuda` |
| **Sparse Embeddings** | `BAAI/bge-m3` (Lexical Weights) | FlagEmbedding | Returns `{token_id: weight}` dot-product dictionary |
| **Reranking** | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Sentence-Transformers | Parameters: 22M, `device=cpu`, Input: `(query, passage)` pairs |
| **Local Generation** | `llama3.1:8b` | Ollama | `temperature=0.0`, `stream=False`, `timeout=60s` |
| **Cloud Generation (OpenAI)** | `gpt-4o-mini` | OpenAI API | `temperature=0.0`, `max_tokens=500` |
| **Cloud Generation (Anthropic)** | `claude-sonnet-4-5` | Anthropic API | `temperature=0.0`, `max_tokens=500` |
| **Cloud Generation (Groq)** | `llama-3.1-8b-instant` | Groq API | `temperature=0.0`, `max_tokens=500` |

---

## 11. Testing, Evaluation & Observability

### Automated Test Suites
The repository contains **21 test files** in `tests/`, covering every pipeline phase:
- `test_api.py`: Tests `/v1/ask`, `/v1/health`, `/v1/compare`, and `/v1/documents`.
- `test_document_ingester.py` & `test_phase1_ingesters.py`: Tests Docling layout parsing, incremental watermarks, and fallback loaders.
- `test_dedup.py` & `test_enterprise_ingestion.py`: Validates SHA-256 state tracking and TF-IDF cosine duplicate filtering.
- `test_phase2_chunking.py` & `test_phase2_e2e_pipeline.py`: Verifies token budgets, Chonkie sentence chunking, and Markdown table row splitting.
- `test_phase3_embeddings.py`: Tests BGE-M3 dual-encoding and Qdrant vector storage.
- `test_phase4_indexbuilder.py`: Verifies `IndexBuilder` sequencing from Phase 1 through Phase 3.
- `test_phase5_memory_observability.py`: Tests Redis session sliding window (`RPUSH`/`LTRIM`) and Langfuse span contexts.
- `test_phase6_evaluation.py`: Verifies lexical and extended proxy metrics (`context_precision`, `hallucination_score`).
- `test_phase7_ablation.py`: Validates Cartesian sweep orchestration across retrieval arms.
- `test_phase8_nl2sql.py`: Validates query classification, SQL validation guards, and programmatic row-level ACL injection.
- `test_retrieval_hybrid_advantage.py`: Regression test proving that hybrid search correctly retrieves exact technical keys (`BIOME_API_KEY`) where dense-only search fails.

### Empirical Evaluation & 18-Arm Ablation Study
Evaluation is executed over `eval/golden_dataset.json` (55 curated enterprise questions covering lookups, relational data, and multi-hop questions).
- **Composite Score Formula:**
  $$\text{Composite} = 0.30 \cdot \text{Correctness} + 0.20 \cdot \text{Faithfulness} + 0.15 \cdot \text{ContextPrecision} + 0.10 \cdot \text{ContextRecall} + 0.10 \cdot \text{AnswerRelevancy} + 0.10 \cdot \text{SemanticSimilarity} - 0.05 \cdot \text{HallucinationScore}$$

#### Top Ablation Study Results (`ABLATION_RESULTS.md`)

| Rank | Arm Configuration | Mode | Top-$k$ | Rerank | Faithfulness | Context Precision | Context Recall | Hallucination $\downarrow$ | Composite Score |
|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 🥇 1 | `hybrid_k10_no_rerank` | **Hybrid** | **10** | **No** | **0.773** | **0.780** | **0.642** | **0.309** | **0.4721** |
| 🥈 2 | `dense_k3_no_rerank` | Dense | 3 | No | 0.733 | 0.833 | 0.440 | 0.310 | 0.4549 |
| 🥉 3 | `hybrid_k5_no_rerank` | Hybrid | 5 | No | 0.751 | 0.767 | 0.526 | 0.309 | 0.4544 |
| 4 | `hybrid_k3_no_rerank` | Hybrid | 3 | No | 0.744 | 0.818 | 0.461 | 0.309 | 0.4541 |
| 5 | `dense_k5_no_rerank` | Dense | 5 | No | 0.734 | 0.811 | 0.453 | 0.310 | 0.4530 |

*Retrieval Mode Averages:*
- **Hybrid (BGE-M3 + BM25 + RRF):** Mean Composite **0.4281**
- **Dense-Only:** Mean Composite **0.4128**
- **Sparse-Only (BM25):** Mean Composite **0.3338**

---

## 12. Risks, Gaps & Code Smells

### 1. Hardcoded Database Credentials in Seed Script (Security Risk)
- **Location:** [seed_db.py:L8](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/seed_db.py#L8)
- **Code:**
  ```python
  DB_URI = "postgresql://postgres:Aditya%402005@localhost:5432/enterprise_rag"
  ```
- **Risk:** High security vulnerability. A plaintext database password (`Aditya@2005`) is committed to source control. If pushed to a public repository, these credentials are fully exposed.
- **Remediation:** Refactor `seed_db.py` to read `os.getenv("POSTGRES_URI")` or import `get_settings().postgres_uri` from `biome_rag.config`.

### 2. Duplicated Ingestion Pipelines (Architectural Debt)
- **Location:** `biome_rag/ingestion/pipeline.py` vs [biome_rag/indexing/builder.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/indexing/builder.py)
- **Details:** The codebase maintains two concurrent pipeline engines: the legacy `IngestionPipeline` (which uses character-based chunkers and writes to ChromaDB/Silver layer) and the modern `IndexBuilder` (which uses Docling, Chonkie, and Qdrant).
- **Risk:** Divergent ingestion logic. Endpoints like `POST /v1/ingest` run the legacy pipeline, while `POST /v1/index/files` runs `IndexBuilder`.

### 3. Incomplete Slack Ingestion Stub (Feature Gap)
- **Location:** [biome_rag/ingestion/slack_ingester.py:L117-L187](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/slack_ingester.py#L117-L187)
- **Details:** Documented in ADR D013 as an intentional stub. Contains `TODO` comments at lines 117, 145, 155, 183. Calling `SlackIngester.ingest()` returns an empty result without making live Slack API calls.

### 4. Single-Process Concurrency Bottlenecks in ChunkStore
- **Location:** [biome_rag/retrieval/stores.py:L10-L42](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/stores.py#L10-L42)
- **Details:** `ChunkStore` loads all chunk texts into memory from a local JSON file (`data/processed/chunks.json`). At scale (>100,000 chunks), deserializing this large JSON file into memory on startup causes severe memory bloat and slow worker boot times.

### 5. Regex-Based SQL Synthesis Vulnerability to Ambiguity
- **Location:** [biome_rag/retrieval/router.py:L296-L390](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/router.py#L296-L390)
- **Details:** `NL2SQLEngine.generate_sql()` generates SQL queries using heuristic keyword pattern matching over questions. Complex multi-table joins or questions phrased outside these patterns fall back to a generic `SELECT *` query. While execution is protected by the sandboxing guard, query synthesis accuracy degrades on novel questions.

---

## 13. Suggested Reading Order

To understand this codebase in the shortest amount of time, read the files in the following sequence:

1. [DECISIONS.md](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/DECISIONS.md)
   - *Why:* Explains the 24 Architecture Decision Records from Phase 0 to Phase 8, documenting why decisions were made and tradeoffs accepted.
2. [biome_rag/config.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/config.py)
   - *Why:* Establishes all environment variables, ports, model names, and system thresholds.
3. [biome_rag/ingestion/models.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/ingestion/models.py)
   - *Why:* Defines the core data entities: `DocumentMetadata`, `DocumentNode`, and `Chunk`.
4. [biome_rag/chunking/document_chunker.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/chunking/document_chunker.py) & [biome_rag/chunking/text_chunker.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/chunking/text_chunker.py)
   - *Why:* Shows how Docling and Chonkie convert raw text into token-budgeted chunks with table splitting.
5. [biome_rag/retrieval/engine.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/engine.py) & [biome_rag/retrieval/qdrant_store.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/qdrant_store.py)
   - *Why:* The core retrieval engine. Shows dual dense/sparse search, RRF rank fusion ($k=60$), and cross-encoder reranking.
6. [biome_rag/retrieval/router.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/retrieval/router.py)
   - *Why:* Demonstrates query routing and sandboxed NL2SQL execution with programmatic row-level ACL injection.
7. [biome_rag/generation/answering.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/generation/answering.py)
   - *Why:* Shows prompt construction, LLM provider dispatch, citation verification, and composite confidence calculation.
8. [biome_rag/indexing/builder.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/indexing/builder.py)
   - *Why:* Ties together ingestion, chunking, and dual-indexing into an end-to-end pipeline.
9. [biome_rag/api/app.py](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/biome_rag/api/app.py)
   - *Why:* The HTTP API gateway connecting memory, observability, retrieval, and generation to the client.
10. [frontend/src/services/api.js](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/frontend/src/services/api.js) & [frontend/src/App.jsx](file:///c:/Users/Aditya%20Singh/OneDrive/Desktop/Projects/Biome/frontend/src/App.jsx)
    - *Why:* Shows how the React frontend interfaces with backend endpoints.

---

## 14. Domain Glossary

- **ACL (Access Control List):** Mechanism enforcing security scopes (`access_scope`) at ingestion, retrieval, and database levels to prevent cross-department data leakage.
- **BGE-M3:** State-of-the-art dual embedding model developed by BAAI. Produces 1024-dimensional dense semantic vectors and lexical term weights simultaneously.
- **BM25 (Best Matching 25):** Probabilistic lexical retrieval algorithm that ranks documents based on query term frequency and inverse document frequency (IDF).
- **Chonkie:** Lightweight, token-aware sentence chunking library tuned for structured entities and conversational threads.
- **Cross-Encoder:** Deep transformer architecture (`ms-marco-MiniLM-L-6-v2`) that scores full cross-attention interactions between query and candidate text.
- **Docling:** IBM open-source layout-aware document parser that extracts heading hierarchies and structural tables from PDFs, Word docs, and slides.
- **E3002:** System error code emitted when the chunk count in the JSON store diverges from the document count in the BM25 inverted index.
- **Hybrid Search:** Search architecture combining semantic vector similarity (dense) with exact lexical matching (sparse/BM25).
- **Langfuse:** Open-source LLM observability platform tracking execution spans, retrieval latencies, and token consumption.
- **NL2SQL:** Natural Language to Structured Query Language translation engine allowing conversational database queries.
- **Reciprocal Rank Fusion (RRF):** Rank aggregation algorithm that merges rankings from multiple retrieval engines into a single score:
  $$\text{RRF Score} = \sum_{m \in M} \frac{w_m}{k + r_m(d)}$$
- **Silver Layer:** Clean, normalized intermediate document storage (`data/silver/documents.jsonl`) generated after deduplication.
- **Watermark:** A persistent timestamp recorded in SQLite tracking the last successful ingestion run to support incremental updates.

---

## 15. Confidence & Coverage Audit Note

- **Parts Fully Read & Verified with Highest Confidence:**
  - `biome_rag/config.py` (Full Pydantic settings schema, properties, and defaults).
  - `biome_rag/ingestion/` (`models.py`, `base.py`, `document_ingester.py`, `postgres_ingester.py`, `slack_ingester.py`, `dedup.py`, `loaders.py`, `pipeline.py`).
  - `biome_rag/chunking/` (`base.py`, `document_chunker.py`, `text_chunker.py`, `__init__.py`).
  - `biome_rag/retrieval/` (`models.py`, `bm25.py`, `dense.py`, `embeddings.py`, `qdrant_store.py`, `stores.py`, `engine.py`, `router.py`).
  - `biome_rag/generation/answering.py` (Prompts, confidence formulas, provider handling, citations).
  - `biome_rag/indexing/builder.py` (Full Phase 1 -> Phase 2 -> Phase 3 orchestration).
  - `biome_rag/memory/session.py` (Redis RPUSH/LTRIM and fallback memory).
  - `biome_rag/observability/langfuse_tracer.py` (Tracing context and span logging).
  - `biome_rag/flows/index_flow.py` (Prefect task and flow definitions).
  - `biome_rag/evaluation/` (`metrics.py`, `extended_metrics.py`, `harness.py`, `report.py`).
  - `biome_rag/api/app.py` & `app.py` (All endpoints, schemas, and routes).
  - `scripts/setup_system.py`, `scripts/seed_index.py`, `seed_db.py`, `generate_mock_files.py`.
  - `eval/ablation_runner.py` & `eval/run_eval.py`.
  - Configuration & container manifests (`docker-compose.yml`, `Dockerfile`, `pyproject.toml`, `requirements.txt`, `.env.example`).
  - `DECISIONS.md`, `README.md`, `ABLATION_RESULTS.md`.
- **Parts Skimmed:**
  - `frontend/src/components/views/*`: UI view components (`ChatView.jsx`, `LandingPage.jsx`, etc.) were inspected for endpoint calls and styling patterns; internal CSS layout logic was reviewed at a high level.
  - Test modules in `tests/`: Tested behaviors and test structures were examined to verify coverage.
- **Parts Marked UNVERIFIED or Out of Scope:**
  - Real Slack API network calls (`SlackIngester._fetch_messages`): Verified in code as an intentional stub (ADR D013); live Slack workspace integration was not executed.
  - Production GPU inference speed: Verified CPU and local Docker execution configurations; CUDA hardware speedups were not benchmarked on live GPUs during this audit.
