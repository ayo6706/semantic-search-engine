from __future__ import annotations

import logging
import os
import shutil
import uuid

import aiofiles
import fitz
from fastapi import HTTPException, UploadFile

from app.core.config import infra_settings
from app.core.queue import create_arq_pool
from app.models.document import Document
from app.repositories.document import DocumentRepository

logger = logging.getLogger(__name__)

_READ_CHUNK = 1024 * 1024  # 1 MB


class DocumentService:

    def __init__(self, doc_repo: DocumentRepository):
        self.doc_repo = doc_repo

    async def upload_document(self, file: UploadFile) -> Document:
        """Validate, persist, and enqueue a PDF for ingestion."""
        self._validate_upload(file)

        temp_path = self._temp_path()
        await self._save_to_disk(file, temp_path)
        self._assert_valid_pdf(temp_path)

        document = await self.doc_repo.create(
            filename=file.filename,
            storage_filename="",
        )
        final_path = self._final_path(document.id)
        self._move_file(temp_path, final_path)
        document.storage_filename = f"{document.id}.pdf"

        await self._enqueue(document, final_path)
        return document

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

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

    async def _enqueue(
        self, document: Document, file_path: str
    ) -> None:
        redis = None
        try:
            redis = await create_arq_pool()
            job = await redis.enqueue_job(
                "process_document", str(document.id)
            )
            if not job:
                raise RuntimeError("Job enqueue returned None")
        except Exception:
            await self.doc_repo.session.rollback()
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(
                status_code=500,
                detail="Failed to start ingestion process.",
            )
        finally:
            if redis:
                await redis.close()
