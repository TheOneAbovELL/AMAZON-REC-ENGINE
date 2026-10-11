"""Ranking metrics with binary relevance."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


def precision_at_k(recommended: Sequence, relevant: set, k: int) -> float:
    if k <= 0:
        return 0.0
    return sum(1 for item in list(recommended)[:k] if item in relevant) / k


def recall_at_k(recommended: Sequence, relevant: set, k: int) -> float:
    if not relevant or k <= 0:
        return 0.0
    return sum(1 for item in list(recommended)[:k] if item in relevant) / len(relevant)


def dcg_at_k(relevance_scores: Iterable[float], k: int) -> float:
    return sum((2**rel - 1) / math.log2(idx + 2) for idx, rel in enumerate(list(relevance_scores)[:k]))


def ndcg_at_k(recommended: Sequence, relevant: set, k: int) -> float:
    """nDCG against the ideal ordering of the *returned* list (relevant items first).

    With rule-based labels the full set of relevant catalog items is unknown, so the ideal
    is computed from the retrieved list: this measures ordering quality, while precision
    measures how many results are relevant at all.
    """
    gains = [1.0 if item in relevant else 0.0 for item in list(recommended)[:k]]
    ideal = dcg_at_k(sorted(gains, reverse=True), k)
    return dcg_at_k(gains, k) / ideal if ideal > 0 else 0.0


def mrr(recommended: Sequence, relevant: set) -> float:
    for rank, item in enumerate(recommended, start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0
