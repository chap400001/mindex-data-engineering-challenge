# Mindex Data Engineer / Data Architect Code Challenge

## Status

Initial project scaffold. The source-specific cleaning, dimensional mappings, and final analytics will be completed after profiling the generated raw CSV files.

## Architecture

```text
data/raw/*.csv
      |
      v
src/profiler.py ----------> output/profiling_report.json
      |
      v
src/cleaner.py
      |
      v
src/loader.py ------------> output/warehouse.db
      |
      v
src/analytics.py ---------> output/analytics.json
```

## Setup

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Generate the challenge data using the supplied script:

```powershell
python scripts/seed_data.py
```

Run the pipeline and tests:

```powershell
python src/pipeline.py
pytest tests/ -v
```

## Data Quality Findings

Complete this table from the profiling output and cleaning audit counts.

| Issue | File | Count | Decision | Rationale |
|---|---|---:|---|---|
| Pending source profiling | — | — | — | Raw CSV files have not yet been generated in this scaffold. |

## Schema Design

The target is a star schema containing `dim_date`, `dim_store`, `dim_product`, and `fact_sales`.

Key preliminary decisions:

- Store actual transaction price in `fact_sales`; a product's price can change over time and is therefore transactional rather than a stable product attribute.
- Preserve returns as negative facts so they reduce net revenue.
- Retain anonymous sales for store/product analytics, but exclude them only from customer-specific analytics.
- Reject or quarantine facts whose required store, product, or transaction date cannot be resolved rather than silently assigning incorrect dimension keys.

## Analytics Approach

SQL will be used for final analytics because the modeled warehouse is the system of record, the queries remain independently testable, and the approach mirrors production warehouse usage.

## Productionization

A production implementation would use orchestrated, idempotent incremental loads; landing and quarantine zones; schema and freshness checks; data-quality assertions; structured logging and metrics; alerting; secrets management; CI/CD; and warehouse-native transformations such as dbt on Snowflake.

## With More Time

- Add source-to-target contracts and explicit schemas.
- Add row-level rejection reporting and audit totals.
- Add reconciliation tests between source, clean, rejected, and loaded record counts.
- Add indexes and query-plan review for larger volumes.
- Add CI automation for linting, tests, and end-to-end execution.
