"""Deterministic query understanding: budget, product-type intent and search terms.

Mirrored by lib/engine/queryParser.mjs; tests/fixtures/query_cases.json keeps them in sync.

Budgets are only read from explicit phrasing ("under 90k", "between 20000 and 30000",
"₹500", "50k") so model numbers such as "RTX 4060" or "i5 12th gen" are never mistaken
for prices.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache

from .text import normalize, query_terms

# A number followed by a unit ("50 cm", "1.5 ton", "2 years") is a spec, not a price.
_UNIT_GUARD = (
    r"(?!\s*(?:inch|inches|in|cm|mm|gb|tb|hz|mah|mp|w|watt|watts|kg|g|gm|ml|l|ltr|litre|litres|"
    r"liter|liters|ton|tons|star|stars|year|years|month|months|day|days|pcs|pieces|pack|x|"
    r"hour|hours|hr|hrs|people|person|persons)\b)"
)
_AMOUNT = r"(?:(?:₹|\brs\.?|\binr)\s*)?(\d+(?:\.\d+)?)\s*(k|thousand|lakhs?|lacs?)?(?![a-z0-9])" + _UNIT_GUARD
_MARKED_AMOUNT = (
    r"(?:(?:₹|\brs\.?|\binr)\s*(\d+(?:\.\d+)?)\s*(k|thousand|lakhs?|lacs?)?"
    r"|\b(\d+(?:\.\d+)?)\s*(k|thousand|lakhs?|lacs?))(?![a-z0-9])"
)
_RANGE_RE = re.compile(r"\b(?:between|from)\s+" + _AMOUNT + r"\s*(?:and|to|-)\s*" + _AMOUNT, re.ASCII)
_MAX_RE = re.compile(
    r"(?:\b(?:under|below|less than|within|upto|up to|max|maximum|budget of|budget is|budget|"
    r"not more than|cheaper than|lower than)|<=?)\s*" + _AMOUNT,
    re.ASCII,
)
_MIN_RE = re.compile(
    r"(?:\b(?:above|over|more than|at least|minimum|min|starting at|starting)|>=?)\s*" + _AMOUNT, re.ASCII
)
_AROUND_RE = re.compile(r"(?:\b(?:around|about|approx|approximately|roughly|near)|~)\s*" + _AMOUNT, re.ASCII)
_MARKED_RE = re.compile(_MARKED_AMOUNT, re.ASCII)
_THOUSANDS_RE = re.compile(r"(?<=\d),(?=\d)", re.ASCII)
MIN_BUDGET = 50.0


@dataclass
class Budget:
    min: float | None = None
    max: float | None = None
    text: str = ""


@dataclass
class Intent:
    id: str
    label: str
    keyword: str


@dataclass
class QueryInterpretation:
    query: str
    normalized: str
    search_text: str = ""
    terms: list[str] = field(default_factory=list)
    budget: Budget | None = None
    intent: Intent | None = None
    prefers_low_price: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _amount(number: str, unit: str | None) -> float:
    value = float(number)
    unit = (unit or "").lower()
    if unit in {"k", "thousand"}:
        value *= 1_000
    elif unit.startswith(("lakh", "lac")):
        value *= 100_000
    return value


def _strip(text: str, match: re.Match) -> str:
    return text[: match.start()] + " " + text[match.end() :]


def parse_budget(normalized: str) -> tuple[Budget | None, str]:
    """Return the budget (if any) and the query with the budget phrase removed."""
    text = _THOUSANDS_RE.sub("", normalized)
    low: float | None = None
    high: float | None = None
    spans: list[str] = []

    match = _RANGE_RE.search(text)
    if match:
        a, b = _amount(match.group(1), match.group(2)), _amount(match.group(3), match.group(4))
        low, high = min(a, b), max(a, b)
        spans.append(match.group(0).strip())
        text = _strip(text, match)

    for regex, kind in ((_AROUND_RE, "around"), (_MAX_RE, "max"), (_MIN_RE, "min")):
        match = regex.search(text)
        if not match:
            continue
        value = _amount(match.group(1), match.group(2))
        if value < MIN_BUDGET:
            continue
        if kind == "around":
            low, high = value * 0.8, value * 1.2
        elif kind == "max":
            high = value if high is None else min(high, value)
        else:
            low = value if low is None else max(low, value)
        spans.append(match.group(0).strip())
        text = _strip(text, match)

    if low is None and high is None:
        match = _MARKED_RE.search(text)
        if match:
            number, unit = (match.group(1), match.group(2)) if match.group(1) else (match.group(3), match.group(4))
            value = _amount(number, unit)
            if value >= MIN_BUDGET:
                high = value
                spans.append(match.group(0).strip())
                text = _strip(text, match)

    if low is None and high is None:
        return None, normalized
    if low is not None and high is not None and low > high:
        low, high = high, low
    return Budget(min=low, max=high, text=" / ".join(spans)), text


@lru_cache(maxsize=64)
def _word_re(phrase: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", re.ASCII)


@lru_cache(maxsize=4096)
def _compiled(pattern: str) -> re.Pattern:
    # ASCII semantics make \b and \d behave like JavaScript RegExp.
    return re.compile(pattern, re.ASCII)


def detect_intent(text: str, intents: dict) -> Intent | None:
    """Pick the product type named last in the query ('laptop bag' -> bag, 'gaming laptop' -> laptop).

    An intent is dropped when the query itself names one of its accessory terms
    ('laptop stand', 'mobile holder'), because the shopper wants the accessory.
    """
    best: tuple[int, int, str, str] | None = None
    for intent_id, spec in intents.items():
        for keyword in spec["query_terms"]:
            for match in _word_re(keyword).finditer(text):
                candidate = (match.end(), len(keyword), intent_id, keyword)
                if best is None or candidate[:2] > best[:2]:
                    best = candidate
    if best is None:
        return None
    _, _, intent_id, keyword = best
    spec = intents[intent_id]
    if any(_compiled(p).search(text) for p in spec.get("product_exclude", [])):
        return None
    return Intent(id=intent_id, label=spec["label"], keyword=keyword)


@lru_cache(maxsize=256)
def _alternation(patterns: tuple[str, ...]) -> re.Pattern | None:
    """One regex equivalent to any(p.search(...) for p in patterns), but far cheaper to run."""
    return re.compile("|".join(f"(?:{p})" for p in patterns), re.ASCII) if patterns else None


def product_matches_intent(normalized_name: str, spec: dict) -> bool:
    include = _alternation(tuple(spec["product_patterns"]))
    if include is None or not include.search(normalized_name):
        return False
    exclude = _alternation(tuple(spec.get("product_exclude", [])))
    return exclude is None or not exclude.search(normalized_name)


def parse_query(query: str, config: dict) -> QueryInterpretation:
    text_cfg = config["text"]
    normalized = normalize(query.strip(), text_cfg["phrase_normalizations"])
    budget, remainder = parse_budget(normalized)
    prefers_low_price = any(_word_re(term).search(normalized) for term in text_cfg["low_price_terms"])
    intent = detect_intent(remainder, config["intents"])
    terms = query_terms(remainder, frozenset(text_cfg["stopwords"]))
    return QueryInterpretation(
        query=query.strip(),
        normalized=normalized,
        search_text=" ".join(remainder.split()),
        terms=terms,
        budget=budget,
        intent=intent,
        prefers_low_price=prefers_low_price,
    )
