"""Redis cache provider."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time

import redis.asyncio as redis
from redis.exceptions import RedisError

from app.core.config import infra_settings, search_settings
from app.schemas.health import ServiceHealth
from app.schemas.search import SearchRequest, SearchResponse

logger = logging.getLogger(__name__)

CACHE_PREFIX = "search:"


class RedisCache:
    def __init__(self, redis_client: redis.Redis | None = None):
        self._redis = redis_client
        self._lock = asyncio.Lock()

    @staticmethod
    def build_cache_key(request: SearchRequest) -> str:
        payload = request.model_dump_json()
        digest = hashlib.sha256(payload.encode()).hexdigest()
        return f"{CACHE_PREFIX}{digest}"

    async def get_client(self) -> redis.Redis:
        if self._redis is None:
            async with self._lock:
                if self._redis is None:
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
                    self._redis = client
        return self._redis

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def check_health(self) -> ServiceHealth:
        start_time = time.perf_counter()
        try:
            client = await self.get_client()
            await client.ping()
            latency = (time.perf_counter() - start_time) * 1000.0
            return ServiceHealth(status="ok", latency_ms=latency)
        except Exception as exc:
            latency = (time.perf_counter() - start_time) * 1000.0
            return ServiceHealth(status="error", latency_ms=latency, error_message=str(exc))

    async def get(self, request: SearchRequest) -> SearchResponse | None:
        try:
            client = await self.get_client()
            data = await client.get(self.build_cache_key(request))
            if data is None:
                return None
            return SearchResponse.model_validate_json(data)
        except Exception:
            logger.warning("Cache read failed, continuing without cache", exc_info=True)
            return None

    async def set(self, request: SearchRequest, response: SearchResponse) -> None:
        try:
            client = await self.get_client()
            await client.set(
                self.build_cache_key(request),
                response.model_dump_json(),
                ex=search_settings.CACHE_TTL_SECONDS,
            )
        except Exception:
            logger.warning("Cache write failed", exc_info=True)

    async def invalidate_all(self) -> None:
        try:
            deleted = 0
            batch: list[str] = []
            client = await self.get_client()

            async for key in client.scan_iter(match=f"{CACHE_PREFIX}*", count=100):
                batch.append(key)
                if len(batch) >= 100:
                    deleted += await self._delete_batch(batch)
                    batch.clear()
            if batch:
                deleted += await self._delete_batch(batch)
            if deleted:
                logger.info("Invalidated %d search cache entries", deleted)
        except Exception:
            logger.warning("Cache invalidation failed", exc_info=True)

    async def _delete_batch(self, keys: list[str]) -> int:
        client = await self.get_client()
        pipeline = client.pipeline(transaction=False)
        pipeline.delete(*keys)
        results = await pipeline.execute()
        return int(results[0]) if results else 0


_redis_cache: RedisCache | None = None
_redis_lock = asyncio.Lock()


async def get_cache() -> RedisCache:
    global _redis_cache
    if _redis_cache is None:
        async with _redis_lock:
            if _redis_cache is None:
                _redis_cache = RedisCache()
    return _redis_cache
