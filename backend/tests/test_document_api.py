import pytest
import io
from fastapi import UploadFile
from fastapi.exceptions import HTTPException

from app.services.document import DocumentService
from app.core.config import infra_settings

@pytest.mark.asyncio
async def test_upload_document_size_limit(mocker):
    mocker.patch.object(infra_settings, 'MAX_UPLOAD_BYTES', 10)

    doc_repo = mocker.AsyncMock()
    service = DocumentService(doc_repo=doc_repo, vector_store=mocker.AsyncMock())

    dummy_file = io.BytesIO(b"This is a dummy file larger than 10 bytes")
    upload_file = UploadFile(filename="test.pdf", file=dummy_file, headers={"content-type": "application/pdf"})

    with pytest.raises(HTTPException) as exc_info:
        await service.upload_document(upload_file)

    assert exc_info.value.status_code == 413


@pytest.mark.asyncio
async def test_upload_document_extension_check(mocker):
    doc_repo = mocker.AsyncMock()
    service = DocumentService(doc_repo=doc_repo, vector_store=mocker.AsyncMock())

    dummy_file = io.BytesIO(b"Dummy")
    upload_file = UploadFile(filename="test.txt", file=dummy_file, headers={"content-type": "text/plain"})

    with pytest.raises(HTTPException) as exc_info:
        await service.upload_document(upload_file)

    assert exc_info.value.status_code == 415


@pytest.mark.asyncio
async def test_upload_document_service_commits_and_refreshes(mocker):
    from app.models.document import Document
    import uuid

    doc_id = uuid.uuid4()
    mock_doc = Document(
        id=doc_id,
        filename="test.pdf",
        storage_filename="",
        status="pending",
    )
    mock_session = mocker.AsyncMock()
    mock_repo = mocker.AsyncMock()
    mock_repo.session = mock_session
    mock_repo.create.return_value = mock_doc

    service = DocumentService(
        doc_repo=mock_repo,
        vector_store=mocker.AsyncMock(),
    )
    mocker.patch.object(service, "_temp_path", return_value="/tmp/upload.pdf")
    mocker.patch.object(service, "_final_path", return_value=f"/tmp/{doc_id}.pdf")
    mocker.patch.object(service, "_save_to_disk", mocker.AsyncMock())
    mocker.patch.object(service, "_assert_valid_pdf")
    mocker.patch.object(service, "_move_file")
    mocker.patch.object(service, "_enqueue", mocker.AsyncMock())

    upload_file = UploadFile(
        filename="test.pdf",
        file=io.BytesIO(b"%PDF-1.7"),
        headers={"content-type": "application/pdf"},
    )

    result = await service.upload_document(upload_file)

    assert result is mock_doc
    assert result.storage_filename == f"{doc_id}.pdf"
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(mock_doc)


@pytest.mark.asyncio
async def test_upload_document_endpoint_success(mocker):
    from app.api.v1.endpoints.documents import upload_document
    from app.models.document import Document
    from datetime import datetime
    import uuid

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

    resp = await upload_document(file=upload_file, service=service)

    assert resp.filename == "test.pdf"
    assert resp.status == "pending"
    service.upload_document.assert_awaited_once_with(upload_file)


@pytest.mark.asyncio
async def test_list_documents_endpoint(mocker):
    from app.api.v1.endpoints.documents import list_documents
    from app.models.document import Document
    from datetime import datetime
    import uuid

    mock_service = mocker.MagicMock()
    mock_docs = [
        Document(
            id=uuid.uuid4(),
            filename="test1.pdf",
            status="ready",
            created_at=datetime.now(),
            updated_at=datetime.now()
        ),
        Document(
            id=uuid.uuid4(),
            filename="test2.pdf",
            status="processing",
            created_at=datetime.now(),
            updated_at=datetime.now()
        ),
    ]
    mock_service.list_documents = mocker.AsyncMock(return_value=(mock_docs, 2))

    resp = await list_documents(service=mock_service)
    assert resp.total == 2
    assert len(resp.items) == 2
    assert resp.items[0].filename == "test1.pdf"
    assert resp.items[1].filename == "test2.pdf"


@pytest.mark.asyncio
async def test_get_document_endpoint_success(mocker):
    from app.api.v1.endpoints.documents import get_document
    from app.models.document import Document
    from datetime import datetime
    import uuid

    mock_service = mocker.MagicMock()
    doc_id = uuid.uuid4()
    mock_doc = Document(
        id=doc_id,
        filename="test1.pdf",
        status="ready",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    mock_service.get_document = mocker.AsyncMock(return_value=mock_doc)

    resp = await get_document(doc_id=doc_id, service=mock_service)
    assert resp.filename == "test1.pdf"
    assert resp.status == "ready"


@pytest.mark.asyncio
async def test_get_document_endpoint_not_found(mocker):
    from app.api.v1.endpoints.documents import get_document
    import uuid

    mock_service = mocker.MagicMock()
    doc_id = uuid.uuid4()
    mock_service.get_document = mocker.AsyncMock(
        side_effect=HTTPException(status_code=404, detail="Document not found.")
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_document(doc_id=doc_id, service=mock_service)

    assert exc_info.value.status_code == 404
