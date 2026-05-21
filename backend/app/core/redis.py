"""Centralized async Redis client factory and shutdown helper."""

from __future__ import annotations

import asyncio
import logging

from typing import Annotated

from fastapi import Depends, Request
import redis.asyncio as redis
from redis.exceptions import RedisError

from app.core.config import infra_settings

logger = logging.getLogger(__name__)

async def get_redis(request: Request) -> redis.Redis:
    """Dependency to get the lifespan-managed Redis client."""
    return request.app.state.redis_client


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
