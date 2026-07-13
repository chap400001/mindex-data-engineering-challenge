"""Reusable DataFrame profiling utilities."""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd


def _json_value(value: Any) -> Any:
    """Convert pandas/numpy values into JSON-serializable Python values."""
    if pd.isna(value):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp, date)):
        return value.isoformat()
    return value


def _looks_like_date(column_name: str, series: pd.Series) -> bool:
    """Identify likely date columns using dtype and conservative name heuristics."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    name = column_name.lower()
    return any(token in name for token in ("date", "timestamp", "_at", "time"))


def profile(df: pd.DataFrame, name: str) -> dict[str, Any]:
    """Return a JSON-ready data quality summary for a DataFrame."""
    row_count = len(df)
    report: dict[str, Any] = {
        "name": name,
        "row_count": row_count,
        "column_count": len(df.columns),
        "duplicate_row_count": int(df.duplicated().sum()),
        "columns": {},
    }

    today = pd.Timestamp.today().normalize()

    for column in df.columns:
        series = df[column]
        null_count = int(series.isna().sum())
        details: dict[str, Any] = {
            "dtype": str(series.dtype),
            "null_count": null_count,
            "null_percentage": round((null_count / row_count * 100), 2) if row_count else 0.0,
        }

        if pd.api.types.is_numeric_dtype(series):
            numeric = pd.to_numeric(series, errors="coerce")
            details["numeric"] = {
                "min": _json_value(numeric.min()),
                "max": _json_value(numeric.max()),
                "mean": _json_value(numeric.mean()),
                "zero_count": int((numeric == 0).sum()),
                "negative_count": int((numeric < 0).sum()),
            }

        if _looks_like_date(column, series):
            parsed = pd.to_datetime(series, errors="coerce")
            valid = parsed.dropna()
            details["date"] = {
                "valid_date_count": int(valid.size),
                "invalid_date_count": int(series.notna().sum() - valid.size),
                "min_date": _json_value(valid.min()) if not valid.empty else None,
                "max_date": _json_value(valid.max()) if not valid.empty else None,
                "future_date_count": int((valid.dt.normalize() > today).sum()) if not valid.empty else 0,
            }

        report["columns"][column] = details

    return report
