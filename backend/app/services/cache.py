"""Redis-backed search result cache service."""

from __future__ import annotations

import hashlib
import logging

import redis.asyncio as redis

from app.core.config import search_settings
from app.schemas.search import SearchRequest, SearchResponse

logger = logging.getLogger(__name__)

CACHE_PREFIX = "search:"


def _build_cache_key(request: SearchRequest) -> str:
    """SHA-256 hash of the full request as a deterministic cache key."""
    payload = request.model_dump_json()
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f"{CACHE_PREFIX}{digest}"


class SearchCacheService:
    """Redis-backed search result cache with graceful degradation."""

    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client

    async def get(self, request: SearchRequest) -> SearchResponse | None:
        """Return cached response or None on miss/error."""
        try:
            key = _build_cache_key(request)
            data = await self._redis.get(key)
            if data is None:
                return None
            return SearchResponse.model_validate_json(data)
        except Exception:
            logger.warning("Cache read failed, continuing without cache", exc_info=True)
            return None

    async def set(self, request: SearchRequest, response: SearchResponse) -> None:
        """Cache a response. Failures are logged, not raised."""
        try:
            key = _build_cache_key(request)
            await self._redis.set(
                key,
                response.model_dump_json(),
                ex=search_settings.CACHE_TTL_SECONDS,
            )
        except Exception:
            logger.warning("Cache write failed", exc_info=True)

    async def invalidate_all(self) -> None:
        """Delete all search cache keys. Non-blocking via SCAN."""
        try:
            deleted = 0
            batch: list[str] = []

            async def delete_batch(keys: list[str]) -> int:
                pipeline = self._redis.pipeline(transaction=False)
                pipeline.delete(*keys)
                results = await pipeline.execute()
                return int(results[0]) if results else 0

            async for key in self._redis.scan_iter(match=f"{CACHE_PREFIX}*", count=100):
                batch.append(key)
                if len(batch) >= 100:
                    deleted += await delete_batch(batch)
                    batch.clear()
            if batch:
                deleted += await delete_batch(batch)
            if deleted:
                logger.info("Invalidated %d search cache entries", deleted)
        except Exception:
            logger.warning("Cache invalidation failed", exc_info=True)
