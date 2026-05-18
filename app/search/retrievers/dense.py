from app.integrations.llm.base import BaseLLMProvider
from app.integrations.vectorstores.base import BaseVectorStore
from app.schemas.search import ScoredChunk
from app.search.retrievers.base import BaseRetriever


class DenseRetriever(BaseRetriever):
    """Retriever that uses dense vector embeddings and cosine similarity."""

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        vector_store: BaseVectorStore,
    ):
        self.llm_provider = llm_provider
        self.vector_store = vector_store

    async def retrieve(
        self,
        query: str,
        top_k: int = 50,
        doc_ids: list[str] | None = None
    ) -> list[ScoredChunk]:
        """Retrieve chunks using dense vector embeddings.
        
        Embeds the query using the LLM provider and queries the vector store.
        """
        if not query.strip():
            return []

        # Generate embedding for the query
        embedding = await self.llm_provider.embed_text(query)

        # Query the vector store
        results = await self.vector_store.query(
            embedding=embedding,
            top_k=top_k,
            doc_ids=doc_ids
        )

        chunks = []
        if not results or not results.get("ids") or not results["ids"][0]:
            return chunks

        # Parse ChromaDB results into ScoredChunk objects
        # ChromaDB returns lists of lists for multiple queries, but we only send one query embedding
        ids = results["ids"][0]
        distances = results["distances"][0]
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]

        for i in range(len(ids)):
            # Convert cosine distance to cosine similarity score (1 - distance)
            score = 1.0 - distances[i]
            metadata = metadatas[i] or {}
            try:
                doc_id = metadata["doc_id"]
                page_number = metadata["page_number"]
            except KeyError as exc:
                raise ValueError(
                    "ChromaDB result metadata is missing required key "
                    f"{exc.args[0]!r} at index {i}: {metadata!r}."
                ) from exc

            chunks.append(
                ScoredChunk(
                    id=ids[i],
                    doc_id=doc_id,
                    text=documents[i],
                    page_num=page_number,
                    dense_score=score
                )
            )

        return chunks
