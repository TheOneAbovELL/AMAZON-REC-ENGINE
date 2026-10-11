import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import Settings, load_engine_config  # noqa: E402
from src.recommender import RecommendationEngine  # noqa: E402
from src.text import tokenize  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
MINI_CATALOG = FIXTURES / "mini_catalog.json"
MINI_META = FIXTURES / "mini_catalog_meta.json"


class FakeEncoder:
    """Deterministic test double for the sentence-embedding model: hashed bag of stemmed
    tokens, L2-normalised. Texts sharing words get high cosine similarity, which is all
    the engine's dense path needs to be exercised without downloading a model."""

    dim = 64

    def __init__(self, name: str = "fake-encoder"):
        self.name = name
        self.calls = 0
        self.phrase_map = load_engine_config()["text"]["phrase_normalizations"]

    def encode(self, texts):
        self.calls += 1
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in tokenize(text, self.phrase_map):
                out[row, int(hashlib.md5(token.encode()).hexdigest(), 16) % self.dim] += 1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.where(norms == 0, 1.0, norms)


@pytest.fixture(scope="session")
def config():
    return load_engine_config()


@pytest.fixture(scope="session")
def query_cases():
    return json.loads((FIXTURES / "query_cases.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def text_cases():
    return json.loads((FIXTURES / "text_cases.json").read_text(encoding="utf-8"))


@pytest.fixture
def mini_settings(tmp_path):
    catalog = tmp_path / "catalog.json"
    shutil.copy(MINI_CATALOG, catalog)
    shutil.copy(MINI_META, tmp_path / "catalog_meta.json")
    return Settings(
        catalog_path=catalog,
        catalog_meta_path=tmp_path / "catalog_meta.json",
        embeddings_path=tmp_path / "models" / "embeddings.npy",
        manifest_path=tmp_path / "models" / "manifest.json",
        embedding_model="fake-encoder",
        auto_build_index=True,
        allow_lexical_fallback=True,
        rate_limit_per_minute=0,
    )


@pytest.fixture
def lexical_engine(mini_settings):
    return RecommendationEngine.load(mini_settings, encoder_factory=None)


@pytest.fixture
def hybrid_engine(mini_settings):
    return RecommendationEngine.load(mini_settings, encoder_factory=FakeEncoder)
