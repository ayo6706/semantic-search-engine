"""Health check endpoint.

Verifies connectivity to all infra.
Returns a structured response indicating the status of each service.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, status

from app.core import health
from app.core.database import DbSessionDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "",
    summary="Health check",
    description="Checks connectivity to PostgreSQL, ChromaDB, and Redis.",
    status_code=status.HTTP_200_OK,
)
async def health_check(db: DbSessionDep) -> dict[str, Any]:
    """Check health of all infrastructure services.

    Args:
        db: Async database session injected by FastAPI.

    Returns:
        A dict with overall status and per-service status details.
    """
    postgres_task = health.check_postgres(db)
    redis_task = health.check_redis()
    chroma_task = health.check_chromadb()

    postgres_health, redis_health, chroma_health = await asyncio.gather(
        postgres_task, redis_task, chroma_task
    )

    services = {
        "postgres": postgres_health.status,
        "redis": redis_health.status,
        "chromadb": chroma_health.status,
    }

    all_ok = all(s == "ok" for s in services.values())

    return {
        "status": "ok" if all_ok else "degraded",
        "services": services,
    }
