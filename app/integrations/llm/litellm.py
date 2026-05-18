import litellm
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import llm_settings
from app.integrations.llm.base import BaseLLMProvider


class LiteLLMProvider(BaseLLMProvider):
    """LiteLLM implementation of the LLM provider."""
    
    def __init__(self):
        self.model = llm_settings.EMBEDDING_MODEL
        self.dimensions = llm_settings.EMBEDDING_DIMENSIONS

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((litellm.exceptions.RateLimitError, litellm.exceptions.Timeout, litellm.exceptions.APIConnectionError))
    )
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
            
        response = await litellm.aembedding(
            model=self.model,
            input=texts,
            dimensions=self.dimensions
        )
        
        # Normalize response
        embeddings = []
        for data_obj in response.data:
            embeddings.append(data_obj["embedding"])
            
        if len(embeddings) != len(texts):
            raise ValueError(f"Provider returned {len(embeddings)} embeddings for {len(texts)} inputs.")
            
        return embeddings

    async def embed_text(self, text: str) -> list[float]:
        embeddings = await self.embed_batch([text])
        return embeddings[0]
