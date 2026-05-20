import pytest
import io
from fastapi import UploadFile
from fastapi.exceptions import HTTPException

from app.services.document import DocumentService
from app.core.config import infra_settings

@pytest.mark.asyncio
async def test_upload_document_size_limit(mocker):
    # Mock settings to have a very small limit
    mocker.patch.object(infra_settings, 'MAX_UPLOAD_BYTES', 10)
    
    doc_repo = mocker.AsyncMock()
    service = DocumentService(doc_repo=doc_repo)
    
    # Create a dummy file larger than 10 bytes
    dummy_file = io.BytesIO(b"This is a dummy file larger than 10 bytes")
    upload_file = UploadFile(filename="test.pdf", file=dummy_file, headers={"content-type": "application/pdf"})
    
    with pytest.raises(HTTPException) as exc_info:
        await service.upload_document(upload_file)
        
    assert exc_info.value.status_code == 413

@pytest.mark.asyncio
async def test_upload_document_extension_check(mocker):
    doc_repo = mocker.AsyncMock()
    service = DocumentService(doc_repo=doc_repo)
    
    dummy_file = io.BytesIO(b"Dummy")
    upload_file = UploadFile(filename="test.txt", file=dummy_file, headers={"content-type": "text/plain"})
    
    with pytest.raises(HTTPException) as exc_info:
        await service.upload_document(upload_file)
        
    assert exc_info.value.status_code == 415


@pytest.mark.asyncio
async def test_upload_document_endpoint_success(mocker):
    from app.api.v1.endpoints.documents import upload_document
    from app.models.document import Document
    from app.models.chunk import Chunk
    from datetime import datetime
    import uuid

    # Mock file and service
    upload_file = mocker.MagicMock(spec=UploadFile)
    
    mock_doc = Document(
        id=uuid.uuid4(),
        filename="test.pdf",
        storage_filename="test_storage.pdf",
        status="pending",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    service = mocker.MagicMock(spec=DocumentService)
    service.upload_document = mocker.AsyncMock(return_value=mock_doc)
    
    # Mock session
    session = mocker.AsyncMock()
    session.commit = mocker.AsyncMock()
    session.refresh = mocker.AsyncMock()
    
    # Call the endpoint
    resp = await upload_document(file=upload_file, service=service, session=session)
    
    # Assert
    assert resp.filename == "test.pdf"
    assert resp.status == "pending"
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(mock_doc)

