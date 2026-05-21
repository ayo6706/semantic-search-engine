"""Infrastructure connectivity checks.

Provides health-check and connection validation functions for
PostgreSQL, Redis, and ChromaDB by delegating to service interfaces.
"""

from __future__ import annotations

import asyncio
import logging

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import database
from app.core import redis as redis_core
from app.integrations.vectorstores.base import BaseVectorStore
from app.schemas.health import ServiceHealth

logger = logging.getLogger(__name__)


async def verify_connectivity(vector_store: BaseVectorStore) -> None:
    """Verify startup connectivity for all core services and fail-fast if any check fails."""
    postgres_task = check_postgres()
    redis_task = check_redis()
    chroma_task = check_chromadb(vector_store)

    postgres_health, redis_health, chroma_health = await asyncio.gather(
        postgres_task, redis_task, chroma_task
    )

    errors = []
    if postgres_health.status != "ok":
        errors.append(f"PostgreSQL: {postgres_health.error_message}")
    if redis_health.status != "ok":
        errors.append(f"Redis: {redis_health.error_message}")
    if chroma_health.status != "ok":
        errors.append(f"ChromaDB: {chroma_health.error_message}")

    if errors:
        error_details = " | ".join(errors)
        raise ConnectionError(f"Infrastructure connection verification failed: {error_details}")


async def check_postgres(session: AsyncSession | None = None) -> ServiceHealth:
    """Verify PostgreSQL connectivity by delegating to the database module."""
    result = await database.check_health(session)
    if result.status == "error":
        logger.error(f"PostgreSQL connectivity check failed: {result.error_message}")
    return result


async def check_redis(client: redis.Redis | None = None) -> ServiceHealth:
    """Verify Redis connectivity by delegating to the redis module."""
    try:
        return await redis_core.check_health(client)
    except Exception as e:
        logger.exception("Redis connectivity check failed")
        return ServiceHealth(status="error", latency_ms=0.0, error_message=str(e))


async def check_chromadb(vector_store: BaseVectorStore) -> ServiceHealth:
    """Verify ChromaDB connectivity by delegating to the vector store interface."""
    try:
        return await vector_store.check_health()
    except Exception as e:
        logger.exception("ChromaDB connectivity check failed")
        return ServiceHealth(status="error", latency_ms=0.0, error_message=str(e))
