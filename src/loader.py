"""SQLite warehouse loading utilities."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


def connect(database_path: Path) -> sqlite3.Connection:
    """Create a SQLite connection with foreign-key enforcement enabled."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_schema(connection: sqlite3.Connection) -> None:
    """Create the dimensional warehouse tables.

    Column mappings will be finalized after the source schemas are inspected.
    """
    connection.executescript(
        """
        DROP TABLE IF EXISTS fact_sales;
        DROP TABLE IF EXISTS dim_product;
        DROP TABLE IF EXISTS dim_store;
        DROP TABLE IF EXISTS dim_date;

        CREATE TABLE dim_date (
            date_key INTEGER PRIMARY KEY,
            full_date TEXT NOT NULL UNIQUE,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            month_name TEXT NOT NULL,
            quarter INTEGER NOT NULL,
            day_of_month INTEGER NOT NULL,
            day_of_week INTEGER NOT NULL,
            day_name TEXT NOT NULL
        );

        CREATE TABLE dim_store (
            store_key INTEGER PRIMARY KEY,
            store_id TEXT NOT NULL UNIQUE,
            store_name TEXT,
            region TEXT
        );

        CREATE TABLE dim_product (
            product_key INTEGER PRIMARY KEY,
            product_id TEXT NOT NULL UNIQUE,
            product_name TEXT,
            category TEXT,
            current_list_price REAL
        );

        CREATE TABLE fact_sales (
            sales_key INTEGER PRIMARY KEY,
            transaction_id TEXT NOT NULL UNIQUE,
            date_key INTEGER NOT NULL,
            store_key INTEGER NOT NULL,
            product_key INTEGER NOT NULL,
            customer_id TEXT,
            quantity REAL NOT NULL,
            unit_price REAL NOT NULL,
            sales_amount REAL NOT NULL,
            is_return INTEGER NOT NULL CHECK (is_return IN (0, 1)),
            FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
            FOREIGN KEY (store_key) REFERENCES dim_store(store_key),
            FOREIGN KEY (product_key) REFERENCES dim_product(product_key)
        );
        """
    )
    connection.commit()


def load_dataframe(
    connection: sqlite3.Connection,
    dataframe: pd.DataFrame,
    table_name: str,
) -> None:
    """Append a prepared DataFrame to a warehouse table."""
    dataframe.to_sql(table_name, connection, if_exists="append", index=False)
