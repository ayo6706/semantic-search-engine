"""Infrastructure connectivity checks.

Provides reusable health-check and connection validation functions for
PostgreSQL, Redis, and ChromaDB.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import time

import httpx
import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.core import database
from app.core import redis as redis_core

logger = logging.getLogger(__name__)


@dataclass
class ServiceHealth:
    """Detailed health check status for a service."""

    status: str  # "ok" or "error"
    latency_ms: float
    error_message: str | None = None


async def check_postgres(session: AsyncSession | None = None) -> ServiceHealth:
    """Verify PostgreSQL connectivity by executing a simple query."""
    start_time = time.perf_counter()
    try:
        if session is not None:
            await session.execute(text("SELECT 1"))
        else:
            async with database.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        latency = (time.perf_counter() - start_time) * 1000.0
        return ServiceHealth(status="ok", latency_ms=latency)
    except Exception as e:
        latency = (time.perf_counter() - start_time) * 1000.0
        logger.exception("PostgreSQL connectivity check failed")
        return ServiceHealth(status="error", latency_ms=latency, error_message=str(e))


async def check_redis(client: redis.Redis | None = None) -> ServiceHealth:
    """Verify Redis connectivity by pinging the server."""
    start_time = time.perf_counter()
    try:
        active_client = (
            client if client is not None else await redis_core.get_redis_client()
        )
        await active_client.ping()
        latency = (time.perf_counter() - start_time) * 1000.0
        return ServiceHealth(status="ok", latency_ms=latency)
    except Exception as e:
        latency = (time.perf_counter() - start_time) * 1000.0
        logger.exception("Redis connectivity check failed")
        return ServiceHealth(status="error", latency_ms=latency, error_message=str(e))


async def check_chromadb() -> ServiceHealth:
    """Verify ChromaDB connectivity by pinging its heartbeat API."""
    start_time = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try v2 first (newer ChromaDB versions)
            try:
                resp = await client.get(
                    f"http://{config.infra_settings.CHROMA_HOST}"
                    f":{config.infra_settings.CHROMA_PORT}/api/v2/heartbeat"
                )
                if resp.status_code == 200:
                    latency = (time.perf_counter() - start_time) * 1000.0
                    return ServiceHealth(status="ok", latency_ms=latency)
            except Exception:
                logger.debug("ChromaDB v2 heartbeat failed, trying v1 fallback")

            # Fallback to v1 (older ChromaDB versions)
            resp = await client.get(
                f"http://{config.infra_settings.CHROMA_HOST}"
                f":{config.infra_settings.CHROMA_PORT}/api/v1/heartbeat"
            )
            latency = (time.perf_counter() - start_time) * 1000.0
            if resp.status_code == 200:
                return ServiceHealth(status="ok", latency_ms=latency)
            else:
                return ServiceHealth(
                    status="error",
                    latency_ms=latency,
                    error_message=f"ChromaDB returned status code {resp.status_code}",
                )
    except Exception as e:
        latency = (time.perf_counter() - start_time) * 1000.0
        logger.exception("ChromaDB connectivity check failed")
        return ServiceHealth(status="error", latency_ms=latency, error_message=str(e))
