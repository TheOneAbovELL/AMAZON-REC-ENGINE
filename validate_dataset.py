import pandas as pd

df = pd.read_csv(
    "data/processed/product_dataset.csv"
)

print("=" * 50)
print("TOTAL PRODUCTS")
print("=" * 50)

print(len(df))

print("\n")

print("=" * 50)
print("TOP CATEGORIES")
print("=" * 50)

print(df["main_category"].value_counts().head(20))

print("\n")

print("=" * 50)
print("SAMPLE PRODUCTS")
print("=" * 50)

print(df[["name", "main_category"]].sample(20))