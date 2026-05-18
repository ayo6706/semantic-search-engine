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
