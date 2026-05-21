"""Unified startup and shutdown lifecycle management for infrastructure resources."""

from __future__ import annotations

import asyncio
import logging

from app.core import database, health, redis

logger = logging.getLogger(__name__)


async def startup() -> None:
    """Verify connectivity of all backing services concurrently at startup.

    Raises:
        ConnectionError: If any of the backing services fail to connect.
    """
    logger.info("Initializing backing services connectivity checks...")
    
    try:
        from app.api.dependencies import get_vector_store
        vector_store = await get_vector_store()
        await health.verify_connectivity(vector_store)
    except Exception as e:
        logger.exception("Failed backing services connectivity verification during startup")
        await shutdown()
        raise ConnectionError(f"Startup connectivity verification failed: {e}") from e

    logger.info("All backing services successfully verified and ready.")


async def shutdown() -> None:
    """Release all infrastructure connections and resources on shutdown."""
    logger.info("Shutting down infrastructure connections...")
    
    try:
        from app.api.dependencies import get_vector_store
        vector_store = await get_vector_store()
        vs_shutdown = vector_store.shutdown()
    except Exception:
        logger.exception("Failed to retrieve vector store for shutdown cleanup")
        vs_shutdown = asyncio.sleep(0)  # No-op coroutine
        
    # Disposing of resources concurrently to speed up shutdown
    await asyncio.gather(
        database.shutdown(),
        redis.shutdown(),
        vs_shutdown,
        return_exceptions=True,
    )
    
    logger.info("All infrastructure connections closed.")
