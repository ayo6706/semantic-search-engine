import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import litellm

from app.integrations.llm.litellm import LiteLLMProvider


@pytest.fixture(autouse=True)
def _clear_class_state():
    """Reset class-level state between tests."""
    LiteLLMProvider._cache.clear()
    LiteLLMProvider._last_call_time = 0.0
    LiteLLMProvider._lock = None
    yield
    LiteLLMProvider._cache.clear()
    LiteLLMProvider._last_call_time = 0.0
    LiteLLMProvider._lock = None


def _make_embedding_response(embeddings: list[list[float]]):
    """Build a mock litellm embedding response."""
    response = MagicMock()
    response.data = [{"embedding": emb} for emb in embeddings]
    return response


def _make_api_connection_error() -> litellm.exceptions.APIConnectionError:
    return litellm.exceptions.APIConnectionError(
        message="connection failed",
        model="test",
        llm_provider="gemini",
    )


@pytest.mark.asyncio
async def test_embed_text_calls_api():
    provider = LiteLLMProvider()
    fake_embedding = [0.1, 0.2, 0.3]

    with patch("app.integrations.llm.litellm.litellm.aembedding", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = _make_embedding_response([fake_embedding])
        result = await provider.embed_text("hello")

    assert result == fake_embedding
    mock_api.assert_awaited_once()


@pytest.mark.asyncio
async def test_embed_text_uses_cache():
    provider = LiteLLMProvider()
    cached = [0.4, 0.5, 0.6]
    LiteLLMProvider._cache["cached query"] = cached

    with patch("app.integrations.llm.litellm.litellm.aembedding", new_callable=AsyncMock) as mock_api:
        result = await provider.embed_text("cached query")

    assert result == cached
    mock_api.assert_not_awaited()


@pytest.mark.asyncio
async def test_embed_text_populates_cache():
    provider = LiteLLMProvider()
    fake_embedding = [0.7, 0.8, 0.9]

    with patch("app.integrations.llm.litellm.litellm.aembedding", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = _make_embedding_response([fake_embedding])
        await provider.embed_text("new query")

    assert LiteLLMProvider._cache["new query"] == fake_embedding


@pytest.mark.asyncio
async def test_embed_batch_rate_limits(monkeypatch):
    """Batch calls enforce the rate limiter sleep between API calls."""
    import time
    provider = LiteLLMProvider()

    # Simulate a recent call so the rate limiter should trigger a sleep.
    LiteLLMProvider._last_call_time = time.time()

    sleep_called_with = []

    async def mock_sleep(duration):
        sleep_called_with.append(duration)

    monkeypatch.setattr("app.integrations.llm.litellm.asyncio.sleep", mock_sleep)

    with patch("app.integrations.llm.litellm.litellm.aembedding", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = _make_embedding_response([[0.1]])
        await provider.embed_batch(["text"])

    assert len(sleep_called_with) == 1
    assert sleep_called_with[0] > 0


@pytest.mark.asyncio
async def test_embed_text_does_not_rate_limit(monkeypatch):
    """Single-text search path bypasses the rate limiter."""
    import time
    provider = LiteLLMProvider()
    LiteLLMProvider._last_call_time = time.time()

    sleep_called = False

    async def mock_sleep(duration):
        nonlocal sleep_called
        sleep_called = True

    monkeypatch.setattr("app.integrations.llm.litellm.asyncio.sleep", mock_sleep)

    with patch("app.integrations.llm.litellm.litellm.aembedding", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = _make_embedding_response([[0.1]])
        await provider.embed_text("search query")

    assert not sleep_called


@pytest.mark.asyncio
async def test_retry_on_rate_limit():
    provider = LiteLLMProvider()

    with patch("app.integrations.llm.litellm.litellm.aembedding", new_callable=AsyncMock) as mock_api:
        mock_api.side_effect = [
            litellm.exceptions.RateLimitError(
                message="rate limited",
                model="test",
                llm_provider="gemini",
            ),
            _make_embedding_response([[1.0, 2.0]]),
        ]
        result = await provider.embed_text("retry test")

    assert result == [1.0, 2.0]
    assert mock_api.await_count == 2


@pytest.mark.asyncio
async def test_retry_on_timeout():
    provider = LiteLLMProvider()

    with patch("app.integrations.llm.litellm.litellm.aembedding", new_callable=AsyncMock) as mock_api:
        mock_api.side_effect = [
            litellm.exceptions.Timeout(
                message="timed out",
                model="test",
                llm_provider="gemini",
            ),
            _make_embedding_response([[3.0, 4.0]]),
        ]
        result = await provider.embed_text("timeout retry test")

    assert result == [3.0, 4.0]
    assert mock_api.await_count == 2


@pytest.mark.asyncio
async def test_no_fallback_on_non_retryable_failure():
    """Non-retryable exceptions propagate instead of silently falling back."""
    provider = LiteLLMProvider()

    with patch("app.integrations.llm.litellm.litellm.aembedding", new_callable=AsyncMock) as mock_api:
        mock_api.side_effect = litellm.exceptions.ServiceUnavailableError(
            message="service down",
            model="test",
            llm_provider="gemini",
        )
        with pytest.raises(litellm.exceptions.ServiceUnavailableError):
            await provider.embed_text("should fail")


@pytest.mark.asyncio
async def test_embed_batch_returns_empty_for_empty_input():
    provider = LiteLLMProvider()
    result = await provider.embed_batch([])
    assert result == []


@pytest.mark.asyncio
async def test_embed_batch_caches_results():
    provider = LiteLLMProvider()
    embeddings = [[0.1, 0.2], [0.3, 0.4]]

    with patch("app.integrations.llm.litellm.litellm.aembedding", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = _make_embedding_response(embeddings)
        result = await provider.embed_batch(["text_a", "text_b"])

    assert result == embeddings
    assert LiteLLMProvider._cache["text_a"] == [0.1, 0.2]
    assert LiteLLMProvider._cache["text_b"] == [0.3, 0.4]


@pytest.mark.asyncio
async def test_embed_batch_skips_cached_texts():
    provider = LiteLLMProvider()
    LiteLLMProvider._cache["already_cached"] = [9.0, 9.0]

    with patch("app.integrations.llm.litellm.litellm.aembedding", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = _make_embedding_response([[1.0, 1.0]])
        result = await provider.embed_batch(["already_cached", "new_text"])

    assert result[0] == [9.0, 9.0]
    assert result[1] == [1.0, 1.0]
    # Only the uncached text should have been sent to the API.
    call_args = mock_api.call_args
    assert call_args.kwargs["input"] == ["new_text"]


@pytest.mark.asyncio
async def test_embed_batch_raises_on_mismatched_count():
    provider = LiteLLMProvider()

    with patch("app.integrations.llm.litellm.litellm.aembedding", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = _make_embedding_response([[1.0, 1.0]])

        with pytest.raises(ValueError, match="Provider returned 1 embeddings for 2 inputs"):
            await provider.embed_batch(["first", "second"])


@pytest.mark.asyncio
async def test_embed_batch_retries_on_api_connection_error():
    provider = LiteLLMProvider()

    with patch("app.integrations.llm.litellm.litellm.aembedding", new_callable=AsyncMock) as mock_api:
        mock_api.side_effect = [
            _make_api_connection_error(),
            _make_embedding_response([[1.0, 2.0]]),
        ]

        result = await provider.embed_batch(["retry batch"])

    assert result == [[1.0, 2.0]]
    assert mock_api.await_count == 2


@pytest.mark.asyncio
async def test_embed_batch_raises_after_api_connection_retry_exhaustion():
    provider = LiteLLMProvider()

    with patch("app.integrations.llm.litellm.litellm.aembedding", new_callable=AsyncMock) as mock_api:
        mock_api.side_effect = [
            _make_api_connection_error(),
            _make_api_connection_error(),
            _make_api_connection_error(),
        ]

        with pytest.raises(litellm.exceptions.APIConnectionError):
            await provider.embed_batch(["retry exhaustion"])

    assert mock_api.await_count == 3
