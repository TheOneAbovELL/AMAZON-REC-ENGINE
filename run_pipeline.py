"""Command-line demo of the recommendation pipeline.

python run_pipeline.py "wireless earbuds under 2000" --profile student
python run_pipeline.py                      # runs the queries in tests/test_queries.txt
python run_pipeline.py "laptop" --lexical   # keyword-only mode (what the Next.js fallback serves)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from src.config import load_settings
from src.explainer import format_inr
from src.recommender import RecommendationEngine

QUERY_FILE = Path(__file__).resolve().parent / "tests" / "test_queries.txt"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query", nargs="?", help="search query (omit to run tests/test_queries.txt)")
    parser.add_argument("--profile", default="general", help="general | student | ai_student | gaming")
    parser.add_argument("-k", "--top-k", type=int, default=5)
    parser.add_argument("--lexical", action="store_true", help="skip the embedding model")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)

    options = {"encoder_factory": None} if args.lexical else {}
    engine = RecommendationEngine.load(load_settings(), **options)
    queries = (
        [args.query]
        if args.query
        else [q.strip() for q in QUERY_FILE.read_text(encoding="utf-8").splitlines() if q.strip()]
    )
    print(f"Engine mode: {engine.mode} · {len(engine.catalog):,} products\n")

    for query in queries:
        response = engine.recommend(query, args.profile, args.top_k)
        it = response["interpretation"]
        intent = it["intent"]["label"] if it["intent"] else None
        print(f"Query: {query!r}  profile={args.profile}  intent={intent}  budget={it['budget']}")
        if response.get("message"):
            print(f"  {response['message']}")
        for rank, item in enumerate(response["results"], start=1):
            print(f"  {rank}. [{item['score']:.3f}] {item['name'][:90]}")
            reason = item["reasons"][0] if item["reasons"] else ""
            print(f"     {format_inr(item['price'])} · {item['rating']}★ ({item['rating_count']:,}) · {reason}")
        print(f"  ({response['total_matches']} relevant products, {response['took_ms']} ms)\n")


if __name__ == "__main__":
    main()
