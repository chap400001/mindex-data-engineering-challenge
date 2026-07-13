import sqlite3

from src.analytics import top_stores_recent_30_days
from src.loader import create_schema


def test_top_stores_recent_30_days_uses_net_revenue() -> None:
    connection = sqlite3.connect(":memory:")
    create_schema(connection)
    connection.executemany(
        "INSERT INTO dim_date VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (20260701, "2026-07-01", 2026, 7, "July", 3, 1, 3, "Wednesday"),
            (20260702, "2026-07-02", 2026, 7, "July", 3, 2, 4, "Thursday"),
        ],
    )
    connection.executemany(
        "INSERT INTO dim_store VALUES (?, ?, ?, ?)",
        [(1, "S1", "North", "East"), (2, "S2", "South", "South")],
    )
    connection.execute(
        "INSERT INTO dim_product VALUES (?, ?, ?, ?, ?)",
        (1, "P1", "Widget", "Tools", 10.0),
    )
    connection.executemany(
        "INSERT INTO fact_sales VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "T1", 20260701, 1, 1, "C1", 1, 100.0, 100.0, 0),
            (2, "T2", 20260702, 1, 1, "C1", -1, 20.0, -20.0, 1),
            (3, "T3", 20260702, 2, 1, "C2", 1, 50.0, 50.0, 0),
        ],
    )

    result = top_stores_recent_30_days(connection)

    assert result[0]["store_id"] == "S1"
    assert result[0]["net_revenue"] == 80.0
