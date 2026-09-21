"""
vector_store.py

FAISS flat inner-product index + metadata for the fixed BloodLink
knowledge base. Persists to disk under rag_index/ so the index
survives restarts (local and most hosting).
"""

import os
import pickle
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import faiss
import numpy as np

# BloodLink project root is two levels up from this file (rag/vector_store.py)
BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_DIR = BASE_DIR / "rag_index"
INDEX_PATH = str(INDEX_DIR / "faiss.index")
METADATA_PATH = str(INDEX_DIR / "metadata.pkl")


@dataclass
class ChunkMetadata:
    filename: str
    page_number: int
    text: str
    chunk_id: int


class VectorStore:
    """Thread-safe FAISS store for the fixed knowledge base."""

    def __init__(self, dimension: int):
        self._lock = threading.Lock()
        self.dimension = dimension
        self.index = faiss.IndexFlatIP(dimension)
        self.metadata: List[ChunkMetadata] = []
        self._vectors: List[np.ndarray] = []
        self._next_chunk_id = 0

    def add_chunks(self, filename: str, vectors: np.ndarray,
                   pages: List[int], texts: List[str]) -> None:
        if len(vectors) == 0:
            return
        with self._lock:
            for i in range(len(vectors)):
                self.metadata.append(
                    ChunkMetadata(
                        filename=filename,
                        page_number=pages[i],
                        text=texts[i],
                        chunk_id=self._next_chunk_id,
                    )
                )
                self._vectors.append(vectors[i])
                self._next_chunk_id += 1
            self.index.add(vectors)

    def reset(self) -> None:
        with self._lock:
            self.index = faiss.IndexFlatIP(self.dimension)
            self.metadata = []
            self._vectors = []
            self._next_chunk_id = 0

    def search(self, query_vector: np.ndarray, top_k: int = 5
               ) -> List[Tuple[float, ChunkMetadata]]:
        with self._lock:
            if self.index.ntotal == 0:
                return []
            k = min(top_k, self.index.ntotal)
            query = np.expand_dims(query_vector.astype("float32"), axis=0)
            scores, indices = self.index.search(query, k)

            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx == -1:
                    continue
                results.append((float(score), self.metadata[idx]))
            return results

    def is_empty(self) -> bool:
        with self._lock:
            return self.index.ntotal == 0

    def total_chunks(self) -> int:
        with self._lock:
            return self.index.ntotal

    def save_to_disk(self) -> None:
        try:
            INDEX_DIR.mkdir(parents=True, exist_ok=True)
            with self._lock:
                faiss.write_index(self.index, INDEX_PATH)
                with open(METADATA_PATH, "wb") as f:
                    pickle.dump(
                        {
                            "metadata": self.metadata,
                            "vectors": self._vectors,
                            "next_chunk_id": self._next_chunk_id,
                            "dimension": self.dimension,
                        },
                        f,
                    )
        except Exception:
            pass

    def load_from_disk(self) -> bool:
        if not (os.path.exists(INDEX_PATH) and os.path.exists(METADATA_PATH)):
            return False
        try:
            with self._lock:
                self.index = faiss.read_index(INDEX_PATH)
                with open(METADATA_PATH, "rb") as f:
                    state = pickle.load(f)
                self.metadata = state["metadata"]
                self._vectors = state["vectors"]
                self._next_chunk_id = state["next_chunk_id"]
                if "dimension" in state:
                    self.dimension = state["dimension"]
            return True
        except Exception:
            return False


_store_instance: Optional[VectorStore] = None
_store_lock = threading.Lock()


def get_vector_store(dimension: int) -> VectorStore:
    """Singleton accessor so the whole Flask app shares one store."""
    global _store_instance
    with _store_lock:
        if _store_instance is None:
            _store_instance = VectorStore(dimension)
            _store_instance.load_from_disk()
        return _store_instance
