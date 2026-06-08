import unittest
import pandas as pd
from src.recommender import RecommendationEngine
from src.embeddings import generate_embeddings
from src.preprocessing import clean_data, create_combined_text
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


class RecommendationEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        df = build_sample_dataframe()
        df = clean_data(df)
        df = create_combined_text(df)
        embeddings = generate_embeddings(df["combined_text"].tolist())
        index = build_index(embeddings)
        cls.engine = RecommendationEngine(df=df, index=index, embeddings=embeddings)

    def test_personalization_changes_order(self):
        query = "Need a gaming laptop under 90000"
        general = self.engine.recommend(query, user_type="general", top_k=3, log_path=None)
        gaming = self.engine.recommend(query, user_type="gaming", top_k=3, log_path=None)
        self.assertNotEqual([item["title"] for item in general], [item["title"] for item in gaming])

    def test_recommended_products_are_relevant(self):
        query = "wireless earbuds"
        results = self.engine.recommend(query, user_type="general", top_k=3, log_path=None)
        self.assertTrue(any("earbuds" in item["title"].lower() or "earbuds" in item["description"].lower() for item in results))


if __name__ == "__main__":
    unittest.main()
