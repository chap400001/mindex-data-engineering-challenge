"""SQLite star-schema preparation and loading utilities."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd


REQUIRED_TRANSACTION_COLUMNS = {
    "transaction_id",
    "transaction_date",
    "store_id",
    "product_id",
    "quantity",
    "unit_price",
}


def connect(database_path: Path) -> sqlite3.Connection:
    """Create a SQLite connection with foreign-key enforcement enabled."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_schema(connection: sqlite3.Connection) -> None:
    """Drop and recreate the dimensional warehouse tables."""
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

        CREATE INDEX idx_fact_sales_date_key ON fact_sales(date_key);
        CREATE INDEX idx_fact_sales_store_key ON fact_sales(store_key);
        CREATE INDEX idx_fact_sales_product_key ON fact_sales(product_key);
        CREATE INDEX idx_fact_sales_customer_id ON fact_sales(customer_id);
        """
    )
    connection.commit()


def _require_columns(dataframe: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required.difference(dataframe.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {', '.join(missing)}")


def build_date_dimension(transactions: pd.DataFrame) -> pd.DataFrame:
    """Build one calendar row for every date in the transaction window."""
    _require_columns(transactions, {"transaction_date"}, "transactions")

    valid_dates = pd.to_datetime(transactions["transaction_date"], errors="coerce").dropna()
    if valid_dates.empty:
        raise ValueError("No valid transaction dates are available for dim_date")

    date_range = pd.date_range(valid_dates.min().normalize(), valid_dates.max().normalize())
    return pd.DataFrame(
        {
            "date_key": date_range.strftime("%Y%m%d").astype(int),
            "full_date": date_range.strftime("%Y-%m-%d"),
            "year": date_range.year,
            "month": date_range.month,
            "month_name": date_range.strftime("%B"),
            "quarter": date_range.quarter,
            "day_of_month": date_range.day,
            # SQLite strftime uses Sunday=0. This uses Monday=1 through Sunday=7.
            "day_of_week": date_range.dayofweek + 1,
            "day_name": date_range.strftime("%A"),
        }
    )


def build_store_dimension(stores: pd.DataFrame) -> pd.DataFrame:
    """Build a deterministic store dimension from the cleaned store reference data."""
    _require_columns(stores, {"store_id"}, "stores")

    columns = [column for column in ("store_id", "store_name", "region") if column in stores]
    dimension = stores[columns].dropna(subset=["store_id"]).drop_duplicates("store_id").copy()
    dimension = dimension.sort_values("store_id").reset_index(drop=True)
    dimension.insert(0, "store_key", range(1, len(dimension) + 1))

    for optional_column in ("store_name", "region"):
        if optional_column not in dimension:
            dimension[optional_column] = pd.NA

    return dimension[["store_key", "store_id", "store_name", "region"]]


def build_product_dimension(
    products: pd.DataFrame,
    transactions: pd.DataFrame,
) -> pd.DataFrame:
    """Build the product dimension with the latest observed selling price.

    The most recent valid transaction price becomes current_list_price.
    Products without a valid transaction price retain their catalog price.
    Historical prices remain preserved in fact_sales.unit_price.
    """
    _require_columns(products, {"product_id"}, "products")
    _require_columns(
        transactions,
        {"product_id", "transaction_date", "unit_price"},
        "transactions",
    )

    price_column = next(
        (
            name
            for name in ("current_list_price", "list_price", "price")
            if name in products
        ),
        None,
    )

    columns = [
        column
        for column in ("product_id", "product_name", "category")
        if column in products
    ]

    if price_column:
        columns.append(price_column)

    dimension = (
        products[columns]
        .dropna(subset=["product_id"])
        .drop_duplicates("product_id", keep="first")
        .copy()
    )

    for optional_column in ("product_name", "category"):
        if optional_column not in dimension:
            dimension[optional_column] = pd.NA

    if price_column:
        dimension = dimension.rename(
            columns={price_column: "current_list_price"}
        )
        dimension["current_list_price"] = pd.to_numeric(
            dimension["current_list_price"],
            errors="coerce",
        )
    else:
        dimension["current_list_price"] = pd.NA

    observed_prices = transactions[
        ["product_id", "transaction_date", "unit_price"]
    ].copy()

    observed_prices["transaction_date"] = pd.to_datetime(
        observed_prices["transaction_date"],
        errors="coerce",
    )
    observed_prices["unit_price"] = pd.to_numeric(
        observed_prices["unit_price"],
        errors="coerce",
    )

    observed_prices = observed_prices.dropna(
        subset=["product_id", "transaction_date", "unit_price"]
    )

    latest_observed_prices = (
        observed_prices
        .sort_values(["transaction_date"])
        .drop_duplicates("product_id", keep="last")
        .set_index("product_id")["unit_price"]
    )

    dimension["current_list_price"] = (
        dimension["product_id"]
        .map(latest_observed_prices)
        .fillna(dimension["current_list_price"])
    )

    dimension = dimension.sort_values("product_id").reset_index(drop=True)
    dimension.insert(0, "product_key", range(1, len(dimension) + 1))

    return dimension[
        [
            "product_key",
            "product_id",
            "product_name",
            "category",
            "current_list_price",
        ]
    ]


def build_sales_fact(
    transactions: pd.DataFrame,
    dim_store: pd.DataFrame,
    dim_product: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Build fact_sales and report why unusable transaction rows were excluded.

    The source transaction amount is retained when available. Otherwise, the amount is
    calculated as quantity multiplied by unit price. Actual transaction unit price remains
    in the fact so historical price variation is preserved independently of catalog price.
    """
    _require_columns(transactions, REQUIRED_TRANSACTION_COLUMNS, "transactions")

    working = transactions.copy()
    starting_rows = len(working)

    duplicate_id_mask = working["transaction_id"].duplicated(keep="first")
    duplicate_transaction_ids = int(duplicate_id_mask.sum())
    working = working.loc[~duplicate_id_mask].copy()

    working["transaction_date"] = pd.to_datetime(
        working["transaction_date"], errors="coerce"
    )
    invalid_date_mask = working["transaction_date"].isna()
    invalid_dates = int(invalid_date_mask.sum())
    working = working.loc[~invalid_date_mask].copy()

    working = working.merge(
        dim_store[["store_key", "store_id"]], on="store_id", how="left", validate="many_to_one"
    )
    unknown_store_mask = working["store_key"].isna()
    unknown_stores = int(unknown_store_mask.sum())
    working = working.loc[~unknown_store_mask].copy()

    working = working.merge(
        dim_product[["product_key", "product_id"]],
        on="product_id",
        how="left",
        validate="many_to_one",
    )
    unknown_product_mask = working["product_key"].isna()
    unknown_products = int(unknown_product_mask.sum())
    working = working.loc[~unknown_product_mask].copy()

    working["quantity"] = pd.to_numeric(working["quantity"], errors="coerce")
    working["unit_price"] = pd.to_numeric(working["unit_price"], errors="coerce")
    invalid_numeric_mask = working[["quantity", "unit_price"]].isna().any(axis=1)
    invalid_numeric_values = int(invalid_numeric_mask.sum())
    working = working.loc[~invalid_numeric_mask].copy()

    amount_column = next(
        (name for name in ("sales_amount", "total_amount") if name in working),
        None,
    )
    calculated_amount = working["quantity"] * working["unit_price"]
    if amount_column:
        source_amount = pd.to_numeric(working[amount_column], errors="coerce")
        working["sales_amount"] = source_amount.fillna(calculated_amount)
    else:
        working["sales_amount"] = calculated_amount

    working["date_key"] = working["transaction_date"].dt.strftime("%Y%m%d").astype(int)
    working["is_return"] = (
        (working["quantity"] < 0) | (working["sales_amount"] < 0)
    ).astype(int)

    if "customer_id" not in working:
        working["customer_id"] = pd.NA

    working = working.sort_values(["transaction_date", "transaction_id"]).reset_index(drop=True)
    working.insert(0, "sales_key", range(1, len(working) + 1))

    fact = working[
        [
            "sales_key",
            "transaction_id",
            "date_key",
            "store_key",
            "product_key",
            "customer_id",
            "quantity",
            "unit_price",
            "sales_amount",
            "is_return",
        ]
    ].copy()
    fact[["store_key", "product_key"]] = fact[["store_key", "product_key"]].astype(int)

    exclusions = {
        "source_rows": starting_rows,
        "duplicate_transaction_ids": duplicate_transaction_ids,
        "invalid_transaction_dates": invalid_dates,
        "unknown_store_ids": unknown_stores,
        "unknown_product_ids": unknown_products,
        "invalid_quantity_or_unit_price": invalid_numeric_values,
        "loaded_fact_rows": len(fact),
    }
    exclusions["excluded_rows"] = starting_rows - len(fact)
    return fact, exclusions


def load_dataframe(
    connection: sqlite3.Connection,
    dataframe: pd.DataFrame,
    table_name: str,
) -> None:
    """Append a prepared DataFrame to a warehouse table."""
    dataframe.to_sql(table_name, connection, if_exists="append", index=False)


def load_warehouse(
    database_path: Path,
    transactions: pd.DataFrame,
    stores: pd.DataFrame,
    products: pd.DataFrame,
) -> dict[str, Any]:
    """Create and populate the complete SQLite warehouse in one transaction."""
    dim_date = build_date_dimension(transactions)
    dim_store = build_store_dimension(stores)
    dim_product = build_product_dimension(products, transactions)
    fact_sales, exclusions = build_sales_fact(transactions,dim_store,dim_product,)

    with connect(database_path) as connection:
        create_schema(connection)
        load_dataframe(connection, dim_date, "dim_date")
        load_dataframe(connection, dim_store, "dim_store")
        load_dataframe(connection, dim_product, "dim_product")
        load_dataframe(connection, fact_sales, "fact_sales")

        foreign_key_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_violations:
            raise ValueError(f"Foreign-key validation failed: {foreign_key_violations}")

    return {
        "database_path": str(database_path),
        "table_row_counts": {
            "dim_date": len(dim_date),
            "dim_store": len(dim_store),
            "dim_product": len(dim_product),
            "fact_sales": len(fact_sales),
        },
        "transaction_exclusions": exclusions,
    }