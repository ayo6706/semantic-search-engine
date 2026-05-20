from app.services.chunker import RecursiveCharacterTextSplitter
from app.lib.document.base import PageContent
from app.lib.utils import build_chunk_id

def test_build_chunk_id_is_deterministic():
    doc_id = "123e4567-e89b-12d3-a456-426614174000"
    chunk_index = 5
    id1 = build_chunk_id(doc_id, chunk_index)
    id2 = build_chunk_id(doc_id, chunk_index)
    assert id1 == id2
    
    id3 = build_chunk_id(doc_id, 6)
    assert id1 != id3

def test_recursive_character_text_splitter():
    chunker = RecursiveCharacterTextSplitter(chunk_size=10, chunk_overlap=2)
    pages = [
        PageContent(page_number=1, text="Hello world! This is a test."),
        PageContent(page_number=2, text="Another page.")
    ]
    chunks = chunker.split_pages(pages)
    
    # We just do a basic sanity check that chunks are returned and page numbers are preserved
    assert len(chunks) > 0
    assert chunks[0]["page_number"] == 1
    assert chunks[-1]["page_number"] == 2
    
    # Check max length
    for chunk in chunks:
        assert len(chunk["text"]) <= 10
