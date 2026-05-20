import chromadb
from chromadb.config import Settings

from app.core.config import infra_settings
from app.integrations.vectorstores.base import BaseVectorStore, ChunkRecord

class ChromaDBVectorStore(BaseVectorStore):
    """ChromaDB implementation of the vector store."""
    
    def __init__(self):
        self._client = None
        self.collection_name = getattr(infra_settings, 'CHROMA_COLLECTION', 'documents')

    async def _get_client(self):
        if not self._client:
            self._client = await chromadb.AsyncHttpClient(
                host=infra_settings.CHROMA_HOST,
                port=infra_settings.CHROMA_PORT,
                settings=Settings(anonymized_telemetry=False)
            )
        return self._client

    async def _get_collection(self):
        client = await self._get_client()
        return await client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    async def upsert_batch(self, chunks: list[ChunkRecord]) -> None:
        if not chunks:
            return
            
        collection = await self._get_collection()
        
        ids = [c["id"] for c in chunks]
        embeddings = [c["embedding"] for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]
        
        await collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

    async def delete_by_doc_id(self, doc_id: str) -> None:
        collection = await self._get_collection()
        await collection.delete(where={"doc_id": doc_id})

    async def query(
        self,
        embedding: list[float],
        top_k: int = 50,
        doc_ids: list[str] | None = None
    ) -> dict:
        collection = await self._get_collection()
        
        where = None
        if doc_ids:
            if len(doc_ids) == 1:
                where = {"doc_id": doc_ids[0]}
            else:
                where = {"doc_id": {"$in": doc_ids}}

        results = await collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"]
        )
        return results
