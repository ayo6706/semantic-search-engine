import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.dependencies import get_document_service
from app.services.document import DocumentService
from app.schemas.document import DocumentResponse, DocumentListResponse

router = APIRouter()
DocumentFile = Annotated[UploadFile, File()]
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]


@router.post("", response_model=DocumentResponse)
async def upload_document(
    file: DocumentFile,
    service: DocumentServiceDep,
) -> DocumentResponse:
    """Upload a new PDF document for ingestion."""
    doc = await service.upload_document(file)
    return DocumentResponse.model_validate(doc)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    service: DocumentServiceDep,
) -> DocumentListResponse:
    """List all documents."""
    docs, total = await service.list_documents()
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in docs],
        total=total,
    )


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: uuid.UUID,
    service: DocumentServiceDep,
) -> DocumentResponse:
    """Get a document's status by ID."""
    doc = await service.get_document(doc_id)
    return DocumentResponse.model_validate(doc)


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: uuid.UUID,
    service: DocumentServiceDep,
) -> None:
    """Delete a document and all its chunks from the database and vector store."""
    await service.delete_document(doc_id)
