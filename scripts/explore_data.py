from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"

transactions = pd.read_csv(RAW_DIR / "transactions.csv")
stores = pd.read_csv(RAW_DIR / "stores.csv")
products = pd.read_csv(RAW_DIR / "products.csv")


print("=" * 80)
print("Duplicate Transactions")
print("=" * 80)

duplicates = transactions[transactions.duplicated(keep=False)]
print(duplicates.sort_values("transaction_id"))


print("\n")
print("=" * 80)
print("Zero Quantity Transactions")
print("=" * 80)

print(transactions[transactions["quantity"] == 0])


print("\n")
print("=" * 80)
print("Negative Quantity Transactions")
print("=" * 80)

print(transactions[transactions["quantity"] < 0])


print("\n")
print("=" * 80)
print("Duplicate Stores")
print("=" * 80)

print(stores[stores.duplicated(subset=["store_id"], keep=False)])


print("\n")
print("=" * 80)
print("Duplicate Products")
print("=" * 80)

print(products[products.duplicated(subset=["product_id"], keep=False)])


# ============================================================
# ADD EVERYTHING BELOW THIS LINE
# ============================================================

print("\n")
print("=" * 80)
print("Transactions with Amount Mismatch")
print("=" * 80)

actual_total = pd.to_numeric(
    transactions["total_amount"]
    .astype(str)
    .str.replace("$", "", regex=False)
    .str.replace(",", "", regex=False),
    errors="coerce",
).round(2)

expected_total = (
    transactions["quantity"] * transactions["unit_price"]
).round(2)

mismatch = transactions[
    expected_total != actual_total
].copy()

mismatch["expected_total"] = expected_total[expected_total != actual_total]
mismatch["actual_total"] = actual_total[expected_total != actual_total]

if mismatch.empty:
    print("No mismatched transaction totals found.")
else:
    print(
        mismatch[
            [
                "transaction_id",
                "quantity",
                "unit_price",
                "total_amount",
                "expected_total",
                "actual_total",
            ]
        ].sort_values("transaction_id")
    )
    