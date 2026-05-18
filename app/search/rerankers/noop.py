from app.schemas.search import ScoredChunk
from app.search.rerankers.base import BaseReranker


class NoopReranker(BaseReranker):
    """A reranker that passes results through unchanged, slicing to top_n.
    
    Used when reranking is disabled.
    """

    async def rerank(
        self,
        query: str,
        chunks: list[ScoredChunk],
        top_n: int = 10
    ) -> list[ScoredChunk]:
        """Return the top_n chunks without rescoring."""
        return chunks[:top_n]
