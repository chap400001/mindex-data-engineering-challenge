import pandas as pd
from src.cleaner import (
    apply_base_cleaning,
    normalize_column_names,
    parse_currency,
    parse_mixed_dates,
)


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


def test_parse_mixed_dates():
    source = pd.Series(
        [
            "2026-03-05",
            "03/19/2026",
            "24-03-2026",
            "not-a-date",
        ]
    )

    result = parse_mixed_dates(source)

    assert result.iloc[0] == pd.Timestamp("2026-03-05")
    assert result.iloc[1] == pd.Timestamp("2026-03-19")
    assert result.iloc[2] == pd.Timestamp("2026-03-24")
    assert pd.isna(result.iloc[3])


def test_parse_currency():
    source = pd.Series(["$615.85", "781.36", "1,185.40", "", None])

    result = parse_currency(source)

    assert result.iloc[0] == 615.85
    assert result.iloc[1] == 781.36
    assert result.iloc[2] == 1185.40
    assert pd.isna(result.iloc[3])
    assert pd.isna(result.iloc[4])    