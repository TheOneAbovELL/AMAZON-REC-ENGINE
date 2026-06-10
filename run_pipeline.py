import glob
import os
from pathlib import Path
import pandas as pd
from src.embeddings import generate_embeddings
from src.recommender import RecommendationEngine
from src.vector_store import build_index
from src.preprocessing import (
    aggregate_product_reviews,
    clean_data,
    create_combined_text,
)


def build_sample_dataframe():
    """Fallback sample data corrected to match the new Amazon India dataset schema."""
    return pd.DataFrame(
        [
            {
                "name": "Lenovo LOQ Gaming Laptop (RTX 4060, 16GB RAM)",
                "main_category": "computers",
                "sub_category": "Laptops",
                "reviewText": "Excellent for AI workloads and heavy gaming. Quiet fans.",
                "overall": 4.6,
                "no_of_ratings": "1,250",
                "discount_price": "₹89,000",
                "actual_price": "₹1,15,000",
            },
            {
                "name": "Sony WH-1000XM4 Wireless Earbuds",
                "main_category": "electronics",
                "sub_category": "Audio",
                "reviewText": "Noise-cancelling earbuds with long battery life and crisp sound.",
                "overall": 4.4,
                "no_of_ratings": "1,100",
                "discount_price": "₹19,990",
                "actual_price": "₹29,990",
            },
            {
                "name": "Logitech MX Mechanical Wireless Keyboard",
                "main_category": "computers",
                "sub_category": "Accessories",
                "reviewText": "Tactile switches and durable design. Great for typing and coding.",
                "overall": 4.7,
                "no_of_ratings": "800",
                "discount_price": "₹12,999",
                "actual_price": "₹15,999",
            },
            {
                "name": "LG 1.5 Ton 3 Star AI DUAL Inverter Split AC",
                "main_category": "appliances",
                "sub_category": "Air Conditioners",
                "reviewText": "Great cooling performance, silent operation, and power efficient.",
                "overall": 4.3,
                "no_of_ratings": "3,450",
                "discount_price": "₹37,990",
                "actual_price": "₹68,990",
            },
        ]
    )


def infer_user_profile(query: str) -> str:
    lower_query = query.lower()
    if "gaming" in lower_query:
        return "gaming"
    if (
        "student" in lower_query
        or "ai" in lower_query
        or "learning" in lower_query
    ):
        return "ai_student"
    return "general"


def load_queries():
    query_file = Path("tests/test_queries.txt")
    if query_file.exists():
        return [
            line.strip()
            for line in query_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    return ["wireless speaker", "air conditioner", "gaming headset"]


def main():
    models_dir = Path("models")
    models_dir.mkdir(parents=True, exist_ok=True)
    (Path("logs")).mkdir(parents=True, exist_ok=True)

    data_path = Path("data/processed/product_dataset.csv")
    raw_data_path = Path("data/processed/unified_dataset.csv")

    engine = RecommendationEngine()

    if data_path.exists():
        print(f"Loading product-level dataset from {data_path}...")
        df = pd.read_csv(data_path)
        df = clean_data(df)
        df = create_combined_text(df)
    elif raw_data_path.exists():
        print(
            f"Product dataset not found. Aggregating review-level data from {raw_data_path}..."
        )
        raw_df = pd.read_csv(raw_data_path)
        raw_df = clean_data(raw_df)
        df = aggregate_product_reviews(raw_df)
        df = clean_data(df)
        df = create_combined_text(df)
        data_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(data_path, index=False)
        print(f"Saved aggregated product dataset to {data_path} ({df.shape[0]} unique products).")
    else:
        print(
            f"Unified data file not found at '{raw_data_path}'. Running with mock dataset..."
        )
        df = build_sample_dataframe()
        df = clean_data(df)
        df = create_combined_text(df)

    embeddings_path = models_dir / "product_embeddings.npy"
    index_path = models_dir / "faiss.index"
    needs_regeneration = (
        not embeddings_path.exists()
        or not index_path.exists()
        or embeddings_path.stat().st_mtime < data_path.stat().st_mtime
        or index_path.stat().st_mtime < data_path.stat().st_mtime
    ) if data_path.exists() else True

    if needs_regeneration:
        print("Generating vector embeddings... This might take a minute.")
        embeddings = generate_embeddings(df["combined_text"].tolist())
        index = build_index(embeddings)

        import numpy as np
        import faiss

        np.save(str(embeddings_path), embeddings)
        faiss.write_index(index, str(index_path))
    else:
        import numpy as np
        import faiss

        embeddings = np.load(str(embeddings_path))
        index = faiss.read_index(str(index_path))

    engine.df = df
    engine.embeddings = embeddings
    engine.index = index

    queries = load_queries()
    print("\nRunning recommendation pipeline for test queries:\n")
    for query in queries:
        user_type = infer_user_profile(query)
        print(f"Query: {query}")
        print(f"User profile: {user_type}")

        recommendations = engine.recommend(
            query,
            user_type=user_type,
            top_k=5,
            log_path="logs/recommendation_logs.csv",
        )

        for rank, product in enumerate(recommendations, start=1):
            explanation = engine.explain(query, product, user_type)
            title_text = product.get("name", product.get("title", "Unknown"))
            price_val = product.get("discount_price", product.get("price", "0.0"))

            print(f"Rank {rank}: {title_text}")
            print(
                f"  Score: {product.get('personalized_score', product.get('final_score', 0.0)):.4f}"
            )
            print(f"  Price: {price_val}")
            print(f"  Rating: {product.get('rating', 0.0)}")
            print(f"  Explanation: {explanation}\n")
        print("-" * 60)


if __name__ == "__main__":
    main()
