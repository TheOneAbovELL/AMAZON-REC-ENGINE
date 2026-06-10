import pandas as pd

df = pd.read_csv(
    "data/processed/product_dataset.csv"
)

for col in [
    "name",
    "main_category",
    "sub_category",
    "reviewText"
]:
    print("\n")
    print(col)
    print(
        df[col]
        .isna()
        .mean()
    )