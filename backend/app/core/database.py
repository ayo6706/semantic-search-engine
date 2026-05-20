"""Async SQLAlchemy engine and session factory.

Provides the async database engine, session factory, and a FastAPI
dependency for injecting database sessions into route handlers.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import infra_settings

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
