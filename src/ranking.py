"""Ranking signals, each scaled to [0, 1], and the weighted final score.

Mirrored by lib/engine/ranking.mjs. Weights live in config/engine.json.
"""

from __future__ import annotations

import math

SIGNALS = ("relevance", "quality", "popularity", "deal", "profile")


def clip01(value: float) -> float:
    return 0.0 if value < 0.0 else 1.0 if value > 1.0 else value


def quality_signal(rating: float, count: float, cfg: dict) -> float:
    """Bayesian-averaged rating: few ratings pull the score toward the prior."""
    prior_rating, prior_count = cfg["prior_rating"], cfg["prior_count"]
    smoothed = (count * rating + prior_count * prior_rating) / (count + prior_count)
    return clip01((smoothed - cfg["floor"]) / (cfg["ceiling"] - cfg["floor"]))


def popularity_signal(count: float, cfg: dict) -> float:
    return clip01(math.log1p(max(count, 0.0)) / math.log1p(cfg["reference_count"]))


def deal_signal(price: float, list_price: float) -> float:
    if list_price <= 0 or price >= list_price:
        return 0.0
    return clip01((list_price - price) / list_price)


def dense_relevance(cosine: float, cfg: dict) -> float:
    """Map raw cosine similarity onto [0, 1] using the calibrated floor/ceiling."""
    return clip01((cosine - cfg["dense_floor"]) / (cfg["dense_ceiling"] - cfg["dense_floor"]))


def combine(signals: dict[str, float], weights: dict[str, float]) -> tuple[float, dict[str, float]]:
    contributions = {name: weights[name] * signals[name] for name in SIGNALS}
    return sum(contributions[name] for name in SIGNALS), contributions


def sort_key(score: float, rating_count: float, asin: str) -> tuple:
    """Deterministic ordering shared with the JS engine: score, then rating count, then ASIN."""
    return (-round(score, 10), -rating_count, asin)
