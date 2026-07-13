"""Source-specific cleaning transformations.

The exact rules should be finalized after profiling the generated CSV files.
"""

from __future__ import annotations

import pandas as pd


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with trimmed, lowercase snake_case column names."""
    cleaned = df.copy()
    cleaned.columns = (
        cleaned.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"[^a-z0-9]+", "_", regex=True)
        .str.strip("_")
    )
    return cleaned


def trim_string_values(df: pd.DataFrame) -> pd.DataFrame:
    """Trim surrounding whitespace while preserving missing values."""
    cleaned = df.copy()
    for column in cleaned.select_dtypes(include=["object", "string"]).columns:
        cleaned[column] = cleaned[column].map(
            lambda value: value.strip() if isinstance(value, str) else value
        )
    return cleaned


def standardize_missing_strings(df: pd.DataFrame) -> pd.DataFrame:
    """Convert common textual missing-value markers to pandas NA."""
    cleaned = df.copy()
    missing_markers = {"": pd.NA, "null": pd.NA, "none": pd.NA, "n/a": pd.NA, "na": pd.NA}
    for column in cleaned.select_dtypes(include=["object", "string"]).columns:
        cleaned[column] = cleaned[column].map(
            lambda value: missing_markers.get(value.lower(), value)
            if isinstance(value, str)
            else value
        )
    return cleaned


def apply_base_cleaning(df: pd.DataFrame) -> pd.DataFrame:
    """Apply safe, source-agnostic normalization before business rules."""
    return standardize_missing_strings(trim_string_values(normalize_column_names(df)))

def parse_mixed_dates(series: pd.Series) -> pd.Series:
    """Parse known transaction date formats into normalized pandas dates."""
    parsed = pd.to_datetime(series, format="%Y-%m-%d", errors="coerce")

    unresolved = parsed.isna() & series.notna()
    parsed.loc[unresolved] = pd.to_datetime(
        series.loc[unresolved],
        format="%m/%d/%Y",
        errors="coerce",
    )

    unresolved = parsed.isna() & series.notna()
    parsed.loc[unresolved] = pd.to_datetime(
        series.loc[unresolved],
        format="%d-%m-%Y",
        errors="coerce",
    )

    return parsed


def clean_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Apply transaction-specific cleaning rules discovered during profiling."""
    cleaned = apply_base_cleaning(df)

    cleaned["transaction_date"] = parse_mixed_dates(cleaned["transaction_date"])
    cleaned["total_amount"] = parse_currency(cleaned["total_amount"])

    return cleaned

def parse_currency(series: pd.Series) -> pd.Series:
    """Convert currency-like text values into numeric amounts."""
    normalized = (
        series.astype("string")
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
    )

    return pd.to_numeric(normalized, errors="coerce")