import csv
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import pandas as pd

from src.embeddings import generate_embeddings
from src.evaluation import precision_at_k, recall_at_k, ndcg_at_k
from src.preprocessing import clean_data, create_combined_text
from src.recommender import RecommendationEngine
from src.vector_store import build_index


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


def keyword_search(df, query, top_k=10):
    tokens = [token.strip().lower() for token in query.split() if token.strip()]
    candidates = []
    for idx, row in df.iterrows():
        text = " ".join(
            [
                str(row.get("title", "")),
                str(row.get("description", "")),
                str(row.get("category", "")),
            ]
        ).lower()
        score = sum(1 for token in tokens if token in text)
        if score > 0:
            candidates.append((score, float(row.get("popularity", 0) or 0), idx))
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [idx for _, _, idx in candidates][:top_k]


def evaluate_model(recommended_indices, relevant_titles, df, k=5):
    recommended_titles = [df.iloc[idx]["title"] for idx in recommended_indices]
    relevant_set = set(relevant_titles)
    return {
        "precision": precision_at_k(recommended_titles, relevant_set, k),
        "recall": recall_at_k(recommended_titles, relevant_set, k),
        "ndcg": ndcg_at_k(recommended_titles, relevant_set, k),
    }


def main():
    df = build_sample_dataframe()
    df = clean_data(df)
    df = create_combined_text(df)
    embeddings = generate_embeddings(df["combined_text"].tolist())
    index = build_index(embeddings)
    engine = RecommendationEngine(df=df, embeddings=embeddings, index=index)

    relevant_items = {
        "gaming laptop under 90000": ["Lenovo LOQ Gaming Laptop", "HP Pavilion Gaming Laptop"],
        "wireless earbuds": ["Sony Wireless Earbuds"],
        "mechanical keyboard": ["Logitech Mechanical Keyboard"],
        "deep learning laptop": ["ASUS Zephyrus Deep Learning Laptop"],
        "monitor for coding": ["Dell UltraSharp Monitor"],
    }

    queries = list(relevant_items.keys())
    report_rows = []
    for model_name, predictor in [
        ("Baseline Search", lambda q: keyword_search(df, q, top_k=5)),
        ("Semantic Search", lambda q: [item["index"] for item in engine.recommend(q, user_type=None, top_k=5, log_path=None)]),
        (
            "Personalized Search",
            lambda q: [item["index"] for item in engine.recommend(q, user_type="ai_student", top_k=5, log_path=None)]
            if "ai" in q or "learning" in q
            else [item["index"] for item in engine.recommend(q, user_type="gaming", top_k=5, log_path=None)]
            if "gaming" in q
            else [item["index"] for item in engine.recommend(q, user_type="general", top_k=5, log_path=None)]
        ),
    ]:
        precision_values = []
        recall_values = []
        ndcg_values = []
        for query in queries:
            predicted_indices = predictor(query)
            metrics = evaluate_model(predicted_indices, relevant_items[query], df, k=5)
            precision_values.append(metrics["precision"])
            recall_values.append(metrics["recall"])
            ndcg_values.append(metrics["ndcg"])
        report_rows.append(
            {
                "model": model_name,
                "precision_at_5": round(sum(precision_values) / len(precision_values), 3),
                "recall_at_5": round(sum(recall_values) / len(recall_values), 3),
                "ndcg_at_5": round(sum(ndcg_values) / len(ndcg_values), 3),
            }
        )

    output_path = Path("results/evaluation_report.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["model", "precision_at_5", "recall_at_5", "ndcg_at_5"])
        writer.writeheader()
        writer.writerows(report_rows)

    print(f"Saved evaluation report to {output_path}")


if __name__ == "__main__":
    main()
