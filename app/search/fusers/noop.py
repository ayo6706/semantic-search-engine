from app.schemas.search import ScoredChunk
from app.search.fusers.base import BaseFuser


class NoopFuser(BaseFuser):
    """A fuser that simply returns the first result set.
    
    Used for single-retriever pipelines where fusion is not needed.
    """

    def fuse(self, result_sets: list[list[ScoredChunk]]) -> list[ScoredChunk]:
        """Return the first result set, or an empty list if none."""
        return result_sets[0] if result_sets else []
