from types import SimpleNamespace
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services.document import DocumentService
from app.workers.ingestion import shutdown


class _FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _FakeSession:
    def in_transaction(self):
        return False

    async def rollback(self):
        pass

    def begin(self):
        return _FakeTransaction()


@pytest.mark.asyncio
@patch("app.services.document.SearchCacheService")
@patch("app.services.document.get_cache_client")
async def test_delete_document_invalidates_search_cache(
    mock_get_cache,
    mock_cache_class,
):
    doc_id = uuid.uuid4()
    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = SimpleNamespace(storage_filename=None)
    mock_repo.delete.return_value = True
    mock_repo.session = _FakeSession()

    vector_store = AsyncMock()
    service = DocumentService(mock_repo, vector_store)
    mock_cache = AsyncMock()
    mock_cache_class.return_value = mock_cache

    await service.delete_document(doc_id)

    vector_store.delete_by_doc_id.assert_awaited_once_with(str(doc_id))
    mock_cache.invalidate_all.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.workers.ingestion.shutdown_cache")
async def test_ingestion_worker_shutdown_closes_cache(mock_shutdown_cache):
    await shutdown({})

    mock_shutdown_cache.assert_awaited_once()
