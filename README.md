# Mindex Data Engineering / Data Architect Code Challenge

## Overview

This project implements an end-to-end data pipeline that profiles, cleans, models, and analyzes retail transaction data provided as CSV extracts.

The solution emphasizes modular design, data quality, reproducibility, and clear modeling decisions while remaining intentionally lightweight for the scope of the exercise.

The pipeline performs the following steps:

1. Read raw source files
2. Profile data quality
3. Apply reusable cleaning transformations
4. Load a SQLite star schema
5. Execute analytical queries
6. Produce JSON outputs for downstream consumption

---

# Architecture

```
                +------------------+
                | Raw CSV Files    |
                +------------------+
                         |
                         v
                +------------------+
                | profiler.py      |
                +------------------+
                         |
                         v
                +------------------+
                | cleaner.py       |
                +------------------+
                         |
                         v
                +------------------+
                | loader.py        |
                | SQLite Warehouse |
                +------------------+
                         |
                         v
                +------------------+
                | analytics.py     |
                +------------------+
                         |
                         v
                +------------------+
                | JSON Outputs     |
                +------------------+
```

---

# Project Structure

```
src/
    profiler.py
    cleaner.py
    loader.py
    analytics.py
    pipeline.py

tests/

data/raw/

output/
```

---

# Running the Project

Install dependencies

```bash
pip install -r requirements.txt
```

Run the pipeline

```bash
python src/pipeline.py
```

Run tests

```bash
python -m pytest -v
```

---

# Outputs

Running the pipeline produces:

```
output/

profiling_report.json
transactions_cleaned_preview.csv
stores_cleaned_preview.csv
products_cleaned_preview.csv

warehouse.db
load_summary.json
analytics.json
```

---

# Data Quality Findings

The pipeline profiles each source before applying any transformations. Profiling results are written to:

`output/profiling_report.json`

Cleaning transformations and warehouse loading decisions are summarized below.

| Issue                                           | File         | Count                   | Decision                                 | Rationale                             
|-------                                          |------        |------:                  |----------                                |-----------                            
| Leading/trailing whitespace                     | All          | All string columns      | Trimmed whitespace                       | Prevents inconsistent values caused by accidental spacing and improves joins and filtering. 
| Inconsistent column names                       | All          | All columns             | Normalized to snake_case                 | Provides a consistent naming convention throughout the pipeline and warehouse. 
| Multiple missing value representations          | All          | Variable                | Standardized to null                     | Ensures missing values are handled consistently during profiling, cleaning, and loading. 
| Mixed date formats                              | Transactions | Transaction date column | Parsed into a consistent datetime format | Enables reliable filtering, comparisons, and loading into the date dimension. 
| Currency formatting ($, commas, parentheses)    | Transactions | Currency columns        | Converted to numeric values              | Allows mathematical calculations and analytical queries. 
| Exact duplicate transaction rows                | Transactions | 15                      | Removed during cleaning                  | Exact duplicate records provide no additional business value and would otherwise double-count sales. 
| Unknown store references                        | Transactions | 5                       | Excluded during warehouse loading        | Fact rows without a matching store dimension would violate referential integrity. 
| Unknown product references                      | Transactions | 3                       | Excluded during warehouse loading        | Fact rows without a matching product dimension cannot be modeled correctly. 
| Duplicate transaction IDs                       | Transactions | 0                       | No action required                       | No duplicate business keys remained after the cleaning phase. 
| Invalid transaction dates                       | Transactions | 0                       | No action required                       | All remaining transaction dates were successfully parsed before loading. 
| Invalid quantity or unit price                  | Transactions | 0                       | No action required                       | All remaining numeric values required for loading were valid. 
| Negative quantities and sales amounts (returns) | Transactions | Retained                | Preserved using the `is_return` flag     | Returns represent valid business events and reduce net revenue rather than being discarded. 

## Pipeline Summary

The transaction data moved through the pipeline as follows:

| Stage                                                                | Transaction Count 
|-------                                                               |------------------:
| Raw source transactions                                              | 505               
| Exact duplicate rows removed during cleaning                         | 15 
| Transactions presented to warehouse loading                          | 490 
| Excluded during warehouse loading (unknown store/product references) | 8 
| Final fact records loaded                                            | 482 

A detailed summary of warehouse loading decisions is written to:

`output/load_summary.json`

---

# Warehouse Design

A simple star schema was implemented.

## Dimensions

### dim_date

Contains one row for every calendar date represented by the transaction data.

Attributes include:

- Year
- Month
- Quarter
- Day of Week

### dim_store

Contains one row per retail location.

### dim_product

Contains one row per product.

The `current_list_price` represents the most recently observed valid selling price for each product. If no transaction price exists, the original catalog price is retained.

Historical pricing is preserved in the fact table.

## Fact Table

### fact_sales

Contains one row per transaction.

Measures include:

- Quantity
- Unit Price
- Sales Amount

Returns are preserved as negative transactions and identified using an `is_return` flag.

---

# Modeling Decisions

## Products with Multiple Prices

Products may be sold at different prices over time because of promotions or price changes.

Rather than overwrite historical sales data, the warehouse stores:

- Current observed selling price in `dim_product`
- Actual transaction price in `fact_sales`

This preserves historical accuracy without introducing a Type 2 Slowly Changing Dimension, which would be unnecessary for the scope of this exercise.

---

## Returns

Returns remain in the warehouse.

They reduce revenue rather than being excluded.

This allows all analytical queries to report true net revenue.

---

## Excluded Records

Records are excluded only when they cannot be loaded into a relational model while maintaining referential integrity.

Examples include:

- Invalid transaction dates
- Missing dimension references
- Duplicate transaction identifiers

Counts for each exclusion are recorded in `load_summary.json`.

---

# Analytics

The pipeline executes five analytical queries against the SQLite warehouse.

1. Top five stores by net revenue during the latest 30-day reporting window.
2. Month-over-month revenue change by product category.
3. Return rate by store with stores exceeding a 10% threshold flagged.
4. Average transaction value by region excluding returns.
5. Top ten customers by lifetime spend excluding anonymous customers.

Results are written to:

```
output/analytics.json
```

---

# Testing

Eight pytest tests validate:

- Profiling logic
- Cleaning transformations
- Duplicate handling
- Date parsing
- Currency parsing
- Warehouse analytics

---

# Production Considerations

For a production implementation I would likely:

- Orchestrate the pipeline using Airflow, Prefect, or Dagster.
- Implement incremental rather than full-refresh loads.
- Add schema validation using Great Expectations or Pandera.
- Introduce structured logging and centralized monitoring.
- Store warehouse data in Snowflake rather than SQLite.
- Add CI/CD with GitHub Actions.
- Add data lineage and operational metrics.

---

# Tradeoffs

The goal of this exercise was to build a clean, understandable solution rather than a production-scale platform.

I intentionally kept the implementation lightweight while emphasizing:

- modular code
- reusable transformations
- documented decisions
- testability
- maintainability
