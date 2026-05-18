from app.schemas.search import ScoredChunk
from app.search.fusers.base import BaseFuser


class RRFFuser(BaseFuser):
    """Reciprocal Rank Fusion (RRF) fuser.
    
    Combines results from multiple retrievers using the RRF algorithm:
    score = sum(1 / (k + rank)) for each retriever's ranking.
    """

    def __init__(self, k: int = 60):
        self.k = k

    def fuse(self, result_sets: list[list[ScoredChunk]]) -> list[ScoredChunk]:
        """Fuse multiple result sets using Reciprocal Rank Fusion."""
        if not result_sets:
            return []

        # Map to accumulate chunks and scores by ID
        # id -> ScoredChunk (merged)
        fused_chunks: dict[str, ScoredChunk] = {}

        for results in result_sets:
            for rank, chunk in enumerate(results):
                if chunk.id not in fused_chunks:
                    # Clone the chunk to avoid mutating the original
                    fused_chunks[chunk.id] = ScoredChunk(
                        id=chunk.id,
                        doc_id=chunk.doc_id,
                        text=chunk.text,
                        page_num=chunk.page_num,
                        dense_score=chunk.dense_score,
                        sparse_score=chunk.sparse_score,
                        fused_score=0.0,
                    )
                else:
                    # Merge scores if they exist on the new chunk but not on the accumulated one
                    if chunk.dense_score is not None and fused_chunks[chunk.id].dense_score is None:
                        fused_chunks[chunk.id].dense_score = chunk.dense_score
                    if chunk.sparse_score is not None and fused_chunks[chunk.id].sparse_score is None:
                        fused_chunks[chunk.id].sparse_score = chunk.sparse_score

                # Accumulate RRF score
                # rank is 0-indexed, RRF usually uses 1-indexed rank
                rrf_score = 1.0 / (self.k + rank + 1)
                
                # fused_score will be initialized to 0.0 on creation above
                fused_chunks[chunk.id].fused_score += rrf_score

        # Convert back to list and sort by fused_score descending
        fused_list = list(fused_chunks.values())
        fused_list.sort(key=lambda x: x.fused_score, reverse=True)

        return fused_list
