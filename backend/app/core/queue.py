"""Configured job queue provider interface."""

from __future__ import annotations

from typing import Protocol

from app.integrations.queues import arq_redis


class QueuePool(Protocol):
    async def enqueue_job(self, function: str, *args: object) -> object: ...

    async def close(self) -> None: ...


class QueueSettings(Protocol):
    host: str
    port: int
    password: str | None
    database: int


def get_queue_settings() -> QueueSettings:
    """Return QueueSettings for consumers that configure queue workers."""
    return arq_redis.parse_queue_settings()


async def create_queue_pool() -> QueuePool:
    """Create and return an async QueuePool ready to enqueue jobs."""
    return await arq_redis.create_queue_pool()
