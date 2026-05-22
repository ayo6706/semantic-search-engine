from app.schemas.search import ScoredChunk
from app.search.rerankers.base import BaseReranker
from app.search.types import StaleChecker


class NoopReranker(BaseReranker):
    """A reranker that passes results through unchanged, slicing to top_n.
    
    Used when reranking is disabled.
    """

    async def rerank(
        self,
        query: str,
        chunks: list[ScoredChunk],
        top_n: int = 10,
        is_stale: StaleChecker | None = None,
    ) -> list[ScoredChunk]:
        """Return the top_n chunks without rescoring."""
        return chunks[:top_n]
