"""Async SQLAlchemy engine and session factory.

Provides the async database engine, session factory, and a FastAPI
dependency for injecting database sessions into route handlers.
"""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import infra_settings
from app.schemas.health import ServiceHealth

engine = create_async_engine(
    infra_settings.DATABASE_URL,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session.

    The session is automatically closed when the request finishes.
    Callers are responsible for committing or rolling back as needed.

    Yields:
        An async SQLAlchemy session.
    """
    async with async_session_factory() as session:
        yield session


DbSessionDep = Annotated[AsyncSession, Depends(get_db)]


async def verify_connectivity() -> None:
    """Verify database connectivity.

    Raises:
        ConnectionError: If the database is unreachable.
    """
    health = await check_health()
    if health.status == "error":
        raise ConnectionError(f"Database connection failed: {health.error_message}")


async def check_health(session: AsyncSession | None = None) -> ServiceHealth:
    """Measure database health status and latency."""
    start_time = time.perf_counter()
    try:
        if session is not None:
            await session.execute(text("SELECT 1"))
        else:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        latency = (time.perf_counter() - start_time) * 1000.0
        return ServiceHealth(status="ok", latency_ms=latency)
    except Exception as e:
        latency = (time.perf_counter() - start_time) * 1000.0
        return ServiceHealth(status="error", latency_ms=latency, error_message=str(e))


async def shutdown() -> None:
    """Shutdown database resources by disposing the engine."""
    await engine.dispose()
