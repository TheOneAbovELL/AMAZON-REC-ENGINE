"""End-to-end behaviour of the recommendation engine on the mini catalog fixture."""

import json

import numpy as np
import pytest

from src import embeddings as emb
from src.lexical import LexicalIndex
from src.personalization import cheapness, profile_signal
from src.ranking import deal_signal, popularity_signal, quality_signal
from src.recommender import Filters, RecommendationEngine, UnknownProductError
from tests.conftest import FakeEncoder


def asins(response):
    return [r["asin"] for r in response["results"]]


# ------------------------------------------------------------------ signals


def test_quality_signal_shrinks_sparse_ratings_toward_prior(config):
    q = config["quality"]
    assert quality_signal(4.8, 6, q) < quality_signal(4.5, 5000, q)
    assert 0.0 <= quality_signal(1.0, 10, q) <= quality_signal(5.0, 10_000, q) <= 1.0


def test_popularity_and_deal_are_bounded(config):
    assert popularity_signal(0, config["popularity"]) == 0.0
    assert popularity_signal(10**9, config["popularity"]) == 1.0
    assert deal_signal(500, 1000) == pytest.approx(0.5)
    assert deal_signal(1000, 500) == 0.0


def test_cheapness_and_profile_signal():
    assert cheapness([300.0, 100.0, 200.0]) == [0.0, 1.0, 0.5]
    assert cheapness([42.0]) == [1.0]
    gamer = {"keywords": ["rtx", "gaming"], "prefers_low_price": False}
    assert profile_signal(1, 0.0, gamer, False) == 0.5
    assert profile_signal(5, 0.0, gamer, False) == 1.0
    assert profile_signal(0, 0.8, {"keywords": [], "prefers_low_price": False}, True) == 0.8


def test_bm25_prefers_rarer_terms_and_coverage_is_bounded():
    index = LexicalIndex(["red shoe", "red shirt", "red red hat", "blue shoe"], {})
    assert index.term_idf("hat") > index.term_idf("red")
    scores = index.bm25(["red", "shoe"])
    assert scores[0] == scores.max()
    coverage = index.coverage(["red", "shoe"], np.arange(4))
    assert coverage[0] == pytest.approx(1.0)
    assert 0 < coverage[1] < 1 and 0 < coverage[3] < 1
    # A term missing from the catalog counts against coverage.
    assert index.coverage(["red", "zzz"], np.arange(1))[0] < 0.5


# ------------------------------------------------------------------ recommend


@pytest.mark.parametrize("engine_name", ["lexical_engine", "hybrid_engine"])
def test_budget_is_a_hard_filter(engine_name, request):
    engine = request.getfixturevalue(engine_name)
    response = engine.recommend("gaming laptop under 80k", "general", 10)
    assert response["results"], "expected laptops under the budget"
    assert all(r["price"] <= 80_000 for r in response["results"])
    assert response["filters"]["max_price"] == 80_000
    assert response["interpretation"]["budget"]["max"] == 80_000


@pytest.mark.parametrize("engine_name", ["lexical_engine", "hybrid_engine"])
def test_product_type_beats_accessories(engine_name, request):
    engine = request.getfixturevalue(engine_name)
    response = engine.recommend("laptop", "general", 5)
    top = response["results"][:3]
    assert all(r["intent_match"] for r in top), [r["name"] for r in top]
    assert "TLBAG00001" not in asins(response)[:3]


def test_accessory_query_returns_accessories(lexical_engine):
    response = lexical_engine.recommend("laptop bag", "general", 3)
    assert asins(response)[0] == "TLBAG00001"


def test_intent_matches_without_keyword_overlap(lexical_engine):
    # Phone listings rarely say "phone"; the smartphone intent recognises them by spec pattern.
    response = lexical_engine.recommend("phone under 15000", "general", 5)
    assert response["results"]
    assert {"TPHONE0003"} <= set(asins(response))
    assert "TPHCASE001" not in asins(response)


def test_variants_sharing_a_review_pool_are_collapsed(lexical_engine):
    response = lexical_engine.recommend("samsung galaxy m13", "general", 5)
    galaxy = [a for a in asins(response) if a in {"TPHONE0001", "TPHONE0002"}]
    assert len(galaxy) == 1


def test_profile_changes_ranking(lexical_engine):
    general = lexical_engine.recommend("laptop", "general", 5)
    gamer = lexical_engine.recommend("laptop", "gaming", 5)
    assert asins(general) != asins(gamer)
    top = gamer["results"][0]
    assert top["profile_keywords"], "gamer's top laptop should match gaming keywords"
    assert any("Gamer profile" in reason for reason in top["reasons"])


def test_student_profile_prefers_cheaper_options(lexical_engine):
    student = lexical_engine.recommend("wireless earbuds", "student", 4)
    general = lexical_engine.recommend("wireless earbuds", "general", 4)
    student_avg = np.mean([r["price"] for r in student["results"]])
    general_avg = np.mean([r["price"] for r in general["results"]])
    assert student_avg <= general_avg


def test_department_and_rating_filters(lexical_engine):
    response = lexical_engine.recommend(
        "running shoes", "general", 10, Filters(department="Accessories", min_rating=4.0)
    )
    assert response["results"]
    assert all(r["main_category"] == "Accessories" and r["rating"] >= 4.0 for r in response["results"])


def test_scores_are_sorted_and_explained(hybrid_engine):
    response = hybrid_engine.recommend("noise cancelling earbuds", "general", 5)
    scores = [r["score"] for r in response["results"]]
    assert scores == sorted(scores, reverse=True)
    for r in response["results"]:
        assert r["reasons"]
        assert sum(r["contributions"].values()) == pytest.approx(r["score"], abs=1e-5)
        assert 0.0 <= r["signals"]["relevance"] <= 1.0
        assert r["product_url"].endswith(r["asin"])


def test_query_without_product_words_asks_for_more(lexical_engine):
    response = lexical_engine.recommend("under 5000", "general", 5)
    assert response["results"] == [] and "message" in response


def test_unknown_terms_return_nothing_rather_than_noise(lexical_engine):
    response = lexical_engine.recommend("xylophone", "general", 5)
    assert response["results"] == []


def test_unknown_profile_is_rejected(lexical_engine):
    with pytest.raises(ValueError):
        lexical_engine.recommend("laptop", "pirate", 5)


def test_top_k_is_respected(hybrid_engine):
    assert len(hybrid_engine.recommend("gaming", "general", 2)["results"]) == 2


# ------------------------------------------------------------------ similar


@pytest.mark.parametrize("engine_name", ["lexical_engine", "hybrid_engine"])
def test_similar_items_exclude_the_product_and_its_variants(engine_name, request):
    engine = request.getfixturevalue(engine_name)
    response = engine.similar("TPHONE0001", 5)
    returned = asins(response)
    assert "TPHONE0001" not in returned and "TPHONE0002" not in returned
    assert response["product"]["asin"] == "TPHONE0001"
    assert len(returned) == len(set(returned))


def test_similar_unknown_product(lexical_engine):
    with pytest.raises(UnknownProductError):
        lexical_engine.similar("B000000000")


# ------------------------------------------------------------------ artifacts & degradation


def test_embeddings_are_built_then_reused(mini_settings):
    first = RecommendationEngine.load(mini_settings, encoder_factory=FakeEncoder)
    assert first.mode == "hybrid" and mini_settings.manifest_path.exists()
    manifest = json.loads(mini_settings.manifest_path.read_text())
    assert manifest["count"] == len(first.catalog) and manifest["catalog_sha256"] == first.catalog.sha256

    encoders = []

    def tracking_factory(name):
        encoders.append(FakeEncoder(name))
        return encoders[-1]

    RecommendationEngine.load(mini_settings, encoder_factory=tracking_factory)
    assert encoders[0].calls == 0, "current embeddings must be reused, not rebuilt"


def test_stale_embeddings_are_detected(mini_settings):
    RecommendationEngine.load(mini_settings, encoder_factory=FakeEncoder)
    payload = json.loads(mini_settings.catalog_path.read_text(encoding="utf-8"))
    payload["rows"] = payload["rows"][:-1]
    mini_settings.catalog_path.write_text(json.dumps(payload), encoding="utf-8")
    catalog = RecommendationEngine.load(mini_settings, encoder_factory=None).catalog
    with pytest.raises(emb.StaleEmbeddingsError):
        emb.load_embeddings(catalog, "fake-encoder", mini_settings.embeddings_path, mini_settings.manifest_path)


def test_stale_embeddings_fail_or_fall_back_when_auto_build_disabled(mini_settings):
    from dataclasses import replace

    strict = replace(mini_settings, auto_build_index=False, allow_lexical_fallback=False)
    with pytest.raises(emb.StaleEmbeddingsError):
        RecommendationEngine.load(strict, encoder_factory=FakeEncoder)
    lenient = replace(mini_settings, auto_build_index=False, allow_lexical_fallback=True)
    engine = RecommendationEngine.load(lenient, encoder_factory=FakeEncoder)
    assert engine.mode == "lexical" and engine.status()["degraded"] is True


def test_model_load_failure_degrades_to_lexical(mini_settings):
    def broken(_name):
        raise OSError("model download failed")

    engine = RecommendationEngine.load(mini_settings, encoder_factory=broken)
    assert engine.mode == "lexical"
    assert "keyword" in engine.status()["notice"]
    assert engine.recommend("earbuds", "general", 3)["results"]
