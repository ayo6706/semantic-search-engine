import asyncio
import time
import litellm
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import llm_settings
from app.integrations.llm.base import BaseLLMProvider


class LiteLLMProvider(BaseLLMProvider):
    """LiteLLM implementation of the LLM provider."""
    
    def __init__(self):
        self.model = llm_settings.EMBEDDING_MODEL
        self.dimensions = llm_settings.EMBEDDING_DIMENSIONS

    # Class-level static cache to persist across instances (e.g. across runner configurations)
    _cache: dict[str, list[float]] = {}
    _last_call_time: float = 0.0
    _lock: asyncio.Lock | None = None
    _local_model = None

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    @retry(
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=2, min=3, max=30),
        retry=retry_if_exception_type((litellm.exceptions.RateLimitError, litellm.exceptions.Timeout, litellm.exceptions.APIConnectionError))
    )
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
            
        results = [None] * len(texts)
        uncached_indices = []
        uncached_texts = []
        
        for idx, text in enumerate(texts):
            if text in self._cache:
                results[idx] = self._cache[text]
            else:
                uncached_indices.append(idx)
                uncached_texts.append(text)
                
        if uncached_texts:
            embeddings = []
            try:
                async with self._get_lock():
                    now = time.time()
                    elapsed = now - self._last_call_time
                    # 15 requests per minute = 1 request every 4 seconds. Use 4.2s for safety.
                    if elapsed < 4.2:
                        sleep_time = 4.2 - elapsed
                        await asyncio.sleep(sleep_time)
                    
                    response = await litellm.aembedding(
                        model=self.model,
                        input=uncached_texts,
                        dimensions=self.dimensions
                    )
                    self._last_call_time = time.time()
                
                for data_obj in response.data:
                    embeddings.append(data_obj["embedding"])
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"LiteLLM embedding failed: {e}. Falling back to local SentenceTransformer 'all-mpnet-base-v2'.")
                
                if LiteLLMProvider._local_model is None:
                    import os
                    from sentence_transformers import SentenceTransformer
                    cache_dir = os.environ.get("HF_HOME", "/app/.cache/huggingface")
                    LiteLLMProvider._local_model = SentenceTransformer(
                        "sentence-transformers/all-mpnet-base-v2",
                        cache_folder=cache_dir,
                    )
                
                loop = asyncio.get_running_loop()
                def encode_texts():
                    res = LiteLLMProvider._local_model.encode(uncached_texts)
                    return [[float(v) for v in vec] for vec in res]
                
                embeddings = await loop.run_in_executor(None, encode_texts)
                
            if len(embeddings) != len(uncached_texts):
                raise ValueError(f"Provider returned {len(embeddings)} embeddings for {len(uncached_texts)} inputs.")
                
            for idx, embedding in enumerate(embeddings):
                text = uncached_texts[idx]
                self._cache[text] = embedding
                original_idx = uncached_indices[idx]
                results[original_idx] = embedding
                
        return results

    async def embed_text(self, text: str) -> list[float]:
        embeddings = await self.embed_batch([text])
        return embeddings[0]
