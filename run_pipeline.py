from pathlib import Path

import pandas as pd
from src.embeddings import generate_embeddings
from src.recommender import RecommendationEngine
from src.vector_store import build_index
from src.preprocessing import clean_data, create_combined_text


def build_sample_dataframe():
    return pd.DataFrame(
        [
            {
                "title": "Lenovo LOQ Gaming Laptop",
                "description": "RTX 4060, 16GB RAM, 512GB SSD, excellent for AI workloads.",
                "category": "Gaming Laptop",
                "rating": 4.6,
                "popularity": 1250,
                "price": "89000",
            },
            {
                "title": "ASUS VivoBook 15",
                "description": "Intel i5, 8GB RAM, 256GB SSD, lightweight student laptop.",
                "category": "Laptop",
                "rating": 4.1,
                "popularity": 980,
                "price": "54999",
            },
            {
                "title": "Dell Inspiron Business Laptop",
                "description": "Core i7, 16GB RAM, 1TB HDD, suitable for productivity.",
                "category": "Laptop",
                "rating": 4.2,
                "popularity": 760,
                "price": "105000",
            },
            {
                "title": "HP Pavilion Gaming Laptop",
                "description": "GTX 1650, 16GB RAM, 512GB SSD, good entry-level gaming machine.",
                "category": "Gaming Laptop",
                "rating": 4.3,
                "popularity": 640,
                "price": "78000",
            },
            {
                "title": "Sony Wireless Earbuds",
                "description": "Noise-cancelling earbuds with long battery life and crisp sound.",
                "category": "Earbuds",
                "rating": 4.4,
                "popularity": 1100,
                "price": "5999",
            },
            {
                "title": "Logitech Mechanical Keyboard",
                "description": "RGB mechanical keyboard with tactile switches and durable design.",
                "category": "Mechanical Keyboard",
                "rating": 4.7,
                "popularity": 800,
                "price": "2999",
            },
            {
                "title": "Dell UltraSharp Monitor",
                "description": "27-inch monitor built for coding and professional workflows.",
                "category": "Monitor",
                "rating": 4.5,
                "popularity": 900,
                "price": "34999",
            },
            {
                "title": "ASUS Zephyrus Deep Learning Laptop",
                "description": "RTX 4080, 32GB RAM, 1TB SSD, designed for deep learning and AI.",
                "category": "Laptop",
                "rating": 4.8,
                "popularity": 1300,
                "price": "150000",
            },
        ]
    )


def infer_user_profile(query: str) -> str:
    lower_query = query.lower()
    if "gaming" in lower_query:
        return "gaming"
    if "student" in lower_query or "ai" in lower_query or "learning" in lower_query:
        return "ai_student"
    return "general"


def load_queries():
    query_file = Path("tests/test_queries.txt")
    if query_file.exists():
        return [line.strip() for line in query_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [
        "gaming laptop under 90000",
        "wireless earbuds",
        "mechanical keyboard",
        "deep learning laptop",
        "monitor for coding",
    ]


def main():
    models_dir = Path("models")
    models_dir.mkdir(parents=True, exist_ok=True)

    data_path = Path("data/meta_Electronics.json")
    engine = RecommendationEngine()

    if data_path.exists():
        engine.load_resources(
            df_path=str(data_path),
            embeddings_path=str(models_dir / "product_embeddings.npy"),
            index_path=str(models_dir / "faiss.index"),
        )
    else:
        df = build_sample_dataframe()
        df = clean_data(df)
        df = create_combined_text(df)
        embeddings = generate_embeddings(df["combined_text"].tolist())
        index = build_index(embeddings)
        engine.df = df
        engine.embeddings = embeddings
        engine.index = index

    queries = load_queries()
    print("Running recommendation pipeline for test queries:\n")
    for query in queries:
        user_type = infer_user_profile(query)
        print(f"Query: {query}")
        print(f"User profile: {user_type}")
        recommendations = engine.recommend(query, user_type=user_type, top_k=5, log_path="logs/recommendation_logs.csv")
        for rank, product in enumerate(recommendations, start=1):
            explanation = engine.explain(query, product, user_type)
            print(f"Rank {rank}: {product['title']}")
            print(f"  Score: {product.get('personalized_score', product.get('score', 0.0)):.4f}")
            print(f"  Price: {product['price']}")
            print(f"  Rating: {product['rating']}")
            print(f"  Explanation: {explanation}\n")
        print("-" * 60)


if __name__ == "__main__":
    main()
