"""Analytical queries for the SQLite retail warehouse."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd


def top_stores_recent_30_days_from_dataframes(
    transactions: pd.DataFrame,
    stores: pd.DataFrame,
    limit: int = 5,
) -> pd.DataFrame:
    """Return top stores by net revenue in the latest 30-day data window.

    This pandas implementation is retained for focused unit testing. The final
    pipeline analytics are executed against the SQLite warehouse below.
    """
    working = transactions.copy()
    working["transaction_date"] = pd.to_datetime(
        working["transaction_date"], errors="coerce"
    )
    working["sales_amount"] = pd.to_numeric(
        working["sales_amount"], errors="coerce"
    )
    working = working.dropna(subset=["transaction_date", "sales_amount", "store_id"])

    if working.empty:
        return pd.DataFrame(columns=["store_id", "store_name", "net_revenue"])

    latest_date = working["transaction_date"].max().normalize()
    window_start = latest_date - pd.Timedelta(days=29)
    recent = working.loc[working["transaction_date"] >= window_start]

    result = (
        recent.groupby("store_id", as_index=False)["sales_amount"]
        .sum()
        .rename(columns={"sales_amount": "net_revenue"})
        .merge(stores[["store_id", "store_name"]], on="store_id", how="left")
        .sort_values(["net_revenue", "store_id"], ascending=[False, True])
        .head(limit)
    )
    return result[["store_id", "store_name", "net_revenue"]].reset_index(drop=True)


def _query(connection: sqlite3.Connection, sql: str) -> list[dict[str, Any]]:
    """Execute a query and return JSON-ready dictionaries."""
    cursor = connection.execute(sql)
    column_names = [description[0] for description in cursor.description]
    return [dict(zip(column_names, row)) for row in cursor.fetchall()]


def top_stores_recent_30_days(
    connection: sqlite3.Connection,
) -> list[dict[str, Any]]:
    """Return the five stores with the highest net revenue in the latest 30 days."""
    return _query(
        connection,
        """
        WITH reporting_window AS (
            SELECT
                date(MAX(d.full_date), '-29 days') AS start_date,
                MAX(d.full_date) AS end_date
            FROM fact_sales AS f
            JOIN dim_date AS d ON d.date_key = f.date_key
        )
        SELECT
            s.store_id,
            s.store_name,
            s.region,
            ROUND(SUM(f.sales_amount), 2) AS net_revenue
        FROM fact_sales AS f
        JOIN dim_date AS d ON d.date_key = f.date_key
        JOIN dim_store AS s ON s.store_key = f.store_key
        CROSS JOIN reporting_window AS w
        WHERE d.full_date BETWEEN w.start_date AND w.end_date
        GROUP BY s.store_id, s.store_name, s.region
        ORDER BY net_revenue DESC, s.store_id
        LIMIT 5
        """,
    )


def query_month_over_month_revenue_by_category(
    connection: sqlite3.Connection,
) -> list[dict[str, Any]]:
    """Return monthly net revenue and month-over-month change by product category."""
    return _query(
        connection,
        """
        WITH monthly_revenue AS (
            SELECT
                p.category,
                strftime('%Y-%m', d.full_date) AS revenue_month,
                SUM(f.sales_amount) AS net_revenue
            FROM fact_sales AS f
            JOIN dim_date AS d ON d.date_key = f.date_key
            JOIN dim_product AS p ON p.product_key = f.product_key
            GROUP BY p.category, strftime('%Y-%m', d.full_date)
        ),
        with_prior_month AS (
            SELECT
                category,
                revenue_month,
                net_revenue,
                LAG(net_revenue) OVER (
                    PARTITION BY category
                    ORDER BY revenue_month
                ) AS prior_month_revenue
            FROM monthly_revenue
        )
        SELECT
            category,
            revenue_month,
            ROUND(net_revenue, 2) AS net_revenue,
            ROUND(prior_month_revenue, 2) AS prior_month_revenue,
            CASE
                WHEN prior_month_revenue IS NULL OR prior_month_revenue = 0 THEN NULL
                ELSE ROUND(
                    (net_revenue - prior_month_revenue)
                    * 100.0 / prior_month_revenue,
                    2
                )
            END AS month_over_month_change_pct
        FROM with_prior_month
        ORDER BY category, revenue_month
        """,
    )


def query_return_rate_by_store(
    connection: sqlite3.Connection,
) -> list[dict[str, Any]]:
    """Return transaction-based return rates and flag rates over ten percent."""
    return _query(
        connection,
        """
        SELECT
            s.store_id,
            s.store_name,
            COUNT(*) AS total_transactions,
            SUM(f.is_return) AS return_transactions,
            ROUND(SUM(f.is_return) * 100.0 / COUNT(*), 2) AS return_rate_pct,
            CASE
                WHEN SUM(f.is_return) * 1.0 / COUNT(*) > 0.10 THEN 1
                ELSE 0
            END AS exceeds_10_percent
        FROM fact_sales AS f
        JOIN dim_store AS s ON s.store_key = f.store_key
        GROUP BY s.store_id, s.store_name
        ORDER BY return_rate_pct DESC, s.store_id
        """,
    )


def query_average_transaction_value_by_region(
    connection: sqlite3.Connection,
) -> list[dict[str, Any]]:
    """Return average non-return transaction value by store region."""
    return _query(
        connection,
        """
        SELECT
            s.region,
            COUNT(*) AS transaction_count,
            ROUND(AVG(f.sales_amount), 2) AS average_transaction_value
        FROM fact_sales AS f
        JOIN dim_store AS s ON s.store_key = f.store_key
        WHERE f.is_return = 0
        GROUP BY s.region
        ORDER BY average_transaction_value DESC, s.region
        """,
    )


def query_top_customers_by_lifetime_spend(
    connection: sqlite3.Connection,
) -> list[dict[str, Any]]:
    """Return the ten identified customers with the highest net lifetime spend."""
    return _query(
        connection,
        """
        SELECT
            TRIM(f.customer_id) AS customer_id,
            COUNT(*) AS transaction_count,
            ROUND(SUM(f.sales_amount), 2) AS lifetime_spend,
            ROUND(AVG(f.sales_amount), 2) AS average_order_value
        FROM fact_sales AS f
        WHERE f.customer_id IS NOT NULL
          AND TRIM(f.customer_id) <> ''
          AND LOWER(TRIM(f.customer_id)) NOT IN (
              'guest',
              'anonymous',
              'unknown',
              'n/a',
              'na',
              'none',
              'null'
          )
        GROUP BY TRIM(f.customer_id)
        ORDER BY lifetime_spend DESC, customer_id
        LIMIT 10
        """,
    )


def run_analytics(database_path: Path) -> dict[str, Any]:
    """Execute all required analytics against the populated SQLite warehouse."""
    if not database_path.exists():
        raise FileNotFoundError(f"Warehouse database not found: {database_path}")

    with sqlite3.connect(database_path) as connection:
        return {
            "top_5_stores_recent_30_days": top_stores_recent_30_days(connection),
            "month_over_month_revenue_by_category": (
                query_month_over_month_revenue_by_category(connection)
            ),
            "return_rate_by_store": query_return_rate_by_store(connection),
            "average_transaction_value_by_region": (
                query_average_transaction_value_by_region(connection)
            ),
            "top_10_customers_by_lifetime_spend": (
                query_top_customers_by_lifetime_spend(connection)
            ),
        }