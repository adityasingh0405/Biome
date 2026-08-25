# Deployment Guide

## Deployment Environments

Biome supports three deployment environments: `dev`, `staging`, and `production`. Set the target with the `BIOME_DEPLOY_TARGET` environment variable.

```bash
export BIOME_DEPLOY_TARGET=staging
```

Forgetting to set `BIOME_DEPLOY_TARGET` before a deployment will return error `E2002 Missing Deployment Target`.

## Docker Deployment

### Single command startup

```bash
docker compose up --build
```

This builds the Docker image, runs the seed script to index the sample corpus, and starts both the API (port 8000) and the Streamlit dashboard (port 8501).

### Services

| Service | Port | Description |
|---------|------|-------------|
| `api` | 8000 | FastAPI backend |
| `dashboard` | 8501 | Streamlit frontend |

### Environment Variables in Docker

Mount your `.env` file or set environment variables directly in `docker-compose.yml`. Never commit secrets to the repository.

## Kubernetes Deployment

For production Kubernetes deployment:

1. Build and push the image to your container registry.
2. Create a Kubernetes Secret for `BIOME_API_KEY` and other secrets.
3. Apply the deployment manifest:

```bash
kubectl apply -f k8s/deployment.yaml
```

### Resource Recommendations

| Component | CPU Request | Memory Request | Notes |
|-----------|------------|---------------|-------|
| API | 500m | 512Mi | Scale horizontally for load |
| Dashboard | 250m | 256Mi | Single replica is fine |

## Rolling Updates

To update the API without downtime, configure a rolling update strategy with `maxUnavailable: 0`. The API is stateless; all state is stored in the ChromaDB volume and BM25 index files.

## Health Checks

The API exposes `GET /health` for readiness and liveness probes.

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
```

## Data Persistence

ChromaDB data is stored in `data/index/chroma/`. Mount this directory as a persistent volume in Docker or Kubernetes to preserve the index across restarts.

BM25 index is stored in `data/index/bm25_index.pkl`. Both files must be present for the API to serve queries.

## Scaling Ingestion

For large corpora (>10,000 documents), run ingestion as a separate job:

```bash
python -m biome_rag.ingestion.cli --raw-dir /data/raw --processed-dir /data/processed --storage-dir /data/index
```

Ingestion is CPU-bound. Allocate at least 4 CPU cores for large corpora.

## CI/CD Integration

Add the following step to your CI pipeline to validate the index:

```bash
python scripts/seed_index.py --validate-only
```

This verifies the index is coherent without re-running ingestion.
