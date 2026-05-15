"""SQLAlchemy model for the ``chunks`` table.

Each chunk is a segment of text extracted from a document. The
``fts_vector`` column is a PostgreSQL generated stored column that
automatically maintains a ``tsvector`` index for full-text search
without any application-side ``to_tsvector()`` calls.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Computed, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.document import Document


class Chunk(Base):
    """A text chunk extracted from a document page.

    The ``fts_vector`` column is automatically populated by PostgreSQL
    via a ``GENERATED ALWAYS AS`` stored expression. This ensures the
    tsvector is always in sync with the ``text`` column.

    Attributes:
        id: Unique chunk identifier (UUID).
        doc_id: Foreign key to the parent document.
        text: The chunk's text content.
        page_number: Page number in the source PDF.
        chunk_index: Sequential index of the chunk within the document.
        token_count: Approximate token count for the chunk text.
        fts_vector: Auto-generated tsvector for full-text search.
        created_at: Timestamp when the chunk was created.
        document: Relationship to the parent document.
    """

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
    )
    text: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int]
    chunk_index: Mapped[int]
    token_count: Mapped[int | None]
    fts_vector: Mapped[Any] = mapped_column(
        TSVECTOR(),
        Computed("to_tsvector('english', text)", persisted=True),
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
    )

    document: Mapped[Document] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("chunks_fts_idx", "fts_vector", postgresql_using="gin"),
        Index("chunks_doc_id_idx", "doc_id"),
    )
