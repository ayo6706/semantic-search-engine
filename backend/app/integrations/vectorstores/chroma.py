import time
import chromadb
from chromadb.config import Settings

from app.core.config import infra_settings
from app.integrations.vectorstores.base import BaseVectorStore, ChunkRecord
from app.schemas.health import ServiceHealth


class ChromaDBVectorStore(BaseVectorStore):
    """ChromaDB implementation of the vector store."""

    def __init__(self):
        self._client = None
        self.collection_name = getattr(infra_settings, 'CHROMA_COLLECTION', 'documents')

    async def verify_connectivity(self) -> None:
        """Verify startup connectivity by checking the ChromaDB heartbeat."""
        health = await self.check_health()
        if health.status == "error":
            raise ConnectionError(f"ChromaDB connection failed: {health.error_message}")

    async def check_health(self) -> ServiceHealth:
        """Measure health status and latency of the ChromaDB connection."""
        start_time = time.perf_counter()
        try:
            client = await self._get_client()
            await client.heartbeat()
            latency = (time.perf_counter() - start_time) * 1000.0
            return ServiceHealth(status="ok", latency_ms=latency)
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000.0
            return ServiceHealth(status="error", latency_ms=latency, error_message=str(e))

    async def _get_client(self):
        if not self._client:
            self._client = await chromadb.AsyncHttpClient(
                host=infra_settings.CHROMA_HOST,
                port=infra_settings.CHROMA_PORT,
                settings=Settings(anonymized_telemetry=False)
            )
        return self._client

    async def shutdown(self) -> None:
        """Close the underlying Chroma client and its connection pool."""
        if self._client:
            import asyncio
            for close_name in ("aclose", "close_async", "close"):
                if hasattr(self._client, close_name):
                    close_method = getattr(self._client, close_name)
                    if asyncio.iscoroutinefunction(close_method):
                        await close_method()
                    else:
                        close_method()
            if hasattr(self._client, "_server") and hasattr(self._client._server, "_clients"):
                for client in list(self._client._server._clients.values()):
                    await client.aclose()
                self._client._server._clients.clear()

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
