"""Health check endpoint.

Verifies connectivity to all infra.
Returns a structured response indicating the status of each service.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
import redis.asyncio as redis
from fastapi import APIRouter, status
from sqlalchemy import text

from app.core.config import infra_settings
from app.core.database import DbSessionDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


async def check_postgres(db: DbSessionDep, services: dict[str, str]) -> None:
    try:
        await db.execute(text("SELECT 1"))
        services["postgres"] = "ok"
    except Exception:
        logger.exception("PostgreSQL health check failed")
        services["postgres"] = "error"


async def check_chromadb(services: dict[str, str]) -> None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try v2 first (newer ChromaDB versions)
            resp = await client.get(
                f"http://{infra_settings.CHROMA_HOST}"
                f":{infra_settings.CHROMA_PORT}/api/v2/heartbeat"
            )
            if resp.status_code == 200:
                services["chromadb"] = "ok"
                return

            # Fallback to v1 (older ChromaDB versions)
            resp = await client.get(
                f"http://{infra_settings.CHROMA_HOST}"
                f":{infra_settings.CHROMA_PORT}/api/v1/heartbeat"
            )
            if resp.status_code == 200:
                services["chromadb"] = "ok"
            else:
                services["chromadb"] = "error"
    except Exception:
        logger.exception("ChromaDB health check failed")
        services["chromadb"] = "error"


async def check_redis(services: dict[str, str]) -> None:
    try:
        r = redis.from_url(
            infra_settings.REDIS_URL,
            decode_responses=True,
        )
        try:
            pong = await r.ping()
            services["redis"] = "ok" if pong else "error"
        finally:
            await r.aclose()
    except Exception:
        logger.exception("Redis health check failed")
        services["redis"] = "error"


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
    services: dict[str, str] = {}

    await asyncio.gather(
        check_postgres(db, services),
        check_chromadb(services),
        check_redis(services)
    )

    all_ok = all(s == "ok" for s in services.values())

    return {
        "status": "ok" if all_ok else "degraded",
        "services": services,
    }
