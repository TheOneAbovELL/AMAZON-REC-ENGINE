"""Paths, environment settings and the shared ranking configuration."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
MODELS_DIR = BASE_DIR / "models"

CATALOG_PATH = PROCESSED_DATA_DIR / "catalog.json"
CATALOG_META_PATH = PROCESSED_DATA_DIR / "catalog_meta.json"
ENGINE_CONFIG_PATH = BASE_DIR / "config" / "engine.json"
EMBEDDINGS_PATH = MODELS_DIR / "embeddings.npy"
EMBEDDINGS_MANIFEST_PATH = MODELS_DIR / "manifest.json"

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name, "").strip()
    return int(value) if value else default


@dataclass(frozen=True)
class Settings:
    catalog_path: Path = CATALOG_PATH
    catalog_meta_path: Path = CATALOG_META_PATH
    embeddings_path: Path = EMBEDDINGS_PATH
    manifest_path: Path = EMBEDDINGS_MANIFEST_PATH
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    # Build embeddings at startup when they are missing or stale (takes a few minutes on CPU).
    auto_build_index: bool = True
    # Serve lexical-only results instead of failing when the embedding model cannot load.
    allow_lexical_fallback: bool = True
    allowed_origins: tuple[str, ...] = field(default_factory=tuple)
    rate_limit_per_minute: int = 120
    query_log_path: Path | None = None


def load_settings() -> Settings:
    origins = tuple(o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip())
    log_path = os.environ.get("QUERY_LOG_PATH", "").strip()
    return Settings(
        catalog_path=Path(os.environ.get("CATALOG_PATH", CATALOG_PATH)),
        embeddings_path=Path(os.environ.get("EMBEDDINGS_PATH", EMBEDDINGS_PATH)),
        manifest_path=Path(os.environ.get("EMBEDDINGS_MANIFEST_PATH", EMBEDDINGS_MANIFEST_PATH)),
        embedding_model=os.environ.get("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
        auto_build_index=_env_bool("AUTO_BUILD_INDEX", True),
        allow_lexical_fallback=_env_bool("ALLOW_LEXICAL_FALLBACK", True),
        allowed_origins=origins,
        rate_limit_per_minute=_env_int("RATE_LIMIT_PER_MINUTE", 120),
        query_log_path=Path(log_path) if log_path else None,
    )


@lru_cache(maxsize=1)
def load_engine_config(path: Path = ENGINE_CONFIG_PATH) -> dict:
    """Ranking weights, query rules, intents and profiles shared with the JavaScript engine."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
