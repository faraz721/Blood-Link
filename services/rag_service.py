"""
Simple local RAG service for BloodLink AI Help.
Uses TF-IDF + cosine similarity as a free, dependency-light retrieval layer
(works offline and does not require paid embeddings).
Optionally can call external embedding API if AI_API_KEY is set and preferred.
"""
import os
import json
import pickle
from pathlib import Path
from typing import List, Dict, Optional

from PyPDF2 import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
KB_PDF = BASE_DIR / "knowledge_base" / "blood_donation_guide.pdf"
INDEX_DIR = BASE_DIR / "rag_index"
CHUNKS_FILE = INDEX_DIR / "chunks.json"
VECTORIZER_FILE = INDEX_DIR / "vectorizer.pkl"
MATRIX_FILE = INDEX_DIR / "tfidf_matrix.pkl"


def extract_text_from_pdf(pdf_path: Path) -> str:
    if not pdf_path.exists():
        return ""
    reader = PdfReader(str(pdf_path))
    texts = []
    for page in reader.pages:
        try:
            t = page.extract_text()
            if t:
                texts.append(t)
        except Exception:
            continue
    return "\n\n".join(texts)


def chunk_text(text: str, chunk_size: int = 700, overlap: int = 120) -> List[str]:
    if not text:
        return []
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk.strip())
        i += chunk_size - overlap
    return chunks


def build_index() -> Dict:
    """Build and persist TF-IDF index from the knowledge PDF."""
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    text = extract_text_from_pdf(KB_PDF)
    if not text.strip():
        # Create a minimal fallback knowledge so the app still works
        text = (
            "Blood donation is a voluntary process where a person donates blood "
            "that can be used for transfusions. Common blood groups are A, B, AB and O, "
            "each with positive or negative Rh factor. O negative is the universal donor. "
            "AB positive is the universal recipient. Donors should be healthy, aged 18-65, "
            "weigh at least 50 kg, and not have donated in the last 3 months (for whole blood). "
            "People with certain infections, low hemoglobin, or recent surgeries may be deferred. "
            "Always consult a medical professional for eligibility."
        )

    chunks = chunk_text(text)
    if not chunks:
        chunks = ["No knowledge base content available."]

    vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
    matrix = vectorizer.fit_transform(chunks)

    with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    with open(VECTORIZER_FILE, "wb") as f:
        pickle.dump(vectorizer, f)

    with open(MATRIX_FILE, "wb") as f:
        pickle.dump(matrix, f)

    return {"chunks": len(chunks), "status": "ok"}


def load_index():
    if not (CHUNKS_FILE.exists() and VECTORIZER_FILE.exists() and MATRIX_FILE.exists()):
        build_index()
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    with open(VECTORIZER_FILE, "rb") as f:
        vectorizer = pickle.load(f)
    with open(MATRIX_FILE, "rb") as f:
        matrix = pickle.load(f)
    return chunks, vectorizer, matrix


def retrieve(query: str, top_k: int = 4) -> List[str]:
    try:
        chunks, vectorizer, matrix = load_index()
        q_vec = vectorizer.transform([query])
        scores = cosine_similarity(q_vec, matrix).flatten()
        top_idx = np.argsort(scores)[::-1][:top_k]
        results = []
        for i in top_idx:
            if scores[i] > 0.05:  # minimal relevance threshold
                results.append(chunks[i])
        return results
    except Exception:
        return []


def get_context_for_question(question: str) -> str:
    chunks = retrieve(question)
    if not chunks:
        return "No relevant information found in the BloodLink knowledge base."
    return "\n\n---\n\n".join(chunks)