import pandas as pd

df = pd.read_csv(
    "data/processed/product_dataset.csv"
)

print(
    "Laptop:",
    df["name"].str.contains(
        "laptop",
        case=False,
        na=False
    ).sum()
)

print(
    "Gaming:",
    df["name"].str.contains(
        "gaming",
        case=False,
        na=False
    ).sum()
)

print(
    "Monitor:",
    df["name"].str.contains(
        "monitor",
        case=False,
        na=False
    ).sum()
)

print(
    "Keyboard:",
    df["name"].str.contains(
        "keyboard",
        case=False,
        na=False
    ).sum()
)