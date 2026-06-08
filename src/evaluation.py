"""Evaluation metrics for recommendation ranking."""

import math
from typing import Iterable, Set


def precision_at_k(recommended: Iterable, relevant: Set, k: int) -> float:
    if k <= 0:
        return 0.0
    recommended_k = list(recommended)[:k]
    hits = sum(1 for item in recommended_k if item in relevant)
    return hits / k


def recall_at_k(recommended: Iterable, relevant: Set, k: int) -> float:
    if not relevant or k <= 0:
        return 0.0
    recommended_k = list(recommended)[:k]
    hits = sum(1 for item in recommended_k if item in relevant)
    return hits / len(relevant)


def dcg_at_k(relevance_scores: Iterable[float], k: int) -> float:
    relevance = list(relevance_scores)[:k]
    return sum((2 ** rel - 1) / math.log2(idx + 2) for idx, rel in enumerate(relevance))


def ndcg_at_k(recommended: Iterable, relevant: Set, k: int) -> float:
    relevance_scores = [1.0 if item in relevant else 0.0 for item in list(recommended)[:k]]
    dcg = dcg_at_k(relevance_scores, k)
    ideal_dcg = dcg_at_k(sorted(relevance_scores, reverse=True), k)
    return dcg / ideal_dcg if ideal_dcg > 0 else 0.0
