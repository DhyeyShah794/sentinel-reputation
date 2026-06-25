"""
Embedding service — Sentence-transformers for semantic operations.

Used by: dedup (Tier 3), classification (Stage 1), theme clustering.
"""

from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    """Lazy-load the embedding model."""
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
        logger.info("Embedding model loaded.")
    return _model


def encode_texts(texts: List[str], batch_size: int = 32) -> np.ndarray:
    """
    Encode a list of texts into embeddings.

    Returns:
        numpy array of shape (len(texts), embedding_dim)
    """
    model = _get_model()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=len(texts) > 50,
        normalize_embeddings=True,
    )
    return embeddings


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def cosine_similarity_matrix(
    query_embeddings: np.ndarray,
    reference_embeddings: np.ndarray,
) -> np.ndarray:
    """
    Compute cosine similarity between each query and all references.

    Returns:
        Matrix of shape (len(queries), len(references))
    """
    # Both should already be normalized from encode_texts
    return np.dot(query_embeddings, reference_embeddings.T)


def find_top_k(
    query_embedding: np.ndarray,
    reference_embeddings: np.ndarray,
    labels: List[str],
    k: int = 3,
) -> List[dict]:
    """
    Find top-k most similar references to a query.

    Returns:
        List of {"label": str, "similarity": float} sorted by similarity desc
    """
    similarities = np.dot(reference_embeddings, query_embedding)
    top_indices = np.argsort(similarities)[::-1][:k]

    return [
        {"label": labels[idx], "similarity": float(similarities[idx])}
        for idx in top_indices
    ]
