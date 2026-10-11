"""Sentence-embedding encoder and the on-disk embedding artifact.

Product embeddings are stored as float16 in models/embeddings.npy next to a manifest that
records the model and the SHA-256 of the catalog they were computed from, so an index can
never silently drift out of sync with the catalog it describes.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import numpy as np

from .catalog import Catalog

log = logging.getLogger(__name__)

ARTIFACT_VERSION = 1


class Encoder(Protocol):
    name: str
    dim: int

    def encode(self, texts: list[str]) -> np.ndarray:
        """Return L2-normalised float32 vectors, one row per text."""


class SentenceTransformerEncoder:
    def __init__(self, model_name: str, batch_size: int = 256):
        from sentence_transformers import SentenceTransformer

        self.name = model_name
        self.batch_size = batch_size
        self._model = SentenceTransformer(model_name, device="cpu")
        # Renamed in sentence-transformers 5.x; keep working on older releases too.
        get_dim = getattr(self._model, "get_embedding_dimension", None) or self._model.get_sentence_embedding_dimension
        self.dim = int(get_dim())
        self._lock = threading.Lock()
        self._cached = lru_cache(maxsize=2048)(self._encode_one)

    def _encode_one(self, text: str) -> np.ndarray:
        with self._lock:
            vector = self._model.encode([text], normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vector, dtype=np.float32)[0]

    def encode(self, texts: list[str]) -> np.ndarray:
        if len(texts) == 1:
            return self._cached(texts[0])[None, :]
        with self._lock:
            vectors = self._model.encode(
                texts,
                batch_size=self.batch_size,
                normalize_embeddings=True,
                show_progress_bar=len(texts) > 1000,
            )
        return np.asarray(vectors, dtype=np.float32)


class StaleEmbeddingsError(RuntimeError):
    """Embeddings are missing, or were built for a different catalog or model."""


def build_embeddings(catalog: Catalog, encoder: Encoder) -> np.ndarray:
    texts = [catalog.embedding_text(i) for i in range(len(catalog))]
    log.info("Encoding %d products with %s", len(texts), encoder.name)
    return encoder.encode(texts)


def save_embeddings(vectors: np.ndarray, catalog: Catalog, model_name: str, path: Path, manifest_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + ".tmp.npy")
    np.save(tmp, vectors.astype(np.float16))
    tmp.replace(path)
    manifest = {
        "artifact_version": ARTIFACT_VERSION,
        "model": model_name,
        "dim": int(vectors.shape[1]),
        "count": int(vectors.shape[0]),
        "catalog_sha256": catalog.sha256,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def load_embeddings(catalog: Catalog, model_name: str, path: Path, manifest_path: Path) -> np.ndarray:
    if not path.exists() or not manifest_path.exists():
        raise StaleEmbeddingsError(f"No embeddings at {path}.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems = []
    if manifest.get("artifact_version") != ARTIFACT_VERSION:
        problems.append("artifact version changed")
    if manifest.get("catalog_sha256") != catalog.sha256:
        problems.append("catalog changed since the embeddings were built")
    if manifest.get("model") != model_name:
        problems.append(f"built with {manifest.get('model')}, configured model is {model_name}")
    if manifest.get("count") != len(catalog):
        problems.append(f"{manifest.get('count')} vectors for {len(catalog)} products")
    if problems:
        raise StaleEmbeddingsError("Embeddings are stale: " + "; ".join(problems) + ".")
    vectors = np.load(path).astype(np.float32)
    if vectors.shape[0] != len(catalog):
        raise StaleEmbeddingsError(f"{path} holds {vectors.shape[0]} vectors for {len(catalog)} products.")
    return vectors
