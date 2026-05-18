import os
import logging
import asyncio
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import infra_settings
from app.repositories.document import DocumentRepository
from app.repositories.chunk import ChunkRepository
from app.lib.document.pymupdf import PyMuPDFParser
from app.services.chunker import RecursiveCharacterTextSplitter
from app.integrations.llm.litellm import LiteLLMProvider
from app.integrations.vectorstores.chroma import ChromaDBVectorStore
from app.lib.utils import build_chunk_id

logger = logging.getLogger(__name__)


class IngestionService:
    """Coordinates the document ingestion pipeline."""

    def __init__(
        self,
        session: AsyncSession,
        doc_repo: DocumentRepository,
        chunk_repo: ChunkRepository,
        parser: PyMuPDFParser,
        chunker: RecursiveCharacterTextSplitter,
        llm_provider: LiteLLMProvider,
        vector_store: ChromaDBVectorStore,
    ):
        self.session = session
        self.doc_repo = doc_repo
        self.chunk_repo = chunk_repo
        self.parser = parser
        self.chunker = chunker
        self.llm_provider = llm_provider
        self.vector_store = vector_store

    async def process_document(self, doc_id_str: str) -> None:
        """Run the ingestion pipeline for a document."""
        doc_id = UUID(doc_id_str)

        # 1. Idempotency Check
        document = await self.doc_repo.get_by_id(doc_id)
        if not document:
            logger.info(f"Document {doc_id} not found, skipping ingestion.")
            return

        if document.status == "ready":
            logger.info(f"Document {doc_id} is already ready, skipping ingestion.")
            return

        if document.status == "processing":
            logger.info(f"Document {doc_id} is stuck in processing, cleaning up before retry.")
            await self.vector_store.delete_by_doc_id(doc_id_str)
            await self.chunk_repo.delete_by_doc_id(doc_id)
            await self.session.commit()

        # 2. Mark processing
        await self.doc_repo.update_status(doc_id, "processing")
        await self.session.commit()

        # Refresh document to get updated storage_filename if needed
        document = await self.doc_repo.get_by_id(doc_id)
        file_path = os.path.join(infra_settings.UPLOAD_DIR, document.storage_filename)

        try:
            # 3. Parse and Embed
            pages = await asyncio.to_thread(self.parser.extract_text, file_path)
            chunk_data_list = await asyncio.to_thread(self.chunker.split_pages, pages)

            if not chunk_data_list:
                raise ValueError("No text could be extracted from the document.")

            texts = [c["text"] for c in chunk_data_list]
            embeddings = await self.llm_provider.embed_batch(texts)

            # Build records
            vector_records = []
            db_records = []
            for i, (chunk_data, embedding) in enumerate(zip(chunk_data_list, embeddings)):
                chunk_id = build_chunk_id(doc_id_str, i)

                vector_records.append({
                    "id": chunk_id,
                    "text": chunk_data["text"],
                    "embedding": embedding,
                    "metadata": {
                        "doc_id": doc_id_str,
                        "page_number": chunk_data["page_number"],
                        "chunk_index": i,
                        "filename": document.filename
                    }
                })

                db_records.append({
                    "id": chunk_id,
                    "doc_id": doc_id,
                    "text": chunk_data["text"],
                    "page_number": chunk_data["page_number"],
                    "chunk_index": i
                })

            # 4. Race Check 1
            current_doc = await self.doc_repo.get_by_id(doc_id)
            if not current_doc:
                logger.info(f"Document {doc_id} deleted during parsing, aborting.")
                return

            # 5. Write ChromaDB
            await self.vector_store.upsert_batch(vector_records)

            # 6. Race Check 2 & DB Commit
            current_doc = await self.doc_repo.get_by_id(doc_id)
            if not current_doc:
                logger.info(f"Document {doc_id} deleted during Chroma write, cleaning up.")
                await self.vector_store.delete_by_doc_id(doc_id_str)
                return

            await self.chunk_repo.bulk_insert(db_records)
            await self.doc_repo.update_counts(doc_id, page_count=len(pages), chunk_count=len(db_records))
            await self.doc_repo.update_status(doc_id, "ready")
            await self.session.commit()

            logger.info(f"Successfully ingested document {doc_id}")

        except Exception as e:
            logger.error(f"Failed to ingest document {doc_id}: {e}", exc_info=True)
            await self.session.rollback() # Rollback any pending transactions

            # 7. Failure Handling
            # Attempt to clean up Chroma vectors to prevent orphans
            try:
                await self.vector_store.delete_by_doc_id(doc_id_str)
            except Exception as chroma_error:
                logger.error(f"Failed to cleanup Chroma vectors for {doc_id}: {chroma_error}")

            # Attempt to clean up DB and update status
            try:
                current_doc = await self.doc_repo.get_by_id(doc_id)
                if current_doc:
                    await self.chunk_repo.delete_by_doc_id(doc_id)
                    await self.doc_repo.update_status(doc_id, "failed", error_message=str(e))
                    await self.session.commit()
            except Exception as db_cleanup_error:
                logger.error(f"Failed to update DB status after ingestion error for {doc_id}: {db_cleanup_error}")
                await self.session.rollback()

            # Since max_tries=3 is set in arq, we re-raise the exception so it will retry
            raise
