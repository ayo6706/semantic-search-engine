"""Domain exception hierarchy for the semantic search engine.

All application-specific exceptions inherit from ``SearchEngineError``
so that error-handling middleware can distinguish domain errors from
unexpected failures.
"""

from __future__ import annotations


class SearchEngineError(Exception):
    """Base exception for the semantic search engine."""


class DocumentNotFoundError(SearchEngineError):
    """Raised when a requested document does not exist."""


class DocumentProcessingError(SearchEngineError):
    """Raised when document ingestion or processing fails."""


class VectorStoreError(SearchEngineError):
    """Raised when a vector store operation fails."""


class CacheError(SearchEngineError):
    """Raised when a cache operation fails.

    Cache errors are non-fatal — the pipeline should continue
    without caching when Redis is unavailable.
    """
