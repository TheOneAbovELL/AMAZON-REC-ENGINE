"""Exact inner-product vector search with FAISS (cosine similarity on normalised vectors)."""

from __future__ import annotations

import faiss
import numpy as np


class VectorIndex:
    def __init__(self, vectors: np.ndarray):
        self.vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        self.index = faiss.IndexFlatIP(self.vectors.shape[1])
        self.index.add(self.vectors)

    def __len__(self) -> int:
        return self.index.ntotal

    def search(self, query: np.ndarray, k: int, allowed: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
        """Top-k (ids, cosine similarities). `allowed` restricts the search to those product ids."""
        query = np.ascontiguousarray(query.reshape(1, -1), dtype=np.float32)
        params = None
        if allowed is not None:
            if len(allowed) == 0:
                return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float32)
            params = faiss.SearchParameters(sel=faiss.IDSelectorBatch(np.asarray(allowed, dtype=np.int64)))
        k = min(k, len(self) if allowed is None else len(allowed))
        scores, ids = self.index.search(query, k, params=params)
        keep = ids[0] >= 0
        return ids[0][keep], scores[0][keep]

    def similarity(self, query: np.ndarray, ids: np.ndarray) -> np.ndarray:
        """Cosine similarity between `query` and the given product ids."""
        return self.vectors[ids] @ query.reshape(-1).astype(np.float32)
