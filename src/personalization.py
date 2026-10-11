"""Shopper-profile signal. Mirrored by lib/engine/personalization.mjs.

A profile contributes keyword affinity (e.g. 'rtx', '144hz' for gamers) and, for
price-sensitive shoppers, a preference for cheaper options among the relevant results.
"""

from __future__ import annotations

import re
from functools import lru_cache

KEYWORD_SATURATION = 2  # matched keywords needed for the full keyword boost


@lru_cache(maxsize=32)
def _keyword_regex(keywords: tuple[str, ...]) -> re.Pattern | None:
    if not keywords:
        return None
    ordered = sorted(keywords, key=len, reverse=True)
    return re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(k) for k in ordered) + r")(?![a-z0-9])")


def matched_keywords(normalized_name: str, profile: dict) -> list[str]:
    pattern = _keyword_regex(tuple(profile.get("keywords", [])))
    if pattern is None:
        return []
    return list(dict.fromkeys(m.group(1) for m in pattern.finditer(normalized_name)))


def cheapness(prices: list[float]) -> list[float]:
    """Share of the other relevant products that cost more than each product."""
    n = len(prices)
    if n == 1:
        return [1.0]
    ordered = sorted(prices)
    out = []
    for price in prices:
        # number of prices strictly greater than `price`
        lo, hi = 0, n
        while lo < hi:
            mid = (lo + hi) // 2
            if ordered[mid] <= price:
                lo = mid + 1
            else:
                hi = mid
        out.append((n - lo) / (n - 1))
    return out


def profile_signal(keyword_hits: int, cheap: float, profile: dict, prefers_low_price: bool) -> float:
    parts = []
    if profile.get("keywords"):
        parts.append(min(1.0, keyword_hits / KEYWORD_SATURATION))
    if prefers_low_price or profile.get("prefers_low_price"):
        parts.append(cheap)
    return sum(parts) / len(parts) if parts else 0.0
