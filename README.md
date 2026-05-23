# Hybrid Semantic Search Engine

A robust, modular hybrid semantic search engine built with FastAPI, PostgreSQL (sparse keyword search with GIN index), ChromaDB (dense vector search), Redis (query caching), and a Cross-Encoder model (re-ranking). 

The project separates the retrieval pipeline from the generation pipeline (RAG), allowing for dedicated tuning, granular latency optimization, and standalone information retrieval evaluation.

Includes a full retrieval ablation across 45 queries (keyword, semantic, hybrid) evaluating dense-only, sparse-only, hybrid RRF, and cross-encoder re-ranking configurations. Key finding: Hybrid RRF with 1024-token chunks matches dense-only retrieval at `0.9370` MRR with `11.51 ms` warm-cache latency, while the MS MARCO re-ranker slightly decreases MRR on legal semantic queries — see the [Retrieval Ablation Evaluation Report](backend/eval/report.md) for analysis and next steps.

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

A full analysis of per-category accuracy breakdown and stage-level latency is available in the standalone [Retrieval Ablation Evaluation Report](backend/eval/report.md).

Latency should be read with the report's measurement protocol. The current saved results use one warm-up run and three measured runs, so they represent warm-cache retrieval latency rather than live Gemini embedding latency.

### Metrics Defined
- **Mean Reciprocal Rank (MRR)**: Evaluates the rank position of the first relevant result.
- **NDCG@10**: Evaluates rank quality using graded relevance with logarithmic reduction.
- **Precision@5**: Evaluates the ratio of relevant results in the top 5 returned elements.

### Ablation Comparison Table

| Configuration | MRR | NDCG@10 | Precision@5 | Latency (ms) |
| :--- | :---: | :---: | :---: | :---: |
| **Dense Only** | 0.9370 | 0.9532 | 0.2000 | 10.00 ms |
| **Sparse Only** | 0.3778 | 0.3778 | 0.0756 | 1.06 ms |
| **Hybrid RRF** | 0.9370 | 0.9532 | 0.2000 | 11.51 ms |
| **Hybrid + Rerank (Chunk=1024)** | 0.9333 | 0.9503 | 0.2000 | 17.97 ms |
| **Hybrid + Rerank (Chunk=256)** | 0.7796 | 0.8072 | 0.1778 | 11.65 ms |

### Key Findings
1. **Recommended configuration**: Use Hybrid RRF with 1024-token chunks for this benchmark. It matches Dense Only accuracy at `0.9370` MRR, keeps warm-cache latency low at `11.51 ms`, preserves sparse exact-match coverage as the corpus grows, and avoids the re-ranker's semantic-query regression.
2. **Re-ranking slightly decreases overall MRR versus Hybrid RRF**: Hybrid RRF reaches `0.9370` MRR, while Hybrid + Rerank (Chunk=1024) reaches `0.9333`. The drop appears in semantic queries, which supports the hypothesis that a general MS MARCO-style re-ranker can be domain-mismatched for legal clause retrieval.
3. **Dense retrieval dominates the aggregate set**: Dense Only reaches `0.9370` MRR while Sparse Only reaches `0.3778`, confirming the current legal queries are better served by embedding semantics than keyword overlap alone.
4. **Hybrid RRF matches Dense Only in this run**: Dense Only and Hybrid RRF both reach `0.9370` MRR and `0.9532` NDCG@10. Sparse retrieval remains useful as an exact-match safety net, but the current corpus does not show an aggregate lift.
5. **Precision@5 is capped by the ground truth design**: Each query currently has one relevant chunk, so the best possible Precision@5 is `1 / 5 = 0.2000`. The next evaluation pass should label 2-3 relevant chunks per query with graded relevance so NDCG@10 can differentiate close configurations.
6. **The warmed local run meets the 350ms latency target**: Dense Only averages `10.00 ms` after one warm-up run and three measured runs. Treat this as warm-cache retrieval latency, because stage timings show cached/local embeddings rather than live Gemini network calls.
7. **Reducing chunk size significantly decreases retrieval accuracy**: Reducing chunk size from 1024 tokens (`Hybrid + Rerank (Chunk=1024)` at `0.9333` MRR) to 256 tokens (`Hybrid + Rerank (Chunk=256)` at `0.7796` MRR) reduces MRR by `-0.1537`. Smaller chunk sizes restrict the semantic context of legal clauses, causing retrieval gaps.

---

## How to Verify & Run Tests

### Run Unit and Mock Tests
Verify the code syntax and mock interfaces locally:
```powershell
# PowerShell (Windows)
$env:PYTHONPATH="backend"
pytest backend/tests

# Bash (Linux/macOS)
PYTHONPATH=backend pytest backend/tests
```

### Run Retrieval Evaluation Suite
Run the full ablation metrics generator:
```powershell
# PowerShell (Windows)
$env:PYTHONPATH="backend"
python backend/eval/runner.py

# Bash (Linux/macOS)
PYTHONPATH=backend python backend/eval/runner.py
```
This regenerates `backend/eval/datasets/evaluation_results.json` and updates the `backend/eval/report.md` metrics table.

### Run End-to-End Integration Test
Run the full automated integration pipeline against your active Docker stack:
```powershell
# PowerShell (Windows)
$env:PYTHONPATH="backend"
python backend/eval/integration_test.py

# Bash (Linux/macOS)
PYTHONPATH=backend python backend/eval/integration_test.py
```
This test covers generating test PDFs, calling API upload and checking statuses, validating query highlighting, verifying Redis cache invalidation, invoking the evaluation suite, and cleaning up records via DELETE calls.
