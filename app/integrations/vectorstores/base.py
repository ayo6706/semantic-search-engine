from abc import ABC, abstractmethod
from typing import TypedDict

class ChunkRecord(TypedDict):
    """Raw record to be upserted to vector store."""
    id: str
    text: str
    embedding: list[float]
    metadata: dict


class BaseVectorStore(ABC):
    """Abstract base class for vector stores."""

    @abstractmethod
    async def upsert_batch(self, chunks: list[ChunkRecord]) -> None:
        """Upsert a batch of chunk records into the vector store.
        
        Args:
            chunks: List of ChunkRecord to upsert.
        """
        pass

    @abstractmethod
    async def delete_by_doc_id(self, doc_id: str) -> None:
        """Delete all chunks belonging to a document.
        
        Must be idempotent (no error if document does not exist).
        
        Args:
            doc_id: The document UUID to delete.
        """
        pass
