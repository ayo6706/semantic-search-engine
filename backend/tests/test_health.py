from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.health import health_check
from app.core.health import ServiceHealth, check_vector_store, check_database, check_cache


@pytest.mark.asyncio
async def test_check_database_with_session_success():
    mock_session = AsyncMock(spec=AsyncSession)
    res = await check_database(mock_session)
    assert res.status == "ok"
    assert res.error_message is None
    assert isinstance(res.latency_ms, float)


@pytest.mark.asyncio
async def test_check_database_with_session_failure():
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute.side_effect = Exception("DB Connection Refused")
    res = await check_database(mock_session)
    assert res.status == "error"
    assert "DB Connection Refused" in res.error_message
    assert isinstance(res.latency_ms, float)


@pytest.mark.asyncio
@patch("app.core.database.engine")
async def test_check_database_no_session_success(mock_engine):
    mock_conn = AsyncMock()
    mock_engine.connect.return_value.__aenter__.return_value = mock_conn
    res = await check_database(None)
    assert res.status == "ok"
    assert res.error_message is None
    assert isinstance(res.latency_ms, float)


@pytest.mark.asyncio
@patch("app.core.database.engine")
async def test_check_database_no_session_failure(mock_engine):
    mock_engine.connect.side_effect = Exception("DB Error")
    res = await check_database(None)
    assert res.status == "error"
    assert "DB Error" in res.error_message
    assert isinstance(res.latency_ms, float)


@pytest.mark.asyncio
async def test_check_cache_with_client_success():
    mock_client = AsyncMock()
    res = await check_cache(mock_client)
    assert res.status == "ok"
    assert res.error_message is None
    assert isinstance(res.latency_ms, float)
    mock_client.ping.assert_called_once()


@pytest.mark.asyncio
async def test_check_cache_with_client_failure():
    mock_client = AsyncMock()
    mock_client.ping.side_effect = Exception("Redis connection timed out")
    res = await check_cache(mock_client)
    assert res.status == "error"
    assert "Redis connection timed out" in res.error_message
    assert isinstance(res.latency_ms, float)


@pytest.mark.asyncio
@patch("app.core.cache.get_cache_client")
async def test_check_cache_no_client_success(mock_get_cache_client):
    mock_client = AsyncMock()
    mock_get_cache_client.return_value = mock_client
    res = await check_cache(None)
    assert res.status == "ok"
    assert isinstance(res.latency_ms, float)
    mock_client.ping.assert_called_once()


@pytest.mark.asyncio
@patch("app.core.cache.get_cache_client")
async def test_check_cache_no_client_failure(mock_get_cache_client):
    mock_get_cache_client.side_effect = Exception("Cache init failed")
    res = await check_cache(None)
    assert res.status == "error"
    assert "Cache init failed" in res.error_message
    assert isinstance(res.latency_ms, float)


@pytest.mark.asyncio
async def test_check_vector_store_success():
    mock_vs = AsyncMock()
    mock_vs.check_health.return_value = ServiceHealth(status="ok", latency_ms=1.5)

    res = await check_vector_store(mock_vs)
    assert res.status == "ok"
    assert res.error_message is None
    assert res.latency_ms == 1.5
    mock_vs.check_health.assert_called_once()


@pytest.mark.asyncio
async def test_check_vector_store_failure():
    mock_vs = AsyncMock()
    mock_vs.check_health.return_value = ServiceHealth(status="error", latency_ms=1.5, error_message="Chroma down")

    res = await check_vector_store(mock_vs)
    assert res.status == "error"
    assert "Chroma down" in res.error_message
    mock_vs.check_health.assert_called_once()


@pytest.mark.asyncio
@patch("chromadb.AsyncHttpClient")
async def test_chroma_vector_store_verify_connectivity_success(mock_client_cls):
    from app.integrations.vectorstores.chroma import ChromaDBVectorStore

    mock_client = AsyncMock()
    mock_client.heartbeat.return_value = 123456789
    mock_client_cls.return_value = mock_client

    vs = ChromaDBVectorStore()
    await vs.verify_connectivity()
    mock_client.heartbeat.assert_called_once()


@pytest.mark.asyncio
@patch("chromadb.AsyncHttpClient")
async def test_chroma_vector_store_verify_connectivity_failure(mock_client_cls):
    from app.integrations.vectorstores.chroma import ChromaDBVectorStore

    mock_client = AsyncMock()
    mock_client.heartbeat.side_effect = Exception("Chroma Connection Error")
    mock_client_cls.return_value = mock_client

    vs = ChromaDBVectorStore()
    with pytest.raises(ConnectionError) as exc_info:
        await vs.verify_connectivity()
    assert "Chroma Connection Error" in str(exc_info.value)


@pytest.mark.asyncio
@patch("app.core.database.check_health")
async def test_database_verify_connectivity_uses_health_result(mock_check_health):
    from app.core import database

    mock_check_health.return_value = ServiceHealth(status="ok", latency_ms=1.0)

    await database.verify_connectivity()

    mock_check_health.assert_awaited_once_with()


@pytest.mark.asyncio
@patch("app.core.database.check_health")
async def test_database_verify_connectivity_raises_on_unhealthy_result(mock_check_health):
    from app.core import database

    mock_check_health.return_value = ServiceHealth(
        status="error",
        latency_ms=1.0,
        error_message="connection refused",
    )

    with pytest.raises(ConnectionError) as exc_info:
        await database.verify_connectivity()

    assert "connection refused" in str(exc_info.value)
    mock_check_health.assert_awaited_once_with()


@pytest.mark.asyncio
@patch("app.core.cache.check_health")
async def test_cache_verify_connectivity_uses_health_result(mock_check_health):
    from app.core import cache

    mock_check_health.return_value = ServiceHealth(status="ok", latency_ms=1.0)

    await cache.verify_connectivity()

    mock_check_health.assert_awaited_once_with()


@pytest.mark.asyncio
@patch("app.core.cache.check_health")
async def test_cache_verify_connectivity_raises_on_unhealthy_result(mock_check_health):
    from app.core import cache

    mock_check_health.return_value = ServiceHealth(
        status="error",
        latency_ms=1.0,
        error_message="operation timed out",
    )

    with pytest.raises(ConnectionError) as exc_info:
        await cache.verify_connectivity()

    assert "operation timed out" in str(exc_info.value)
    mock_check_health.assert_awaited_once_with()


@pytest.mark.asyncio
@patch("chromadb.AsyncHttpClient")
async def test_chroma_vector_store_check_health_success(mock_client_cls):
    from app.integrations.vectorstores.chroma import ChromaDBVectorStore

    mock_client = AsyncMock()
    mock_client.heartbeat.return_value = 123456789
    mock_client_cls.return_value = mock_client

    vs = ChromaDBVectorStore()
    res = await vs.check_health()
    assert res.status == "ok"
    assert res.error_message is None
    assert isinstance(res.latency_ms, float)


@pytest.mark.asyncio
@patch("chromadb.AsyncHttpClient")
async def test_chroma_vector_store_check_health_failure(mock_client_cls):
    from app.integrations.vectorstores.chroma import ChromaDBVectorStore

    mock_client = AsyncMock()
    mock_client.heartbeat.side_effect = Exception("Chroma Host Unreachable")
    mock_client_cls.return_value = mock_client

    vs = ChromaDBVectorStore()
    res = await vs.check_health()
    assert res.status == "error"
    assert "Chroma Host Unreachable" in res.error_message



@pytest.mark.asyncio
@patch("app.core.health.check_database")
@patch("app.core.health.check_cache")
@patch("app.core.health.check_vector_store")
async def test_health_check_endpoint_all_ok(
    mock_check_vector_store, mock_check_cache, mock_check_database
):
    mock_check_database.return_value = ServiceHealth(status="ok", latency_ms=1.5)
    mock_check_cache.return_value = ServiceHealth(status="ok", latency_ms=2.0)
    mock_check_vector_store.return_value = ServiceHealth(status="ok", latency_ms=5.0)

    db_session = AsyncMock(spec=AsyncSession)
    mock_vs = AsyncMock()
    response = await health_check(db_session, mock_vs)

    assert response["status"] == "ok"
    assert response["services"]["database"] == "ok"
    assert response["services"]["cache"] == "ok"
    assert response["services"]["vector_store"] == "ok"


@pytest.mark.asyncio
@patch("app.core.health.check_database")
@patch("app.core.health.check_cache")
@patch("app.core.health.check_vector_store")
async def test_health_check_endpoint_degraded(
    mock_check_vector_store, mock_check_cache, mock_check_database
):
    mock_check_database.return_value = ServiceHealth(status="ok", latency_ms=1.5)
    mock_check_cache.return_value = ServiceHealth(status="error", latency_ms=2.0, error_message="cache error")
    mock_check_vector_store.return_value = ServiceHealth(status="ok", latency_ms=5.0)

    db_session = AsyncMock(spec=AsyncSession)
    mock_vs = AsyncMock()
    response = await health_check(db_session, mock_vs)

    assert response["status"] == "degraded"
    assert response["services"]["database"] == "ok"
    assert response["services"]["cache"] == "error"
    assert response["services"]["vector_store"] == "ok"


@pytest.mark.asyncio
@patch("app.core.health.check_database")
@patch("app.core.health.check_cache")
@patch("app.core.health.check_vector_store")
async def test_verify_connectivity_success(
    mock_check_vector_store, mock_check_cache, mock_check_database
):
    from app.core.health import verify_connectivity

    mock_check_database.return_value = ServiceHealth(status="ok", latency_ms=1.0)
    mock_check_cache.return_value = ServiceHealth(status="ok", latency_ms=1.0)
    mock_check_vector_store.return_value = ServiceHealth(status="ok", latency_ms=1.0)

    mock_vs = AsyncMock()
    await verify_connectivity(mock_vs)
    mock_check_database.assert_called_once_with()
    mock_check_cache.assert_called_once_with()
    mock_check_vector_store.assert_called_once_with(mock_vs)


@pytest.mark.asyncio
@patch("app.core.health.check_database")
@patch("app.core.health.check_cache")
@patch("app.core.health.check_vector_store")
async def test_verify_connectivity_failure(
    mock_check_vector_store, mock_check_cache, mock_check_database
):
    from app.core.health import verify_connectivity

    mock_check_database.return_value = ServiceHealth(status="error", latency_ms=1.0, error_message="DB down")
    mock_check_cache.return_value = ServiceHealth(status="ok", latency_ms=1.0)
    mock_check_vector_store.return_value = ServiceHealth(status="error", latency_ms=1.0, error_message="Chroma down")

    mock_vs = AsyncMock()
    with pytest.raises(ConnectionError) as exc_info:
        await verify_connectivity(mock_vs)

    assert "DB down" in str(exc_info.value)
    assert "Chroma down" in str(exc_info.value)
    assert "database:" in str(exc_info.value)
    assert "vector_store:" in str(exc_info.value)
    assert "cache" not in str(exc_info.value)
