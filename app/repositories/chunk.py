import uuid
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.models.chunk import Chunk


class ChunkRepository:
    """Repository for Chunk entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_insert(self, chunks_data: list[dict]) -> None:
        """Bulk insert chunks into the database.
        
        Args:
            chunks_data: List of dicts with keys:
                id (UUID), doc_id (UUID), text (str), page_number (int), chunk_index (int)
        """
        if not chunks_data:
            return
            
        stmt = insert(Chunk).values(chunks_data)
        # Use on_conflict_do_nothing because we are generating deterministic IDs
        stmt = stmt.on_conflict_do_nothing(
            constraint="uq_chunk_doc_id_index"
        )
        await self.session.execute(stmt)

    async def delete_by_doc_id(self, doc_id: uuid.UUID) -> None:
        """Delete all chunks for a given document.
        
        Idempotent operation.
        """
        stmt = delete(Chunk).where(Chunk.doc_id == doc_id)
        await self.session.execute(stmt)
