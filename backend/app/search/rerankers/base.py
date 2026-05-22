from abc import ABC, abstractmethod

from app.schemas.search import ScoredChunk
from app.search.types import StaleChecker


class BaseReranker(ABC):
    """Abstract base class for reranking strategies."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        chunks: list[ScoredChunk],
        top_n: int = 10,
        is_stale: StaleChecker | None = None,
    ) -> list[ScoredChunk]:
        """Rerank a list of chunks based on a query.

        Args:
            query: The search query string.
            chunks: The candidate chunks to rerank.
            top_n: The number of top chunks to return after reranking.
            is_stale: Optional callable that returns True if the request
                should stop before expensive reranking work.

        Returns:
            A list of the top N reranked ScoredChunk objects.
        """
        pass
