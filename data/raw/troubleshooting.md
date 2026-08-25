# Troubleshooting Guide

## Ingestion Problems

### Problem: Zero chunks produced after ingestion

**Symptom:** `seed_index.py` reports `Chunks created: 0`

**Causes and solutions:**
1. Documents in `data/raw/` are in an unsupported format. Check that files end in `.md`, `.txt`, `.html`, `.htm`, or `.pdf`.
2. All documents are empty. Open each file and confirm it has content.
3. Near-duplicate detection is too aggressive. Lower `DEDUP_THRESHOLD` in `.env` (default `0.95`).

### Problem: Error E3001 — Chunking Failed

Returned when ingestion succeeds but chunking produces zero output for a document. Usually caused by a document with only whitespace or special characters. Check the raw file and ensure it contains readable text.

### Problem: Error E3002 — Index Out of Sync

The BM25 index and ChromaDB vector store contain different chunk counts. This happens if ingestion is interrupted mid-run.

**Solution:** Delete the index directory and re-run ingestion:
```bash
rm -rf data/index/
python scripts/seed_index.py
```

### Problem: ChromaDB fails to open

If ChromaDB raises a schema migration error, the database format has changed between package versions.

**Solution:** Delete the Chroma directory and re-index:
```bash
rm -rf data/index/chroma/
python scripts/seed_index.py
```

## Retrieval Problems

### Problem: All answers are "I don't know"

**Causes:**
1. Ingestion has not been run (indexes are empty). Run `python scripts/seed_index.py`.
2. `INSUFFICIENT_CONFIDENCE_THRESHOLD` is too high. Lower it in `.env` (try `0.2`).
3. The cross-encoder model failed to load, and the fallback keyword overlap is too weak. Check logs for `CrossEncoder` load errors.

### Problem: Wrong documents retrieved

The query might be too short or ambiguous. Try adding more context. If exact-term queries are failing, ensure the BM25 index is built (check `data/index/bm25_index.pkl` exists).

### Problem: Slow queries

The cross-encoder reranker runs on CPU by default. First-query latency includes model loading (~5s). Subsequent queries are faster (~0.1–0.3s for reranking).

For consistently faster queries:
- Use `LLM_PROVIDER=openai` with a fast model like `gpt-4o-mini`
- Reduce `DENSE_TOP_K` to `3`

## Generation Problems

### Problem: LLM returns generic answers not from the documents

The LLM is ignoring the context. Check:
1. `MAX_CONTEXT_TOKENS` is high enough (raise to `2000`).
2. The context chunks are relevant (check `retrieved_chunks` in the API response).
3. The LLM provider is set correctly (`LLM_PROVIDER` in `.env`).

### Problem: Citation numbers in answers don't match chunks

Citation parsing depends on the LLM strictly following the `[n]` format. Some smaller models (like `llama3.2:3b`) may not follow the instruction reliably. Use a larger model or `openai`/`anthropic` for reliable citations.

### Problem: Ollama connection refused

Ensure Ollama is running before starting the API:
```bash
ollama serve
```

Pull the model if it's not downloaded:
```bash
ollama pull llama3.2:3b
```

## Docker Problems

### Problem: Services cannot reach each other

The dashboard must reach the API using the Docker service name, not `localhost`. Ensure `API_BASE=http://api:8000` is set in the dashboard service environment.

### Problem: Index files missing in container

Mount the `data/` directory as a volume so the index persists across container restarts:
```yaml
volumes:
  - ./data:/app/data
```
