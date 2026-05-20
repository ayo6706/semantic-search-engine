from abc import ABC, abstractmethod

class BaseLLMProvider(ABC):
    """Abstract base class for LLM text embedding."""
    
    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text chunk.
        
        Args:
            text: Text to embed.
            
        Returns:
            A list of floats representing the embedding vector.
        """
        pass

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of text chunks.
        
        Args:
            texts: List of text strings to embed.
            
        Returns:
            A list of embedding vectors, ordered to match the input texts.
        """
        pass
