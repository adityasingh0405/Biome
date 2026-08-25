FROM python:3.11-slim

WORKDIR /app

# Install system deps needed for some Python packages (pypdf, sentence-transformers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Ensure data directories exist
RUN mkdir -p data/raw data/processed data/index

EXPOSE 8000
