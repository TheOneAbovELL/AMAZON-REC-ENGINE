from src.data_loader import load_data


def main():
    df = load_data("data/meta_Electronics.json")
    print(df.head())
    print(df.columns.tolist())


if __name__ == "__main__":
    main()
