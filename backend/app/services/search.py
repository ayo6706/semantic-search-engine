from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import SearchCache, get_search_cache
from app.integrations.llm.base import BaseLLMProvider
from app.integrations.vectorstores.base import BaseVectorStore
from app.repositories.document import DocumentRepository
from app.schemas.search import ScoredChunk, SearchRequest, SearchResponse, SearchResult
from app.search.factory import build_pipeline
from app.search.pipeline import SearchPipelineCancelled
from app.search.rerankers.cross_encoder import CrossEncoderReranker
from app.search.snippet import extract_snippet
from app.search.types import DisconnectChecker, StaleChecker

logger = logging.getLogger(__name__)

CrossEncoderProvider = Callable[[], Awaitable[CrossEncoderReranker]]


class SearchService:
    def __init__(
        self,
        session: AsyncSession,
        llm_provider: BaseLLMProvider,
        vector_store: BaseVectorStore,
        cross_encoder_provider: CrossEncoderProvider,
    ):
        self.session = session
        self.llm_provider = llm_provider
        self.vector_store = vector_store
        self.cross_encoder_provider = cross_encoder_provider

    async def search(
        self,
        request: SearchRequest,
        is_disconnected: DisconnectChecker | None = None,
        is_stale: StaleChecker | None = None,
    ) -> SearchResponse:
        cache = await self._get_cache()
        cached_response = await self._get_cached_response(cache, request)
        if cached_response is not None:
            return cached_response

        start = time.perf_counter()
        if is_stale and await is_stale():
            return self._build_cancelled_response(request, start, reranker_used=False)

        cross_encoder, reranker_used = await self._load_reranker(request)

        pipeline = build_pipeline(
            search_mode=request.search_mode,
            use_reranker=reranker_used,
            llm_provider=self.llm_provider,
            vector_store=self.vector_store,
            session=self.session,
            cross_encoder=cross_encoder,
        )
        try:
            scored_chunks = await pipeline.execute(
                query=request.query,
                top_k=request.top_k,
                doc_ids=request.doc_ids,
                is_disconnected=is_disconnected,
                is_stale=is_stale,
            )
        except SearchPipelineCancelled:
            return self._build_cancelled_response(request, start, reranker_used)

        if is_stale and await is_stale():
            return self._build_cancelled_response(request, start, reranker_used)

        response = await self._build_response(request, scored_chunks, start, reranker_used)
        await self._cache_response(cache, request, response, reranker_used)
        return response

    async def _get_cache(self) -> SearchCache | None:
        try:
            return await get_search_cache()
        except Exception:
            logger.warning("Search cache unavailable, continuing without cache", exc_info=True)
            return None

    @staticmethod
    async def _get_cached_response(
        cache: SearchCache | None,
        request: SearchRequest,
    ) -> SearchResponse | None:
        if cache is None:
            return None
        try:
            return await cache.get(request)
        except Exception:
            logger.warning("Cache lookup failed, continuing without cache", exc_info=True)
            return None

    async def _load_reranker(
        self,
        request: SearchRequest,
    ) -> tuple[CrossEncoderReranker | None, bool]:
        if not request.use_reranker:
            return None, False

        try:
            return await self.cross_encoder_provider(), True
        except Exception:
            logger.error(
                "Cross-encoder reranker unavailable, continuing without reranking",
                exc_info=True,
            )
            return None, False

    async def _build_response(
        self,
        request: SearchRequest,
        scored_chunks: list[ScoredChunk],
        start: float,
        reranker_used: bool,
    ) -> SearchResponse:
        doc_repo = DocumentRepository(self.session)
        unique_doc_ids = {chunk.doc_id for chunk in scored_chunks}
        filename_map = await doc_repo.get_filenames_by_ids(unique_doc_ids)

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
        return SearchResponse(
            results=results,
            query=request.query,
            total_results=len(results),
            latency_ms=round(elapsed_ms, 2),
            search_mode=request.search_mode.value,
            reranker_used=reranker_used,
        )

    @staticmethod
    async def _cache_response(
        cache: SearchCache | None,
        request: SearchRequest,
        response: SearchResponse,
        reranker_used: bool,
    ) -> None:
        if cache is None or reranker_used != request.use_reranker:
            return
        try:
            await cache.set(request, response)
        except Exception:
            logger.warning("Cache write failed after search", exc_info=True)

    @staticmethod
    def _build_cancelled_response(
        request: SearchRequest,
        start: float,
        reranker_used: bool,
    ) -> SearchResponse:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return SearchResponse(
            results=[],
            query=request.query,
            total_results=0,
            latency_ms=round(elapsed_ms, 2),
            search_mode=request.search_mode.value,
            reranker_used=reranker_used,
        )
