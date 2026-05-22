import asyncio
import logging

from app.core.config import search_settings
from app.schemas.search import ScoredChunk
from app.search.fusers.base import BaseFuser
from app.search.rerankers.base import BaseReranker
from app.search.retrievers.base import BaseRetriever
from app.search.types import DisconnectChecker, StaleChecker

logger = logging.getLogger(__name__)


class SearchPipelineCancelled(Exception):
    pass


class SearchPipeline:
    """Orchestrates the execution of search strategies.

    Runs configured retrievers concurrently, fuses their results,
    and applies a reranker to the top fused candidates.
    """

    def __init__(
        self,
        retrievers: list[BaseRetriever],
        fuser: BaseFuser,
        reranker: BaseReranker
    ):
        self.retrievers = retrievers
        self.fuser = fuser
        self.reranker = reranker

    async def execute(
        self,
        query: str,
        top_k: int = 10,
        doc_ids: list[str] | None = None,
        is_disconnected: DisconnectChecker | None = None,
        is_stale: StaleChecker | None = None,
    ) -> list[ScoredChunk]:
        """Execute the search pipeline.

        Args:
            query: Search query string.
            top_k: Number of final results to return.
            doc_ids: Optional list of document IDs to filter by.
            is_disconnected: Optional async callable that returns True
                when the client has disconnected. Checked before expensive
                stages to avoid wasted work.
            is_stale: Optional callable that returns True when a newer search
                from the same client session has superseded this request.

        Returns:
            Ranked list of top_k ScoredChunk objects.
        """
        # Retrieve a larger candidate pool since fusion may surface chunks
        # that fall outside individual top_k bounds.
        retrieval_k = max(top_k * 5, 50)

        tasks = [
            r.retrieve(query, top_k=retrieval_k, doc_ids=doc_ids)
            for r in self.retrievers
        ]
        result_sets = await asyncio.gather(*tasks)

        if is_stale and await is_stale():
            logger.info("Search request became stale after retrieval, skipping reranking")
            raise SearchPipelineCancelled

        if is_disconnected and await is_disconnected():
            logger.debug("Client disconnected after retrieval, skipping fusion and reranking")
            raise SearchPipelineCancelled

        fused_results = self.fuser.fuse(list(result_sets))

        rerank_candidate_count = max(top_k, search_settings.RERANK_TOP_N)
        rerank_candidates = fused_results[:rerank_candidate_count]

        if is_stale and await is_stale():
            logger.info("Search request became stale after fusion, skipping reranking")
            raise SearchPipelineCancelled

        if is_disconnected and await is_disconnected():
            logger.debug("Client disconnected after fusion, skipping reranking")
            raise SearchPipelineCancelled

        return await self.reranker.rerank(
            query,
            rerank_candidates,
            top_n=top_k,
            is_stale=is_stale,
        )
