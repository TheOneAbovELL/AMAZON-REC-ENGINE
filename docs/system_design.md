# System Design

This document explains high-level design decisions for the Amazon-Style Recommendation Engine and why we selected key components.

## Components

- Embeddings: Sentence Transformers (all-MiniLM-L6-v2)
- Vector Search: FAISS (IndexFlatL2)
- Two-stage Retrieval: FAISS candidate retrieval + multi-signal ranking
- Personalization: lightweight rule-based preference boosts
- Explainability: LLM-generated human-readable explanations

## Why Embeddings?
Embeddings capture semantic relationships between text that go beyond keyword overlap. They allow the system to retrieve products that are conceptually relevant to a query even when exact keywords are missing.

## Why FAISS?
FAISS is optimized for fast approximate nearest-neighbor search in high-dimensional embedding spaces. It provides high-throughput retrieval for production-style candidate generation and integrates well with NumPy arrays and persisted index files.

## Why Two-Stage Retrieval + Ranking?
Ranking every product for every query is computationally expensive. The two-stage approach retrieves a small set of likely candidates using vector search, then applies a richer, computationally heavier ranking model to those candidates. This balances latency and quality.

## Why Personalization?
Different users have different needs and priorities (e.g., gamers favor GPUs and refresh rates, students value portability and battery life). Personalization applies lightweight boosts to better match candidate ordering to user preferences.

## Why LLM Explanations?
LLM-based explanations turn model signals into human-readable rationales that improve trust and interpretability. They summarize why a product matched the query and highlight features relevant to the user's intent.

## Extensions and Future Work
- Learning-to-rank: replace heuristic scoring with a supervised model trained on interaction logs (clicks, purchases, dwell time). Popular choices: LambdaMART, LightGBM Ranker, XGBoost Ranker.
- Collaborative filtering: augment content signals with user-item interaction embeddings.
- Online evaluation: A/B tests and interleaving for live metric monitoring.

## Reviewer Q&A (short answers)

Q: Why use FAISS instead of SQL?
A: SQL is optimized for structured queries and exact matching over relational data. FAISS is designed for high-dimensional nearest-neighbor search and is much faster and more accurate for embedding-based semantic search.

Q: Why not rank all products directly?
A: Ranking all products per query is costly. Retrieval narrows candidates to a manageable set, enabling more complex ranking features without excessive latency.

Q: Why embeddings?
A: They capture semantic meaning and allow generalization beyond keyword overlap.

Q: Why personalization?
A: It tailors recommendations to user preferences, increasing relevance and satisfaction.

Q: What would you improve next?
A: Incorporate learning-to-rank, collaborative filtering, implicit feedback, and an online evaluation setup.
