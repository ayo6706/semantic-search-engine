import uuid
from sqlalchemy import bindparam, delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import ARRAY, UUID, insert

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

    async def full_text_search(
        self,
        query: str,
        top_k: int = 50,
        doc_ids: list[str] | None = None
    ) -> list[dict]:
        """Execute ts_rank full-text search against the chunks table.

        Args:
            query: The search query string.
            top_k: Maximum number of results to return.
            doc_ids: Optional list of document UUID strings to filter by.

        Returns:
            List of dictionaries containing id, doc_id, text, page_number, and rank.
        """
        # Build the base SQL query using plainto_tsquery for natural language search
        sql = """
            SELECT
                id,
                doc_id,
                text,
                page_number,
                ts_rank(fts_vector, plainto_tsquery('english', :query)) AS rank
            FROM chunks
            WHERE fts_vector @@ plainto_tsquery('english', :query)
        """
        params = {"query": query, "top_k": top_k}

        # Add optional document filtering
        if doc_ids:
            sql += " AND doc_id = ANY(:doc_ids)"
            validated_doc_ids = []
            for doc_id in doc_ids:
                try:
                    validated_doc_ids.append(uuid.UUID(str(doc_id)))
                except ValueError as exc:
                    raise ValueError(
                        f"doc_ids must contain valid UUID strings; got {doc_id!r}."
                    ) from exc
            params["doc_ids"] = validated_doc_ids

        # Order by rank and limit
        sql += " ORDER BY rank DESC LIMIT :top_k"

        stmt = text(sql)
        if doc_ids:
            stmt = stmt.bindparams(
                bindparam("doc_ids", type_=ARRAY(UUID(as_uuid=True)))
            )

        result = await self.session.execute(stmt, params)

        # Convert rows to dictionaries
        return [
            {
                "id": str(row.id),
                "doc_id": str(row.doc_id),
                "text": row.text,
                "page_number": row.page_number,
                "rank": float(row.rank)
            }
            for row in result
        ]
