"""Search API endpoint."""

from __future__ import annotations

import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_cross_encoder, get_llm_provider, get_vector_store
from app.core.database import DbSessionDep
from app.core.redis import get_redis_client
from app.integrations.llm.litellm import LiteLLMProvider
from app.integrations.vectorstores.chroma import ChromaDBVectorStore
from app.repositories.document import DocumentRepository
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.search.factory import build_pipeline
from app.search.snippet import extract_snippet
from app.services.cache import SearchCacheService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    session: DbSessionDep,
    llm_provider: Annotated[LiteLLMProvider, Depends(get_llm_provider)],
    vector_store: Annotated[ChromaDBVectorStore, Depends(get_vector_store)],
) -> SearchResponse:
    """Execute a search query against the index."""

    cache: SearchCacheService | None = None
    try:
        cache = SearchCacheService(await get_redis_client())
        cached_response = await cache.get(request)
        if cached_response is not None:
            return cached_response
    except Exception:
        logger.warning("Cache lookup failed, continuing without cache", exc_info=True)

    start = time.perf_counter()

    cross_encoder = None
    reranker_used = False
    if request.use_reranker:
        try:
            cross_encoder = await get_cross_encoder()
            reranker_used = True
        except RuntimeError:
            logger.error(
                "Cross-encoder reranker unavailable, continuing without reranking",
                exc_info=True,
            )

    pipeline = build_pipeline(
        search_mode=request.search_mode,
        use_reranker=reranker_used,
        llm_provider=llm_provider,
        vector_store=vector_store,
        session=session,
        cross_encoder=cross_encoder,
    )

    scored_chunks = await pipeline.execute(
        query=request.query,
        top_k=request.top_k,
        doc_ids=request.doc_ids,
    )

    # Batch-resolve filenames
    doc_repo = DocumentRepository(session)
    unique_doc_ids = {chunk.doc_id for chunk in scored_chunks}
    filename_map = await doc_repo.get_filenames_by_ids(unique_doc_ids)

    # Build results with snippets
    results = [
        SearchResult(
            chunk_id=chunk.id,
            doc_id=chunk.doc_id,
            doc_filename=filename_map.get(chunk.doc_id, "unknown"),
            page_num=chunk.page_num,
            snippet=extract_snippet(chunk.text, request.query),
            text=chunk.text,
            score=chunk.final_score,
            dense_score=chunk.dense_score,
            sparse_score=chunk.sparse_score,
            rerank_score=chunk.rerank_score,
        )
        for chunk in scored_chunks
    ]

    elapsed_ms = (time.perf_counter() - start) * 1000

    response = SearchResponse(
        results=results,
        query=request.query,
        total_results=len(results),
        latency_ms=round(elapsed_ms, 2),
        search_mode=request.search_mode.value,
        reranker_used=reranker_used,
    )

    # Cache the result before returning
    if cache is not None and reranker_used == request.use_reranker:
        try:
            await cache.set(request, response)
        except Exception:
            logger.warning("Cache write failed after search", exc_info=True)

    return response
