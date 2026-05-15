FROM python:3.12-slim AS base

# System dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create uploads directory and change ownership
RUN mkdir -p uploads && chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

# Default command — overridden in docker-compose for worker
CMD ["fastapi", "run", "app/main.py", "--port", "8080"]
