"""Cleaning helpers for the raw Amazon India product export (data/raw/*.csv)."""

from __future__ import annotations

import math
import re

_ASIN_RE = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})", re.IGNORECASE)
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def _is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return str(value).strip() == ""


def clean_price(value) -> float | None:
    """Parse a rupee string such as '₹32,999' into 32999.0. Returns None when absent."""
    if _is_missing(value):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    match = _NUMBER_RE.search(str(value).replace(",", ""))
    if not match:
        return None
    price = float(match.group())
    return price if price > 0 else None


def parse_count(value) -> int | None:
    """Parse a rating count such as '2,255' into 2255. Returns None when absent."""
    if _is_missing(value):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    match = _NUMBER_RE.search(str(value).replace(",", ""))
    return int(float(match.group())) if match else None


def parse_rating(value) -> float | None:
    """Parse a star rating, keeping only values on the 0-5 scale."""
    if _is_missing(value):
        return None
    try:
        rating = float(str(value).strip())
    except ValueError:
        return None
    return rating if 0.0 < rating <= 5.0 else None


def extract_asin(url) -> str | None:
    """Extract the 10-character ASIN from an Amazon product URL."""
    if _is_missing(url):
        return None
    match = _ASIN_RE.search(str(url))
    return match.group(1).upper() if match else None


REPLACEMENT_CHAR = "\N{REPLACEMENT CHARACTER}"
_MOJIBAKE_MARKERS = ("â€", "Ã", "Â")  # 'â€', 'Ã', 'Â': UTF-8 read as cp1252
_INVISIBLE_RE = re.compile("[​-‏⁠﻿\u0080-\u009f]")


def repair_mojibake(text: str) -> str:
    """Undo UTF-8 text that was decoded as cp1252 ('3050Â Ti', 'â€™'), when it round-trips cleanly."""
    if not any(marker in text for marker in _MOJIBAKE_MARKERS):
        return text
    try:
        return text.encode("cp1252").decode("utf-8")
    except UnicodeError:
        return text.replace("Â", " ")


def clean_text(value) -> str:
    """Collapse whitespace and repair encoding damage present in the export."""
    if _is_missing(value):
        return ""
    text = str(value).replace("D" + REPLACEMENT_CHAR + "cor", "D\N{LATIN SMALL LETTER E WITH ACUTE}cor")
    text = repair_mojibake(text.replace(REPLACEMENT_CHAR, ""))
    text = _INVISIBLE_RE.sub("", text).replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip()
