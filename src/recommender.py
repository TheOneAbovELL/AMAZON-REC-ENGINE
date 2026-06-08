"""Orchestrator for the Amazon-style recommendation engine."""

import os
import re
from pathlib import Path
from typing import Optional

import numpy as np

from .data_loader import load_data
from .preprocessing import clean_data, create_combined_text
from .embeddings import (
    generate_embeddings,
    load_embeddings,
    save_embeddings,
)
from .ranking import rank_products
from .vector_store import build_index, load_index, save_index, search
from .personalization import personalize_recommendations
from .llm_explainer import explain_recommendation
from .logger import log_recommendation


def parse_price(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    price_text = str(value).replace("₹", "").replace(",", "")
    match = re.search(r"\d+(?:\.\d+)?", price_text)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None


def extract_budget(query: str) -> Optional[float]:
    if not query:
        return None
    cleaned = query.replace("₹", "").replace(",", "")
    matches = re.findall(r"\d+(?:\.\d+)?", cleaned)
    values = []
    for match in matches:
        try:
            values.append(float(match))
        except ValueError:
            continue
    return max(values) if values else None


def compute_budget_score(price: Optional[float], budget: Optional[float]) -> float:
    if budget is None or price is None:
        return 0.0
    if price <= budget:
        return 1.0
    return max(0.0, 1.0 - (price - budget) / budget)


def compute_category_score(query: str, category: str) -> float:
    if not query or not category:
        return 0.0
    query_lower = query.lower()
    category_lower = str(category).lower()
    if "gaming" in query_lower and "gaming" in category_lower:
        return 1.0
    if "laptop" in query_lower and "laptop" in category_lower:
        return 1.0
    if "monitor" in query_lower and "monitor" in category_lower:
        return 1.0
    return 0.0


class RecommendationEngine:
    def __init__(self, df=None, index=None, embeddings=None):
        self.df = df
        self.index = index
        self.embeddings = embeddings
        self.embeddings_path = None
        self.index_path = None

    def load_resources(
        self,
        df_path: Optional[str] = None,
        embeddings_path: Optional[str] = None,
        index_path: Optional[str] = None,
        save_if_missing: bool = True,
    ):
        self.embeddings_path = embeddings_path
        self.index_path = index_path

        if self.df is None:
            if df_path is None:
                raise ValueError("df_path is required when no DataFrame is loaded.")
            self.df = load_data(df_path)
            self.df = clean_data(self.df)
            self.df = create_combined_text(self.df)

        if self.embeddings is None:
            if embeddings_path and os.path.exists(embeddings_path):
                self.embeddings = load_embeddings(embeddings_path)
            else:
                self.embeddings = generate_embeddings(self.df["combined_text"].tolist())
                if save_if_missing and embeddings_path:
                    save_embeddings(self.embeddings, embeddings_path)

        if self.index is None:
            if index_path and os.path.exists(index_path):
                self.index = load_index(index_path)
            else:
                self.index = build_index(self.embeddings)
                if save_if_missing and index_path:
                    save_index(self.index, index_path)

    def retrieve_candidates(self, query: str, top_k: int = 50):
        query_embedding = generate_embeddings([query])
        distances, indices = search(query_embedding, self.index, top_k)
        similarities = [1.0 / (1.0 + float(distance)) for distance in distances[0]]
        return indices[0].tolist(), similarities

    def rank_candidates(self, indices, similarities, query: str):
        budget = extract_budget(query)
        candidates = []

        for idx, similarity in zip(indices, similarities):
            row = self.df.iloc[idx]
            price = parse_price(row.get("price", None))
            rating = row.get("rating", 0.0) or 0.0
            popularity = row.get("popularity", 0.0) or 0.0
            budget_score = compute_budget_score(price, budget)
            category_score = compute_category_score(query, row.get("category", ""))
            candidate = {
                "index": int(idx),
                "title": row.get("title", ""),
                "description": row.get("description", ""),
                "category": row.get("category", ""),
                "price": price,
                "rating": float(rating),
                "popularity": float(popularity),
                "combined_text": row.get("combined_text", ""),
                "similarity": float(similarity),
                "budget_score": float(budget_score),
                "category_score": float(category_score),
            }
            candidates.append(candidate)

        ranked = rank_products(candidates)
        return ranked

    def personalize(self, products, user_type: Optional[str] = None):
        if not user_type:
            return products
        return personalize_recommendations(products, user_type)

    def recommend(
        self,
        query: str,
        user_type: Optional[str] = None,
        top_k: int = 10,
        log_path: Optional[str] = "logs/recommendation_logs.csv",
    ):
        indices, similarities = self.retrieve_candidates(query, top_k=50)
        ranked = self.rank_candidates(indices, similarities, query)
        personalized = self.personalize(ranked, user_type)
        recommended = personalized[:top_k]

        if log_path:
            retrieved_titles = [product["title"] for product in ranked[:top_k]]
            final_product = recommended[0]["title"] if recommended else ""
            score = float(recommended[0].get("personalized_score", recommended[0].get("score", 0.0))) if recommended else 0.0
            log_recommendation(
                query=query,
                user_profile=user_type or "general",
                retrieved_products=retrieved_titles,
                final_product=final_product,
                score=score,
                log_path=Path(log_path),
            )

        return recommended

    def explain(self, query: str, product, user_type: Optional[str] = None):
        return explain_recommendation(query, product, user_type)
