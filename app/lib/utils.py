import uuid

def build_chunk_id(doc_id: str, chunk_index: int) -> str:
    """Generate a deterministic UUID5 for a chunk based on its document ID and index.
    
    Args:
        doc_id: The document UUID string.
        chunk_index: The chunk's sequential index.
        
    Returns:
        A deterministic UUID string.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}:{chunk_index}"))
