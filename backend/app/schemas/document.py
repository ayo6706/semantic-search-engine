from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


DocumentStatus = Literal["pending", "processing", "ready", "failed"]


class DocumentResponse(BaseModel):
    """Schema for a single document response."""
    
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    status: DocumentStatus
    page_count: int | None = None
    chunk_count: int | None = None
    error_message: str | None = None
    warning_message: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """Schema for listing documents."""

    items: list[DocumentResponse]
    total: int
