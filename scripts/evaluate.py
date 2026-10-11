"""Offline ranking evaluation over eval/queries.json.

Compares three systems on the full catalog:
  dense-only  pure embedding nearest neighbours (no query parsing, no ranking signals)
  lexical     the keyword pipeline (what the Next.js fallback serves)
  hybrid      the full pipeline: dense + keyword retrieval with multi-signal ranking

Metrics at k=10: precision, nDCG, MRR, hit rate (>=1 relevant), budget violations
(results above a stated budget), and latency.

Relevance labels are rules (see eval/queries.json), i.e. silver-standard. They measure
whether results are the right *kind* of product at the right price, not whether a shopper
would prefer them.

Usage: python -m scripts.evaluate   (writes results/evaluation_report.{csv,md})
"""

from __future__ import annotations

import csv
import json
import re
import statistics
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import load_settings  # noqa: E402
from src.evaluation import mrr, ndcg_at_k, precision_at_k  # noqa: E402
from src.recommender import RecommendationEngine  # noqa: E402

K = 10
OUT_DIR = ROOT / "results"


def is_relevant(item: dict, rule: dict) -> bool:
    name = item["name"].lower()
    if not re.search(rule["name"], name):
        return False
    if rule.get("not_name") and re.search(rule["not_name"], name):
        return False
    if rule.get("max_price") is not None and item["price"] > rule["max_price"]:
        return False
    return rule.get("min_price") is None or item["price"] >= rule["min_price"]


def dense_only(engine: RecommendationEngine, query: str) -> list[dict]:
    vector = engine.dense.encoder.encode([query])[0]
    ids, _ = engine.dense.index.search(vector, K)
    return [engine.catalog.record(int(i)) for i in ids]


def run_system(engine: RecommendationEngine, name: str, rule: dict) -> tuple[list[dict], float]:
    started = time.perf_counter()
    if name == "dense-only":
        results = dense_only(engine, rule["query"])
    else:
        results = engine.recommend(rule["query"], rule["profile"], K, use_dense=(name == "hybrid"))["results"]
    return results, (time.perf_counter() - started) * 1000


def main() -> None:
    spec = json.loads((ROOT / "eval" / "queries.json").read_text(encoding="utf-8"))
    engine = RecommendationEngine.load(load_settings())
    systems = ["dense-only", "lexical", "hybrid"] if engine.dense else ["lexical"]
    if not engine.dense:
        print("Embedding model unavailable: evaluating the lexical system only.")

    # Warm-up so the first query's latency is not dominated by one-off model/regex setup.
    for system in systems:
        run_system(engine, system, spec["queries"][0])

    per_query = []
    for rule in spec["queries"]:
        row = {"query": rule["query"], "profile": rule["profile"]}
        for system in systems:
            results, ms = run_system(engine, system, rule)
            flags = [is_relevant(item, rule) for item in results]
            ids = [item["asin"] for item in results]
            relevant = {a for a, f in zip(ids, flags, strict=True) if f}
            budget = rule.get("max_price")
            row[system] = {
                "p": precision_at_k(ids, relevant, K),
                "ndcg": ndcg_at_k(ids, relevant, K),
                "mrr": mrr(ids, relevant),
                "hit": 1.0 if relevant else 0.0,
                "over_budget": sum(1 for item in results if budget is not None and item["price"] > budget),
                "n": len(results),
                "ms": ms,
            }
        per_query.append(row)

    summary = {}
    for system in systems:
        rows = [q[system] for q in per_query]
        latencies = sorted(r["ms"] for r in rows)
        summary[system] = {
            f"precision@{K}": statistics.mean(r["p"] for r in rows),
            f"ndcg@{K}": statistics.mean(r["ndcg"] for r in rows),
            "mrr": statistics.mean(r["mrr"] for r in rows),
            "hit_rate": statistics.mean(r["hit"] for r in rows),
            "over_budget_results": sum(r["over_budget"] for r in rows),
            "p50_ms": float(np.percentile(latencies, 50)),
            "p95_ms": float(np.percentile(latencies, 95)),
        }

    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "evaluation_report.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        metrics = list(next(iter(summary.values())))
        writer.writerow(["system", *metrics])
        for system, values in summary.items():
            writer.writerow([system, *(round(values[m], 4) for m in metrics)])

    lines = [
        "# Ranking evaluation",
        "",
        f"Catalog: {len(engine.catalog):,} products · {len(per_query)} rule-labelled queries "
        f"(`eval/queries.json`) · k = {K} · embedding model: {engine.dense.encoder.name if engine.dense else 'n/a'}",
        "",
        "Labels are silver-standard regex rules on product name and price, written independently of the",
        "engine's intent patterns. They check that results are the right kind of product within budget.",
        "",
        "| System | " + " | ".join(next(iter(summary.values()))) + " |",
        "|---|" + "---|" * len(next(iter(summary.values()))),
    ]
    for system, values in summary.items():
        cells = [
            f"{v:.3f}" if isinstance(v, float) and not k.endswith("_ms") else f"{v:.0f}" for k, v in values.items()
        ]
        lines.append(f"| {system} | " + " | ".join(cells) + " |")
    lines += ["", f"## Per-query precision@{K}", "", "| Query | Profile | " + " | ".join(systems) + " |"]
    lines.append("|---|---|" + "---|" * len(systems))
    for q in per_query:
        lines.append(f"| {q['query']} | {q['profile']} | " + " | ".join(f"{q[s]['p']:.1f}" for s in systems) + " |")
    (OUT_DIR / "evaluation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    for system, values in summary.items():
        print(
            system.ljust(11),
            "  ".join(f"{k}={v:.3f}" if not k.endswith("_ms") else f"{k}={v:.0f}" for k, v in values.items()),
        )
    print(f"Wrote {OUT_DIR / 'evaluation_report.csv'} and evaluation_report.md")


if __name__ == "__main__":
    main()
