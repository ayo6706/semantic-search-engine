from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.health import health_check
from app.core.health import ServiceHealth, check_chromadb, check_postgres, check_redis


@pytest.mark.asyncio
async def test_check_postgres_with_session_success():
    mock_session = AsyncMock(spec=AsyncSession)
    res = await check_postgres(mock_session)
    assert res.status == "ok"
    assert res.error_message is None
    assert isinstance(res.latency_ms, float)


@pytest.mark.asyncio
async def test_check_postgres_with_session_failure():
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute.side_effect = Exception("DB Connection Refused")
    res = await check_postgres(mock_session)
    assert res.status == "error"
    assert "DB Connection Refused" in res.error_message
    assert isinstance(res.latency_ms, float)


@pytest.mark.asyncio
@patch("app.core.database.engine")
async def test_check_postgres_no_session_success(mock_engine):
    mock_conn = AsyncMock()
    mock_engine.connect.return_value.__aenter__.return_value = mock_conn
    res = await check_postgres(None)
    assert res.status == "ok"
    assert res.error_message is None


@pytest.mark.asyncio
@patch("app.core.database.engine")
async def test_check_postgres_no_session_failure(mock_engine):
    mock_engine.connect.side_effect = Exception("DB Error")
    res = await check_postgres(None)
    assert res.status == "error"
    assert "DB Error" in res.error_message


@pytest.mark.asyncio
async def test_check_redis_with_client_success():
    mock_client = AsyncMock()
    res = await check_redis(mock_client)
    assert res.status == "ok"
    assert res.error_message is None
    mock_client.ping.assert_called_once()


@pytest.mark.asyncio
async def test_check_redis_with_client_failure():
    mock_client = AsyncMock()
    mock_client.ping.side_effect = Exception("Redis connection timed out")
    res = await check_redis(mock_client)
    assert res.status == "error"
    assert "Redis connection timed out" in res.error_message


@pytest.mark.asyncio
@patch("app.core.redis.get_redis_client")
async def test_check_redis_no_client_success(mock_get_redis_client):
    mock_client = AsyncMock()
    mock_get_redis_client.return_value = mock_client
    res = await check_redis(None)
    assert res.status == "ok"
    mock_client.ping.assert_called_once()


@pytest.mark.asyncio
@patch("app.core.redis.get_redis_client")
async def test_check_redis_no_client_failure(mock_get_redis_client):
    mock_get_redis_client.side_effect = Exception("Redis Init Failed")
    res = await check_redis(None)
    assert res.status == "error"
    assert "Redis Init Failed" in res.error_message


@pytest.mark.asyncio
async def test_check_chromadb_success():
    mock_vs = AsyncMock()
    mock_vs.check_health.return_value = ServiceHealth(status="ok", latency_ms=1.5)

    res = await check_chromadb(mock_vs)
    assert res.status == "ok"
    assert res.error_message is None
    assert res.latency_ms == 1.5
    mock_vs.check_health.assert_called_once()


@pytest.mark.asyncio
async def test_check_chromadb_failure():
    mock_vs = AsyncMock()
    mock_vs.check_health.return_value = ServiceHealth(status="error", latency_ms=1.5, error_message="Chroma down")

    res = await check_chromadb(mock_vs)
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
@patch("app.core.redis.check_health")
async def test_redis_verify_connectivity_uses_health_result(mock_check_health):
    from app.core import redis

    mock_check_health.return_value = ServiceHealth(status="ok", latency_ms=1.0)

    await redis.verify_connectivity()

    mock_check_health.assert_awaited_once_with()


@pytest.mark.asyncio
@patch("app.core.redis.check_health")
async def test_redis_verify_connectivity_raises_on_unhealthy_result(mock_check_health):
    from app.core import redis

    mock_check_health.return_value = ServiceHealth(
        status="error",
        latency_ms=1.0,
        error_message="operation timed out",
    )

    with pytest.raises(ConnectionError) as exc_info:
        await redis.verify_connectivity()

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
@patch("app.core.health.check_postgres")
@patch("app.core.health.check_redis")
@patch("app.core.health.check_chromadb")
async def test_health_check_endpoint_all_ok(
    mock_check_chromadb, mock_check_redis, mock_check_postgres
):
    mock_check_postgres.return_value = ServiceHealth(status="ok", latency_ms=1.5)
    mock_check_redis.return_value = ServiceHealth(status="ok", latency_ms=2.0)
    mock_check_chromadb.return_value = ServiceHealth(status="ok", latency_ms=5.0)

    db_session = AsyncMock(spec=AsyncSession)
    mock_vs = AsyncMock()
    response = await health_check(db_session, mock_vs)

    assert response["status"] == "ok"
    assert response["services"]["postgres"] == "ok"
    assert response["services"]["redis"] == "ok"
    assert response["services"]["chromadb"] == "ok"


@pytest.mark.asyncio
@patch("app.core.health.check_postgres")
@patch("app.core.health.check_redis")
@patch("app.core.health.check_chromadb")
async def test_health_check_endpoint_degraded(
    mock_check_chromadb, mock_check_redis, mock_check_postgres
):
    mock_check_postgres.return_value = ServiceHealth(status="ok", latency_ms=1.5)
    mock_check_redis.return_value = ServiceHealth(status="error", latency_ms=2.0, error_message="Redis error")
    mock_check_chromadb.return_value = ServiceHealth(status="ok", latency_ms=5.0)

    db_session = AsyncMock(spec=AsyncSession)
    mock_vs = AsyncMock()
    response = await health_check(db_session, mock_vs)

    assert response["status"] == "degraded"
    assert response["services"]["postgres"] == "ok"
    assert response["services"]["redis"] == "error"
    assert response["services"]["chromadb"] == "ok"


@pytest.mark.asyncio
@patch("app.core.health.check_postgres")
@patch("app.core.health.check_redis")
@patch("app.core.health.check_chromadb")
async def test_verify_connectivity_success(
    mock_check_chromadb, mock_check_redis, mock_check_postgres
):
    from app.core.health import verify_connectivity

    mock_check_postgres.return_value = ServiceHealth(status="ok", latency_ms=1.0)
    mock_check_redis.return_value = ServiceHealth(status="ok", latency_ms=1.0)
    mock_check_chromadb.return_value = ServiceHealth(status="ok", latency_ms=1.0)

    # Should not raise any exception
    mock_vs = AsyncMock()
    await verify_connectivity(mock_vs)


@pytest.mark.asyncio
@patch("app.core.health.check_postgres")
@patch("app.core.health.check_redis")
@patch("app.core.health.check_chromadb")
async def test_verify_connectivity_failure(
    mock_check_chromadb, mock_check_redis, mock_check_postgres
):
    from app.core.health import verify_connectivity

    mock_check_postgres.return_value = ServiceHealth(status="error", latency_ms=1.0, error_message="DB down")
    mock_check_redis.return_value = ServiceHealth(status="ok", latency_ms=1.0)
    mock_check_chromadb.return_value = ServiceHealth(status="error", latency_ms=1.0, error_message="Chroma down")

    mock_vs = AsyncMock()
    with pytest.raises(ConnectionError) as exc_info:
        await verify_connectivity(mock_vs)

    assert "DB down" in str(exc_info.value)
    assert "Chroma down" in str(exc_info.value)
    assert "Redis" not in str(exc_info.value)
