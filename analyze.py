import pandas as pd
import numpy as np
import os

print("=" * 50)
print("   SALES DATA ANALYSIS")
print("=" * 50)

# ── 1. LOAD FROM MOUNTED PATH ─────────────────
path = "/app/data/sales.csv"

if not os.path.exists(path):
    print(f"File not found at {path}")
    print("   Make sure you mounted the data folder!")
    exit(1)

df = pd.read_csv(path)
print(f"\nLoaded {len(df)} rows from {path}")

# ── 2. BASIC STATS ────────────────────────────
print(f"\nDataset Preview:")
print(df.to_string(index=False))

print(f"\nTotal Revenue : ₹{(df['quantity'] * df['price']).sum():,.0f}")
print(f"Total Orders  : {len(df)}")
print(f" Cities        : {df['city'].nunique()}")

# ── 3. REVENUE BY CATEGORY ────────────────────
df["revenue"] = df["quantity"] * df["price"]
cat_summary = df.groupby("category")["revenue"].sum().sort_values(ascending=False)

print(f"\nRevenue by Category:")
for cat, rev in cat_summary.items():
    bar = "█" * int(rev / 5000)
    print(f"   {cat:<15} ₹{rev:>10,.0f}  {bar}")

# ── 4. TOP CITY ───────────────────────────────
city_summary = df.groupby("city")["revenue"].sum().sort_values(ascending=False)
print(f"\nTop City: {city_summary.index[0]} — ₹{city_summary.iloc[0]:,.0f}")

# ── 5. SAVE OUTPUT ────────────────────────────
out_path = "/app/outputs/summary.csv"
summary = df.groupby("category").agg(
    total_orders=("order_id", "count"),
    total_revenue=("revenue", "sum"),
    avg_price=("price", "mean")
).reset_index()

summary.to_csv(out_path, index=False)
print(f"\nSummary saved to {out_path}")
print("=" * 50)
