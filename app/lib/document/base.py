from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class PageContent:
    """Represents the text content of a single page in a document."""
    page_number: int
    text: str


class BaseDocumentParser(ABC):
    """Abstract base class for document parsers."""

    @abstractmethod
    def extract_text(self, file_path: str) -> list[PageContent]:
        """Extract text from a document.

        Args:
            file_path: The local path to the document file.

        Returns:
            A list of PageContent objects, one for each page.
            
        Raises:
            ValueError: If the file is invalid or corrupted.
        """
        pass
