from __future__ import annotations

import logging
import os
import shutil
import uuid

import aiofiles
import fitz
from fastapi import HTTPException, UploadFile

from app.core.config import infra_settings
from app.core.queue import create_queue_pool
from app.core.cache import get_cache_client
from app.integrations.vectorstores.base import BaseVectorStore
from app.models.document import Document
from app.repositories.document import DocumentRepository
from app.services.cache import SearchCacheService

logger = logging.getLogger(__name__)

_READ_CHUNK = 1024 * 1024  # 1 MB


class DocumentService:

    def __init__(
        self,
        doc_repo: DocumentRepository,
        vector_store: BaseVectorStore,
    ):
        self.doc_repo = doc_repo
        self.vector_store = vector_store

    async def upload_document(self, file: UploadFile) -> Document:
        """Validate, persist, and enqueue a PDF for ingestion."""
        self._validate_upload(file)

        temp_path = self._temp_path()
        final_path = ""

        try:
            await self._save_to_disk(file, temp_path)
            self._assert_valid_pdf(temp_path)

            document = await self.doc_repo.create(
                filename=file.filename,
                storage_filename="",
            )
            final_path = self._final_path(document.id)
            self._move_file(temp_path, final_path)
            document.storage_filename = f"{document.id}.pdf"

            await self._commit_upload(document, final_path)
        except HTTPException:
            await self.doc_repo.session.rollback()
            self._remove_file(temp_path)
            raise
        except Exception as exc:
            await self.doc_repo.session.rollback()
            self._remove_file(temp_path)
            self._remove_file(final_path)
            logger.exception("Failed to upload document %s", file.filename)
            raise HTTPException(
                status_code=500,
                detail="Failed to upload document.",
            ) from exc

        try:
            await self._enqueue(document)
        except HTTPException:
            await self._mark_upload_failed(document.id)
            raise
        return document

    async def list_documents(self) -> tuple[list[Document], int]:
        """List all documents and total count."""
        return await self.doc_repo.list_documents()

    async def get_document(self, doc_id: uuid.UUID) -> Document:
        """Get document by ID, raising 404 if not found."""
        doc = await self.doc_repo.get_by_id(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")
        return doc

    async def delete_document(self, doc_id: uuid.UUID) -> None:
        """Delete a document and all its chunks from the database and vector store."""
        doc = await self.doc_repo.get_by_id(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")
        storage_filename = doc.storage_filename

        session = self.doc_repo.session
        if session.in_transaction():
            # Clear read transaction state from the earlier lookup before opening a write transaction.
            await session.rollback()
        try:
            async with session.begin():
                deleted = await self.doc_repo.delete(doc_id)
                if not deleted:
                    raise HTTPException(status_code=404, detail="Document not found.")
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "Failed to delete database record for document %s",
                doc_id,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to delete document metadata.",
            ) from exc

        try:
            await self.vector_store.delete_by_doc_id(str(doc_id))
        except Exception as exc:
            logger.exception(
                "Failed to delete vectors from vector store for document %s",
                doc_id,
            )
            raise HTTPException(
                status_code=502,
                detail="Document metadata was deleted, but vector cleanup failed.",
            ) from exc

        if storage_filename:
            file_path = os.path.join(infra_settings.UPLOAD_DIR, storage_filename)
            if os.path.exists(file_path):
                os.remove(file_path)

        try:
            cache = SearchCacheService(await get_cache_client())
            await cache.invalidate_all()
        except Exception:
            logger.exception("Cache invalidation failed after deleting document %s", doc_id)

    @staticmethod
    def _validate_upload(file: UploadFile) -> None:
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)

        if size > infra_settings.MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"File too large. "
                    f"Max size is {infra_settings.MAX_UPLOAD_BYTES} bytes."
                ),
            )

        if not (file.filename or "").lower().endswith(".pdf"):
            raise HTTPException(
                status_code=415, detail="Only PDF files are supported."
            )
        if file.content_type != "application/pdf":
            raise HTTPException(
                status_code=415,
                detail="Invalid content type. Expected application/pdf.",
            )

    @staticmethod
    def _temp_path() -> str:
        os.makedirs(infra_settings.UPLOAD_DIR, exist_ok=True)
        return os.path.join(
            infra_settings.UPLOAD_DIR, f"temp_{uuid.uuid4()}.pdf"
        )

    @staticmethod
    def _final_path(doc_id: uuid.UUID) -> str:
        return os.path.join(infra_settings.UPLOAD_DIR, f"{doc_id}.pdf")

    @staticmethod
    async def _save_to_disk(file: UploadFile, dest: str) -> None:
        try:
            async with aiofiles.open(dest, "wb") as out:
                while chunk := await file.read(_READ_CHUNK):
                    await out.write(chunk)
        except Exception:
            if os.path.exists(dest):
                os.remove(dest)
            raise HTTPException(
                status_code=500, detail="Failed to save file."
            )

    @staticmethod
    def _assert_valid_pdf(path: str) -> None:
        doc = None
        valid = False
        try:
            doc = fitz.open(path)
            if not doc.is_pdf:
                raise HTTPException(
                    status_code=415,
                    detail="File is not a valid PDF document.",
                )
            valid = True
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=415, detail="Failed to parse PDF document."
            )
        finally:
            if doc is not None:
                doc.close()
            if not valid and os.path.exists(path):
                os.remove(path)

    @staticmethod
    def _move_file(src: str, dest: str) -> None:
        if os.path.exists(dest):
            os.remove(dest)
        try:
            os.replace(src, dest)
        except OSError:
            try:
                shutil.move(src, dest)
            except Exception:
                logger.exception(
                    "Failed to move uploaded file from %s to %s",
                    src,
                    dest,
                )
                if os.path.exists(src):
                    os.remove(src)
                raise

    async def _commit_upload(self, document: Document, file_path: str) -> None:
        try:
            await self.doc_repo.session.commit()
            await self.doc_repo.session.refresh(document)
        except Exception as exc:
            await self.doc_repo.session.rollback()
            self._remove_file(file_path)
            raise HTTPException(
                status_code=500,
                detail="Failed to save document metadata.",
            ) from exc

    async def _mark_upload_failed(self, doc_id: uuid.UUID) -> None:
        try:
            await self.doc_repo.update_status(
                doc_id,
                "failed",
                error_message="Failed to start ingestion process.",
            )
            await self.doc_repo.session.commit()
        except Exception:
            await self.doc_repo.session.rollback()
            logger.exception("Failed to mark document %s as failed", doc_id)

    async def _enqueue(self, document: Document) -> None:
        queue = None
        try:
            queue = await create_queue_pool()
            job = await queue.enqueue_job(
                "process_document", str(document.id)
            )
            if not job:
                raise RuntimeError("Job enqueue returned None")
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail="Failed to start ingestion process.",
            ) from exc
        finally:
            if queue:
                await queue.close()

    @staticmethod
    def _remove_file(path: str) -> None:
        if path and os.path.exists(path):
            os.remove(path)
