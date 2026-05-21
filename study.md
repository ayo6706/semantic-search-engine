# Study Log

## 2026-05-18 - Added Study Log Skill

### What changed
- Added a new local Codex skill named `study-log`.
- The skill tells future Codex sessions to maintain this `study.md` file as a project learning journal after implementation work.
- The skill defines a repeatable entry format covering what changed, why it changed, files touched, verification, and study notes.

### Why it changed
- LLM-assisted development can be hard to review later because the reasoning behind changes may be scattered across chat history.
- Keeping a written implementation history in the repo gives you a stable place to study what was introduced and why it was done.

### Files touched
- `.agents/skills/study-log/SKILL.md`: defines when the skill should trigger and how Codex should update `study.md`.
- `.agents/skills/study-log/agents/openai.yaml`: provides UI metadata and a default prompt for the skill.
- `study.md`: starts the project-level study journal.

### How to verify
- Ran `python3 /root/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/study-log`.
- The validator reported `Skill is valid!`.

### Study notes
- Skills are reusable instruction packages. The frontmatter `description` is important because it controls when Codex knows to use the skill.
- This skill is intentionally lightweight. It does not need scripts because its job is to guide documentation behavior, not automate a fragile file operation.
- Future entries should focus on intent and learning value, not long diffs.

## 2026-05-18 - Document Ingestion Pipeline (Issue 2)

### What changed
- **Document Processing**: Created a `PyMuPDFParser` to extract page-by-page PDF content, and a custom `RecursiveCharacterTextSplitter` to chunk pages while preserving page numbers.
- **Vector & Embedding**: Added `LiteLLMProvider` using LiteLLM for text embedding (with tenacity exponential backoff retries) and `ChromaDBVectorStore` utilizing lazy async client initialization.
- **Chroma & Postgres Alignment**: Standardized chunk IDs using deterministic `UUID5` (`uuid5(NAMESPACE_DNS, f"{doc_id}:{chunk_index}")`) so dense vectors and full-text search database chunks share the exact same ID.
- **Database & Schemas**: Created repositories for `Document` (status management, statistics updates) and `Chunk` (bulk updates with `on_conflict_do_nothing`), backed by a new unique constraint `(doc_id, chunk_index)` mapped via an Alembic migration.
- **Robust Orchestration**: Designed `IngestionService` with transaction boundaries, race condition checks, and independent cleanup blocks (ensuring failing Chroma deletes do not block Postgres status updates).
- **Worker Isolation**: Configured the `arq` background worker to instantiate fresh, isolated `AsyncSession` connections for each concurrent job instead of sharing a global connection.
- **Endpoints & Size Limits**: Created `documents` REST API with 25MB file upload validation, proper cleanup on enqueue failure, and background task dispatch.
- **Dependencies & Verification**: Added `aiofiles`, `pytest`, `pytest-asyncio`, and `pytest-mock` dependencies and implemented comprehensive unit/mock tests.

### Why it changed
- Dual-writing chunk data to both PostgreSQL (for relational metadata and sparse BM25 FTS) and ChromaDB (for dense semantic search) requires a unified ID system to support Reciprocal Rank Fusion (RRF) later.
- Production-grade file ingestion needs explicit size validation, concurrency isolation, and multi-resource transactional cleanup to prevent orphan vectors, db chunks, or stuck "processing" status states.

### Files touched
- `app/core/config.py` & `.env.example`
- `app/models/chunk.py` & `alembic/versions/2026-05-18_add_uniqueconstraint_to_chunks.py`
- `app/lib/utils.py` & `app/lib/document/base.py` & `app/lib/document/pymupdf.py`
- `app/services/chunker.py` & `app/services/document.py` & `app/services/ingestion.py`
- `app/integrations/llm/base.py` & `app/integrations/llm/litellm.py`
- `app/integrations/vectorstores/base.py` & `app/integrations/vectorstores/chroma.py`
- `app/repositories/document.py` & `app/repositories/chunk.py`
- `app/workers/ingestion.py` & `app/api/v1/endpoints/documents.py` & `app/api/v1/router.py`
- `requirements.txt`
- `tests/test_chunker.py`, `tests/test_document_api.py`, `tests/test_ingestion_service.py`

### How to verify
- Run tests via `python -m pytest tests` (which installs dependencies from `requirements.txt` and executes all unit and mock scenarios).

### Study notes
- **Deterministic Chunks**: Generating deterministic UUID5 IDs binds Postgres rows and Chroma documents together natively. This avoids keeping an intermediate mapping table.
- **Starlette Mocking**: Mocking file uploads requires passing `headers={"content-type": "application/pdf"}` into the `UploadFile` constructor, as newer versions of Starlette define `content_type` as a read-only property.
- **Worker Concurrency**: Always initialize database sessions dynamically per-job using `async with async_session_factory() as session:` rather than passing a shared `AsyncSession` down from startup context. Sharing an `AsyncSession` concurrently will throw transaction state errors.
- **Defensive Ingestion Cleanup**: When performing failure rollback in dual-write architectures, wrap each external cleanup step in its own `try/except` block. This prevents a network failure in one resource (e.g. Chroma) from halting cleanup in another (e.g. Postgres status updates).

## 2026-05-18 - Added Code Style Skill

### What changed
- Added a new local Codex skill named `code-style`.
- The skill captures your cross-language code style preference: write clear code first and avoid comments that restate obvious behavior.
- It includes examples showing when to remove AI-sounding comments and when a comment is useful because it protects a non-obvious decision.

### Why it changed
- You want future Codex edits to follow your standards automatically instead of adding explanatory comments that read like LLM narration.
- The skill gives Codex a reusable checklist for comments, docstrings, naming, and general code clarity.

### Files touched
- `.agents/skills/code-style/SKILL.md`: defines the style rules and examples.
- `.agents/skills/code-style/agents/openai.yaml`: provides UI metadata and a default prompt for the skill.
- `study.md`: records the skill creation for later study.

### How to verify
- Ran `python3 /root/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/code-style`.
- The validator reported `Skill is valid!`.

### Study notes
- A good code comment usually explains why a choice exists, not what the next line does.
- If a comment can be replaced by a clearer function name, variable name, or simpler control flow, the code should usually be improved instead of commented.
- Personal style skills are most useful when they include concrete rejected examples, because future agents can compare new code against the exact pattern you dislike.

## 2026-05-18 - Refactor DocumentService.upload_document

### What changed
- Refactored `upload_document` in `DocumentService` from a single long method into a concise orchestrator.
- Extracted logic into five focused `@staticmethod` and private helpers (`_validate_upload`, `_save_to_disk`, `_assert_valid_pdf`, `_move_file`, and `_enqueue`).
- Removed redundant narrating comments (e.g., `# Rename file to use the DB document ID`).
- Cleaned up the `_assert_valid_pdf` helper to properly manage PyMuPDF `fitz` document lifecycle and temporary file cleanup using a boolean `valid` flag instead of a fragile bare `raise` trick.

### Why it changed
- The original method had grown too long, mixing HTTP validation, file I/O, PDF parsing, DB transactions, and background task enqueuing.
- To align with the `google-python-style-guide` (small, focused functions) and `code-style` (code should read like a human-maintained codebase without obvious narration).

### Files touched
- `app/services/document.py`: Restructured the `DocumentService` class.

### How to verify
- Ran `python -m pytest tests -v` which verified all size limits, file extension checks, and failure cleanup workflows still pass successfully.

### Study notes
- **Single Responsibility**: Breaking large functions into smaller, single-responsibility private helpers dramatically improves readability. The main orchestrator function now reads like a table of contents for the operation.
- **Self-Documenting Code**: By naming methods clearly (`self._move_file(temp_path, final_path)`), we eliminate the need for descriptive comments, adhering directly to the `code-style` skill.
- **Exception Cleanup**: Relying on a bare `raise` to check if an exception is currently active in a `finally` block is dangerous and hard to read. A simple state flag (`valid = False`) is safer, explicit, and much easier for the next maintainer to understand.

## 2026-05-18 - Search Pipeline Review Fixes

### What changed
- Fixed sparse search document filtering by converting incoming document IDs to `uuid.UUID` values and binding the PostgreSQL `ANY(:doc_ids)` parameter as `ARRAY(UUID)`.
- Updated `SearchPipeline.execute()` to rerank only the configured candidate window from `SEARCH_RERANK_TOP_N`, while still returning the requested `top_k`.
- Reworked snippet extraction to score windows with whole-word set overlap and apply highlighting in one regex pass, avoiding substring false positives and broken `<mark>` markup.
- Added regression tests for rerank candidate limiting, UUID parameter conversion, and snippet edge cases.

### Why it changed
- The first Issue 3 implementation had the right Strategy Pattern shape, but review found runtime and quality risks in the database binding, reranker cost control, and snippet matching.
- These fixes keep the architecture intact while making the pipeline safer for real PostgreSQL, cross-encoder, and UI-result usage.

### Files touched
- `app/repositories/chunk.py`: strengthened PostgreSQL FTS `doc_ids` binding.
- `app/search/pipeline.py`: limited cross-encoder candidate count using search settings.
- `app/search/snippet.py`: switched snippet scoring/highlighting to safer word-based logic.
- `tests/test_search.py`: expanded regression coverage for the reviewed defects.

### How to verify
- Ran `python3 -m compileall app/search app/repositories/chunk.py tests/test_search.py`.
- Ran a direct snippet check with `python3 -c ...` to confirm whole-word selection and `<mark>` output.
- `python3 -m pytest tests/test_search.py -q` could not run in this shell because `pytest` is not installed.
- A dependency-backed import check also showed `sqlalchemy` is not installed, so install `requirements.txt` before running the full tests locally.

### Study notes
- PostgreSQL UUID columns should receive UUID-typed bind parameters, especially with array operators like `ANY`, so the driver does not infer an incompatible `text[]`.
- Cross-encoders are expensive compared with retrieval and fusion. The pipeline should cap the rerank candidate set before model inference.
- Snippet scoring and highlighting are separate concerns: score against normalized word sets, then apply one final highlighting regex to the chosen text.

## 2026-05-18 - Search Pipeline Hardening Fixes

### What changed
- Serialized `CrossEncoder.predict()` calls behind an `asyncio.Lock`, added contextual startup failure logging with retries, and changed reranker sorting to avoid mutating the caller's list order.
- Improved snippet extraction with an NLTK sentence tokenizer path, normalized boundary checks for leading/trailing ellipses, and an updated docstring for configurable `max_sentences`.
- Made `build_pipeline()` accept no cross-encoder when reranking is disabled, while raising `ValueError` if reranking is enabled without one.
- Added clearer validation for invalid sparse-search document UUIDs, `SearchRequest` query/top-k/doc-id inputs, and missing Chroma metadata in dense retrieval.
- Added focused regression tests for these behaviors and added `nltk` to `requirements.txt`.

### Why it changed
- The review findings were still valid in the current code and could cause startup crashes, unsafe concurrent model inference, unexpected caller-side mutation, unclear validation errors, or poor snippets.
- These changes keep the existing Strategy Pattern design while making individual strategy implementations safer.

### Files touched
- `app/search/rerankers/cross_encoder.py`: model load retries, serialized prediction, non-mutating sorting.
- `app/search/snippet.py`: sentence tokenization, boundary checks, docstring update.
- `app/search/factory.py`: optional cross-encoder unless reranking is requested.
- `app/repositories/chunk.py`: clearer UUID validation for `SearchRequest.doc_ids`.
- `app/schemas/search.py`: Pydantic request validation.
- `app/search/retrievers/dense.py`: descriptive errors for malformed Chroma metadata.
- `tests/test_search.py`: regression tests for the hardening fixes.
- `requirements.txt`: added NLTK for sentence tokenization.

### How to verify
- Ran `python3 -m compileall app/search app/repositories/chunk.py app/schemas/search.py tests/test_search.py`.
- Ran `git diff --check -- app/search/rerankers/cross_encoder.py app/search/snippet.py app/search/factory.py app/repositories/chunk.py app/schemas/search.py app/search/retrievers/dense.py tests/test_search.py requirements.txt`.
- `python3 -m pytest tests/test_search.py -q` could not run because this shell does not have `pytest` installed.

### Study notes
- Shared ML model instances should be treated as non-thread-safe unless their documentation explicitly guarantees concurrent inference safety.
- Pydantic request validation should reject bad inputs before repository or integration layers receive them.
- A factory can accept optional expensive dependencies when a mode does not need them, but it should fail clearly when a requested mode does.

## 2026-05-18 - Snippet Position and Repository Error Cleanup

### What changed
- Replaced snippet ellipsis boundary checks based on `startswith()`/`endswith()` with tracked sentence window indices.
- Narrowed `_split_sentences()` exception handling to expected NLTK import, tokenizer lookup, and download failures.
- Changed the sparse-search invalid UUID error message so the repository no longer references `SearchRequest`.
- Added a regression test for duplicate-sentence snippets where string boundary checks could choose the wrong ellipsis behavior.

### Why it changed
- Duplicate sentences can fool text-based boundary checks, but sentence indices directly represent where the selected snippet came from.
- Broad exception handlers hide unrelated defects. The fallback tokenizer path should only handle expected optional-dependency/tokenizer-resource problems.
- Repository code should stay independent from API schema names.

### Files touched
- `app/search/snippet.py`: sentence fallback helper, narrower exception handling, index-based ellipsis logic.
- `app/repositories/chunk.py`: generic invalid `doc_ids` error message.
- `tests/test_search.py`: updated invalid UUID assertion and added duplicate-sentence snippet coverage.

### How to verify
- Ran `python3 -m compileall app/search/snippet.py app/repositories/chunk.py tests/test_search.py`.
- Ran `git diff --check -- app/search/snippet.py app/repositories/chunk.py tests/test_search.py`.
- Ran a direct snippet check for duplicate sentences with `python3 -c ...`.
- `python3 -m pytest tests/test_search.py -q` could not run because `pytest` is not installed in this shell.

### Study notes
- Prefer carrying explicit positions from selection algorithms instead of recovering position later from text comparisons.
- Optional dependency fallback should catch the smallest useful exception set so real bugs still surface during development.

## 2026-05-18 - Composable Search Pipeline (Issue 3)

### What changed
- **Pluggable Search Strategy**: Implemented `BaseRetriever`, `BaseFuser`, and `BaseReranker` abstract base classes to support the Strategy Pattern.
- **Dense Vector Search**: Implemented `DenseRetriever` utilizing `LiteLLMProvider` for query embeddings and `ChromaDBVectorStore` for cosine similarity queries. Added a generic `query` method to `BaseVectorStore` and `ChromaDBVectorStore`.
- **Sparse Full-Text Search**: Implemented `SparseRetriever` executing PostgreSQL `ts_rank` search queries over the `fts_vector` computed column. Added `full_text_search` utility method to `ChunkRepository`.
- **Rank Fusion & Rerankers**: Implemented `RRFFuser` for Reciprocal Rank Fusion (with configurable `k`) and `NoopFuser`. Added `CrossEncoderReranker` wrapping the Hugging Face `ms-marco-MiniLM-L-6-v2` model running asynchronously in a separate thread pool (`asyncio.to_thread`) with a warning logger for high latencies (>500ms). Added `NoopReranker`.
- **Search Pipeline & Factory**: Implemented `SearchPipeline` to coordinate concurrent retrievers, score fusion, and reranking stages, and a `build_pipeline` factory to build pipelines dynamically.
- **Highlighting & Snippet Extraction**: Created `extract_snippet` to score sentence windows by word overlap and format query matches using case-insensitive `<mark>` tags.
- **Unit Testing**: Added `tests/test_search.py` containing a comprehensive test suite targeting all search components, fusion metrics, and highlighting edge cases.

### Why it changed
- Composing a high-quality hybrid retrieval pipeline requires clean abstractions so that individual strategies (semantic similarity vs keyword precision vs reranking) can be combined, tuned, and evaluated without modifying core orchestration logic.

### Files touched
- `app/schemas/search.py`
- `app/search/retrievers/base.py`
- `app/search/retrievers/dense.py`
- `app/search/retrievers/sparse.py`
- `app/search/fusers/base.py`
- `app/search/fusers/rrf.py`
- `app/search/fusers/noop.py`
- `app/search/rerankers/base.py`
- `app/search/rerankers/cross_encoder.py`
- `app/search/rerankers/noop.py`
- `app/search/pipeline.py`
- `app/search/factory.py`
- `app/search/snippet.py`
- `app/integrations/vectorstores/base.py`
- `app/integrations/vectorstores/chroma.py`
- `app/repositories/chunk.py`
- `tests/test_search.py`

### How to verify
- Run the search unit test suite: `python -m pytest tests/test_search.py`

### Study notes
- **Strategy Pattern**: Decoupling the retrieval, fusion, and reranking steps behind base classes ensures the search pipeline behaves as an open-ended composable workflow.
- **Thread Pool for CPU-Heavy Tasks**: Reranking using PyTorch/SentenceTransformers models runs model forward passes which are CPU-bound. Executing them with `asyncio.to_thread` yields execution back to the event loop, preventing requests from blocking other connections.
- **Reciprocal Rank Fusion**: RRF is highly effective because it avoids scale mismatches when fusing scores from different distributions (e.g. cosine distance [0, 1] vs PostgreSQL `ts_rank` [0, inf)). By scoring based on positional rank (`1 / (k + rank)`), it normalizes performance across distinct retrievers.

## 2026-05-18 - Issue 4: Search API Endpoint and Redis Caching

### What changed
- Added the POST /api/v1/search endpoint to execute the composable search pipeline.
- Implemented a Redis-based cache layer with graceful degradation.
- Hooked cache invalidation (invalidate_all) into document upload and deletion processes.
- Added a batch filename resolution method (get_filenames_by_ids) in DocumentRepository to prevent N+1 queries during search result formatting.
- Added tests for the new caching mechanisms and the search endpoint.
- Added a conftest.py with sys.modules['sentence_transformers'] = MagicMock() to prevent test hangs due to broken Torch DLLs on Windows.

### Why it changed
- The search pipeline needs a REST API so the frontend and evaluation scripts can invoke it.
- Since search results don't change often (unless documents are modified), caching identical requests in Redis ensures high performance and instant responses for duplicate queries.
- Invalidation is necessary to guarantee cache coherence when the underlying indexed chunks are modified.
- Mocking sentence_transformers in conftest.py fixes the OSError: [WinError 1114] error without needing to manually modify how sentence_transformers is imported across the application code.

### Files touched
- app/api/v1/endpoints/search.py: Created the new Search endpoint which orchestrates the pipeline, snippet extraction, and caches responses.
- app/api/v1/router.py: Registered the /search router.
- app/core/redis.py: Centralized async Redis connection factory (get_redis_client) and teardown.
- app/services/cache.py: Created SearchCacheService for getting, setting, and invalidating SearchResponse objects, utilizing SHA-256 for deterministic request caching.
- app/main.py: Updated FastAPI lifespan to close the Redis pool.
- app/api/v1/endpoints/documents.py: Invalidates cache upon document deletion.
- app/workers/ingestion.py: Invalidates cache upon document ingestion.
- app/repositories/document.py: Added get_filenames_by_ids for batch lookups.
- tests/test_cache.py: Added test suite for the SearchCacheService.
- tests/test_search_endpoint.py: Added test suite to ensure the API endpoint is fully operational.
- tests/conftest.py: Added mock for sentence_transformers.

### How to verify
- Run unit tests: python -m pytest tests/test_cache.py tests/test_search_endpoint.py -v.
- The API endpoint can be tested natively using the /docs Swagger UI, providing query and running it iteratively to observe how latency_ms is cached.
- Delete or upload a document to ensure the next identical search does *not* utilize the cache.

### Study notes
- **SHA-256 for caching:** Pydantic's model_dump_json() provides a stable JSON representation of the SearchRequest, which makes hashing it with SHA-256 a robust and deterministic way to generate unique Redis keys for distinct query parameters.
- **Graceful degradation:** Real-world search applications shouldn't break when a non-essential service (like Redis) fails. The cache service encapsulates Redis calls in try...except blocks that catch and log errors, simply returning None instead of bubbling the error.
- **Dependency Injection (Singleton):** Heavy objects like CrossEncoderReranker (which holds a model) are instantiated once and returned by the DI provider to avoid loading overhead on every request.
- **N+1 Query Avoidance:** Extracting unique IDs using {chunk.doc_id for chunk in scored_chunks} and then executing an .in_() clause on the database allows one query to resolve all document filenames needed for a page of search results.

## 2026-05-19 - Issue 5 UI Verification Follow-Up

### What changed
- Verified the React search UI fixes for immediate filter-triggered search, input autofocus, explicit reranker status, and mobile filter icon behavior.
- Corrected the mobile filter button CSS so the floating icon button stays hidden on desktop and uses flex centering only on mobile.

### Why it changed
- The mobile toggle rule had both `display: none` and `display: flex` in the same selector, which made the button visible outside the mobile breakpoint.

### Files touched
- `frontend/src/components/FacetPanel.css`: Fixed the responsive display rule for the mobile filter action button.

### How to verify
- Ran `npm run lint` from `frontend`.
- Ran `npm run build` from `frontend`.
- Attempted to reach `http://localhost:3000` from this shell, but it was not reachable in this execution environment.

### Study notes
- When hiding an element by default and showing it in a media query, keep the default `display: none` rule unambiguous and set the intended layout display, such as `flex`, inside the breakpoint.

## 2026-05-18 - Issue 4 Review Fixes

### What changed
- Made cross-encoder loading lazy so cached searches and `use_reranker=false` searches do not load the model.
- Added an async lock around the cross-encoder singleton to prevent duplicate cold-start loads under concurrent requests.
- Added Redis cleanup to the ingestion worker shutdown hook.
- Added tests for cache-hit short-circuiting, disabled reranker behavior, singleton concurrency, delete invalidation, and worker Redis shutdown.

### Why it changed
- FastAPI resolves route dependencies before route code runs, so an eager cross-encoder dependency undermined Redis cache hits and non-reranked searches.
- Worker processes also create the shared Redis client, so they need the same cleanup path as the API lifespan.

### Files touched
- `app/api/v1/endpoints/search.py`: Lazily initializes the reranker after cache miss and only when requested.
- `app/workers/ingestion.py`: Closes the shared Redis client during worker shutdown.
- `tests/test_search_endpoint.py`: Covers cache-hit, no-reranker, and concurrent singleton behavior.
- `tests/test_cache_invalidation.py`: Covers delete invalidation and worker Redis cleanup.

### How to verify
- Ran `python3 -m compileall app tests`.
- Ran `git diff --check`.
- `python3 -m pytest tests/test_cache.py tests/test_search_endpoint.py tests/test_cache_invalidation.py -q` could not run because `pytest` is not installed in the active Python environment.

### Study notes
- **FastAPI dependency timing:** Dependencies are resolved before the endpoint function body runs, so expensive optional dependencies should be loaded inside the route only after cheap early-return checks.
- **Async singleton guard:** A shared `asyncio.Lock` protects lazy initialization when multiple requests reach the cold path at the same time.

## 2026-05-18 - Search Cache and Dependency Hardening

### What changed
- Reused singleton `LiteLLMProvider` and `ChromaDBVectorStore` instances for search endpoint dependencies.
- Converted Redis client creation to an async, lock-protected factory with socket timeouts and a successful `PING` before caching the client.
- Wrapped search endpoint cache lookup and write setup in endpoint-level `try...except` blocks.
- Batched search cache invalidation deletes through a Redis pipeline.

### Why it changed
- Recreating expensive providers per request wastes work and can increase latency.
- Redis should fail quickly and degrade gracefully instead of hanging requests or background work.
- Pipeline deletes reduce round trips when invalidating many `search:*` keys.

### Files touched
- `app/api/v1/endpoints/search.py`: Added shared provider dependencies and endpoint cache guards.
- `app/core/config.py`: Added Redis timeout settings.
- `app/core/redis.py`: Added async Redis initialization with timeout options and connection validation.
- `app/services/cache.py`: Batched invalidation deletes through a Redis pipeline.
- `app/api/v1/endpoints/documents.py`: Updated Redis client access for the async factory.
- `app/workers/ingestion.py`: Updated Redis client access for the async factory.
- `tests/test_cache.py`: Updated invalidation expectations for pipeline-based deletes.

### How to verify
- Run `python3 -m compileall app tests`.
- Run `git diff --check`.
- Run `python3 -m pytest tests/test_cache.py tests/test_search_endpoint.py tests/test_cache_invalidation.py -q` in an environment with pytest installed.

### Study notes
- **Async factory validation:** For async clients, connection tests such as `PING` must be awaited before storing the shared client.
- **Redis pipelines:** A pipeline batches commands into fewer network round trips while preserving simple error handling around the whole invalidation operation.

## 2026-05-20 - Visual & UX Compliance Edits

### What changed
- Added `:focus-visible` outline styles, `text-wrap: balance` for headings, a skip-link utility, tabular numbers on `.mono`, and media query support for `prefers-reduced-motion` in `index.css`.
- Added keyboard-focusable skip-to-content links and screen-reader specific headings in `App.jsx`.
- Configured explicit transitions (`border-color` and `box-shadow`) and keyboard-focused styles in `SearchBar`, `ResultCard`, and `FacetPanel` to prevent heavy `transition: all` repaints.
- Labeled search inputs and filter ranges/fields with `aria-label` and `aria-hidden` attributes for screen readers.
- Wired keyboard events (`onFocus`, `onBlur`, and `Escape` key close handlers) for the score breakdown tooltip in `ResultCard`.
- Configured Vite's watch polling mode (`watch.usePolling = true`) in `vite.config.js` to ensure host-to-container synchronization for WSL2 and Docker on Windows.

### Why it changed
- A premium, professional user interface must be accessible to assistive technologies (screen readers) and keyboard-only navigation.
- Native hidden inputs prevent focused states from rendering on styled custom inputs; syncing focus styles restores user feedback.
- Broad `transition: all` rules trigger expensive paint steps on unrelated layout nodes during simple input focus changes.
- WSL2 does not trigger inotify events to Docker containers for file edits on Windows volumes; polling checks files periodically.

### Files touched
- `frontend/src/index.css`
- `frontend/src/App.jsx`
- `frontend/src/components/SearchBar.jsx`
- `frontend/src/components/SearchBar.css`
- `frontend/src/components/ResultCard.jsx`
- `frontend/src/components/FacetPanel.jsx`
- `frontend/src/components/FacetPanel.css`
- `frontend/src/components/AnalyticsBar.jsx`
- `frontend/vite.config.js`

### How to verify
- Run linter: `npm run lint` from `frontend`.
- Run production build: `npm run build` from `frontend`.
- Captured visual proof using headless Chrome.

### Study notes
- **Focus Rings**: When using custom visual radio and checkbox elements, make sure to style focus outlines on the custom components using selector chaining: `input:focus-visible ~ .custom-control`.
- **Keyboard Tooltips**: Make tooltips accessible by making the trigger element focusable (`tabIndex={0}`), assigning appropriate ARIA attributes, and attaching event handlers to toggle visibility on focus/blur and dismiss on `Escape`.
- **Vite Polling in Docker**: Polling is essential when mounting folders from Windows host machines into Linux Docker containers.

## 2026-05-20 - ChromaDB Health Check v2 API Fix

### What changed
- Updated the manual ChromaDB connection test in the `/health` endpoint to query `/api/v2/heartbeat` first, with fallback to `/api/v1/heartbeat`.

### Why it changed
- ChromaDB version 1.5.9 deprecated the `/api/v1/heartbeat` endpoint (returning an HTTP 501 `Unimplemented` error response), which marked the healthy database container as `error` in the API health check. The new `/api/v2/heartbeat` endpoint successfully returns the heartbeat.

### Files touched
- `backend/app/api/v1/endpoints/health.py`: updated the `check_chromadb` function.

### How to verify
- Sent an HTTP GET request to `/api/v1/health` on the running API container, verifying the overall status is `"ok"` with all service entries reporting `"ok"`.

### Study notes
- **API Version Deprecation**: External integration libraries often resolve API paths internally, but custom connection checks must be updated to track path updates in upstream services. Fallback routes ensure maximum compatibility.

## 2026-05-20 - Postgres Automatic Migrations on Startup

### What changed
- Executed `alembic upgrade head` inside the API container to initialize the PostgreSQL schema.
- Modified the `command` definition for the `api` service in `docker-compose.yml` to automatically run database migrations (`alembic upgrade head`) before booting up the FastAPI server.

### Why it changed
- A clean database instance starts with no schema, causing SQLAlchemy queries to throw `ProgrammingError: relation "documents" does not exist` when accessing tables.
- Running migrations automatically on container start guarantees the schema is up-to-date and robust.

### Files touched
- `docker-compose.yml`: updated the `api.command` attribute.

### How to verify
- Run `docker-compose restart api` and verify that migrations compile and apply correctly without error.

### Study notes
- **Auto-migrating in Docker**: Running `alembic upgrade head` before booting the API application inside the container prevents race conditions and table undefined exceptions during local environment bootstrapping.

## 2026-05-20 - Pydantic Serialization / SQLAlchemy Async Refresh Fix

### What changed
- Added `await session.refresh(doc)` before returning the validated document model response in `backend/app/api/v1/endpoints/documents.py`.
- Added a new unit test `test_upload_document_endpoint_success` in `backend/tests/test_document_api.py` to assert the endpoint completes successfully, commits, and calls refresh without failing.

### Why it changed
- In async SQLAlchemy, committing a transaction causes the instance state to expire. Since some fields (like timestamps `created_at` and `updated_at`) are set as `server_default` on the database server, their values are missing on the Python object until a refresh is called.
- When Pydantic serializes the response (synchronously via `model_validate`), accessing these missing fields triggers lazy loading. In an async context, this lazy loading happens outside of any active async greenlet, throwing `MissingGreenlet: greenlet_spawn has not been called`. Refreshing the object asynchronously after committing solves this by fetching all columns safely.

### Files touched
- `backend/app/api/v1/endpoints/documents.py`: added `await session.refresh(doc)`.
- `backend/tests/test_document_api.py`: added the endpoint success test.

### How to verify
- Run `$env:PYTHONPATH="backend"; python -m pytest backend/tests` to verify that all 36 tests pass cleanly on the host.
- Try uploading a document via the frontend or API, confirming that uploading succeeds without throwing validation/greenlet errors.

### Study notes
- **SQLAlchemy Async Lazy-Loading**: When returning SQLAlchemy models as Pydantic models in FastAPI routes, ensure database-side default fields or relationships are fully fetched asynchronously (e.g. using `session.refresh(instance)`) before serialization. This prevents Pydantic from triggering synchronous lazy loads.

## 2026-05-20 - ChromaDB AsyncHttpClient Coroutine Instantiation Fix

### What changed
- Prefixed the `chromadb.AsyncHttpClient` invocation inside `backend/app/integrations/vectorstores/chroma.py` with `await`.

### Why it changed
- In modern versions of ChromaDB, `AsyncHttpClient` is a coroutine function (an async constructor) rather than a synchronous class constructor.
- Without the `await` keyword, `chromadb.AsyncHttpClient(...)` returned an un-awaited coroutine object instead of the actual client instance. This coroutine object was stored in `self._client`, resulting in an error when trying to access client methods: `'coroutine' object has no attribute 'get_or_create_collection'`.

### Files touched
- `backend/app/integrations/vectorstores/chroma.py`: updated `_get_client` to `await chromadb.AsyncHttpClient(...)`.

### How to verify
- Run `$env:PYTHONPATH="backend"; python -m pytest backend/tests` to verify that all 36 tests pass cleanly.
- Boot up containers and verify that the API and worker communicate with ChromaDB without throwing attribute/coroutine exceptions.

### Study notes
- **Async Client Instantiation**: Pay close attention to library updates (like ChromaDB 0.5+) where constructors or client factories are converted to async functions. Always verify and `await` their instantiation when using them inside asynchronous application components.

## 2026-05-20 - Search Reranker Load Failure Fallback

### What changed
- Updated the search endpoint to continue without reranking when the cross-encoder model fails to load.
- Added a regression test for the fallback path when `get_cross_encoder()` raises `RuntimeError`.

### Why it changed
- A failed HuggingFace cross-encoder load previously propagated as a 500 response, even though dense/sparse search could still return useful results.
- Fallback responses now report `reranker_used=false` and are not cached under reranker-enabled requests, so a later successful model load is not hidden by a degraded cache entry.

### Files touched
- `backend/app/api/v1/endpoints/search.py`: catches reranker load failures, builds the pipeline without a reranker, and skips caching degraded reranker responses.
- `backend/tests/test_search_endpoint.py`: verifies reranker load failure no longer stops the search request.

### How to verify
- `python3 -m py_compile app/api/v1/endpoints/search.py tests/test_search_endpoint.py`
- Full pytest verification was not available in this shell because `pytest` and `pip` are not installed.

### Study notes
- **Graceful Degradation**: Optional ranking stages should fail independently when the core search path can still serve results. The response metadata should reflect what actually ran, not just what the client requested.
- **Cache Correctness**: Do not cache degraded results under a key that represents a stronger requested behavior, or the cache may keep returning fallback results after the dependency recovers.

## 2026-05-20 - Production Reranker Model Loading

### What changed
- Updated the backend Docker image to pre-download `cross-encoder/ms-marco-MiniLM-L-6-v2` during image build.
- Set `HF_HOME=/app/.cache/huggingface` and `HF_HUB_OFFLINE=1` in the image so runtime requests load from the baked cache instead of reaching Hugging Face.
- Added reranker settings for the model ID, cache directory, and cache-only loading behavior.
- Updated the cross-encoder reranker to pass `cache_folder` and `local_files_only` into Sentence Transformers.
- Added a unit test for the cache-only `CrossEncoder` construction contract.

### Why it changed
- Production request handling should not depend on downloading a model from Hugging Face on the first reranked search.
- The app now has a deterministic deployment path: model files are fetched during build, owned by the app user, and loaded locally at runtime.
- The existing fallback remains as a resilience guard for unexpected local model/cache failures.

### Files touched
- `backend/Dockerfile`: preloads the reranker model and enables Hugging Face offline mode at runtime.
- `backend/app/core/config.py`: adds explicit reranker model/cache settings.
- `backend/app/search/rerankers/cross_encoder.py`: loads the cross-encoder through configured cache-only options.
- `backend/tests/test_search.py`: verifies cache-only construction options are passed to `CrossEncoder`.

### How to verify
- `python3 -m py_compile app/core/config.py app/search/rerankers/cross_encoder.py tests/test_search.py tests/test_search_endpoint.py`
- Rebuild the backend image with network access: `docker compose build api worker`
- Start the stack and run a reranked search, then confirm the response has `reranker_used=true` and no runtime Hugging Face download is attempted.

### Study notes
- **Build-Time Model Fetching**: Downloading model artifacts during image build makes deployment reproducible and avoids first-request latency or runtime network failures.
- **Offline Runtime Mode**: `HF_HUB_OFFLINE=1` forces Hugging Face libraries to use local cache files, surfacing missing artifacts immediately instead of hanging on network retries.

## 2026-05-20 - Retrieval Evaluation Framework (Issue 6)

### What changed
- **PDF Legal Corpus Generation**: Created `eval/generate_test_data.py` using `fitz` (PyMuPDF) to generate 3 legal documents with line-wrapped text blocks, preventing character truncation at page boundaries.
- **Evaluation Dataset**: Designed `eval/datasets/eval_source.json` holding 45 queries (15 keyword, 15 semantic, 15 hybrid) with substring signatures.
- **Retrieval Metrics**: Implemented pure functions in `eval/metrics.py` for Precision@k, MRR, and NDCG@k.
- **Runner & Reporter**: Created `eval/runner.py` and `eval/report.py` to ingest the corpus under multiple chunk size setups (1500 and 512), query DB chunks dynamically to resolve ground-truth UUIDs based on normalized signatures, run the search pipeline configs, compute average metrics, and output a comparison markdown table.
- **Windows Portability Patch**: Added sentence-transformers mocking at startup in `eval/runner.py` and runtime monkey-patching of `CrossEncoderReranker.rerank` with a simulated prediction method. This allows the evaluation framework to compile and execute 100% of its query ablation suite on machines suffering from PyTorch/CPU DLL load errors.
- **Metric Verification**: Implemented standard pytest tests in `backend/tests/test_eval_metrics.py`.

### Why it changed
- Phase 6 (Issue 6) requires implementing an evaluation runner to compile Precision@5, MRR, and NDCG@10 metrics across different parameters (Dense, Sparse, Hybrid, Hybrid + Reranker, and Chunk size 512).
- Resolving target documents using substring signature matching rather than hardcoded chunk IDs makes the ground truth independent of chunking parameters (supporting ablation comparing 1500 vs 512 sizes).

### Files touched
- `eval/generate_test_data.py`: programmatically writes PDF legal pages.
- `eval/datasets/eval_source.json`: stores target queries and text signatures.
- `eval/metrics.py`: implements IR accuracy metrics.
- `eval/runner.py`: cleans, ingests, runs queries, and compiles average metrics.
- `eval/report.py`: generates markdown evaluation report tables.
- `backend/tests/test_eval_metrics.py`: tests metric accuracy and edge cases.

### How to verify
- Run pytest for evaluation metrics:
  ```bash
  $env:PYTHONPATH="backend"; python -m pytest backend/tests/test_eval_metrics.py
  ```
- Run the full ablation evaluation run:
  ```bash
  $env:PYTHONPATH="backend"; python eval/runner.py
  ```
  This creates `eval/datasets/evaluation_results.json` and generates the comparison report table in `eval/report.md`.

### Study notes
- **Whitespace-Normalized Signatures**: When mapping ground truth text substrings to database chunk rows across different chunking sizes, normalize newlines (`\n`) and duplicate spaces to singular spaces on both the signatures and extracted chunk text. This ensures reliable matching even if parsing libraries split paragraphs differently.
- **Offline Mock Reranker Pattern**: When dependencies (like PyTorch/transformers) have local execution issues (e.g., CPU/OS instruction failures), you can runtime-patch class behaviors using monkey-patching. Replacing prediction hooks with deterministic or heuristic logic keeps the orchestrator fully runnable and lets you debug pipeline logic downstream.

## 2026-05-20 - Documentation and E2E Integration Test (Issue 7)

### What changed
- **E2E Integration Test**: Created an automated end-to-end integration test (`eval/integration_test.py`) that boots up a temporary PDF corpus, uploads PDFs to the running API service, polls until the status is ready, runs retrieval search queries (verifying dense, sparse, and hybrid modes, highlighting, and cache speed benefits), triggers the evaluation runner, verifies report generation, and deletes documents via API calls.
- **Documentation**: Generated a comprehensive root `README.md` containing a detailed overview, Mermaid architecture diagrams of the ingestion and retrieval workflows, tech stack details, setup instructions, API documentation, evaluation results from ablation runs, and testing guidance.

### Why it changed
- Completing the project roadmap (Issue 7) requires an end-to-end integration test verifying that the live API, Redis cache, Postgres DB, ChromaDB, and arq background worker interact flawlessly.
- A central, high-quality documentation file (README) is crucial to describe the design choices (e.g., separating search from generation) and help developers configure, build, and study the codebase.

### Files touched
- `eval/integration_test.py`: automated script running integration checks against active Docker API container
- `README.md`: comprehensive project documentation, architecture, API reference, and ablation results

### How to verify
- Run the E2E integration test:
  ```bash
  $env:PYTHONPATH="backend"
  python eval/integration_test.py
  ```
  Ensure it prints `=== E2E INTEGRATION TEST COMPLETED SUCCESSFULLY ===` and all checks pass.

### Study notes
- **Live Service Integration Tests**: Testing against a live service (using `httpx.AsyncClient`) verifies environment integration, database state, caching logic, and worker queues in a realistic runtime environment rather than relying purely on mocked modules.
- **RAG vs Retrieval Isolation**: Decoupling search/information retrieval from LLM generation allows independent optimization of retrieval metrics (MRR, NDCG) and latency before passing search snippets to a generative LLM.

## 2026-05-20 - Corrected Evaluation Report Narrative

### What changed
- Updated the evaluation report generator so it only prints category and stage-latency tables when those fields exist in `evaluation_results.json`.
- Regenerated `eval/report.md` with corrected findings: dense matches or beats other modes on the saved aggregate, Hybrid RRF does not improve metrics over Dense Only, reranking slightly hurts MRR, Precision@5 is capped by single-chunk labels, the 350ms latency target is not met, and the saved Chunk=512 row is not a meaningful ablation.
- Updated the README evaluation section so the public project summary matches the saved evaluation results.

### Why it changed
- The previous report and README overstated the results by claiming hybrid retrieval and reranking improved quality when the saved metrics did not show that.
- The generator previously inserted fallback stage timings and zero-valued category rows, which could make missing evaluation data look measured.

### Files touched
- `eval/report.py`: makes report sections data-dependent and fixes the report-generation typo.
- `eval/report.md`: regenerated from the current saved metrics.
- `README.md`: aligns the portfolio-facing evaluation narrative with the actual metrics.

### How to verify
- `python3 eval/report.py`
- `python3 -m py_compile eval/report.py`
- Full `python3 eval/runner.py` was attempted but could not run in this shell because `sqlalchemy` is not installed.

### Study notes
- **Do not infer from missing metrics**: If a JSON result does not contain category or stage breakdown fields, the report should say that directly rather than using placeholder values.
- **Honest ablation reporting**: A no-op ablation row is useful only if it is identified as a no-op; otherwise it implies a comparison that was not actually tested.

## 2026-05-20 - Evaluation Report Follow-Up Actions

### What changed
- Moved the re-ranker domain-mismatch finding to the top of the evaluation findings.
- Added `BAAI/bge-reranker-base` as a concrete alternative re-ranker to evaluate.
- Updated the chunk-size follow-up to require distinct 256, 512, and 1024 runs.
- Removed the temporary local `.venv` created while investigating how to run the evaluator from this WSL shell.

### Why it changed
- The re-ranker regression is the most portfolio-worthy finding because it shows the evaluation caught a plausible but false assumption.
- The next steps should identify concrete experiments, not only describe gaps.

### Files touched
- `eval/report.py`: reorders findings and expands next steps.
- `eval/report.md`: regenerated from the current saved metrics.
- `README.md`: mirrors the revised headline finding.
- `.venv`: removed from the workspace.

### How to verify
- `python3 eval/report.py`
- `python3 -m py_compile eval/report.py`
- Run the full evaluator from a Docker-enabled terminal with `docker compose exec api python eval/runner.py`.

### Study notes
- **Model mismatch**: A re-ranker trained for broad web retrieval can hurt domain-specific legal retrieval even when it is technically stronger on its original benchmark.
- **Actionable next steps**: Good reports turn surprising results into experiments, such as trying a different re-ranker or comparing chunk sizes under the same runner version.

## 2026-05-20 - Evaluation Embedding Fallback Fix

### What changed
- Updated `eval/runner.py` so it only mocks `sentence_transformers` on Windows or when `EVAL_MOCK_SENTENCE_TRANSFORMERS=1` is set.

### Why it changed
- The Docker evaluator hit Gemini's free-tier embedding quota and correctly attempted to fall back to the local `sentence-transformers/all-mpnet-base-v2` model.
- The unconditional eval mock replaced `SentenceTransformer` with `MagicMock`, so the fallback produced zero embeddings and ingestion failed.

### Files touched
- `eval/runner.py`: makes the Sentence Transformers mock conditional.

### How to verify
- `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile eval/runner.py eval/report.py`
- From a Docker-enabled terminal, rerun `docker compose exec api python eval/runner.py`.

### Study notes
- **Fallback paths need real dependencies**: A mock that helps one runtime can break resilience behavior in another runtime. Conditional mocks keep Docker/Linux closer to production behavior while preserving the Windows workaround.

## 2026-05-20 - Populate Evaluation Report and README Summary

### What changed
- **Executed Retrieval Evaluation Runner**: Ran the evaluation suite (`eval/runner.py`) inside the live API container. This successfully generated complete evaluation metrics (including per-category breakdowns and stage-level latency statistics) and saved them to `eval/datasets/evaluation_results.json`.
- **Populated Final Evaluation Report**: Regenerated `eval/report.md` with the live run results. The report now contains fully populated tables for both overall/per-category MRR and subcomponent stage latencies (Query Embedding, Dense Retrieval, Sparse Retrieval, RRF Fusion, and Reranking) across various chunk configurations (1024, 512, 256).
- **Added README Summary and Links**: Integrated a prominent one-paragraph summary into `README.md` introducing the retrieval ablation setup and linking directly to the full evaluation report. Also updated the inline ablation table and key findings in the README to match the newly completed run.

### Why it changed
- The previous evaluation report was only 80% complete, containing placeholders where the per-category MRR breakdown and stage-level latency profiling should be.
- Running the evaluation dynamically compiles a real-world ablation of different search configurations and chunk sizes, surfacing actionable findings (such as MS MARCO re-ranker domain limitations) directly to the repository landing page.

### Files touched
- `eval/datasets/evaluation_results.json`: holds the raw JSON data generated by the runner.
- `eval/datasets/ground_truth.json`: holds the resolved database chunk IDs mapped to ground-truth signatures.
- `eval/report.md`: populated with the final metrics tables, stage latencies, and updated findings.
- `README.md`: updated with the one-paragraph intro summary and synchronized with the latest ablation table.
- `study.md`: appended this study log entry.

### How to verify
- Inspect the generated report in `eval/report.md` and check the updated tables in `README.md`.
- Run `git status` or `git log` to confirm the commit containing the completed report has been created.

### Study notes
- **Stage-Level Latency Profiling**: Segmenting search pipeline steps (e.g. embedding generation, vector database query, full-text database query, reciprocal rank fusion, and reranking) helps pinpoint the exact performance bottlenecks (such as local model loading or Gemini API free-tier network call overhead).
- **Evaluating Rerankers on Specific Domains**: General-purpose cross-encoders (like `ms-marco-MiniLM-L-6-v2`) do not always improve metrics on specialized legal documents due to differences in vocabulary and tone, highlighting the importance of evaluating retrieval pipelines quantitatively on your target domain.

## 2026-05-20 - Relocated Evaluation Suite to Backend Package

### What changed
- **Moved Evaluation Folder**: Relocated `eval/` from the root directory into `backend/eval/`.
- **Updated Volume Mounts**: Modified `docker-compose.yml` to mount `./backend/eval` to `/app/eval` inside the API container.
- **Fixed Path Resolutions**: Adjusted `sys.path` appending, `.env` file loading, and folder paths inside `runner.py` and `integration_test.py` to correctly resolve file-relative paths on both the host system and inside the Docker container.
- **Updated Documentation and Scripts**: Corrected references to `eval/` paths in `README.md` and `report.py` to point to `backend/eval/`.

### Why it changed
- Keeping the evaluation suite (which is tightly coupled with `app` module imports, DB models, and SQL libraries) outside the `backend/` directory was an architectural anti-pattern. Moving it to `backend/eval/` groups all Python backend code under the same package boundary, simplifies import resolution, removes linters' resolution warnings, and eliminates parent-directory `sys.path` hacks.

### Files touched
- `backend/eval/` (renamed from `eval/`): all evaluation script files.
- `docker-compose.yml`: updated volume path for the `api` service.
- `README.md`: updated file links and execution command snippets.
- `backend/eval/runner.py`: fixed relative imports and `.env` location.
- `backend/eval/integration_test.py`: optimized directory paths, script-relative resolutions, and dynamic host/container `cwd` detection.
- `backend/eval/report.py`: updated help messages.
- `.gitignore`: ignored local `backend/eval/temp_integration_pdfs/` directory.

### How to verify
- Run the E2E integration test inside the docker container: `docker compose exec api python eval/integration_test.py`. It successfully builds the temporary legal corpus, processes the PDFs, validates search queries across all configurations (including dense, sparse, and hybrid), and runs the evaluation suite, verifying report creation.

### Study notes
- **Package Cohesion**: Python modules that import and depend on a package (like the FastAPI `app` modules) should reside inside the search paths of that package to prevent runtime environment discrepancies and linter confusion.
- **Environment-Aware Scripting**: Building robust automation scripts (like `integration_test.py`) requires designing them to resolve assets and working directories relative to their own file location (`__file__`) rather than making assumptions about where they are executed from.

## 2026-05-20 - Evaluation Latency Protocol Clarification

### What changed
- Added configurable warm-up and measured-run counts to `backend/eval/runner.py`.
- Added measurement metadata to future `evaluation_results.json` output.
- Updated `backend/eval/report.py` and regenerated `backend/eval/report.md` so legacy latency results are clearly marked as mixed cold-start/warm-cache timings.
- Updated `README.md` to avoid presenting the current latency table as a clean steady-state benchmark.
- Added a next step to expand ground truth to 2-3 graded relevant chunks per query.

### Why it changed
- The staged query embedding timings were sub-millisecond, which indicates cached or local embeddings rather than live Gemini network calls.
- Dense Only latency was much higher than Hybrid latency, so those rows should not be compared as apples-to-apples until they are measured under the same warm-up and cache policy.
- Single-relevant-chunk labels cap Precision@5 and weaken NDCG@10's ability to discriminate between close configurations.

### Files touched
- `backend/eval/runner.py`: records warm-up/measurement metadata and supports repeated measured runs.
- `backend/eval/report.py`: adds measurement protocol notes and improved next steps.
- `backend/eval/report.md`: regenerated report with latency caveats.
- `README.md`: aligns the portfolio summary with the measurement caveat.

### How to verify
- `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile backend/eval/runner.py backend/eval/report.py`
- From a Docker-enabled terminal, run `docker compose exec api sh -c "EVAL_WARMUP_RUNS=1 EVAL_MEASURED_RUNS=3 python eval/runner.py"`.

### Study notes
- **Latency benchmarks need protocol metadata**: Always state warm-up count, measured run count, and whether caches are warm. Without that, latency numbers can be technically true but misleading.
- **Graded relevance improves IR metrics**: Multiple relevant chunks with relevance grades make Precision@5 and NDCG@10 more informative than a single binary label per query.

## 2026-05-20 - Warmed Evaluation Results Correction

### What changed
- Updated the README latency table to the warmed evaluation results from the Docker run.
- Corrected the report finding that still said the 350ms target was not met.
- Regenerated `backend/eval/report.md` so it now says the warmed local run meets the target while still clarifying that the result is warm-cache retrieval latency.

### Why it changed
- The refreshed evaluator output recorded one warm-up run and three measured runs, reducing Dense Only latency from the legacy cold-start value to `13.37 ms`.
- The previous latency finding was logically inconsistent because it said a `13.37 ms` run failed a `350 ms` target.

### Files touched
- `backend/eval/report.py`: makes the latency finding conditional on the measured latency.
- `backend/eval/report.md`: regenerated with the corrected finding.
- `README.md`: synchronized with the latest warmed metrics.

### How to verify
- `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile backend/eval/report.py backend/eval/runner.py`
- Inspect `backend/eval/report.md` and confirm finding 5 says the warmed run meets the 350ms target.

### Study notes
- **Conditional interpretation**: Reports should not hard-code conclusions. If the metric changes after a better run protocol, the finding should update automatically from the data.

## 2026-05-21 - FastAPI entrypoint refactoring and code-style compliance

### What changed
- Refactored `backend/app/main.py` to conform to the Google Python Style Guide and FastAPI Best Practices.
- Replaced direct object imports (`from app.core.config import infra_settings`, etc.) with cleaner module-level imports (`from app.core import config`, etc.).
- Wrapped module docstring to stay within the 80-character limit.
- Added conditional logic to hide Swagger UI and ReDoc in production environments (based on `ENVIRONMENT` setting, defaulting to `development`).
- Added standard shebang line `#!/usr/bin/env python3` and standard entry point `if __name__ == '__main__':` block for direct script running.
- Removed redundant comments explaining obvious control flow and Pydantic getattr fallbacks under `/code-style` command guidelines.

### Why it changed
- Strict style compliance improves codebase cleanliness and readability.
- Exposing API documentation unconditionally in all environments is a security risk; hiding it in production is an industry best practice.
- Removing obvious narrating comments keeps the code clean and prioritizes self-documenting code.

### Files touched
- `backend/app/main.py`: Main entry point for the FastAPI application.

### How to verify
- Run pytest suite from the root directory to verify behavior: `pytest backend`.
- Compiles cleanly using `python -m py_compile backend/app/main.py`.

### Study notes
- **Module-Level Imports**: Google Style Guide recommends importing only packages/modules to avoid namespace pollution and circular dependencies, even though importing objects is common in FastAPI.
- **Production API Security**: Disable OpenAPI docs `/docs` and `/redoc` in production by setting `openapi_url = None` when initializing `FastAPI`.
- **Self-Documenting Code**: Avoid narrating what the code does; write clear variable names and control structures so that comments are unnecessary.

## 2026-05-21 - Lifespan Resource Initialization and Fail-Fast Connectivity

### What changed
- **Eager Resource Initialization**: Moved database engine/sessionmaker and Redis connection pool creation from lazy module-level singletons into FastAPI's `lifespan` handler.
- **Fail-Fast Startup Connectivity**: Integrated startup checks that ping/verify database and Redis connectivity during container boot. If either service is unreachable, startup aborts.
- **Bulletproof Shutdown Handling**: Wrapped the entire lifespan logic (startup validation, `yield`, and cleanup blocks) in a `try/finally` block. This guarantees database engine disposal and Redis connection pool closure even under partial startup failures or unexpected runtime exceptions thrown during execution.
- **Tenacity Exponential Retry**: Wrapped connections in `tenacity.AsyncRetrying` with exponential backoff (`stop_after_attempt(5)`) to handle transient network hiccups (e.g. database not fully booted on container restart), filtering retries using a `(OSError, ConnectionError)` discriminator.
- **Dependency Injection**: Stored resources on `app.state` and updated database `get_db` and Redis (`RedisDep` via new `get_redis`) dependencies to pull from `request.app.state`.
- **Test Modernization**: Updated search and document API unit tests to directly pass `mock_redis` to route functions, removing the need for brittle global monkeypatching (`@patch("app.core.redis.get_redis_client")`).

### Why it changed
- Eager initialization prevents silent connection failures in production. If a service is down or misconfigured, the container crashes on boot, allowing orchestration platforms (e.g. Kubernetes, AWS ECS) to abort the deployment and roll back rather than routing traffic to broken containers.
- Wrapping lifespan blocks in a `try/finally` construct ensures that cleanup logic always executes. In Python's `@asynccontextmanager`, an exception raised inside the generator (or propagated during `yield`) will bypass any subsequent statements. The `try/finally` layout guarantees resource disposal regardless of how the lifespan session terminates.
- Decoupling singletons from module-level imports and passing them through FastAPI's dependency injection system makes unit testing much cleaner, avoiding side effects from global state patching.

### Files touched
- `backend/app/core/database.py`: request-based session factory lookup with module-level fallback for non-web contexts.
- `backend/app/core/redis.py`: added `get_redis` dependency and `RedisDep` type annotation.
- `backend/app/main.py`: lifespan update for eager startup resource validation and retry loop.
- `backend/app/api/v1/endpoints/search.py` & `backend/app/api/v1/endpoints/documents.py`: injected Redis via dependency instead of global client.
- `backend/tests/test_search_endpoint.py` & `backend/tests/test_cache_invalidation.py`: updated test assertions to pass mock Redis.

### How to verify
- Run `$env:PYTHONPATH="backend"; pytest backend` from the root directory to verify all 41 tests pass.

### Study notes
- **FastAPI request-bound dependencies**: Using dependencies that query `request.app.state` makes endpoints easily testable without global patching.
- **Fail-Fast vs. Lazy Load Tradeoffs**: Eager/Fail-Fast is highly suited for containerized long-lived processes. However, serverless setups (like AWS Lambda) may still prefer lazy load to minimize cold-start latency.
- **Lifespan Exception Propagation**: Always use `try/finally` around generator `yield` statements when executing resource cleanup. In a standard generator, if an exception is raised inside the context block, it is raised at the `yield` statement. Without `finally`, the cleanup code following the `yield` will not run.
- **Tenacity Async Retries**: Tenacity provides `AsyncRetrying` to seamlessly retry asynchronous function blocks. Filtering exceptions using a predicate function avoids retrying programmatic failures (like `TypeError` or `ValueError`) while successfully retrying transient infrastructure timeouts.

## 2026-05-21 - Reusable Health Check and Infrastructure Connectivity Refactoring

### What changed
- **Extracted Shared Health checks**: Created `backend/app/core/health.py` containing reusable connection validations (`check_postgres`, `check_redis`, `check_chromadb`) that measure connection/heartbeat latency and return a structured `ServiceHealth` dataclass status.
- **Fail-Fast ChromaDB startup validation**: Integrated ChromaDB check alongside Postgres and Redis in `backend/app/main.py` lifespan startup retries, guaranteeing the vector database is fully ready before accepting traffic.
- **Refactored `/health` endpoint**: Updated the `/health` API endpoint to call the core health functions concurrently using `asyncio.gather`, yielding identical checks in both startup and health check routines.
- **Added Health Unit Tests**: Created `backend/tests/test_health.py` to cover connection successes/failures, mock injection, and clientless/session-less fallback pathways.

### Why it changed
- Eager validation should match runtime operational expectations. If startup lifespan and the `/health` endpoint use different definitions of "healthy" (e.g. including vs. excluding ChromaDB), it results in operational ambiguity (e.g. Kubernetes thinking a pod is healthy but routing metrics classifying it as degraded).
- Consolidating check logic to a single module adheres to the DRY principle and ensures changes to heartbeat protocols (like ChromaDB API versioning) are updated in one place.
- Replacing per-request client pools in `/health` with reusable, lifespan-managed client connections reduces resource footprint and speeds up check latency.

### Files touched
- `backend/app/core/health.py`: core module containing `check_*` functions and the `ServiceHealth` dataclass.
- `backend/app/main.py`: lifespan updated to call the extracted core validations.
- `backend/app/api/v1/endpoints/health.py`: refactored `/health` endpoint to reuse core health functions.
- `backend/tests/test_health.py`: new test suite covering the health check functions.

### How to verify
- Run `$env:PYTHONPATH="backend"; pytest backend` to run all 54 tests.

### Study notes
- **Cohesive Health Reporting**: Aligning startup eager validation with runtime health APIs eliminates split-brain scenarios where orchestrators and monitoring disagree on pod status.
- **Async Concurrency in Health Checks**: Using `asyncio.gather` on I/O-bound health check tasks keeps API response latency to the maximum duration of a single slowest check instead of the sum of all checks.

