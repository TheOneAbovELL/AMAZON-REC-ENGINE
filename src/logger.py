import csv
import json
from datetime import datetime
from pathlib import Path

DEFAULT_LOG_PATH = Path("logs/recommendation_logs.csv")

LOG_FIELDS = [
    "timestamp",
    "query",
    "user_profile",
    "retrieved_products",
    "final_product",
    "score",
]


def ensure_log_file(log_path: Path = DEFAULT_LOG_PATH):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not log_path.exists():
        with log_path.open("w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=LOG_FIELDS)
            writer.writeheader()


def log_recommendation(
    query: str,
    user_profile: str,
    retrieved_products,
    final_product: str,
    score: float,
    log_path: Path = DEFAULT_LOG_PATH,
):
    ensure_log_file(log_path)
    row = {
        "timestamp": datetime.utcnow().isoformat(),
        "query": query,
        "user_profile": user_profile,
        "retrieved_products": json.dumps(retrieved_products, ensure_ascii=False),
        "final_product": final_product,
        "score": f"{score:.4f}",
    }
    with log_path.open("a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=LOG_FIELDS)
        writer.writerow(row)
