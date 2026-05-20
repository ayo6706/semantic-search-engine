"""SQLAlchemy model for the ``documents`` table.

Tracks uploaded PDF documents and their processing status through
the ingestion pipeline (pending → processing → ready | failed).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.chunk import Chunk


class Document(Base):
    """A PDF document uploaded for indexing and search.

    Attributes:
        id: Unique document identifier (UUID).
        filename: Original uploaded filename.
        storage_filename: Filename used for local storage.
        status: Processing status (pending, processing, ready, failed).
        page_count: Number of pages in the PDF.
        chunk_count: Number of text chunks created from the document.
        error_message: Error description if ingestion failed.
        warning_message: Non-fatal warning from ingestion.
        created_at: Timestamp when the document was uploaded.
        updated_at: Timestamp of the last status update.
        chunks: Related chunk records.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    filename: Mapped[str] = mapped_column(String(255))
    storage_filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    page_count: Mapped[int | None]
    chunk_count: Mapped[int | None]
    error_message: Mapped[str | None] = mapped_column(Text)
    warning_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
    )

    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
