"""
chunker.py

Splits per-page text into overlapping chunks suitable for embedding.

Chunks never span across a page boundary so page-number metadata
stays accurate.
"""

from dataclasses import dataclass
from typing import List

from .pdf_processor import PageText

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


@dataclass
class Chunk:
    text: str
    page_number: int


def chunk_page(page: PageText, chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> List[Chunk]:
    """Split a single page's text into overlapping chunks."""
    text = page.text
    if not text:
        return []

    if len(text) <= chunk_size:
        return [Chunk(text=text, page_number=page.page_number)]

    chunks: List[Chunk] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        if end < text_len:
            boundary = text.rfind(" ", start + int(chunk_size * 0.5), end)
            if boundary != -1:
                end = boundary

        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(Chunk(text=chunk_text, page_number=page.page_number))

        if end >= text_len:
            break

        next_start = end - overlap
        start = next_start if next_start > start else end

    return chunks


def chunk_pages(pages: List[PageText], chunk_size: int = CHUNK_SIZE,
                overlap: int = CHUNK_OVERLAP) -> List[Chunk]:
    """Chunk every page of a document and return a flat list of chunks."""
    all_chunks: List[Chunk] = []
    for page in pages:
        all_chunks.extend(chunk_page(page, chunk_size, overlap))
    return all_chunks
