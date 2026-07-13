import pandas as pd

from src.profiler import profile


def test_profile_numeric_quality_metrics() -> None:
    dataframe = pd.DataFrame({"amount": [10, 0, -5, None]})

    result = profile(dataframe, "sales")

    assert result["row_count"] == 4
    assert result["columns"]["amount"]["null_count"] == 1
    assert result["columns"]["amount"]["numeric"]["zero_count"] == 1
    assert result["columns"]["amount"]["numeric"]["negative_count"] == 1


def test_profile_empty_dataframe_and_all_null_column() -> None:
    dataframe = pd.DataFrame({"empty_value": pd.Series(dtype="object")})

    result = profile(dataframe, "empty")

    assert result["row_count"] == 0
    assert result["column_count"] == 1
    assert result["columns"]["empty_value"]["null_percentage"] == 0.0
