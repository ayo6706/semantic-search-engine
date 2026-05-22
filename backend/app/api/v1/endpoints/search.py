"""Search API endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_search_service
from app.schemas.search import SearchRequest, SearchResponse
from app.services.search import SearchService

router = APIRouter()
SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]


@router.post("", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    service: SearchServiceDep,
) -> SearchResponse:
    """Execute a search query against the index."""
    return await service.search(request)
