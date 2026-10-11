"""Product catalog loading (data/processed/catalog.json, produced by scripts/build_catalog.py)."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .text import normalize, variant_key

CATALOG_COLUMNS = (
    "asin",
    "name",
    "main_category",
    "sub_category",
    "price",
    "list_price",
    "rating",
    "rating_count",
    "image_id",
)


class CatalogError(RuntimeError):
    """The catalog file is missing or malformed."""


@dataclass
class Catalog:
    asins: list[str]
    names: list[str]
    main_categories: list[str]
    sub_categories: list[str]
    image_ids: list[str | None]
    price: np.ndarray
    list_price: np.ndarray
    rating: np.ndarray
    rating_count: np.ndarray
    sha256: str
    urls: dict
    phrase_map: dict

    def __post_init__(self) -> None:
        self.position = {asin: i for i, asin in enumerate(self.asins)}
        # Lower-cased, spelling-normalised names used for intent and profile matching.
        self.normalized_names = [normalize(name, self.phrase_map) for name in self.names]

    def __len__(self) -> int:
        return len(self.asins)

    def index_text(self, i: int) -> str:
        """Text indexed for keyword search."""
        return f"{self.names[i]} {self.sub_categories[i]} {self.main_categories[i]}"

    def embedding_text(self, i: int) -> str:
        """Text encoded by the sentence-embedding model."""
        return f"{self.names[i]} | {self.sub_categories[i]} | {self.main_categories[i]}"

    def variant_keys(self, i: int, tokens: int) -> tuple[str, str]:
        """Two keys under which colour/size variants of one product collide: leading title words
        outside brackets, and the brand + review pool that Amazon shares across variants."""
        key = variant_key(self.normalized_names[i], tokens)
        brand = key.split(" ", 1)[0]
        return "t:" + key, f"p:{brand}|{int(self.rating_count[i])}|{float(self.rating[i]):.1f}"

    def record(self, i: int) -> dict:
        price = float(self.price[i])
        list_price = float(self.list_price[i])
        # floor(x + 0.5) rather than round(): matches JavaScript's Math.round on .5 ties.
        discount = math.floor(100 * (list_price - price) / list_price + 0.5) if list_price > price else 0
        image_id = self.image_ids[i]
        return {
            "asin": self.asins[i],
            "name": self.names[i],
            "main_category": self.main_categories[i],
            "sub_category": self.sub_categories[i],
            "price": price,
            "list_price": list_price,
            "discount_pct": int(discount),
            "rating": float(self.rating[i]),
            "rating_count": int(self.rating_count[i]),
            "image_url": self.urls["image"].format(image_id=image_id) if image_id else None,
            "product_url": self.urls["product"].format(asin=self.asins[i]),
        }


def load_catalog(path: Path, config: dict) -> Catalog:
    if not path.exists():
        raise CatalogError(f"Catalog not found at {path}. Run `python -m scripts.build_catalog` first.")
    raw = path.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8"))
        columns = payload["columns"]
        rows = payload["rows"]
    except (ValueError, KeyError, TypeError) as exc:
        raise CatalogError(f"Catalog at {path} is not a valid columnar catalog: {exc}") from exc
    missing = [c for c in CATALOG_COLUMNS if c not in columns]
    if missing:
        raise CatalogError(f"Catalog at {path} is missing columns: {missing}")
    if not rows:
        raise CatalogError(f"Catalog at {path} contains no products.")

    col = {name: columns.index(name) for name in CATALOG_COLUMNS}

    def column(name: str) -> list:
        j = col[name]
        return [row[j] for row in rows]

    return Catalog(
        asins=column("asin"),
        names=column("name"),
        main_categories=column("main_category"),
        sub_categories=column("sub_category"),
        image_ids=column("image_id"),
        price=np.asarray(column("price"), dtype=np.float64),
        list_price=np.asarray(column("list_price"), dtype=np.float64),
        rating=np.asarray(column("rating"), dtype=np.float64),
        rating_count=np.asarray(column("rating_count"), dtype=np.float64),
        sha256=hashlib.sha256(raw).hexdigest(),
        urls=config["urls"],
        phrase_map=config["text"]["phrase_normalizations"],
    )
