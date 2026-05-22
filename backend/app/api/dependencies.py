"""Shared API dependencies.
Contains dependency injection providers for services and external integrations.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import Depends

from app.core.database import DbSessionDep
from app.integrations.llm.litellm import LiteLLMProvider
from app.integrations.vectorstores.base import BaseVectorStore
from app.integrations.vectorstores.chroma import ChromaDBVectorStore
from app.repositories.document import DocumentRepository
from app.search.rerankers.cross_encoder import CrossEncoderReranker
from app.services.document import DocumentService
from app.services.search import SearchService

# Lazy globals guarded against concurrent coroutine initialization.
_cross_encoder: CrossEncoderReranker | None = None
_llm_provider: LiteLLMProvider | None = None
_vector_store: BaseVectorStore | None = None

_cross_encoder_lock = asyncio.Lock()
_llm_provider_lock = asyncio.Lock()
_vector_store_lock = asyncio.Lock()


async def get_cross_encoder() -> CrossEncoderReranker:
    """Dependency to retrieve the shared CrossEncoderReranker instance.

    Uses lazy initialization and a lock to prevent concurrent coroutine races.
    """
    global _cross_encoder
    if _cross_encoder is None:
        async with _cross_encoder_lock:
            if _cross_encoder is None:
                _cross_encoder = await asyncio.to_thread(CrossEncoderReranker)
    return _cross_encoder


async def get_llm_provider() -> LiteLLMProvider:
    """Dependency to retrieve the shared LiteLLMProvider instance.

    Uses lazy initialization and a lock to prevent concurrent coroutine races.
    """
    global _llm_provider
    if _llm_provider is None:
        async with _llm_provider_lock:
            if _llm_provider is None:
                _llm_provider = await asyncio.to_thread(LiteLLMProvider)
    return _llm_provider


async def get_vector_store() -> BaseVectorStore:
    """Dependency to retrieve the shared vector-store provider.

    Uses lazy initialization and a lock to prevent concurrent coroutine races.
    """
    global _vector_store
    if _vector_store is None:
        async with _vector_store_lock:
            if _vector_store is None:
                _vector_store = await asyncio.to_thread(ChromaDBVectorStore)
    return _vector_store


async def get_document_repository(session: DbSessionDep) -> DocumentRepository:
    """Dependency to retrieve the DocumentRepository."""
    return DocumentRepository(session)


async def get_document_service(
    session: DbSessionDep,
    vector_store: Annotated[BaseVectorStore, Depends(get_vector_store)],
) -> DocumentService:
    """Dependency for DocumentService, building the repository dynamically."""
    repo = DocumentRepository(session)
    return DocumentService(repo, vector_store)


async def get_search_service(
    session: DbSessionDep,
    llm_provider: Annotated[LiteLLMProvider, Depends(get_llm_provider)],
    vector_store: Annotated[BaseVectorStore, Depends(get_vector_store)],
) -> SearchService:
    """Dependency for SearchService."""
    return SearchService(
        session=session,
        llm_provider=llm_provider,
        vector_store=vector_store,
        cross_encoder_provider=get_cross_encoder,
    )
