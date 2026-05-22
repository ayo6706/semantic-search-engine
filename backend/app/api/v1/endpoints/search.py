"""Search API endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from app.api.dependencies import get_search_service
from app.schemas.search import SearchRequest, SearchResponse
from app.search.cancellation import search_cancellation_registry
from app.services.search import SearchService

router = APIRouter()
SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]
SearchSessionHeader = Annotated[str | None, Header(alias="X-Search-Session-Id")]
SearchRequestHeader = Annotated[int | None, Header(alias="X-Search-Request-Id")]


@router.post("", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    raw_request: Request,
    service: SearchServiceDep,
    search_session_id: SearchSessionHeader = None,
    search_request_id: SearchRequestHeader = None,
) -> SearchResponse:
    """Execute a search query against the index."""
    is_stale = None
    if search_session_id is not None and search_request_id is not None:
        await search_cancellation_registry.mark_latest(search_session_id, search_request_id)

        async def is_stale() -> bool:
            return await search_cancellation_registry.is_stale(
                search_session_id,
                search_request_id,
            )

    return await service.search(
        request,
        is_disconnected=raw_request.is_disconnected,
        is_stale=is_stale,
    )
