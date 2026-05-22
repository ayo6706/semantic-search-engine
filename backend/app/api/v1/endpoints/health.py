"""Health check endpoint."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_vector_store
from app.core import health
from app.core.database import DbSessionDep
from app.integrations.vectorstores.base import BaseVectorStore

router = APIRouter(prefix="/health", tags=["health"])
VectorStoreDep = Annotated[BaseVectorStore, Depends(get_vector_store)]


@router.get(
    "",
    summary="Health check",
    description="Checks connectivity to configured infrastructure providers.",
    status_code=status.HTTP_200_OK,
)
async def health_check(
    db: DbSessionDep,
    vector_store: VectorStoreDep,
) -> dict[str, Any]:
    """Check health of all infrastructure services."""
    return await health.check_system_health(db, vector_store)
