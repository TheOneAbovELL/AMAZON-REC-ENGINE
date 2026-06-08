"""Load and validate data for the recommendation engine."""

import pandas as pd


def load_data(filepath: str) -> pd.DataFrame:
    """Load a line-delimited JSON dataset from the given filepath."""
    return pd.read_json(filepath, lines=True)
