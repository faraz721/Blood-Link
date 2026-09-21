"""
pdf_processor.py

Extract text from a PDF while keeping page boundaries intact
so every chunk can be traced back to an exact page number.
"""

from dataclasses import dataclass
from typing import List

try:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError
except ImportError:
    # Fallback if only PyPDF2 is installed
    from PyPDF2 import PdfReader
    PdfReadError = Exception


class PDFProcessingError(Exception):
    """Raised when a PDF cannot be read or contains no usable text."""


@dataclass
class PageText:
    page_number: int  # 1-indexed
    text: str


def extract_pages(file_path: str) -> List[PageText]:
    """
    Extract text from every page of a PDF.

    Raises PDFProcessingError for:
      - files that are not valid PDFs / are corrupted
      - encrypted PDFs that cannot be opened
      - PDFs with zero extractable text (e.g. scanned image-only PDFs)
    """
    try:
        reader = PdfReader(file_path)
    except Exception as exc:
        raise PDFProcessingError(f"Could not open PDF file: {exc}") from exc

    if getattr(reader, "is_encrypted", False):
        try:
            result = reader.decrypt("")
            if result == 0:
                raise PDFProcessingError(
                    "This PDF is password-protected and cannot be read."
                )
        except Exception as exc:
            raise PDFProcessingError(
                "This PDF is password-protected and cannot be read."
            ) from exc

    if len(reader.pages) == 0:
        raise PDFProcessingError("This PDF has no pages.")

    pages: List[PageText] = []
    for index, page in enumerate(reader.pages):
        try:
            raw_text = page.extract_text() or ""
        except Exception:
            raw_text = ""
        cleaned = _clean_text(raw_text)
        pages.append(PageText(page_number=index + 1, text=cleaned))

    total_chars = sum(len(p.text) for p in pages)
    if total_chars < 10:
        raise PDFProcessingError(
            "No readable text was found in this PDF. It may be a scanned "
            "or image-only document that requires OCR, which is not supported."
        )

    return pages


def _clean_text(text: str) -> str:
    """Collapse excessive whitespace produced by PDF text extraction."""
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)
