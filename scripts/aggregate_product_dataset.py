from pathlib import Path
import pandas as pd

from src.preprocessing import aggregate_product_reviews, clean_data


def main():
    raw_data_path = Path("data/processed/unified_dataset.csv")
    product_data_path = Path("data/processed/product_dataset.csv")

    if not raw_data_path.exists():
        raise FileNotFoundError(
            f"Raw unified dataset not found at {raw_data_path}. "
            "Please generate or place the review-level dataset at this path."
        )

    raw_df = pd.read_csv(raw_data_path)
    raw_df = clean_data(raw_df)
    product_df = aggregate_product_reviews(raw_df)
    product_data_path.parent.mkdir(parents=True, exist_ok=True)
    product_df.to_csv(product_data_path, index=False)

    print(
        f"Aggregated {len(raw_df)} review rows into {len(product_df)} unique products."
    )
    print(f"Saved product-level dataset to {product_data_path}")


if __name__ == "__main__":
    main()
