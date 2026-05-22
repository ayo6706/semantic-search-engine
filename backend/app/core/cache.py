"""Configured cache provider interface."""

from __future__ import annotations

from typing import Any

from app.integrations.cache import redis as cache_provider
from app.schemas.health import ServiceHealth


async def get_cache_client() -> Any:
    return await cache_provider.get_client()


async def verify_connectivity() -> None:
    health = await check_health()
    if health.status == "error":
        raise ConnectionError(f"Cache connection failed: {health.error_message}")


async def check_health(client: Any | None = None) -> ServiceHealth:
    active_client = client if client is not None else await get_cache_client()
    return await cache_provider.check_health(active_client)


async def shutdown() -> None:
    await cache_provider.shutdown()
