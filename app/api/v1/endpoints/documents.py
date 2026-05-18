import os
import uuid
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from app.core.database import DbSessionDep
from app.repositories.document import DocumentRepository
from app.services.document import DocumentService
from app.schemas.document import DocumentResponse, DocumentListResponse
from app.core.config import infra_settings
from app.integrations.vectorstores.chroma import ChromaDBVectorStore


router = APIRouter()
logger = logging.getLogger(__name__)


async def get_document_service(session: DbSessionDep) -> DocumentService:
    """Dependency for DocumentService."""
    repo = DocumentRepository(session)
    return DocumentService(repo)


async def get_vector_store() -> ChromaDBVectorStore:
    """Dependency for ChromaDB vector store operations."""
    return ChromaDBVectorStore()


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
    return DocumentResponse.model_validate(doc)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    session: DbSessionDep
) -> DocumentListResponse:
    """List all documents."""
    repo = DocumentRepository(session)
    docs, total = await repo.list_documents()
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in docs],
        total=total
    )


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: uuid.UUID,
    session: DbSessionDep
) -> DocumentResponse:
    """Get a document's status by ID."""
    repo = DocumentRepository(session)
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
