import re
from typing import TypedDict
from app.lib.document.base import PageContent
from app.core.config import search_settings


class ChunkData(TypedDict):
    """Raw chunk data before it is persisted."""
    text: str
    page_number: int


class RecursiveCharacterTextSplitter:
    """Splits text recursively using a list of separators."""
    
    def __init__(self, chunk_size: int = search_settings.CHUNK_SIZE, chunk_overlap: int = search_settings.CHUNK_OVERLAP):
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._separators = ["\n\n", "\n", " ", ""]

    def _split_text(self, text: str, separators: list[str]) -> list[str]:
        """Recursively split text by separators until chunks are small enough."""
        final_chunks = []
        separator = separators[-1]
        for s in separators:
            if s == "":
                separator = s
                break
            if re.search(re.escape(s), text):
                separator = s
                break

        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)

        good_splits = []
        for s in splits:
            if len(s) < self._chunk_size:
                good_splits.append(s)
            else:
                if len(separators) > 1:
                    # Recursive split
                    next_level_splits = self._split_text(s, separators[1:])
                    good_splits.extend(next_level_splits)
                else:
                    # We are at character level ("") and it's still too large (impossible), 
                    # but just in case, we chunk by character chunks
                    for i in range(0, len(s), self._chunk_size):
                        good_splits.append(s[i:i + self._chunk_size])

        # Merge good splits with overlap
        current_doc = []
        length = 0
        for s in good_splits:
            s_len = len(s)
            if length + s_len + (len(separator) if len(current_doc) > 0 else 0) > self._chunk_size and len(current_doc) > 0:
                joined_text = separator.join(current_doc)
                if joined_text.strip():
                    final_chunks.append(joined_text.strip())
                
                # Setup next chunk with overlap
                while length > self._chunk_overlap or (
                    length + s_len + (len(separator) if len(current_doc) > 0 else 0) > self._chunk_size and len(current_doc) > 0
                ):
                    popped = current_doc.pop(0)
                    length -= len(popped) + (len(separator) if len(current_doc) > 0 else 0)
            
            current_doc.append(s)
            length += s_len + (len(separator) if len(current_doc) > 1 else 0)

        if current_doc:
            joined_text = separator.join(current_doc)
            if joined_text.strip():
                final_chunks.append(joined_text.strip())

        return final_chunks

    def split_pages(self, pages: list[PageContent]) -> list[ChunkData]:
        """Split pages into chunks, preserving page numbers."""
        chunks = []
        for page in pages:
            if not page.text.strip():
                continue
            texts = self._split_text(page.text, self._separators)
            for text in texts:
                chunks.append(ChunkData(text=text, page_number=page.page_number))
        return chunks
