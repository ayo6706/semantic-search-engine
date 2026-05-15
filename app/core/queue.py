"""arq job queue setup.

Provides helpers for creating an arq Redis connection pool
used by the background worker for document ingestion tasks.
"""

from __future__ import annotations

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import infra_settings


def _parse_redis_settings() -> RedisSettings:
    """Parse the REDIS_URL into arq RedisSettings.

    arq's ``RedisSettings`` does not accept a DSN directly, so we parse
    the URL components manually.

    Returns:
        An arq ``RedisSettings`` instance.
    """
    from urllib.parse import urlparse

    parsed = urlparse(infra_settings.REDIS_URL)
    path = parsed.path.lstrip("/")
    try:
        database = int(path) if path else 0
    except ValueError as e:
        raise ValueError(
            f"Invalid Redis database index in REDIS_URL: '{infra_settings.REDIS_URL}'. "
            f"Expected an integer, got '{path}'."
        ) from e

    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password,
        database=database,
    )


async def create_arq_pool() -> ArqRedis:
    """Create an arq Redis connection pool.

    Returns:
        An ``ArqRedis`` connection pool for enqueuing jobs.
    """
    return await create_pool(_parse_redis_settings())
