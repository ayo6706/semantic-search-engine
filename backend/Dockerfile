FROM python:3.12-slim

# System dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

ENV HF_HOME=/app/.cache/huggingface

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

RUN python -c "from sentence_transformers import CrossEncoder, SentenceTransformer; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', cache_folder='/app/.cache/huggingface'); SentenceTransformer('sentence-transformers/all-mpnet-base-v2', cache_folder='/app/.cache/huggingface')"

ENV HF_HUB_OFFLINE=1

# Copy application code
COPY . .

# Create uploads directory and change ownership
RUN mkdir -p uploads && chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

# Default command — overridden in docker-compose for worker
CMD ["fastapi", "run", "app/main.py", "--port", "8080"]
