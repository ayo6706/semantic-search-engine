import logging
from typing import Any

from app.core.queue import get_queue_settings
from app.core.database import async_session_factory
from app.repositories.document import DocumentRepository
from app.repositories.chunk import ChunkRepository
from app.lib.document.pymupdf import PyMuPDFParser
from app.services.chunker import RecursiveCharacterTextSplitter
from app.integrations.llm.litellm import LiteLLMProvider
from app.integrations.vectorstores.chroma import ChromaDBVectorStore
from app.services.ingestion import IngestionService
from app.services.cache import SearchCacheService
from app.core.cache import get_cache_client, shutdown as shutdown_cache

logger = logging.getLogger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    """Initialize stateless dependencies for the worker."""
    ctx["parser"] = PyMuPDFParser()
    ctx["chunker"] = RecursiveCharacterTextSplitter()
    ctx["llm_provider"] = LiteLLMProvider()
    ctx["vector_store"] = ChromaDBVectorStore()

async def shutdown(ctx: dict[str, Any]) -> None:
    """Clean up dependencies."""
    await shutdown_cache()

async def process_document(ctx: dict[str, Any], document_id: str) -> None:
    """arq task to process a document."""
    async with async_session_factory() as session:
        doc_repo = DocumentRepository(session)
        chunk_repo = ChunkRepository(session)
        
        ingestion_service = IngestionService(
            session=session,
            doc_repo=doc_repo,
            chunk_repo=chunk_repo,
            parser=ctx["parser"],
            chunker=ctx["chunker"],
            llm_provider=ctx["llm_provider"],
            vector_store=ctx["vector_store"],
        )
        
        try:
            await ingestion_service.process_document(document_id)
        except Exception as e:
            logger.error(f"Error processing document {document_id}: {e}")
            from tenacity import RetryError
            if isinstance(e, RetryError):
                raise RuntimeError(f"Ingestion failed after retries: {e.last_attempt.exception()}") from None
            raise

    try:
        cache = SearchCacheService(await get_cache_client())
        await cache.invalidate_all()
    except Exception:
        logger.exception("Cache invalidation failed, continuing ingestion")


class WorkerSettings:
    """arq worker configuration."""
    functions = [process_document]
    redis_settings = get_queue_settings()
    on_startup = startup
    on_shutdown = shutdown
    max_tries = 3
    job_timeout = 600  # 10 minutes timeout for ingestion
