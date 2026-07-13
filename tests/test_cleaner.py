import pandas as pd

from src.cleaner import apply_base_cleaning, normalize_column_names


def test_normalize_column_names() -> None:
    dataframe = pd.DataFrame(columns=[" Store ID ", "Product-Name"])

    result = normalize_column_names(dataframe)

    assert list(result.columns) == ["store_id", "product_name"]


def test_base_cleaning_trims_and_standardizes_missing_strings() -> None:
    dataframe = pd.DataFrame({" Customer ": ["  C-100  ", "N/A", None]})

    result = apply_base_cleaning(dataframe)

    assert result.loc[0, "customer"] == "C-100"
    assert pd.isna(result.loc[1, "customer"])
    assert pd.isna(result.loc[2, "customer"])
