"""Integration with the real sentence-embedding model (all-MiniLM-L6-v2).

Downloads ~90 MB on first run; skipped when the model cannot be loaded (e.g. offline CI
without a cache). Run only these with: pytest -m model
"""

import pytest

from src import embeddings as emb
from src.recommender import RecommendationEngine

pytestmark = pytest.mark.model


@pytest.fixture(scope="module")
def encoder():
    try:
        return emb.SentenceTransformerEncoder("sentence-transformers/all-MiniLM-L6-v2")
    except Exception as exc:  # no network and no cache
        pytest.skip(f"embedding model unavailable: {exc}")


@pytest.fixture
def semantic_engine(mini_settings, encoder):
    from dataclasses import replace

    settings = replace(mini_settings, embedding_model=encoder.name)
    return RecommendationEngine.load(settings, encoder_factory=lambda _name: encoder)


def test_vectors_are_normalised(encoder):
    vectors = encoder.encode(["wireless earbuds", "pressure cooker"])
    assert vectors.shape == (2, encoder.dim)
    assert abs(float((vectors[0] ** 2).sum()) - 1.0) < 1e-4


def test_semantic_retrieval_finds_products_without_shared_keywords(semantic_engine):
    # No catalog listing contains "gym" or "workout": only the embedding can connect them.
    response = semantic_engine.recommend("something to listen to music during my workout", "general", 3)
    assert response["engine"]["mode"] == "hybrid"
    top = {r["sub_category"] for r in response["results"]}
    assert top & {"Headphones", "Speakers"}, [r["name"] for r in response["results"]]


def test_hybrid_ranks_relevant_products_first(semantic_engine):
    response = semantic_engine.recommend("noise cancelling headphones", "general", 3)
    assert all(r["signals"]["semantic"] is not None for r in response["results"])
    assert response["results"][0]["asin"] in {"THEADPH001", "TEARBUD003", "TEARBUD004"}


def test_similar_items_use_embeddings(semantic_engine):
    response = semantic_engine.similar("TEARBUD001", 3)
    assert response["engine"]["mode"] == "hybrid"
    assert {r["sub_category"] for r in response["results"]} <= {"Headphones", "Speakers"}
