"""API v1 router aggregator.

Collects all v1 endpoint routers into a single router mounted
at ``/api/v1`` on the main FastAPI application.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import health, documents, search

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
