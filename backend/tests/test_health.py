import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.core.health import check_postgres, check_redis, check_chromadb, ServiceHealth
from app.api.v1.endpoints.health import health_check


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
@patch("httpx.AsyncClient.get")
async def test_check_chromadb_v2_success(mock_get):
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_get.return_value = mock_resp
    res = await check_chromadb()
    assert res.status == "ok"
    assert res.error_message is None


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_check_chromadb_v1_fallback_success(mock_get):
    mock_resp_v1 = MagicMock(spec=httpx.Response)
    mock_resp_v1.status_code = 200
    mock_get.side_effect = [Exception("v2 failed"), mock_resp_v1]
    res = await check_chromadb()
    assert res.status == "ok"
    assert res.error_message is None
    assert mock_get.call_count == 2


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_check_chromadb_failure(mock_get):
    mock_get.side_effect = Exception("Chroma Host Unreachable")
    res = await check_chromadb()
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
    response = await health_check(db_session)

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
    response = await health_check(db_session)

    assert response["status"] == "degraded"
    assert response["services"]["postgres"] == "ok"
    assert response["services"]["redis"] == "error"
    assert response["services"]["chromadb"] == "ok"
