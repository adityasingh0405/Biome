# Biome RAG

Biome RAG is a portfolio-style retrieval-augmented generation system for internal documentation. It lets you drop in documents, search them intelligently, and ask questions about them without reading every file manually.

## What this project does

Think of this app as a document assistant.

- You put documents into the project.
- The app breaks those documents into smaller pieces.
- It stores those pieces in a searchable form.
- When you ask a question, it finds the most relevant pieces and builds an answer from them.
- It also shows where the answer came from, so you can trust it more.

This is useful for onboarding docs, support articles, internal wikis, API references, study notes, or any collection of information that people need to search quickly.

## How the workflow works

The project follows a clear pipeline from raw documents to a final answer:

1. Put documents in [data/raw](data/raw).
2. The ingestion layer loads them.
3. The chunking layer splits long documents into smaller, searchable chunks.
4. The deduplication step removes repeated or near-duplicate content.
5. The pipeline saves the processed chunks to [data/processed](data/processed) and builds a BM25 index in [data/index](data/index).
6. When a question is asked, the retrieval layer searches those chunks.
7. The generation layer turns the retrieved evidence into a grounded answer.
8. The FastAPI service exposes the whole workflow through HTTP endpoints.

In simple terms: documents go in, useful answers come out.

## Architecture

```mermaid
flowchart LR
    A[Raw docs] --> B[Loaders]
    B --> C[Chunkers]
    C --> D[Deduplication]
    D --> E[Processed Chunks + BM25 Index + Dense Vector Store]
    E --> F[Hybrid Retrieval with RRF(Reciprocal Rank Fusion)]
    F --> G[Answer Builder + Citation Verification]
    G --> H[FastAPI API + Streamlit Dashboard]
```

The retrieval path now uses both a sparse BM25 index and a dense vector store. The dense and sparse ranked lists are combined through reciprocal rank fusion (RRF), so the final ranking reflects both semantic similarity and keyword overlap.

## What each folder and file does

### Top-level files

- [README.md](README.md) — explains the project and how to use it.
- [pyproject.toml](pyproject.toml) — Python project metadata and test configuration.
- [requirements.txt](requirements.txt) — Python dependencies for the app.
- [.env.example](.env.example) — example environment variables.
- [app.py](app.py) — starts the FastAPI app.
- [streamlit_app.py](streamlit_app.py) — starts the Streamlit dashboard.
- [docker-compose.yml](docker-compose.yml) — runs the API and dashboard in Docker.
- [docker-entrypoint.sh](docker-entrypoint.sh) — startup helper for container-based execution.
- [CASE_STUDY.md](CASE_STUDY.md) — a project write-up and architecture summary.

### [biome_rag](biome_rag)

This is the main Python package that contains the app logic.

- [biome_rag/__init__.py](biome_rag/__init__.py) — package marker.

#### [biome_rag/ingestion](biome_rag/ingestion)

This folder handles everything related to taking raw files and turning them into searchable chunks.

- [biome_rag/ingestion/models.py](biome_rag/ingestion/models.py) — defines the data structures for documents, chunks, and ingestion settings.
- [biome_rag/ingestion/loaders.py](biome_rag/ingestion/loaders.py) — reads markdown, text, HTML, and PDF-style files.
- [biome_rag/ingestion/chunkers.py](biome_rag/ingestion/chunkers.py) — splits content into smaller chunks using different strategies.
- [biome_rag/ingestion/dedup.py](biome_rag/ingestion/dedup.py) — removes duplicated or near-duplicate chunks.
- [biome_rag/ingestion/pipeline.py](biome_rag/ingestion/pipeline.py) — orchestrates the full ingestion workflow from start to finish.
- [biome_rag/ingestion/cli.py](biome_rag/ingestion/cli.py) — command-line entry point for running ingestion.

#### [biome_rag/retrieval](biome_rag/retrieval)

This folder handles searching the processed chunks and ranking the best results.

- [biome_rag/retrieval/models.py](biome_rag/retrieval/models.py) — defines the ranking output model.
- [biome_rag/retrieval/stores.py](biome_rag/retrieval/stores.py) — loads saved chunk data from disk.
- [biome_rag/retrieval/bm25.py](biome_rag/retrieval/bm25.py) — builds and stores a BM25 search index.
- [biome_rag/retrieval/engine.py](biome_rag/retrieval/engine.py) — runs the hybrid retrieval logic with ranking and reranking.

#### [biome_rag/generation](biome_rag/generation)

This folder turns retrieved context into a final answer.

- [biome_rag/generation/answering.py](biome_rag/generation/answering.py) — builds the answer, citations, and confidence signals.

#### [biome_rag/evaluation](biome_rag/evaluation)

This folder supports testing and quality checks.

- [biome_rag/evaluation/metrics.py](biome_rag/evaluation/metrics.py) — computes evaluation metrics.
- [biome_rag/evaluation/report.py](biome_rag/evaluation/report.py) — creates summary reports from evaluation data.

#### [biome_rag/api](biome_rag/api)

This folder exposes the app as an HTTP API.

- [biome_rag/api/app.py](biome_rag/api/app.py) — defines the FastAPI endpoints such as ask, ingest, documents, and health.

### [data](data)

This folder stores the input and output data for the app.

- [data/raw](data/raw) — original documents that should be ingested.
- [data/processed](data/processed) — saved processed chunks after ingestion.
- [data/index](data/index) — saved search indexes such as the BM25 index.

### [eval](eval)

This folder holds evaluation data.

- [eval/golden_qa.jsonl](eval/golden_qa.jsonl) — example questions and expected answers used for testing.

### [tests](tests)

This folder contains automated tests to verify the ingestion, retrieval, generation, and API behavior.

## Quickstart

### Local development

1. Copy [.env.example](.env.example) to `.env` and adjust any values you want to change.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Ingest the seed corpus:
   ```bash
   python -m biome_rag.ingestion.cli --raw-dir data/raw --processed-dir data/processed --storage-dir data/index
   ```
4. Start the API:
   ```bash
   python app.py
   ```
5. Start the dashboard in a second terminal:
   ```bash
   streamlit run streamlit_app.py --server.port 8501
   ```

The API will be available at `http://localhost:8000` and exposes `/v1/ask`, `/v1/documents`, `/v1/ingest`, and `/health`. The dashboard is available at `http://localhost:8501` and supports question entry, citation display, confidence output, retrieved-chunk score breakdowns, and a hybrid-vs-dense-only toggle.

### Docker

From the project root, run:

```bash
docker compose up --build
```

This starts the API and the Streamlit dashboard so the sample corpus is available without manual setup.

## Configuration

The project uses environment variables for core behavior. The defaults are defined in [.env.example](.env.example) and include:

- `EMBEDDING_MODEL`
- `CHUNK_SIZE`
- `CHUNK_OVERLAP`
- `DEDUP_THRESHOLD`
- `DENSE_TOP_K`
- `RRF_DENSE_WEIGHT`
- `RRF_SPARSE_WEIGHT`
- `LLM_PROVIDER`
- `CITATION_VERIFICATION_ENABLED`
- `INSUFFICIENT_CONFIDENCE_THRESHOLD`
- `EMBEDDING_COLLECTION_NAME`

These settings control dense retrieval depth, the RRF fusion weights, the provider used for citation verification, the confidence threshold for insufficient-context responses, and the collection name used for persisted dense embeddings.

## Evaluation

The repository includes a golden QA set in [eval/golden_qa.jsonl](eval/golden_qa.jsonl) and metric utilities in [biome_rag/evaluation/metrics.py](biome_rag/evaluation/metrics.py). Run the test suite with:

```bash
python -m pytest -q
```

## Results

The evaluation report is emitted as a JSON payload with row-level metrics and aggregate summaries. The current structure is:

| Metric | Chunking strategy | Status |
| --- | --- | --- |
| Answer correctness | fixed / structure / semantic | [TODO: fill in after running eval suite] |
| Faithfulness | fixed / structure / semantic | [TODO: fill in after running eval suite] |
| Retrieval relevance | fixed / structure / semantic | [TODO: fill in after running eval suite] |
| Citation accuracy | fixed / structure / semantic | [TODO: fill in after running eval suite] |

The report format is defined by [biome_rag/evaluation/report.py](biome_rag/evaluation/report.py) and currently writes `rows` plus aggregate values such as `mean_correctness` and `mean_citation_accuracy`.

## Notes

The sample corpus in [data/raw](data/raw) is synthetic seed data. The ingestion pipeline is designed to work with real documentation as well. BM25 and dense retrieval indexes are persisted to [data/index](data/index) so the API can restart without re-running ingestion.
#   B i o m e  
 