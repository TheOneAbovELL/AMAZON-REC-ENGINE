"""The JavaScript fallback engine (lib/engine) must rank exactly like the Python engine in
lexical mode. Runs the JS engine through Node on the same catalog, config and requests."""

import json
import shutil
import subprocess

import pytest

from src.config import ENGINE_CONFIG_PATH
from src.recommender import Filters
from tests.conftest import MINI_CATALOG, ROOT

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

REQUESTS = [
    {"type": "recommend", "query": "gaming laptop under 80k", "profile": "general", "top_k": 5},
    {"type": "recommend", "query": "laptop", "profile": "gaming", "top_k": 5},
    {"type": "recommend", "query": "laptop", "profile": "ai_student", "top_k": 5},
    {"type": "recommend", "query": "laptop bag", "profile": "general", "top_k": 5},
    {"type": "recommend", "query": "wireless earbuds", "profile": "student", "top_k": 5},
    {"type": "recommend", "query": "cheap bluetooth speaker", "profile": "general", "top_k": 5},
    {"type": "recommend", "query": "phone under 15000", "profile": "general", "top_k": 5},
    {"type": "recommend", "query": "samsung galaxy m13", "profile": "general", "top_k": 5},
    {"type": "recommend", "query": "noise cancelling headphones", "profile": "general", "top_k": 5},
    {"type": "recommend", "query": "43 inch smart tv", "profile": "general", "top_k": 5},
    {"type": "recommend", "query": "gaming mouse pad", "profile": "gaming", "top_k": 5},
    {
        "type": "recommend",
        "query": "running shoes",
        "profile": "general",
        "top_k": 5,
        "filters": {"department": "Accessories", "min_rating": 4.0},
    },
    {"type": "recommend", "query": "earbuds between 1000 and 6000", "profile": "general", "top_k": 5},
    {"type": "recommend", "query": "under 5000", "profile": "general", "top_k": 5},
    {"type": "similar", "asin": "TPHONE0001", "k": 5},
    {"type": "similar", "asin": "TLAPTOP002", "k": 5},
]


def run_js():
    spec = ROOT / "tests" / "fixtures" / "_parity_requests.json"
    spec.write_text(
        json.dumps({"catalog": str(MINI_CATALOG), "config": str(ENGINE_CONFIG_PATH), "requests": REQUESTS}),
        encoding="utf-8",
    )
    try:
        out = subprocess.run(
            [NODE, str(ROOT / "scripts" / "js_engine_cli.mjs"), str(spec)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            timeout=60,
        )
    finally:
        spec.unlink(missing_ok=True)
    return json.loads(out.stdout)


def run_python(engine):
    results = []
    for r in REQUESTS:
        if r["type"] == "similar":
            results.append(engine.similar(r["asin"], r["k"]))
        else:
            results.append(engine.recommend(r["query"], r["profile"], r["top_k"], Filters(**r.get("filters", {}))))
    return results


def test_js_engine_matches_python_lexical_mode(lexical_engine):
    js_results = run_js()
    py_results = run_python(lexical_engine)
    for request, js, py in zip(REQUESTS, js_results, py_results, strict=True):
        label = request.get("query") or request["asin"]
        assert [r["asin"] for r in js["results"]] == [r["asin"] for r in py["results"]], label
        for a, b in zip(js["results"], py["results"], strict=True):
            assert a["score"] == pytest.approx(b["score"], abs=1e-9), label
            assert a.get("reasons") == b.get("reasons"), label
            assert a.get("signals") == pytest.approx(b.get("signals"), abs=1e-9) if "signals" in b else True
            assert a["discount_pct"] == b["discount_pct"] and a["image_url"] == b["image_url"]
        if request["type"] == "recommend":
            assert js["interpretation"] == py["interpretation"], label
            assert js["total_matches"] == py["total_matches"], label
            assert js["filters"] == py["filters"], label
            assert js.get("message") == py.get("message"), label
