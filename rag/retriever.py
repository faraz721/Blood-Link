"""
retriever.py

Given a user question, embeds it and searches the FAISS vector store
for the most relevant document chunks from the fixed knowledge base.
"""

from dataclasses import dataclass
from typing import List

from . import embeddings
from .vector_store import ChunkMetadata, VectorStore

TOP_K = 5
SCORE_THRESHOLD = 0.15  # cosine similarity


@dataclass
class RetrievedChunk:
    score: float
    filename: str
    page_number: int
    text: str


def retrieve(question: str, store: VectorStore, top_k: int = TOP_K,
             score_threshold: float = SCORE_THRESHOLD) -> List[RetrievedChunk]:
    query_vector = embeddings.embed_query(question)
    raw_results = store.search(query_vector, top_k=top_k)

    results: List[RetrievedChunk] = []
    for score, meta in raw_results:
        if score < score_threshold:
            continue
        results.append(
            RetrievedChunk(
                score=score,
                filename=meta.filename,
                page_number=meta.page_number,
                text=meta.text,
            )
        )
    return results
