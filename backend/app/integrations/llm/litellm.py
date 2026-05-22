import asyncio
import logging
import time
from collections import OrderedDict
from typing import cast

import litellm
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import llm_settings
from app.integrations.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

_BATCH_RATE_LIMIT_SECONDS = 4.2
_EMBEDDING_CACHE_MAXSIZE = 10_000


class LiteLLMProvider(BaseLLMProvider):
    """LiteLLM implementation of the LLM provider."""

    _cache: OrderedDict[str, list[float]] = OrderedDict()
    _last_call_time: float = 0.0
    _lock: asyncio.Lock | None = None

    def __init__(self) -> None:
        self.model = llm_settings.EMBEDDING_MODEL
        self.dimensions = llm_settings.EMBEDDING_DIMENSIONS

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    def _get_cached_embedding(cls, text: str) -> list[float] | None:
        if text not in cls._cache:
            return None
        embedding = cls._cache[text]
        cls._cache.move_to_end(text)
        return embedding

    @classmethod
    def _cache_embedding(cls, text: str, embedding: list[float]) -> None:
        cls._cache[text] = embedding
        cls._cache.move_to_end(text)
        while len(cls._cache) > _EMBEDDING_CACHE_MAXSIZE:
            cls._cache.popitem(last=False)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((
            litellm.exceptions.RateLimitError,
            litellm.exceptions.Timeout,
            litellm.exceptions.APIConnectionError,
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _call_embedding_api(self, texts: list[str]) -> list[list[float]]:
        start = time.perf_counter()
        response = await litellm.aembedding(
            model=self.model,
            input=texts,
            dimensions=self.dimensions,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        if elapsed_ms > 2000:
            logger.warning(
                "Embedding API took %.1fms for %d text(s)", elapsed_ms, len(texts)
            )

        return [item["embedding"] for item in response.data]

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text. No rate limiting — designed for the search path."""
        cached = self._get_cached_embedding(text)
        if cached is not None:
            return cached

        embeddings = await self._call_embedding_api([text])
        self._cache_embedding(text, embeddings[0])
        return embeddings[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts with rate limiting for ingestion."""
        if not texts:
            return []

        results: list[list[float] | None] = [None] * len(texts)
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        for idx, text in enumerate(texts):
            cached = self._get_cached_embedding(text)
            if cached is not None:
                results[idx] = cached
            else:
                uncached_indices.append(idx)
                uncached_texts.append(text)

        if uncached_texts:
            async with self._get_lock():
                now = time.time()
                elapsed = now - self._last_call_time
                if elapsed < _BATCH_RATE_LIMIT_SECONDS:
                    await asyncio.sleep(_BATCH_RATE_LIMIT_SECONDS - elapsed)

                embeddings = await self._call_embedding_api(uncached_texts)
                type(self)._last_call_time = time.time()

            if len(embeddings) != len(uncached_texts):
                raise ValueError(
                    f"Provider returned {len(embeddings)} embeddings "
                    f"for {len(uncached_texts)} inputs."
                )

            for i, embedding in enumerate(embeddings):
                self._cache_embedding(uncached_texts[i], embedding)
                results[uncached_indices[i]] = embedding

        return cast(list[list[float]], results)
