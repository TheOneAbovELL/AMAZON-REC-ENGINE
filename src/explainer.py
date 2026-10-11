"""Human-readable reasons derived only from the signals that produced the ranking.

Deterministic by design: every sentence corresponds to a measured signal, so explanations
cannot claim anything the ranker did not use. Mirrored by lib/engine/explainer.mjs.
"""

from __future__ import annotations

import math


def format_inr(value: float) -> str:
    """Indian digit grouping: 125000 -> '₹1,25,000'."""
    whole = math.floor(value + 0.5)  # half-up, like JavaScript's Math.round
    digits = str(abs(whole))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups) + "," + tail
    return ("-" if whole < 0 else "") + "₹" + digits


def explain(
    item: dict,
    *,
    matched_terms: list[str],
    semantic: float | None,
    cosine: float | None = None,
    intent: dict | None,
    intent_match: bool,
    budget: dict | None,
    profile_id: str,
    profile: dict,
    profile_hits: list[str],
    cheap: float | None,
) -> list[str]:
    reasons = []
    if intent and intent_match:
        reasons.append(f"Matches what you asked for: {intent['label'].lower()}.")
    if matched_terms:
        quoted = ", ".join(f"“{t}”" for t in matched_terms[:4])
        reasons.append(f"Listing mentions {quoted}.")
    if semantic is not None and semantic >= 0.5 and cosine is not None:
        reasons.append(f"Close in meaning to your query (cosine similarity {cosine:.2f}).")
    if budget:
        price = item["price"]
        if budget.get("max") is not None and budget.get("min") is not None:
            reasons.append(
                f"{format_inr(price)} is inside your {format_inr(budget['min'])}–{format_inr(budget['max'])} range."
            )
        elif budget.get("max") is not None:
            reasons.append(f"{format_inr(price)} fits your {format_inr(budget['max'])} budget.")
        elif budget.get("min") is not None:
            reasons.append(f"{format_inr(price)} is above your {format_inr(budget['min'])} minimum.")
    if item["rating_count"] >= 50 and item["rating"] >= 4.0:
        reasons.append(f"Rated {item['rating']:.1f}★ across {item['rating_count']:,} ratings.")
    elif item["rating_count"] < 50:
        reasons.append(f"Only {item['rating_count']} ratings so far, so its {item['rating']:.1f}★ is less certain.")
    if item["discount_pct"] >= 20:
        reasons.append(f"{item['discount_pct']}% below its list price.")
    if profile_id != "general" and profile_hits:
        reasons.append(f"Fits your {profile['label']} profile: {', '.join(profile_hits[:4])}.")
    if cheap is not None and cheap >= 0.6:
        reasons.append("Cheaper than most of the relevant options.")
    return reasons
