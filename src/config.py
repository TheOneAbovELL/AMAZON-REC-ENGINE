"""Configuration settings for the Amazon recommendation engine."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
MODELS_DIR = BASE_DIR / "models"

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_RANKING_MODEL = "gpt-4.1"


def get_config():
    return {
        "base_dir": BASE_DIR,
        "raw_data_dir": RAW_DATA_DIR,
        "processed_data_dir": PROCESSED_DATA_DIR,
        "models_dir": MODELS_DIR,
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "ranking_model": DEFAULT_RANKING_MODEL,
    }
