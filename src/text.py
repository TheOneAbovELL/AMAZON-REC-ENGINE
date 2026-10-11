"""Text normalisation and tokenisation.

Mirrored line-for-line by lib/engine/text.mjs; tests/fixtures/text_cases.json keeps them in sync.
"""

from __future__ import annotations

import re
from functools import lru_cache

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_BRACKETS_RE = re.compile(r"\([^)]*\)|\[[^\]]*\]")
# "16 GB" -> "16gb", "43 inches" / 43" -> "43inch" so specs match however they are written.
_UNIT_RE = re.compile(r"(\d)\s*(inches|inch|gb|tb|hz|mah|mp|w|kg|ml)\b|(\d)\s*(\"|”)", re.ASCII)
_UNIT_CANON = {"inches": "inch", '"': "inch", "”": "inch"}


@lru_cache(maxsize=8)
def _phrase_pattern(phrases: tuple[str, ...]) -> re.Pattern | None:
    if not phrases:
        return None
    ordered = sorted(phrases, key=len, reverse=True)
    return re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(p) for p in ordered) + r")(?![a-z0-9])")


def _join_unit(match: re.Match) -> str:
    digit, unit = (match.group(1), match.group(2)) if match.group(1) else (match.group(3), match.group(4))
    return digit + _UNIT_CANON.get(unit, unit)


def normalize(text: str, phrase_map: dict[str, str]) -> str:
    """Lower-case, unify spelling variants ('t-shirt' -> 'tshirt') and join units ('16 gb' -> '16gb')."""
    lowered = (text or "").lower()
    pattern = _phrase_pattern(tuple(phrase_map))
    if pattern is not None:
        lowered = pattern.sub(lambda m: phrase_map[m.group(1)], lowered)
    return _UNIT_RE.sub(_join_unit, lowered)


def stem(token: str) -> str:
    """Strip English plural endings so 'earbuds' matches 'earbud'. Tokens with digits are kept."""
    if any(ch.isdigit() for ch in token):
        return token
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and (token.endswith(("ches", "shes")) or (token.endswith("es") and token[-3] in "sxz")):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def raw_tokens(normalized: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(normalized) if len(t) > 1 or t.isdigit()]


def tokenize(text: str, phrase_map: dict[str, str]) -> list[str]:
    """Tokens used for indexing product text."""
    return [stem(t) for t in raw_tokens(normalize(text, phrase_map))]


def query_terms(normalized_query: str, stopwords: frozenset[str]) -> list[str]:
    """Distinct, stemmed, non-stopword query tokens in query order."""
    seen: dict[str, None] = {}
    for token in raw_tokens(normalized_query):
        if token in stopwords:
            continue
        seen.setdefault(stem(token), None)
    return list(seen)


def variant_key(normalized_name: str, tokens: int) -> str:
    """Leading title words outside brackets: '(Aqua Green, 4GB)' variants share a key."""
    return " ".join(raw_tokens(_BRACKETS_RE.sub(" ", normalized_name))[:tokens])
