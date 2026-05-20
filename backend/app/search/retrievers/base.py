from abc import ABC, abstractmethod

from app.schemas.search import ScoredChunk


class BaseRetriever(ABC):
    """Abstract base class for all retrievers (dense, sparse, etc.)."""

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        top_k: int = 50,
        doc_ids: list[str] | None = None
    ) -> list[ScoredChunk]:
        """Retrieve chunks relevant to the query.

        Args:
            query: The search query string.
            top_k: Maximum number of chunks to return.
            doc_ids: Optional list of document IDs to filter by.

        Returns:
            A list of ScoredChunk objects, scored by the specific retrieval method.
        """
        pass
