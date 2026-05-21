import pytest
from unittest.mock import AsyncMock, patch

from app.core import lifecycle


@pytest.mark.asyncio
@patch("app.core.lifecycle.health")
@patch("app.api.dependencies.get_vector_store")
async def test_lifecycle_startup_success(mock_get_vector_store, mock_health):
    mock_health.verify_connectivity = AsyncMock()
    mock_vs = AsyncMock()
    mock_get_vector_store.return_value = mock_vs

    await lifecycle.startup()

    mock_health.verify_connectivity.assert_called_once_with(mock_vs)
    mock_get_vector_store.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.core.lifecycle.health")
@patch("app.core.lifecycle.shutdown")
@patch("app.api.dependencies.get_vector_store")
async def test_lifecycle_startup_failure(mock_get_vector_store, mock_shutdown, mock_health):
    mock_vs = AsyncMock()
    mock_get_vector_store.return_value = mock_vs
    mock_health.verify_connectivity = AsyncMock(side_effect=Exception("Chroma Offline"))
    mock_shutdown.return_value = None

    with pytest.raises(ConnectionError) as exc_info:
        await lifecycle.startup()

    assert "Startup connectivity verification failed" in str(exc_info.value)
    mock_health.verify_connectivity.assert_called_once_with(mock_vs)
    mock_shutdown.assert_called_once()


@pytest.mark.asyncio
@patch("app.core.lifecycle.redis")
@patch("app.core.lifecycle.database")
@patch("app.api.dependencies.get_vector_store")
async def test_lifecycle_shutdown(mock_get_vector_store, mock_database, mock_redis):
    mock_database.shutdown = AsyncMock()
    mock_redis.shutdown = AsyncMock()
    mock_vs = AsyncMock()
    mock_get_vector_store.return_value = mock_vs
    mock_vs.shutdown = AsyncMock()

    await lifecycle.shutdown()

    mock_database.shutdown.assert_called_once()
    mock_redis.shutdown.assert_called_once()
    mock_vs.shutdown.assert_called_once()
