"""Shared API dependencies.
Contains dependency injection providers for services and external integrations.
"""

from __future__ import annotations

import asyncio

from app.core.database import DbSessionDep
from app.integrations.llm.litellm import LiteLLMProvider
from app.search.rerankers.cross_encoder import CrossEncoderReranker
from app.integrations.vectorstores.chroma import ChromaDBVectorStore
from app.repositories.document import DocumentRepository
from app.services.document import DocumentService

# Thread-safe global instances for lazy initialization
_cross_encoder: CrossEncoderReranker | None = None
_llm_provider: LiteLLMProvider | None = None
_vector_store: ChromaDBVectorStore | None = None

_cross_encoder_lock = asyncio.Lock()
_llm_provider_lock = asyncio.Lock()
_vector_store_lock = asyncio.Lock()


async def get_cross_encoder() -> CrossEncoderReranker:
    """Dependency to retrieve the shared CrossEncoderReranker instance.

    Uses lazy initialization and a lock to ensure thread safety.
    """
    global _cross_encoder
    if _cross_encoder is None:
        async with _cross_encoder_lock:
            if _cross_encoder is None:
                _cross_encoder = await asyncio.to_thread(CrossEncoderReranker)
    return _cross_encoder


async def get_llm_provider() -> LiteLLMProvider:
    """Dependency to retrieve the shared LiteLLMProvider instance.

    Uses lazy initialization and a lock to ensure thread safety.
    """
    global _llm_provider
    if _llm_provider is None:
        async with _llm_provider_lock:
            if _llm_provider is None:
                _llm_provider = await asyncio.to_thread(LiteLLMProvider)
    return _llm_provider


async def get_vector_store() -> ChromaDBVectorStore:
    """Dependency to retrieve the shared ChromaDBVectorStore instance.

    Uses lazy initialization and a lock to ensure thread safety.
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


async def get_document_service(session: DbSessionDep) -> DocumentService:
    """Dependency for DocumentService, building the repository dynamically."""
    repo = DocumentRepository(session)
    return DocumentService(repo)
