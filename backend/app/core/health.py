"""Infrastructure connectivity checks."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache as cache_core
from app.core import database
from app.integrations.vectorstores.base import BaseVectorStore
from app.schemas.health import ServiceHealth

logger = logging.getLogger(__name__)


async def verify_connectivity(vector_store: BaseVectorStore) -> None:
    """Verify startup connectivity for all core services and fail-fast if any check fails."""
    database_task = check_database()
    cache_task = check_cache()
    vector_store_task = check_vector_store(vector_store)

    database_health, cache_health, vector_store_health = await asyncio.gather(
        database_task, cache_task, vector_store_task
    )

    errors = []
    if database_health.status != "ok":
        errors.append(f"database: {database_health.error_message}")
    if cache_health.status != "ok":
        errors.append(f"cache: {cache_health.error_message}")
    if vector_store_health.status != "ok":
        errors.append(f"vector_store: {vector_store_health.error_message}")

    if errors:
        error_details = " | ".join(errors)
        raise ConnectionError(f"Infrastructure connection verification failed: {error_details}")


async def check_database(session: AsyncSession | None = None) -> ServiceHealth:
    """Verify database connectivity by delegating to the configured database module."""
    result = await database.check_health(session)
    if result.status == "error":
        logger.error("Database connectivity check failed: %s", result.error_message)
    return result


async def check_cache(client: Any | None = None) -> ServiceHealth:
    """Verify cache connectivity by delegating to the configured cache module."""
    try:
        return await cache_core.check_health(client)
    except Exception as e:
        logger.exception("Cache connectivity check failed")
        return ServiceHealth(status="error", latency_ms=0.0, error_message=str(e))


async def check_vector_store(vector_store: BaseVectorStore) -> ServiceHealth:
    """Verify vector-store connectivity by delegating to the vector-store interface."""
    try:
        return await vector_store.check_health()
    except Exception as e:
        logger.exception("Vector-store connectivity check failed")
        return ServiceHealth(status="error", latency_ms=0.0, error_message=str(e))


async def check_system_health(
    session: AsyncSession,
    vector_store: BaseVectorStore,
) -> dict[str, str | dict[str, str]]:
    """Return aggregate infrastructure health for API responses."""
    database_task = check_database(session)
    cache_task = check_cache()
    vector_store_task = check_vector_store(vector_store)

    database_health, cache_health, vector_store_health = await asyncio.gather(
        database_task, cache_task, vector_store_task
    )

    services = {
        "database": database_health.status,
        "cache": cache_health.status,
        "vector_store": vector_store_health.status,
    }
    all_ok = all(status == "ok" for status in services.values())

    return {
        "status": "ok" if all_ok else "degraded",
        "services": services,
    }
