"""Unified startup and shutdown lifecycle management for infrastructure resources."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core import cache, database, health

logger = logging.getLogger(__name__)


async def startup() -> None:
    """Verify connectivity of all backing services concurrently at startup.

    Raises:
        ConnectionError: If any of the backing services fail to connect.
    """
    logger.info("Initializing backing services connectivity checks...")
    vector_store = None

    try:
        from app.api.dependencies import get_vector_store
        vector_store = await get_vector_store()
        await health.verify_connectivity(vector_store)
    except Exception as e:
        logger.exception("Failed backing services connectivity verification during startup")
        await shutdown(vector_store)
        raise ConnectionError(f"Startup connectivity verification failed: {e}") from e

    logger.info("All backing services successfully verified and ready.")


async def shutdown(vector_store: Any | None = None) -> None:
    """Release all infrastructure connections and resources on shutdown."""
    logger.info("Shutting down infrastructure connections...")

    if vector_store is None:
        try:
            from app.api.dependencies import get_vector_store
            vector_store = await get_vector_store()
        except Exception:
            logger.exception("Failed to retrieve vector store for shutdown cleanup")

    vs_shutdown = vector_store.shutdown() if vector_store is not None else asyncio.sleep(0)
        
    shutdown_tasks = {
        "database.shutdown": database.shutdown(),
        "cache.shutdown": cache.shutdown(),
        "vector_store.shutdown": vs_shutdown,
    }
    results = await asyncio.gather(
        *shutdown_tasks.values(),
        return_exceptions=True,
    )
    for name, result in zip(shutdown_tasks, results, strict=True):
        if isinstance(result, Exception):
            logger.error(
                "%s failed during infrastructure shutdown",
                name,
                exc_info=(type(result), result, result.__traceback__),
            )
    
    logger.info("All infrastructure connections closed.")
