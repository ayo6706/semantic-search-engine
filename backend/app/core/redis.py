"""Centralized async Redis client factory and shutdown helper."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Annotated

from fastapi import Depends
import redis.asyncio as redis
from redis.exceptions import RedisError

from app.core.config import infra_settings
from app.schemas.health import ServiceHealth

logger = logging.getLogger(__name__)

async def get_redis() -> redis.Redis:
    """Dependency to get the Redis client."""
    return await get_redis_client()


RedisDep = Annotated[redis.Redis, Depends(get_redis)]


_redis_client: redis.Redis | None = None
_redis_lock = asyncio.Lock()


async def get_redis_client() -> redis.Redis:
    """Lazy-init a reusable async Redis client.
    
    Returns:
        An async Redis client instance.
    """
    global _redis_client
    if _redis_client is None:
        async with _redis_lock:
            if _redis_client is None:
                try:
                    client = redis.from_url(
                        infra_settings.REDIS_URL,
                        decode_responses=True,
                        socket_connect_timeout=infra_settings.REDIS_CONNECT_TIMEOUT,
                        socket_timeout=infra_settings.REDIS_SOCKET_TIMEOUT,
                        retry_on_timeout=True,
                    )
                    await client.ping()
                except RedisError:
                    logger.exception("Failed to initialize Redis client")
                    raise
                _redis_client = client
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection pool. Call on shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


async def verify_connectivity() -> None:
    """Verify Redis connectivity.

    Raises:
        ConnectionError: If Redis is unreachable.
    """
    health = await check_health()
    if health.status == "error":
        raise ConnectionError(f"Redis connection failed: {health.error_message}")


async def check_health(client: redis.Redis | None = None) -> ServiceHealth:
    """Measure Redis health status and latency."""
    start_time = time.perf_counter()
    try:
        active_client = client if client is not None else await get_redis_client()
        await active_client.ping()
        latency = (time.perf_counter() - start_time) * 1000.0
        return ServiceHealth(status="ok", latency_ms=latency)
    except Exception as e:
        latency = (time.perf_counter() - start_time) * 1000.0
        return ServiceHealth(status="error", latency_ms=latency, error_message=str(e))


async def shutdown() -> None:
    """Shutdown Redis resources."""
    await close_redis()
