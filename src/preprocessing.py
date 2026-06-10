"""Preprocessing utilities for Amazon product and user data."""

import re
import pandas as pd


def clean_price(price):
    """Convert currency strings like '₹32,999' into clean float values."""
    if pd.isna(price):
        return 0.0

    # Remove currency symbols, commas, spaces, and any non-numeric characters except decimals
    cleaned = re.sub(r"[^\d.]", "", str(price).strip())
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean the raw dataset by handling missing values, types, and duplicates."""
    df = df.copy()

    # Drop explicit duplicates based on the user-product pairing
    if "reviewerID" in df.columns and "asin" in df.columns:
        df.drop_duplicates(subset=["reviewerID", "asin"], inplace=True)
    else:
        df.drop_duplicates(inplace=True)

    # Standardize string fields to prevent concatenation crashes
    text_cols = ["name", "main_category", "sub_category", "reviewText"]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    # Fix Prices using your clean_price helper
    if "discount_price" in df.columns:
        df["discount_price"] = df["discount_price"].apply(clean_price)
    if "actual_price" in df.columns:
        df["actual_price"] = df["actual_price"].apply(clean_price)

    # Map Recommendation Metrics
    if "overall" in df.columns:
        df["rating"] = pd.to_numeric(df["overall"], errors="coerce").fillna(0.0)

    if "no_of_ratings" in df.columns:
        # Strip commas out of strings like '1,250 ratings' if present, then convert to numeric
        cleaned_pop = (
            df["no_of_ratings"]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.extract(r"(\d+)")
        )
        df["popularity"] = pd.to_numeric(cleaned_pop[0], errors="coerce").fillna(
            0
        )
    else:
        df["popularity"] = 0

    return df


def aggregate_product_reviews(
    df: pd.DataFrame,
    max_reviews_per_product: int = 5,
) -> pd.DataFrame:
    """Aggregate review-level data into product-level product records."""
    df = df.copy()

    if "asin" not in df.columns:
        return df

    aggregation = {
        "name": "first",
        "main_category": "first",
        "sub_category": "first",
        "reviewText": lambda values: " ".join(
            values.astype(str).head(max_reviews_per_product)
        ),
        "overall": "mean",
        "no_of_ratings": "first",
        "discount_price": "first",
        "actual_price": "first",
    }

    available_columns = df.columns.tolist()
    aggregation = {
        key: agg
        for key, agg in aggregation.items()
        if key in available_columns
    }

    if "title" in available_columns:
        aggregation["title"] = "first"
    if "brand" in available_columns:
        aggregation["brand"] = "first"
    if "category" in available_columns and "main_category" not in available_columns:
        aggregation["category"] = "first"

    aggregated = (
        df.groupby("asin")
        .agg(aggregation)
        .reset_index()
    )

    return aggregated


def create_combined_text(df):
    df = df.copy()

    if "name" in df.columns:
        name = df["name"].fillna("").astype(str)
    else:
        name = df.get("title", "").astype(str)

    if "main_category" in df.columns:
        category = df["main_category"].fillna("").astype(str)
    else:
        category = df.get("category", "").astype(str)

    if "sub_category" in df.columns:
        subcategory = df["sub_category"].fillna("").astype(str)
    else:
        subcategory = ""

    if "reviewText" in df.columns:
        review = (
            df["reviewText"]
            .fillna("")
            .astype(str)
            .str[:300]
        )
    else:
        review = (
            df.get("description", "")
            .astype(str)
        )

    df["combined_text"] = (
        name
        + " "
        + category
        + " "
        + str(subcategory)
        + " "
        + review
    )

    return df
