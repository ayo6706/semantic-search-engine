"""Async SQLAlchemy engine and session factory.

Provides the async database engine, session factory, and a FastAPI
dependency for injecting database sessions into route handlers.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
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


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session.

    If the app state has a lifespan-managed session factory, it uses that.
    Otherwise, falls back to the default.

    Yields:
        An async SQLAlchemy session.
    """
    if hasattr(request.app.state, "db_session_factory"):
        factory = request.app.state.db_session_factory
    else:
        factory = async_session_factory

    async with factory() as session:
        yield session


DbSessionDep = Annotated[AsyncSession, Depends(get_db)]

