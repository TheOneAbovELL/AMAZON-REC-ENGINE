"""Vector store implementation for nearest neighbor lookups."""

import faiss


def build_index(embeddings):
    """Build a FAISS index from precomputed embeddings."""
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings.astype("float32"))
    return index


def search(query_embedding, index, top_k=10):
    """Search the FAISS index using a query embedding."""
    distances, indices = index.search(query_embedding.astype("float32"), top_k)
    return distances, indices


def save_index(index, filepath: str):
    """Persist a FAISS index to disk."""
    faiss.write_index(index, filepath)


def load_index(filepath: str):
    """Load a FAISS index from disk."""
    return faiss.read_index(filepath)
