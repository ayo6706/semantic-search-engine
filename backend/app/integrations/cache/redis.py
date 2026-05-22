"""Redis cache provider."""

from __future__ import annotations

import asyncio
import logging
import time

import redis.asyncio as redis
from redis.exceptions import RedisError

from app.core.config import infra_settings
from app.schemas.health import ServiceHealth

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None
_redis_lock = asyncio.Lock()


async def get_client() -> redis.Redis:
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
                    logger.exception("Failed to initialize Redis cache client")
                    raise
                _redis_client = client
    return _redis_client


async def close() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


async def check_health(client: redis.Redis | None = None) -> ServiceHealth:
    start_time = time.perf_counter()
    try:
        active_client = client if client is not None else await get_client()
        await active_client.ping()
        latency = (time.perf_counter() - start_time) * 1000.0
        return ServiceHealth(status="ok", latency_ms=latency)
    except Exception as exc:
        latency = (time.perf_counter() - start_time) * 1000.0
        return ServiceHealth(status="error", latency_ms=latency, error_message=str(exc))


async def shutdown() -> None:
    await close()
