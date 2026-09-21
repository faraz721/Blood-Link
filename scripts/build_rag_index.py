"""
Build the semantic RAG index from knowledge_base/blood_donation_guide.pdf
using Sentence Transformers + FAISS.

Run once after installing dependencies (or whenever you replace the PDF):

    python scripts/build_rag_index.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.rag_service import build_index

result = build_index()
print("RAG index built (Sentence Transformers + FAISS):", result)
