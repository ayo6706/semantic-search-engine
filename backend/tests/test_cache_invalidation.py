from types import SimpleNamespace
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1.endpoints.documents import delete_document
from app.workers.ingestion import shutdown


class _FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _FakeSession:
    async def rollback(self):
        pass

    def begin(self):
        return _FakeTransaction()


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.documents.SearchCacheService")
@patch("app.api.v1.endpoints.documents.DocumentRepository")
async def test_delete_document_invalidates_search_cache(
    mock_repo_class,
    mock_cache_class,
):
    doc_id = uuid.uuid4()
    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = SimpleNamespace(storage_filename=None)
    mock_repo.delete.return_value = True
    mock_repo_class.return_value = mock_repo

    vector_store = AsyncMock()
    mock_redis = AsyncMock()
    mock_cache = AsyncMock()
    mock_cache_class.return_value = mock_cache

    await delete_document(doc_id, _FakeSession(), mock_redis, vector_store)

    vector_store.delete_by_doc_id.assert_awaited_once_with(str(doc_id))
    mock_cache.invalidate_all.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.workers.ingestion.close_redis")
async def test_ingestion_worker_shutdown_closes_redis(mock_close_redis):
    await shutdown({})

    mock_close_redis.assert_awaited_once()
