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
from sqlalchemy import text
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception

from app.api.v1 import router as api_v1_router
from app.core import config
from app.core import database
from app.core import health
from app.core import redis

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown.

    Startup: Eagerly initialize and verify database and Redis connections
    with exponential backoff retries for transient failures.
    Shutdown: Dispose the database engine and close the Redis client.

    Yields:
        Control to the running application.
    """
    logger.info("Semantic Search Engine starting up")

    engine = database.engine
    db_session_factory = database.async_session_factory
    try:
        redis_client = await redis.get_redis_client()

        def is_transient_error(e: Exception) -> bool:
            """Filter to retry only on transient socket/connection errors."""
            return isinstance(e, (OSError, ConnectionError))

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception(is_transient_error),
            reraise=True,
        ):
            with attempt:
                logger.info("Verifying database, Redis, and ChromaDB connectivity...")

                db_health = await health.check_postgres()
                if db_health.status != "ok":
                    raise ConnectionError(
                        f"Database connection failed: {db_health.error_message}"
                    )

                redis_health = await health.check_redis(redis_client)
                if redis_health.status != "ok":
                    raise ConnectionError(
                        f"Redis connection failed: {redis_health.error_message}"
                    )

                chroma_health = await health.check_chromadb()
                if chroma_health.status != "ok":
                    raise ConnectionError(
                        f"ChromaDB connection failed: {chroma_health.error_message}"
                    )

                logger.info("All infrastructure connections verified successfully.")

        # Store verified resources in app.state
        app.state.db_engine = engine
        app.state.db_session_factory = db_session_factory
        app.state.redis_client = redis_client

        yield
    except Exception as exc:
        logger.exception("Failed during application startup or run")
        raise exc
    finally:
        logger.info("Semantic Search Engine shutting down")
        try:
            await redis.close_redis()
        except Exception:
            logger.exception("Error closing Redis connection")
        try:
            await database.engine.dispose()
        except Exception:
            logger.exception("Error disposing database engine")



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

# If the ENVIRONMENT is set (e.g. in config) and is not in SHOW_DOCS_IN, disable Swagger/ReDoc
# Falls back to "development" if not explicitly configured in infra_settings
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
