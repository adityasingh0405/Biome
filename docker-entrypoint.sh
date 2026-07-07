#!/bin/sh
set -e
pip install -r requirements.txt
python -m uvicorn biome_rag.api.app:app --host 0.0.0.0 --port 8000
