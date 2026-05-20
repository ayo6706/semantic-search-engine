from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.chunk import ChunkRepository
from app.schemas.search import ScoredChunk
from app.search.retrievers.base import BaseRetriever


class SparseRetriever(BaseRetriever):
    """Retriever that uses PostgreSQL full-text search (tsvector/ts_rank)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.chunk_repo = ChunkRepository(session)

    async def retrieve(
        self,
        query: str,
        top_k: int = 50,
        doc_ids: list[str] | None = None
    ) -> list[ScoredChunk]:
        """Retrieve chunks using PostgreSQL full-text search."""
        if not query.strip():
            return []

        results = await self.chunk_repo.full_text_search(
            query=query,
            top_k=top_k,
            doc_ids=doc_ids
        )

        chunks = []
        for row in results:
            chunks.append(
                ScoredChunk(
                    id=row["id"],
                    doc_id=row["doc_id"],
                    text=row["text"],
                    page_num=row["page_number"],
                    sparse_score=row["rank"]
                )
            )

        return chunks
