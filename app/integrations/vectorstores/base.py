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

    @abstractmethod
    async def query(
        self,
        embedding: list[float],
        top_k: int = 50,
        doc_ids: list[str] | None = None
    ) -> dict:
        """Query the vector store by embedding similarity.
        
        Args:
            embedding: The query vector.
            top_k: Maximum number of results to return.
            doc_ids: Optional list of document IDs to filter by.
            
        Returns:
            A dictionary containing the query results (implementation specific format,
            but should contain ids, documents, metadatas, and distances).
        """
        pass
