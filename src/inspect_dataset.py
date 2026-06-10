import glob
import os
import re
import pandas as pd


def extract_asin(url):
    """Extracts a 10-character Amazon ASIN from product URLs."""
    if pd.isna(url) or not isinstance(url, str):
        return None
    patterns = [
        r"/dp/([A-Z0-9]{10})",
        r"/gp/product/([A-Z0-9]{10})",
        r"\b([A-Z0-9]{10})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return None


def main():
    print("=== 1. LOADING AND COMBINING CSV PRODUCT FILES ===")
    folder_path = "data/raw"
    all_csv_files = glob.glob(os.path.join(folder_path, "*.csv"))

    if not all_csv_files:
        print(" Error: No CSV files found in 'data/raw' folder.")
        return

    print(f"Found {len(all_csv_files)} CSV files. Merging files...")
    df_csv_list = [pd.read_csv(file) for file in all_csv_files]
    df_csv = pd.concat(df_csv_list, ignore_index=True)
    df_csv["asin"] = df_csv["link"].apply(extract_asin)

    # Drop products that didn't have a valid ASIN or are duplicate products
    df_csv = df_csv.dropna(subset=["asin"]).drop_duplicates(subset=["asin"])
    print(f"Unique Indian products available for matching: {len(df_csv)}")

    # Create a quick-lookup set of your Indian ASINs
    indian_asin_set = set(df_csv["asin"].unique())

    print("\n=== 2. STREAMING & FILTERING JSON REVIEWS ===")
    json_path = "data/raw/Electronics_5.json"

    matched_chunks = []
    chunk_size = 50000  # Reads 50,000 lines at a time to prevent crash
    total_processed = 0

    print("Scanning large JSON file for matches... Please wait...")
    # Read the JSON file line-by-line using chunks
    for chunk in pd.read_json(
        json_path, lines=True, chunksize=chunk_size, dtype={"asin": str}
    ):
        total_processed += len(chunk)

        # Standardize JSON ASINs to match CSV format
        chunk["asin"] = chunk["asin"].str.strip().str.upper()

        # ONLY keep rows that exist in your CSV set
        filtered_chunk = chunk[chunk["asin"].isin(indian_asin_set)]

        if not filtered_chunk.empty:
            matched_chunks.append(filtered_chunk)

        # Visual progress counter
        print(f"   Processed {total_processed:,} lines...", end="\r")

    print(f"\nFinished scanning JSON. Total lines evaluated: {total_processed:,}")

    if not matched_chunks:
        print(
            "\n Zero overlap found. The Electronics_5.json file has no overlapping products with your Indian CSV files."
        )
        return

    # Combine all the matched review rows
    df_json_matched = pd.concat(matched_chunks, ignore_index=True)
    print(
        f"Found {len(df_json_matched)} total reviews that match your product CSVs!"
    )

    print("\n=== 3. MERGING METADATA ===")
    # Inner join since we verified these exist in both datasets
    df = pd.merge(df_json_matched, df_csv, on="asin", how="inner")

    print("\n=== 4. FINAL UNIFIED DATASET INFO ===")
    print("Data Shape:", df.shape)
    print("Columns List:", df.columns.tolist())
    print("\nFirst 5 successfully matched rows:")
    print(df[["asin", "name", "overall", "reviewText"]].head())

    # Save merged dataset
    os.makedirs("data/processed", exist_ok=True)
    output_path = "data/processed/unified_dataset.csv"
    df.to_csv(
        output_path,
        index=False
        )
    print("\n=====================================")
    print("Unified dataset saved successfully!")
    print(f"Location: {output_path}")
    print("=====================================")

if __name__ == "__main__":
    main()
