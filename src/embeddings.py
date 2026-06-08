"""Embedding utilities for item and user representations."""

import numpy as np
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")


def generate_embeddings(texts):
    """Generate embeddings for a list of texts using a SentenceTransformer model."""
    return model.encode(texts, show_progress_bar=True)


def save_embeddings(embeddings, filepath: str):
    """Persist embeddings to disk using NumPy."""
    np.save(filepath, embeddings)


def load_embeddings(filepath: str):
    """Load embeddings from a NumPy file."""
    return np.load(filepath)
