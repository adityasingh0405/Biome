# Biome Onboarding Guide

## Welcome to Biome

Biome is an internal knowledge management platform that lets teams search, retrieve, and query their documentation using AI. This guide walks you through getting started in under 30 minutes.

## Prerequisites

- Python 3.11 or higher
- Docker (optional, for containerised deployment)
- A Biome API key (request from your team administrator)

## Step 1 — Install the Biome CLI

```bash
pip install biome-rag
```

## Step 2 — Configure Your Environment

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Set the following required variables in `.env`:
- `BIOME_API_KEY` — your authentication token. Without this, all API calls will fail with E1001.
- `LLM_PROVIDER` — set to `ollama` for local inference or `openai` for cloud inference.
- `OLLAMA_MODEL` — the local model to use (e.g. `llama3.2:3b`).

## Step 3 — Add Your Documents

Place documents in the `data/raw/` directory. Supported formats are Markdown (`.md`), plain text (`.txt`), HTML (`.html`, `.htm`), and PDF (`.pdf`).

```
data/raw/
├── api-reference.md
├── onboarding.md
└── my-policy.pdf
```

## Step 4 — Run Ingestion

```bash
python scripts/seed_index.py
```

This will:
1. Load all documents from `data/raw/`
2. Chunk them using three strategies (fixed, structure-aware, semantic)
3. Build the BM25 sparse index
4. Build the ChromaDB dense vector index
5. Print a summary of indexed chunks

Expected output:
```
Ingestion complete.
Documents processed: 10
Chunks created: 342
Duplicates skipped: 18
BM25 index: data/index/bm25_index.pkl
Chroma collection: biome-chunks (data/index/chroma/)
```

## Step 5 — Start the API

```bash
python app.py
```

The API will be reachable at `http://localhost:8000`. Visit `http://localhost:8000/docs` for interactive API documentation.

## Step 6 — Start the Dashboard

In a second terminal:

```bash
streamlit run streamlit_app.py
```

The dashboard will open at `http://localhost:8501`.

## Verifying Authentication

If authentication fails after setup, verify:
1. `BIOME_API_KEY` is set in your `.env` file
2. The token has not expired (tokens expire after 90 days)
3. You are not exceeding the rate limit (E1002)

Contact your administrator if E1001 persists after verifying the token is present in the environment.

## Common First-Run Issues

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| `E1001 Invalid Credentials` | Missing API key | Set `BIOME_API_KEY` in `.env` |
| `E2002 Missing Deployment Target` | `BIOME_DEPLOY_TARGET` not set | Set to `staging`, `production`, or `dev` |
| Empty answers | Ingestion not run | Run `python scripts/seed_index.py` |
| Slow first query | Cross-encoder loading | Wait 10–15s on first query; subsequent queries are faster |
