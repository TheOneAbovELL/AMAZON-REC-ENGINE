"""Load and validate data for the recommendation engine."""

import pandas as pd


def load_data(filepath: str) -> pd.DataFrame:
    """Load a dataset from CSV or line-delimited JSON."""
    if str(filepath).endswith(".csv"):
        return pd.read_csv(filepath)
    return pd.read_json(filepath, lines=True)
