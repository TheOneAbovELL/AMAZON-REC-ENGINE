"""
Lightweight REST API server for Amazon Recommendation Engine.
Can be run locally or deployed to external container platforms (Render, Railway, Cloud Run).
Uses standard library http.server to avoid introducing heavy external frameworks.
"""

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import pandas as pd
import numpy as np

from src.recommender import RecommendationEngine
from src.preprocessing import clean_data, create_combined_text
from src.embeddings import generate_embeddings
from src.vector_store import build_index

engine = None


def init_engine():
    global engine
    if engine is not None:
        return engine

    engine = RecommendationEngine()
    data_path = Path("data/processed/product_dataset.csv")
    models_dir = Path("models")
    models_dir.mkdir(parents=True, exist_ok=True)

    if data_path.exists():
        print(f"Loading dataset from {data_path}...")
        df = pd.read_csv(data_path)
        df = clean_data(df)
        df = create_combined_text(df)
        engine.df = df

        embeddings_path = models_dir / "product_embeddings.npy"
        index_path = models_dir / "faiss.index"

        if embeddings_path.exists() and index_path.exists():
            import faiss
            engine.embeddings = np.load(str(embeddings_path))
            engine.index = faiss.read_index(str(index_path))
            print(f"Loaded precomputed embeddings and FAISS index ({len(df)} products).")
        else:
            print("Generating vector embeddings...")
            engine.embeddings = generate_embeddings(df["combined_text"].tolist())
            engine.index = build_index(engine.embeddings)
            import faiss
            np.save(str(embeddings_path), engine.embeddings)
            faiss.write_index(engine.index, str(index_path))
    else:
        print("Product dataset not found. Using fallback mock data.")
        from app import build_sample_dataframe
        df = build_sample_dataframe()
        df = clean_data(df)
        df = create_combined_text(df)
        engine.df = df
        engine.embeddings = generate_embeddings(df["combined_text"].tolist())
        engine.index = build_index(engine.embeddings)

    return engine


class APIHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ["/", "/health", "/api/health"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            response = {
                "status": "healthy",
                "service": "amazon-rec-engine-backend",
                "products_count": len(engine.df) if engine and engine.df is not None else 0,
            }
            self.wfile.write(json.dumps(response).encode("utf-8"))
            return

        if path in ["/analytics", "/api/analytics"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()

            df = engine.df
            cat_col = "category" if "category" in df.columns else ("main_category" if "main_category" in df.columns else None)
            category_counts = (
                df[cat_col].fillna("Unknown").value_counts().head(10).to_dict()
                if cat_col
                else {"All": len(df)}
            )

            title_col = "title" if "title" in df.columns else ("name" if "name" in df.columns else None)
            if "brand" in df.columns:
                brand_counts = df["brand"].fillna("Unknown").value_counts().head(8).to_dict()
            elif title_col:
                brand_counts = df[title_col].astype(str).str.split().str[0].fillna("Unknown").value_counts().head(8).to_dict()
            else:
                brand_counts = {}

            rating_col = "rating" if "rating" in df.columns else ("overall" if "overall" in df.columns else None)
            ratings = (
                df[rating_col].dropna().round(1).value_counts().sort_index().to_dict()
                if rating_col
                else {}
            )

            response = {
                "categories": category_counts,
                "top_brands": brand_counts,
                "ratings": {str(k): int(v) for k, v in ratings.items()},
                "total_products": len(df),
            }
            self.wfile.write(json.dumps(response).encode("utf-8"))
            return

        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"error": "Not Found"}).encode("utf-8"))

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ["/recommend", "/api/recommend"]:
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                payload = json.loads(body.decode("utf-8")) if body else {}

                query = payload.get("query", "").strip()
                user_type = payload.get("user_type", "general")
                top_k = int(payload.get("top_k", 5))

                if not query:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Query parameter cannot be empty"}).encode("utf-8"))
                    return

                recommendations = engine.recommend(
                    query=query,
                    user_type=user_type,
                    top_k=top_k,
                    log_path="logs/recommendation_logs.csv",
                )

                sanitized = []
                for p in recommendations:
                    item = {
                        "index": int(p.get("index", 0)),
                        "title": str(p.get("title", p.get("name", "Unknown Product"))),
                        "name": str(p.get("name", p.get("title", "Unknown Product"))),
                        "price": p.get("price"),
                        "rating": float(p.get("rating", 0.0)),
                        "popularity": float(p.get("popularity", 0.0)),
                        "category": str(p.get("main_category", p.get("category", ""))),
                        "sub_category": str(p.get("sub_category", "")),
                        "similarity": float(p.get("similarity", 0.0)),
                        "score": float(p.get("score", p.get("final_score", 0.0))),
                        "personalized_score": float(p.get("personalized_score", p.get("score", 0.0))),
                        "explanation": str(p.get("explanation", "")),
                    }
                    sanitized.append(item)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                response = {
                    "query": query,
                    "user_type": user_type,
                    "count": len(sanitized),
                    "recommendations": sanitized,
                }
                self.wfile.write(json.dumps(response).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"error": "Not Found"}).encode("utf-8"))


def run(port=8000):
    init_engine()
    server_address = ("", port)
    httpd = HTTPServer(server_address, APIHandler)
    print(f"Backend API server running at http://localhost:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    run(port=port)
