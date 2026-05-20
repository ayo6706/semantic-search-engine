from abc import ABC, abstractmethod

from app.schemas.search import ScoredChunk


class BaseReranker(ABC):
    """Abstract base class for reranking strategies."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        chunks: list[ScoredChunk],
        top_n: int = 10
    ) -> list[ScoredChunk]:
        """Rerank a list of chunks based on a query.

        Args:
            query: The search query string.
            chunks: The candidate chunks to rerank.
            top_n: The number of top chunks to return after reranking.

        Returns:
            A list of the top N reranked ScoredChunk objects.
        """
        pass
