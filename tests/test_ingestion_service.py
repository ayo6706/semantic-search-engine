import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ingestion import IngestionService
from app.models.document import Document
from app.lib.document.base import PageContent

@pytest.mark.asyncio
async def test_ingestion_service_idempotent_skip():
    # Setup mocks
    session = AsyncMock()
    doc_repo = AsyncMock()
    chunk_repo = AsyncMock()
    parser = MagicMock()
    chunker = MagicMock()
    llm_provider = AsyncMock()
    vector_store = AsyncMock()
    
    # Document already ready
    doc_id_str = str(uuid.uuid4())
    doc = Document(id=uuid.UUID(doc_id_str), status="ready")
    doc_repo.get_by_id.return_value = doc
    
    service = IngestionService(
        session=session, doc_repo=doc_repo, chunk_repo=chunk_repo,
        parser=parser, chunker=chunker, llm_provider=llm_provider,
        vector_store=vector_store
    )
    
    await service.process_document(doc_id_str)
    
    # Verify processing was skipped
    parser.extract_text.assert_not_called()
    doc_repo.update_status.assert_not_called()

@pytest.mark.asyncio
async def test_ingestion_service_failure_cleanup():
    # Setup mocks
    session = AsyncMock()
    doc_repo = AsyncMock()
    chunk_repo = AsyncMock()
    parser = MagicMock()
    chunker = MagicMock()
    llm_provider = AsyncMock()
    vector_store = AsyncMock()
    
    doc_id_str = str(uuid.uuid4())
    doc = Document(id=uuid.UUID(doc_id_str), status="pending", storage_filename="test.pdf")
    
    # get_by_id returns the document successfully
    doc_repo.get_by_id.return_value = doc
    
    # parser raises error to simulate failure
    parser.extract_text.side_effect = ValueError("Corrupt PDF")
    
    service = IngestionService(
        session=session, doc_repo=doc_repo, chunk_repo=chunk_repo,
        parser=parser, chunker=chunker, llm_provider=llm_provider,
        vector_store=vector_store
    )
    
    with pytest.raises(ValueError, match="Corrupt PDF"):
        await service.process_document(doc_id_str)
        
    # Verify cleanup was called
    vector_store.delete_by_doc_id.assert_called_once_with(doc_id_str)
    chunk_repo.delete_by_doc_id.assert_called_once_with(uuid.UUID(doc_id_str))
    doc_repo.update_status.assert_any_call(uuid.UUID(doc_id_str), "failed", error_message="Corrupt PDF")
