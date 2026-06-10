from numpy.ma import product
import streamlit as st
from pathlib import Path

import pandas as pd
from src.embeddings import generate_embeddings
from src.preprocessing import clean_data, create_combined_text
from src.recommender import RecommendationEngine
from src.vector_store import build_index
from analytics.visualization import (
    plot_category_distribution,
    plot_top_brands,
    plot_rating_distribution,
    plot_score_distribution,
)


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


@st.cache_resource
def load_engine():
    engine = RecommendationEngine()
    data_path = Path("data/meta_Electronics.json")
    models_dir = Path("models")
    models_dir.mkdir(parents=True, exist_ok=True)

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

    return engine


def main():
    st.set_page_config(page_title="Amazon-Style Recommendation Engine", layout="wide")
    st.title("Amazon-Style Recommendation Engine")
    st.markdown("---")

    engine = load_engine()
    user_profile = st.sidebar.selectbox(
        "User Profile",
        ["general", "gaming", "student", "ai_student"],
        index=3,
    )
    query = st.sidebar.text_input("Query", "Need laptop for AI under 90k")
    st.sidebar.markdown("---")
    st.sidebar.write("Select a user profile and enter a product search query, then click Recommend.")

    recommendation_area, analytics_area = st.columns([2, 1])

    with recommendation_area:
        st.subheader("Recommendations")
        if st.button("Recommend") and query.strip():
            recommendations = engine.recommend(
                query=query,
                user_type=user_profile,
                top_k=5,
                log_path="logs/recommendation_logs.csv",
            )
            if not recommendations:
                st.warning("No recommendations could be generated for this query.")
            for idx, product in enumerate(recommendations, start=1):
                title = product.get(
                    "title",
                    product.get(
                        "name",
                        "Unknown Product"
                        )
                )
                with st.expander(f"{idx}. {title}"):
                    st.markdown(f"### {title}")
                    st.write(f"⭐ Rating: {product.get('rating', 'N/A')}")
                    st.write(f"💰 Price: ₹{product.get('price', 'N/A')}")
                    st.write(
                        f"🎯 Recommendation Score: "
                        f"{product.get('personalized_score', product.get('score', 0)):.4f}"
                        )
                    st.write(f"👤 User Profile: {user_profile}")
                    st.markdown("### Why Recommended?")
                    st.write(
                        product.get(
                            "explanation",
                            "Recommended because it is highly relevant to your query."
                            )
                        
                        )
    with analytics_area:
        st.subheader("Analytics")
        st.pyplot(plot_category_distribution(engine.df))
        st.pyplot(plot_top_brands(engine.df))
        recommendations = []
        if query.strip():
            recommendations = engine.recommend(
                query=query,
                user_type=user_profile,
                top_k=10,
                log_path=None,
            )
        st.pyplot(plot_score_distribution(recommendations))
        st.pyplot(plot_rating_distribution(engine.df))

    st.markdown("---")
    st.write("Built-in analytics and recommendation cards help reviewers verify relevance, ordering, personalization, and explanation quality.")


if __name__ == "__main__":
    main()
