"""
embeddings.py

Thin wrapper around a Hugging Face sentence-transformers model.

Default model: all-MiniLM-L6-v2
  - ~90MB, runs fast on CPU, no GPU required.
  - 384-dimensional vectors, good quality/speed trade-off.
"""

import os
import threading
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

_model_lock = threading.Lock()
_model_instance = None
_model_name_loaded = None


def get_embedding_model_name() -> str:
    return os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")


def _get_model() -> SentenceTransformer:
    global _model_instance, _model_name_loaded
    model_name = get_embedding_model_name()

    if _model_instance is not None and _model_name_loaded == model_name:
        return _model_instance

    with _model_lock:
        if _model_instance is None or _model_name_loaded != model_name:
            _model_instance = SentenceTransformer(model_name, device="cpu")
            _model_name_loaded = model_name

    return _model_instance


def embed_texts(texts: List[str]) -> np.ndarray:
    """
    Embed a list of strings and return an (N, D) float32 numpy array,
    L2-normalized so that inner-product search == cosine similarity.
    """
    if not texts:
        return np.zeros((0, embedding_dimension()), dtype="float32")

    model = _get_model()
    vectors = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return vectors.astype("float32")


def embed_query(text: str) -> np.ndarray:
    """Embed a single query string, returned as a 1-D float32 array."""
    return embed_texts([text])[0]


def embedding_dimension() -> int:
    model = _get_model()
    return model.get_sentence_embedding_dimension()
