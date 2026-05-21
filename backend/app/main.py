"""FastAPI application entry point.
    Configures the application with lifespan events and CORS middleware.
    The lifespan context manager handles startup and shutdown (engine disposal).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import router as api_v1_router
from app.core import config
from app.core import lifecycle

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown.

    Startup: Eagerly verify core infrastructure connectivity (fail-fast).
    Shutdown: Dispose database engine and close Redis connection.

    Yields:
        Control to the running application.
    """
    logger.info("Semantic Search Engine starting up")

    await lifecycle.startup()

    try:
        yield
    finally:
        logger.info("Semantic Search Engine shutting down")
        await lifecycle.shutdown()




SHOW_DOCS_IN = {"local", "development", "staging"}

app_kwargs = {
    "title": "Semantic Search Engine",
    "description": (
        "Hybrid search API with dense vector retrieval, sparse full-text "
        "search, Reciprocal Rank Fusion, and cross-encoder re-ranking."
    ),
    "version": "0.1.0",
    "lifespan": lifespan,
}

app_env = getattr(config.infra_settings, "ENVIRONMENT", "development")
if app_env not in SHOW_DOCS_IN:
    app_kwargs["openapi_url"] = None

app = FastAPI(**app_kwargs)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.infra_settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router.api_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=config.infra_settings.API_HOST,
        port=config.infra_settings.API_PORT,
        reload=True,
    )
