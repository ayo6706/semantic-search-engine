"""arq Redis queue provider."""

from __future__ import annotations

from urllib.parse import urlparse

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import infra_settings


def parse_queue_settings() -> RedisSettings:
    redis_url = infra_settings.REDIS_URL
    if not redis_url:
        raise ValueError("Queue Redis URL is required.")

    parsed = urlparse(redis_url)
    if parsed.scheme not in {"redis", "rediss"}:
        raise ValueError("Queue Redis URL must use redis:// or rediss://.")
    if not parsed.hostname:
        raise ValueError("Queue Redis URL must include a hostname.")

    path = parsed.path.lstrip("/")
    try:
        database = int(path) if path else 0
    except ValueError as exc:
        raise ValueError(
            f"Invalid queue database index in REDIS_URL path: '{path}'."
        ) from exc

    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password,
        database=database,
    )


async def create_queue_pool() -> ArqRedis:
    return await create_pool(parse_queue_settings())
