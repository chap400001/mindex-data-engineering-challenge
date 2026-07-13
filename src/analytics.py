"""Warehouse analytics queries."""

from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd


def query_records(connection: sqlite3.Connection, sql: str) -> list[dict[str, Any]]:
    """Execute SQL and return JSON-ready row dictionaries."""
    return pd.read_sql_query(sql, connection).to_dict(orient="records")


def top_stores_recent_30_days(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return the top five stores by net revenue in the latest 30-day data window."""
    sql = """
        WITH bounds AS (
            SELECT MAX(d.full_date) AS max_date
            FROM fact_sales f
            JOIN dim_date d ON d.date_key = f.date_key
        )
        SELECT
            s.store_id,
            s.store_name,
            ROUND(SUM(f.sales_amount), 2) AS net_revenue
        FROM fact_sales f
        JOIN dim_date d ON d.date_key = f.date_key
        JOIN dim_store s ON s.store_key = f.store_key
        CROSS JOIN bounds b
        WHERE d.full_date BETWEEN DATE(b.max_date, '-29 days') AND b.max_date
        GROUP BY s.store_id, s.store_name
        ORDER BY net_revenue DESC
        LIMIT 5
    """
    return query_records(connection, sql)
