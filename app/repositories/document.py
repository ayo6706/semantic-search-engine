import uuid
from sqlalchemy import select, delete, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document

class DocumentRepository:
    """Repository for Document entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, filename: str, storage_filename: str) -> Document:
        """Create a new document record in pending state."""
        doc = Document(
            filename=filename,
            storage_filename=storage_filename,
            status="pending"
        )
        self.session.add(doc)
        await self.session.flush()
        return doc

    async def get_by_id(self, doc_id: uuid.UUID) -> Document | None:
        """Get document by ID."""
        result = await self.session.execute(
            select(Document).where(Document.id == doc_id)
        )
        return result.scalar_one_or_none()

    async def list_documents(self) -> tuple[list[Document], int]:
        """List all documents and total count."""
        result = await self.session.execute(
            select(Document).order_by(Document.created_at.desc())
        )
        docs = result.scalars().all()
        count_result = await self.session.execute(
            select(func.count()).select_from(Document)
        )
        return list(docs), count_result.scalar_one()

    async def delete(self, doc_id: uuid.UUID) -> bool:
        """Delete a document by ID."""
        result = await self.session.execute(
            delete(Document).where(Document.id == doc_id)
        )
        return result.rowcount > 0

    async def update_status(self, doc_id: uuid.UUID, status: str, error_message: str | None = None) -> bool:
        """Update document status."""
        result = await self.session.execute(
            update(Document)
            .where(Document.id == doc_id)
            .values(status=status, error_message=error_message)
        )
        return result.rowcount > 0

    async def update_counts(self, doc_id: uuid.UUID, page_count: int, chunk_count: int) -> bool:
        """Update document page and chunk counts."""
        result = await self.session.execute(
            update(Document)
            .where(Document.id == doc_id)
            .values(page_count=page_count, chunk_count=chunk_count)
        )
        return result.rowcount > 0
