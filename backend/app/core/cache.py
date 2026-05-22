"""Configured cache provider interface."""

from __future__ import annotations

from typing import Any, Protocol

from app.integrations.cache import redis as cache_provider
from app.schemas.health import ServiceHealth
from app.schemas.search import SearchRequest, SearchResponse


class SearchCache(Protocol):
    async def get(self, request: SearchRequest) -> SearchResponse | None: ...

    async def set(self, request: SearchRequest, response: SearchResponse) -> None: ...

    async def invalidate_all(self) -> None: ...


async def get_cache_client() -> Any:
    cache = await cache_provider.get_cache()
    return await cache.get_client()


async def get_search_cache() -> SearchCache:
    return await cache_provider.get_cache()


async def verify_connectivity() -> None:
    health = await check_health()
    if health.status == "error":
        raise ConnectionError(f"Cache connection failed: {health.error_message}")


async def check_health(client: Any | None = None) -> ServiceHealth:
    active_client = client if client is not None else await get_cache_client()
    cache = cache_provider.RedisCache(active_client)
    return await cache.check_health()


async def shutdown() -> None:
    cache = await cache_provider.get_cache()
    await cache.close()
