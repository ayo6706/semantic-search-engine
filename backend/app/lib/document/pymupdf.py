import fitz

from app.lib.document.base import BaseDocumentParser, PageContent

class PyMuPDFParser(BaseDocumentParser):
    """Document parser using PyMuPDF (fitz) for PDF extraction."""

    def extract_text(self, file_path: str) -> list[PageContent]:
        """Extract text from a PDF file page by page.
        
        Args:
            file_path: The local path to the PDF file.
            
        Returns:
            A list of PageContent objects.
            
        Raises:
            ValueError: If the PDF cannot be opened or is corrupted.
        """
        pages = []
        doc = None
        try:
            doc = fitz.open(file_path)
            # Check if it's a valid PDF and can be opened
            if not doc.is_pdf:
                raise ValueError("File is not a valid PDF")

            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text()
                # page_number is 1-indexed for the user
                pages.append(PageContent(page_number=page_num + 1, text=text))

            return pages

        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Failed to open or parse PDF: {e}")
        finally:
            if doc is not None:
                doc.close()
