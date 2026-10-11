"""HTTP contract of api_server.py, with the engine built from the mini catalog fixture."""

import pytest
from fastapi.testclient import TestClient

import api_server
from src.recommender import RecommendationEngine
from tests.conftest import FakeEncoder


@pytest.fixture
def client(mini_settings, monkeypatch):
    engine = RecommendationEngine.load(mini_settings, encoder_factory=FakeEncoder)
    # Skip the background loader: serve the fixture engine directly.
    monkeypatch.setattr(api_server.holder, "engine", engine)
    monkeypatch.setattr(api_server.holder, "state", "ready")
    monkeypatch.setattr(api_server, "settings", mini_settings)
    monkeypatch.setattr(api_server, "limiter", api_server.RateLimiter(0))
    api_server.catalog_meta.cache_clear()
    monkeypatch.setattr(api_server.holder.__class__, "load", lambda self, settings: None)
    with TestClient(api_server.app) as c:
        yield c
    api_server.catalog_meta.cache_clear()


def test_health_and_ready(client):
    assert client.get("/api/health").json()["status"] == "ok"
    ready = client.get("/api/ready")
    assert ready.status_code == 200
    assert ready.json()["engine"]["mode"] == "hybrid"
    assert ready.headers["x-request-id"]


def test_recommend_happy_path(client):
    response = client.post("/api/recommend", json={"query": "gaming laptop under 80k", "profile": "gaming", "top_k": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["engine"]["mode"] == "hybrid"
    assert 0 < len(body["results"]) <= 3
    assert all(r["price"] <= 80_000 for r in body["results"])
    assert body["interpretation"]["intent"]["id"] == "laptop"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"query": ""},
        {"query": "   "},
        {"query": "x" * 201},
        {"query": "laptop", "profile": "pirate"},
        {"query": "laptop", "top_k": 0},
        {"query": "laptop", "top_k": 51},
        {"query": "laptop", "filters": {"min_price": 10, "max_price": 5}},
        {"query": "laptop", "filters": {"min_rating": 7}},
        {"query": "laptop", "filters": {"department": "Nope"}},
        {"query": "laptop", "unexpected": True},
    ],
)
def test_recommend_validation(client, payload):
    response = client.post("/api/recommend", json=payload)
    assert response.status_code == 400
    assert "error" in response.json()


def test_similar(client):
    response = client.get("/api/products/TPHONE0001/similar?k=3")
    assert response.status_code == 200
    assert len(response.json()["results"]) <= 3
    assert client.get("/api/products/B000000000/similar").status_code == 404
    assert client.get("/api/products/short/similar").status_code in (400, 404)
    assert client.get("/api/products/TPHONE0001/similar?k=99").status_code == 400


def test_catalog(client):
    body = client.get("/api/catalog").json()
    assert body["total_products"] == 32
    assert set(body["profiles"]) == {"general", "student", "ai_student", "gaming"}


def test_engine_loading_returns_503(client, monkeypatch):
    monkeypatch.setattr(api_server.holder, "engine", None)
    monkeypatch.setattr(api_server.holder, "state", "loading")
    assert client.get("/api/ready").status_code == 503
    response = client.post("/api/recommend", json={"query": "laptop"})
    assert response.status_code == 503
    assert response.headers["retry-after"] == "10"


def test_rate_limit(client, monkeypatch):
    monkeypatch.setattr(api_server, "limiter", api_server.RateLimiter(2))
    codes = [client.post("/api/recommend", json={"query": "earbuds"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    assert client.get("/api/health").status_code == 200  # health checks are never limited


def test_errors_do_not_leak_internals(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(api_server.holder.engine, "recommend", boom)
    with TestClient(api_server.app, raise_server_exceptions=False) as c:
        response = c.post("/api/recommend", json={"query": "laptop"})
    assert response.status_code == 500
    assert "secret" not in response.text
