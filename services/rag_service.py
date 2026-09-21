"""
BloodLink RAG service — upgraded retrieval layer.

Uses Sentence Transformers (all-MiniLM-L6-v2) + FAISS for semantic
retrieval over the fixed knowledge base PDF.

Public API kept compatible with the old TF-IDF version so
services/ai_service.py continues to work unchanged:

  - get_context_for_question(question) -> str
  - build_index() -> dict
  - retrieve(query, top_k) -> List[str]
"""

from pathlib import Path
from typing import List, Dict

from rag.embeddings import embed_texts, embedding_dimension
from rag.pdf_processor import extract_pages, PDFProcessingError
from rag.chunker import chunk_pages
from rag.vector_store import get_vector_store, VectorStore
from rag.retriever import retrieve as semantic_retrieve

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
KB_PDF = BASE_DIR / "knowledge_base" / "blood_donation_guide.pdf"
INDEX_DIR = BASE_DIR / "rag_index"

# Fallback text if PDF is missing or empty
FALLBACK_TEXT = (
    "Blood donation is a voluntary process where a person donates blood "
    "that can be used for transfusions. Common blood groups are A, B, AB and O, "
    "each with positive or negative Rh factor. O negative is the universal donor. "
    "AB positive is the universal recipient. Donors should be healthy, aged 18-65, "
    "weigh at least 50 kg, and not have donated in the last 3 months (for whole blood). "
    "People with certain infections, low hemoglobin, or recent surgeries may be deferred. "
    "Always consult a medical professional for eligibility."
)


def _get_store() -> VectorStore:
    dim = embedding_dimension()
    return get_vector_store(dim)


def build_index() -> Dict:
    """
    Build (or rebuild) the FAISS index from the fixed knowledge PDF.
    Call this once after placing/updating knowledge_base/blood_donation_guide.pdf
    or run: python scripts/build_rag_index.py
    """
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    store = _get_store()
    store.reset()

    filename = "blood_donation_guide.pdf"
    pages = []
    chunks = []

    if KB_PDF.exists():
        try:
            pages = extract_pages(str(KB_PDF))
            chunks = chunk_pages(pages)
        except PDFProcessingError:
            pages = []
            chunks = []

    if not chunks:
        # Minimal fallback so the chatbot still works
        from rag.chunker import Chunk
        chunks = [Chunk(text=FALLBACK_TEXT, page_number=1)]

    texts = [c.text for c in chunks]
    page_numbers = [c.page_number for c in chunks]
    vectors = embed_texts(texts)

    store.add_chunks(filename, vectors, page_numbers, texts)
    store.save_to_disk()

    return {"chunks": len(chunks), "status": "ok"}


def _ensure_index() -> VectorStore:
    """Load index from disk; build automatically if missing."""
    store = _get_store()
    if store.is_empty():
        # Try loading again in case another process wrote it
        if not store.load_from_disk() or store.is_empty():
            build_index()
            store = _get_store()
    return store


def retrieve(query: str, top_k: int = 5) -> List[str]:
    """Return top-k relevant chunk texts (for compatibility with old API)."""
    try:
        store = _ensure_index()
        results = semantic_retrieve(query, store, top_k=top_k)
        return [r.text for r in results]
    except Exception:
        return []


def get_context_for_question(question: str) -> str:
    """
    Main entry point used by services/ai_service.py.
    Returns a single context string built from the best semantic matches.
    """
    try:
        store = _ensure_index()
        results = semantic_retrieve(question, store, top_k=5)
        if not results:
            return "No relevant information found in the BloodLink knowledge base."
        parts = []
        for r in results:
            parts.append(r.text)
        return "\n\n---\n\n".join(parts)
    except Exception:
        return "No relevant information found in the BloodLink knowledge base."
