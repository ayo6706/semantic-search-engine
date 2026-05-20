# Hybrid Semantic Search Engine

A production-grade, high-performance hybrid semantic search engine built with FastAPI, PostgreSQL (sparse keyword search with GIN index), ChromaDB (dense vector search), Redis (query caching), and a Cross-Encoder model (re-ranking). 

The project separates the retrieval pipeline from the generation pipeline (RAG), allowing for dedicated tuning, granular latency optimization, and standalone information retrieval evaluation.

---

## Architecture

The system consists of two primary workflows: **Dual-Write Ingestion Pipeline** and the **Composable Search Pipeline**.

### 1. Ingestion Pipeline (Dual-Write)
```mermaid
graph TD
    User([User]) -->|Upload PDF| API[FastAPI API]
    API -->|Save Metadata & File| DB[(PostgreSQL)]
    API -->|Enqueue Job| Redis[(Redis Queue / arq)]
    Redis -->|Process Job| Worker[arq Background Worker]
    Worker -->|Read PDF & Extract Pages| PyMuPDF[PyMuPDF Parser]
    PyMuPDF -->|Split Text into Pages| Chunker[Recursive Chunker]
    Chunker -->|Generate Embeddings| LLM[LiteLLM Provider / Gemini]
    Worker -->|Write Vectors| Chroma[(ChromaDB Vector Store)]
    Worker -->|Write Text & TSVector| DB
    Worker -->|Update Status to Ready| DB
    Worker -->|Invalidate Search Cache| Redis
```

### 2. Composable Search Pipeline
```mermaid
graph TD
    Client([React Frontend / Client]) -->|Search Query| API[FastAPI API]
    API -->|Check Cache| Cache[Redis Cache Service]
    Cache -->|Cache Hit| ReturnCached[Return Results Instantly]
    Cache -->|Cache Miss| Factory[Search Pipeline Factory]
    
    Factory -->|Build Pipeline| Pipeline[Search Pipeline]
    
    subgraph Parallel Retrieval
        Pipeline -->|Query Vector| Dense[Dense Retriever - ChromaDB]
        Pipeline -->|Query Keyword| Sparse[Sparse Retriever - PostgreSQL]
    end
    
    Dense -->|Dense Scores| Fuser[RRF Fuser]
    Sparse -->|Sparse Scores| Fuser[RRF Fuser]
    
    Fuser -->|Fused Rank Score| Reranker[Cross-Encoder Reranker]
    Reranker -->|Re-scored Top N| Snippet[Snippet Extractor & Highlighter]
    Snippet -->|Return with Highlighted HTML| API
    
    API -->|Write Response to Cache| Cache
    API -->|Return JSON Response| Client
```

---

## Tech Stack

| Technology | Purpose |
| :--- | :--- |
| **FastAPI** | High-performance, async Python web framework for APIs. |
| **PostgreSQL 16** | Relational storage for documents and text chunks, with custom `tsvector` columns and GIN indexes for sparse (BM25-style) keyword search. |
| **ChromaDB** | Vector database for storing and querying dense embeddings. |
| **Redis 7** | Shared service for the background job queue (arq) and fast SHA-256 query caching. |
| **LiteLLM** | Unified interface for generating dense text embeddings (using `gemini-embedding-001`). |
| **Sentence-Transformers** | Hugging Face cross-encoder model (`ms-marco-MiniLM-L-6-v2`) for async re-ranking. |
| **React + Vite** | Premium frontend UI with debounced search, tooltips, analytics graphs, and responsive layout. |

---

## Setup & Ingestion

### Prerequisites
- Docker & Docker Compose
- Python 3.12 (optional, for local script execution)

### 1. Environment Configuration
Create a `.env` file in the root directory (based on `.env.example`):
```env
# PostgreSQL
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/semantic_search

# ChromaDB
CHROMA_HOST=localhost
CHROMA_PORT=8000

# Redis
REDIS_URL=redis://:searchredis@localhost:6379/0

# LLM / Embedding
LLM_EMBEDDING_MODEL=gemini/gemini-embedding-001
LLM_EMBEDDING_DIMENSIONS=768
GEMINI_API_KEY=your_gemini_api_key_here

# Search
SEARCH_DEFAULT_TOP_K=10
SEARCH_RRF_K=60
SEARCH_RERANK_TOP_N=20
SEARCH_CACHE_TTL_SECONDS=300
```

### 2. Start the Docker Stack
Run the following command from the root directory:
```bash
docker-compose up -d --build
```
This boots up the following services:
- **`postgres`**: Configured with automatic healthchecks.
- **`chromadb`**: Host for dense vector indexing.
- **`redis`**: Password-protected cache and queue broker.
- **`api`**: FastAPI service (automatically executes Alembic migrations on startup).
- **`worker`**: Background ingestion worker.
- **`frontend`**: React client running on `http://localhost:3000`.

---

## API Reference

### 1. Document Management

#### Upload Document
- **Endpoint**: `POST /api/v1/documents`
- **Content-Type**: `multipart/form-data`
- **Request Body**:
  - `file`: PDF file (max 25MB)
- **Response** (200 OK):
  ```json
  {
    "id": "78642c60-6d91-41c0-8450-22599d92460e",
    "filename": "payment_agreement.pdf",
    "status": "pending",
    "page_count": 0,
    "chunk_count": 0,
    "created_at": "2026-05-20T15:00:00.000000",
    "updated_at": "2026-05-20T15:00:00.000000"
  }
  ```

#### Get Document Status
- **Endpoint**: `GET /api/v1/documents/{doc_id}`
- **Response** (200 OK):
  ```json
  {
    "id": "78642c60-6d91-41c0-8450-22599d92460e",
    "filename": "payment_agreement.pdf",
    "status": "ready",
    "page_count": 3,
    "chunk_count": 5,
    "created_at": "2026-05-20T15:00:00.000000",
    "updated_at": "2026-05-20T15:00:15.000000"
  }
  ```

#### Delete Document
- **Endpoint**: `DELETE /api/v1/documents/{doc_id}`
- **Response**: `204 No Content` (removes database records, Chroma vectors, raw upload files, and invalidates search caches).

---

### 2. Search

#### Execute Search Query
- **Endpoint**: `POST /api/v1/search`
- **Request Body**:
  ```json
  {
    "query": "billing frequency under the payment agreement",
    "doc_ids": null,
    "top_k": 10,
    "use_reranker": true,
    "search_mode": "hybrid"
  }
  ```
- **Response** (200 OK):
  ```json
  {
    "results": [
      {
        "chunk_id": "834c9c14-5d98-5c4d-91b7-d1a1b5c2d3e4",
        "doc_id": "78642c60-6d91-41c0-8450-22599d92460e",
        "doc_filename": "payment_agreement.pdf",
        "page_num": 1,
        "snippet": "The billing frequency and schedule under this agreement shall be strictly <mark>monthly</mark>. Invoices will be generated...",
        "text": "The billing frequency and schedule under this agreement shall be strictly monthly. Invoices will be generated and delivered to the client on the first day of each calendar month.",
        "score": 0.8923,
        "dense_score": 0.9123,
        "sparse_score": 0.6543,
        "rerank_score": 0.8923
      }
    ],
    "query": "billing frequency under the payment agreement",
    "total_results": 1,
    "latency_ms": 14.5,
    "search_mode": "hybrid",
    "reranker_used": true
  }
  ```

---

## Evaluation & Ablation Results

The system implements a standalone evaluation suite measuring information retrieval accuracy. The ground-truth test suite consists of 45 test queries (divided into 15 keyword, 15 semantic, and 15 hybrid queries) evaluated against 3 legal contracts.

### Metrics Defined
- **Mean Reciprocal Rank (MRR)**: Evaluates the rank position of the first relevant result.
- **NDCG@10**: Evaluates rank quality using graded relevance with logarithmic reduction.
- **Precision@5**: Evaluates the ratio of relevant results in the top 5 returned elements.

### Ablation Comparison Table

| Configuration | MRR | NDCG@10 | Precision@5 | Latency (ms) |
| :--- | :---: | :---: | :---: | :---: |
| **Dense Only** | 0.9370 | 0.9532 | 0.2000 | 829.03 ms |
| **Sparse Only** | 0.3778 | 0.3778 | 0.0756 | 4.59 ms |
| **Hybrid RRF** | 0.9370 | 0.9532 | 0.2000 | 763.97 ms |
| **Hybrid + Rerank** | 0.9333 | 0.9503 | 0.2000 | 838.53 ms |
| **Hybrid + Rerank (Chunk=512)** | 0.9333 | 0.9503 | 0.2000 | 828.92 ms |

### Key Findings
1. **Re-ranking slightly hurts the current metrics**: Hybrid + Rerank drops from `0.9370` to `0.9333` MRR. The likely cause is domain mismatch: `cross-encoder/ms-marco-MiniLM-L-6-v2` is trained for general web search, not legal clause retrieval. A broader retrieval model such as `BAAI/bge-reranker-base` is a practical next candidate to evaluate.
2. **Dense retrieval dominates this saved run**: Dense Only reaches `0.9370` MRR while Sparse Only reaches `0.3778`, so the aggregate dataset currently favors semantic matching over keyword-only retrieval.
3. **Hybrid RRF matches dense retrieval but does not beat it here**: Hybrid RRF and Dense Only have identical MRR and NDCG@10. Sparse retrieval may still help exact phrase, number, and section-code queries, but this needs the per-category breakdown to prove.
4. **Precision@5 is capped by the labels**: The ground truth currently has one relevant chunk per query, so the best possible Precision@5 is `1 / 5 = 0.2000`.
5. **The local latency target is not met**: Dense Only averages `829.03 ms`, above the 350ms target. The evaluator now supports stage-level latency profiling so the next full run can identify whether embeddings, retrieval, fusion, or reranking dominates.
6. **The saved chunk-size row is not a useful ablation yet**: The `Chunk=512` row is identical to the default reranked row on MRR, NDCG@10, and Precision@5. Re-run the evaluator to populate the newer 256, 512, and 1024 comparison.

---

## How to Verify & Run Tests

### Run Unit and Mock Tests
Verify the code syntax and mock interfaces locally:
```bash
$env:PYTHONPATH="backend"
pytest backend/tests
```

### Run Retrieval Evaluation Suite
Run the full ablation metrics generator:
```bash
$env:PYTHONPATH="backend"
python eval/runner.py
```
This regenerates `eval/datasets/evaluation_results.json` and updates the `eval/report.md` metrics table.

### Run End-to-End Integration Test
Run the full automated integration pipeline against your active Docker stack:
```bash
$env:PYTHONPATH="backend"
python eval/integration_test.py
```
This test covers generating test PDFs, calling API upload and checking statuses, validating query highlighting, verifying Redis cache invalidation, invoking the evaluation suite, and cleaning up records via DELETE calls.
