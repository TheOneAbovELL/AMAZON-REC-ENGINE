"""Preprocessing utilities for Amazon product and user data."""

import pandas as pd


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean the raw dataset by handling missing values and duplicates."""
    df = df.copy()
    df.fillna("", inplace=True)
    df.drop_duplicates(inplace=True)
    return df


def create_combined_text(df: pd.DataFrame) -> pd.DataFrame:
    """Build a single text field from title, description, and category."""
    df = df.copy()
    df["combined_text"] = (
        df["title"].astype(str)
        + " "
        + df["description"].astype(str)
        + " "
        + df["category"].astype(str)
    )
    return df
