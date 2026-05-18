"""FastAPI application entry point.

Configures the application with lifespan events, CORS middleware. The lifespan context manager handles startup
and shutdown (engine disposal).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import infra_settings
from app.core.database import engine
from app.core.redis import close_redis

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown.

    Startup: log readiness.
    Shutdown: dispose the async SQLAlchemy engine to release
    all pooled database connections.

    Yields:
        Control to the running application.
    """
    logger.info("Semantic Search Engine starting up")
    yield
    logger.info("Semantic Search Engine shutting down")
    try:
        await close_redis()
    except Exception:
        logger.exception("Error closing Redis connection")
    try:
        await engine.dispose()
    except Exception:
        logger.exception("Error disposing database engine")


app = FastAPI(
    title="Semantic Search Engine",
    description=(
        "Hybrid search API with dense vector retrieval, sparse full-text "
        "search, Reciprocal Rank Fusion, and cross-encoder re-ranking."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=infra_settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
