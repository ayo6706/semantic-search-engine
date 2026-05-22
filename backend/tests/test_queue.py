from unittest.mock import AsyncMock

import pytest

from app.core.config import infra_settings


def test_queue_boundary_delegates_settings(mocker):
    from app.core import queue

    expected = object()
    mock_parse = mocker.patch(
        "app.core.queue.arq_redis.parse_queue_settings",
        return_value=expected,
    )

    assert queue.get_queue_settings() is expected
    mock_parse.assert_called_once_with()


@pytest.mark.asyncio
async def test_queue_boundary_delegates_pool_creation(mocker):
    from app.core import queue

    expected = object()
    mock_create = mocker.patch(
        "app.core.queue.arq_redis.create_queue_pool",
        AsyncMock(return_value=expected),
    )

    assert await queue.create_queue_pool() is expected
    mock_create.assert_awaited_once_with()


def test_arq_redis_parse_queue_settings(mocker):
    from app.integrations.queues.arq_redis import parse_queue_settings

    mocker.patch.object(
        infra_settings,
        "REDIS_URL",
        "redis://:secret@example.test:6380/3",
    )

    settings = parse_queue_settings()

    assert settings.host == "example.test"
    assert settings.port == 6380
    assert settings.password == "secret"
    assert settings.database == 3


def test_arq_redis_parse_queue_settings_rejects_invalid_database(mocker):
    from app.integrations.queues.arq_redis import parse_queue_settings

    mocker.patch.object(
        infra_settings,
        "REDIS_URL",
        "redis://localhost/not-a-number",
    )

    with pytest.raises(ValueError, match="Invalid queue database index"):
        parse_queue_settings()


def test_arq_redis_parse_queue_settings_rejects_empty_url(mocker):
    from app.integrations.queues.arq_redis import parse_queue_settings

    mocker.patch.object(infra_settings, "REDIS_URL", "")

    with pytest.raises(ValueError, match="required"):
        parse_queue_settings()


@pytest.mark.parametrize("url", ["http://localhost:6379/0", "postgres://localhost/db"])
def test_arq_redis_parse_queue_settings_rejects_invalid_scheme(mocker, url):
    from app.integrations.queues.arq_redis import parse_queue_settings

    mocker.patch.object(infra_settings, "REDIS_URL", url)

    with pytest.raises(ValueError, match="redis:// or rediss://"):
        parse_queue_settings()


@pytest.mark.parametrize("url", ["redis:///0", "redis://"])
def test_arq_redis_parse_queue_settings_rejects_missing_hostname(mocker, url):
    from app.integrations.queues.arq_redis import parse_queue_settings

    mocker.patch.object(infra_settings, "REDIS_URL", url)

    with pytest.raises(ValueError, match="hostname"):
        parse_queue_settings()


def test_arq_redis_parse_queue_settings_defaults_port(mocker):
    from app.integrations.queues.arq_redis import parse_queue_settings

    mocker.patch.object(infra_settings, "REDIS_URL", "redis://localhost/0")

    assert parse_queue_settings().port == 6379


def test_arq_redis_parse_queue_settings_allows_missing_password(mocker):
    from app.integrations.queues.arq_redis import parse_queue_settings

    mocker.patch.object(infra_settings, "REDIS_URL", "redis://localhost:6379/0")

    assert parse_queue_settings().password is None


@pytest.mark.parametrize("url", ["redis://localhost:6379", "redis://localhost:6379/"])
def test_arq_redis_parse_queue_settings_defaults_database(mocker, url):
    from app.integrations.queues.arq_redis import parse_queue_settings

    mocker.patch.object(infra_settings, "REDIS_URL", url)

    assert parse_queue_settings().database == 0
