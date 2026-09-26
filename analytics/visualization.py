import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

sns.set_theme(style="whitegrid")


def plot_category_distribution(df: pd.DataFrame, top_n: int = 8):
    cat_col = "category" if "category" in df.columns else ("main_category" if "main_category" in df.columns else None)
    if cat_col:
        counts = df[cat_col].fillna("Unknown").value_counts().head(top_n).reset_index()
        counts.columns = ["category", "count"]
    else:
        counts = pd.DataFrame([{"category": "All Products", "count": len(df)}])
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.barplot(data=counts, x="count", y="category", palette="muted", ax=ax)
    ax.set_title("Product Category Distribution")
    ax.set_xlabel("Count")
    ax.set_ylabel("Category")
    plt.tight_layout()
    return fig


def plot_top_brands(df: pd.DataFrame, top_n: int = 8):
    brands = df.get("brand") if "brand" in df.columns else None
    if brands is None:
        title_col = "title" if "title" in df.columns else ("name" if "name" in df.columns else None)
        if title_col:
            brands = df[title_col].astype(str).str.split().str[0].fillna("Unknown")
        else:
            brands = pd.Series(["Unknown"] * len(df))
    counts = brands.value_counts().head(top_n).reset_index()
    counts.columns = ["brand", "count"]
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.barplot(data=counts, x="count", y="brand", palette="deep", ax=ax)
    ax.set_title("Top Brands")
    ax.set_xlabel("Count")
    ax.set_ylabel("Brand")
    plt.tight_layout()
    return fig


def plot_rating_distribution(df: pd.DataFrame):
    rating_col = "rating" if "rating" in df.columns else ("overall" if "overall" in df.columns else None)
    ratings = df[rating_col].dropna() if rating_col else pd.Series([4.0] * len(df))
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.histplot(ratings, bins=10, kde=False, color="#5A9", ax=ax)
    ax.set_title("Rating Distribution")
    ax.set_xlabel("Rating")
    ax.set_ylabel("Count")
    plt.tight_layout()
    return fig


def plot_score_distribution(recommendations):
    if not recommendations:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No recommendations yet", ha="center", va="center")
        ax.axis("off")
        return fig
    scores = [item.get("score", 0.0) for item in recommendations]
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.histplot(scores, bins=min(10, len(scores)), kde=False, color="#4676FF", ax=ax)
    ax.set_title("Recommendation Score Distribution")
    ax.set_xlabel("Score")
    ax.set_ylabel("Count")
    plt.tight_layout()
    return fig
