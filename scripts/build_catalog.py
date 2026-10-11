"""Build the served product catalog from the raw Amazon India product export.

Input : data/raw/Amazon-Products.csv  (~550k listings scraped from amazon.in, March 2023)
Output: data/processed/catalog.json       columnar product records served by both engines
        data/processed/catalog_meta.json  catalog statistics + provenance

Selection rules (deterministic):
  * the listing must have an ASIN, a price, a star rating and at least --min-ratings ratings
  * duplicate ASINs and colour/size variants (same leading title words outside brackets,
    or the same shared review pool) are collapsed, keeping the most-reviewed listing
  * each sub-category keeps its most-reviewed products, capped at
    min(n, --base-cap + --cap-fraction * n) so broad buckets keep proportionally more
  * every product type defined in config/engine.json keeps at least --intent-quota products

Usage: python -m scripts.build_catalog [--min-ratings 20] [--base-cap 200] [--cap-fraction 0.15]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.catalog import CATALOG_COLUMNS  # noqa: E402
from src.config import CATALOG_META_PATH, CATALOG_PATH, load_engine_config  # noqa: E402
from src.preprocessing import (  # noqa: E402
    clean_price,
    clean_text,
    extract_asin,
    parse_count,
    parse_rating,
)
from src.query_parser import product_matches_intent  # noqa: E402
from src.text import normalize, variant_key  # noqa: E402

RAW_PATH = ROOT / "data" / "raw" / "Amazon-Products.csv"
VARIANT_TOKENS = 8
UPPERCASE_WORDS = {"tv": "TV", "stem": "STEM"}


def extract_image_id(url: str) -> str | None:
    """Amazon image URLs differ only by their /images/I/<id> part; engines rebuild the URL."""
    match = re.search(r"/images/I/([^./]+)\.", url or "")
    return match.group(1) if match else None


def pretty_label(label: str) -> str:
    words = []
    for word in label.split(" "):
        lower = word.lower()
        bare = lower.rstrip(",;:")
        if bare in UPPERCASE_WORDS:
            words.append(UPPERCASE_WORDS[bare] + word[len(bare) :])
        elif lower == "&":
            words.append("&")
        else:
            words.append(word[:1].upper() + word[1:])
    return " ".join(words)


def snapshot_month(links: pd.Series) -> str | None:
    """The export's product URLs carry a `qid` unix timestamp of the crawl."""
    stamps = pd.to_numeric(links.str.extract(r"qid=(\d{10})")[0], errors="coerce").dropna()
    if stamps.empty:
        return None
    return datetime.fromtimestamp(int(stamps.median()), tz=UTC).strftime("%Y-%m")


def load_raw(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, dtype=str, keep_default_na=False, encoding="utf-8")
    out = pd.DataFrame(
        {
            "asin": df["link"].map(extract_asin),
            "name": df["name"].map(clean_text),
            "main_category": df["main_category"].map(clean_text).map(pretty_label),
            "sub_category": df["sub_category"].map(clean_text),
            "price": df["discount_price"].map(clean_price),
            "list_price": df["actual_price"].map(clean_price),
            "rating": df["ratings"].map(parse_rating),
            "rating_count": df["no_of_ratings"].map(parse_count),
            "image_id": df["image"].map(extract_image_id),
        }
    )
    out.attrs["snapshot"] = snapshot_month(df["link"])
    return out


def select_products(
    df: pd.DataFrame, min_ratings: int, base_cap: int, cap_fraction: float, intent_quota: int, config: dict
) -> pd.DataFrame:
    df = df.dropna(subset=["asin", "price", "rating", "rating_count"])
    df = df[(df["rating_count"] >= min_ratings) & (df["name"].str.len() > 3)].copy()
    # Some listings report a discounted price above the list price; trust the selling price.
    df["list_price"] = df[["list_price", "price"]].max(axis=1)
    df = df.sort_values(["rating_count", "price", "asin"], ascending=[False, True, True])
    df = df.drop_duplicates("asin")

    # Collapse colour/size variants: same leading title words, or the same shared review pool.
    phrase_map = config["text"]["phrase_normalizations"]
    df["normalized"] = df["name"].map(lambda n: normalize(n, phrase_map))
    df["fingerprint"] = df["normalized"].map(lambda n: variant_key(n, VARIANT_TOKENS))
    df["review_pool"] = (
        df["fingerprint"].str.split(" ").str[0] + "|" + df["rating_count"].astype(str) + "|" + df["rating"].astype(str)
    )
    df = df.drop_duplicates("fingerprint").drop_duplicates("review_pool")

    kept = []
    for _, group in df.groupby("sub_category", sort=True):
        cap = int(min(len(group), base_cap + cap_fraction * len(group)))
        kept.append(group.head(cap))
    selected = pd.concat(kept)

    # Guarantee coverage of every product type the query parser understands, even when the
    # type is a small slice of a broad sub-category (e.g. laptops inside "All Electronics").
    chosen = set(selected["asin"])
    extra = []
    for spec in config["intents"].values():
        matches = df[df["normalized"].map(lambda n, spec=spec: product_matches_intent(n, spec))]
        already = matches["asin"].map(chosen.__contains__)
        missing = matches[~already].head(max(0, intent_quota - int(already.sum())))
        chosen.update(missing["asin"])
        extra.append(missing)
    selected = pd.concat([selected, *extra]).drop(columns=["normalized", "fingerprint", "review_pool"])
    selected["rating_count"] = selected["rating_count"].astype(int)
    return selected.sort_values(
        ["main_category", "sub_category", "rating_count", "asin"], ascending=[True, True, False, True]
    ).reset_index(drop=True)


def leading_brand(name: str) -> str | None:
    match = re.match(r"[A-Za-z][A-Za-z0-9&'.-]+", name)
    return match.group(0).strip(".-") if match else None


def build_meta(catalog: pd.DataFrame, snapshot: str | None, catalog_sha256: str, source_rows: int) -> dict:
    rating_bins = (catalog["rating"] * 2).round() / 2
    price_bands = [
        ("Under ₹500", 0, 500),
        ("₹500–2,000", 500, 2000),
        ("₹2,000–10,000", 2000, 10000),
        ("₹10,000–50,000", 10000, 50000),
        ("₹50,000+", 50000, float("inf")),
    ]
    brands = Counter(b for b in map(leading_brand, catalog["name"]) if b)
    departments = (
        catalog.groupby("main_category")
        .agg(count=("asin", "size"), sub_categories=("sub_category", lambda s: sorted(set(s))))
        .reset_index()
        .sort_values("count", ascending=False)
    )
    return {
        "source": "Amazon India product listings export (data/raw/Amazon-Products.csv)",
        "snapshot": snapshot,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "catalog_sha256": catalog_sha256,
        "source_rows": source_rows,
        "total_products": int(len(catalog)),
        "departments": [
            {"name": row.main_category, "count": int(row.count), "sub_categories": row.sub_categories}
            for row in departments.itertuples()
        ],
        "rating_histogram": {f"{k:.1f}": int(v) for k, v in rating_bins.value_counts().sort_index().items()},
        "price_bands": [
            {"label": label, "count": int(((catalog["price"] >= lo) & (catalog["price"] < hi)).sum())}
            for label, lo, hi in price_bands
        ],
        "top_brands": [{"name": name, "count": count} for name, count in brands.most_common(12)],
        "median_price": float(catalog["price"].median()),
        "median_rating": float(catalog["rating"].median()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw", type=Path, default=RAW_PATH)
    parser.add_argument("--min-ratings", type=int, default=20)
    parser.add_argument("--base-cap", type=int, default=200)
    parser.add_argument("--cap-fraction", type=float, default=0.15)
    parser.add_argument("--intent-quota", type=int, default=150, help="min products per known product type")
    args = parser.parse_args()

    if not args.raw.exists():
        sys.exit(f"Raw export not found at {args.raw}. Place Amazon-Products.csv in data/raw/.")

    raw = load_raw(args.raw)
    catalog = select_products(
        raw, args.min_ratings, args.base_cap, args.cap_fraction, args.intent_quota, load_engine_config()
    )

    catalog["price"] = catalog["price"].round(2)
    catalog["list_price"] = catalog["list_price"].round(2)
    catalog["rating"] = catalog["rating"].round(1)
    columns = list(CATALOG_COLUMNS)
    rows = [
        [None if (isinstance(v, float) and v != v) else v for v in row]
        for row in catalog[columns].itertuples(index=False, name=None)
    ]
    payload = json.dumps(
        {"schema_version": 1, "columns": columns, "rows": rows},
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    meta = build_meta(catalog, raw.attrs.get("snapshot"), digest, len(raw))
    CATALOG_META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    print(f"Selected {len(catalog):,} products from {len(raw):,} raw listings (snapshot {meta['snapshot']}).")
    print(f"Wrote {CATALOG_PATH.relative_to(ROOT)} ({CATALOG_PATH.stat().st_size / 1e6:.1f} MB)")
    print(f"Wrote {CATALOG_META_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
