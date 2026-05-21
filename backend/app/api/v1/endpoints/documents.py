import os
import uuid
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from app.api.dependencies import get_document_service, get_vector_store, get_document_repository
from app.core.database import DbSessionDep
from app.repositories.document import DocumentRepository
from app.services.document import DocumentService
from app.schemas.document import DocumentResponse, DocumentListResponse
from app.core.config import infra_settings
from app.core.redis import get_redis_client
from app.integrations.vectorstores.chroma import ChromaDBVectorStore
from app.services.cache import SearchCacheService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=DocumentResponse)
async def upload_document(
    file: Annotated[UploadFile, File(...)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    session: DbSessionDep,
) -> DocumentResponse:
    """Upload a new PDF document for ingestion."""
    doc = await service.upload_document(file)
    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        if doc.storage_filename:
            file_path = os.path.join(infra_settings.UPLOAD_DIR, doc.storage_filename)
            if os.path.exists(file_path):
                os.remove(file_path)
        raise HTTPException(
            status_code=500,
            detail="Failed to save document metadata.",
        ) from exc
    await session.refresh(doc)
    return DocumentResponse.model_validate(doc)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    repo: Annotated[DocumentRepository, Depends(get_document_repository)],
) -> DocumentListResponse:
    """List all documents."""
    docs, total = await repo.list_documents()
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in docs],
        total=total
    )


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: uuid.UUID,
    repo: Annotated[DocumentRepository, Depends(get_document_repository)],
) -> DocumentResponse:
    """Get a document's status by ID."""
    doc = await repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentResponse.model_validate(doc)


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: uuid.UUID,
    session: DbSessionDep,
    vector_store: Annotated[ChromaDBVectorStore, Depends(get_vector_store)],
) -> None:
    """Delete a document and all its chunks from the database and vector store."""
    repo = DocumentRepository(session)
    doc = await repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    storage_filename = doc.storage_filename

    try:
        await vector_store.delete_by_doc_id(str(doc_id))
    except Exception as exc:
        logger.exception("Failed to delete Chroma vectors for document %s", doc_id)
        raise HTTPException(
            status_code=502,
            detail="Failed to delete document vectors.",
        ) from exc

    await session.rollback()
    try:
        async with session.begin():
            deleted = await repo.delete(doc_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Document not found.")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Document %s vectors were deleted, but database deletion failed",
            doc_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Document vectors were deleted, but database deletion failed.",
        ) from exc

    if storage_filename:
        file_path = os.path.join(infra_settings.UPLOAD_DIR, storage_filename)
        if os.path.exists(file_path):
            os.remove(file_path)

    try:
        cache = SearchCacheService(await get_redis_client())
        await cache.invalidate_all()
    except Exception:
        logger.exception("Cache invalidation failed after deleting document %s", doc_id)
