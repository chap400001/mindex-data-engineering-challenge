"""End-to-end entry point for the Mindex code challenge."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

#from cleaner import apply_base_cleaning
from cleaner import apply_base_cleaning, clean_transactions

from profiler import profile
from loader import load_warehouse
from analytics import run_analytics
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUTPUT_DIR = ROOT / "output"
SOURCE_FILES = ("transactions.csv", "stores.csv", "products.csv")

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOGGER = logging.getLogger(__name__)


def read_sources() -> dict[str, pd.DataFrame]:
    """Read all required CSV exports without modifying the raw files."""
    missing = [filename for filename in SOURCE_FILES if not (RAW_DIR / filename).exists()]
    if missing:
        raise FileNotFoundError(
            "Missing source files in data/raw: " + ", ".join(missing) +
            ". Run scripts/seed_data.py from the original challenge package first."
        )
    return {
        Path(filename).stem: pd.read_csv(RAW_DIR / filename)
        for filename in SOURCE_FILES
    }


def write_json(payload: object, path: Path) -> None:
    """Write formatted JSON, creating the destination directory as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")


def main() -> None:
    """Profile sources and establish the cleaning-stage baseline."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Reading raw source files")
    sources = read_sources()

    LOGGER.info("Profiling source files")
    profiling_report = {
        name: profile(dataframe, name)
        for name, dataframe in sources.items()
    }
    write_json(profiling_report, OUTPUT_DIR / "profiling_report.json")

    LOGGER.info("Applying safe base normalization")
    cleaned = {
       "transactions": clean_transactions(sources["transactions"]),
        "stores": apply_base_cleaning(sources["stores"]),
        "products": apply_base_cleaning(sources["products"]),
    }

    for name, dataframe in cleaned.items():
        dataframe.to_csv(OUTPUT_DIR / f"{name}_cleaned_preview.csv", index=False)

    LOGGER.info("Building SQLite star schema")
    load_summary = load_warehouse(
        OUTPUT_DIR / "warehouse.db",
        cleaned["transactions"],
        cleaned["stores"],
        cleaned["products"],
    )
    write_json(load_summary, OUTPUT_DIR / "load_summary.json")

    LOGGER.info(
        "Warehouse complete: %s fact rows loaded",
        load_summary["table_row_counts"]["fact_sales"],
    )
    LOGGER.info("Running warehouse analytics")
    analytics_results = run_analytics(OUTPUT_DIR / "warehouse.db")

    write_json(
        analytics_results,
        OUTPUT_DIR / "analytics.json",
    )

    LOGGER.info("Analytics complete: output/analytics.json created")

if __name__ == "__main__":
    main()