"""Generate the demo dataset: synthetic retail orders with realistic mess (case variants, missing values, duplicates)."""
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
n = 3000
# order dates with seasonality: Nov/Dec are busier. Draw extra candidates, keep with month-dependent probability.
cand = pd.to_datetime("2023-01-01") + pd.to_timedelta(rng.integers(0, 910, n * 3), unit="D")
keep = rng.random(len(cand)) < np.where(cand.month.isin([11, 12]), 1.0, 0.5)
dates = cand[keep][:n]
n = len(dates)

category = rng.choice(["Technology", "Furniture", "Office Supplies"], n, p=[0.25, 0.3, 0.45])
base = pd.Series(category).map({"Technology": 420, "Furniture": 260, "Office Supplies": 35}).to_numpy()
price = (base * rng.lognormal(0, 0.35, n)).round(2)
quantity = rng.poisson(2.2, n).clip(1, 12)
discount = rng.choice([0, 0.1, 0.2, 0.3], n, p=[0.5, 0.25, 0.15, 0.1])
revenue = (price * quantity * (1 - discount)).round(2)
margin = pd.Series(category).map({"Technology": 0.22, "Furniture": 0.12, "Office Supplies": 0.3}).to_numpy()
profit = (revenue * margin - revenue * discount * 0.6 + rng.normal(0, 8, n)).round(2)
region = rng.choice(["North", "South", "East", "West"], n, p=[0.3, 0.2, 0.25, 0.25])
shipping = (2 + (region == "South") * 2 + rng.poisson(2, n)).astype(float)

df = pd.DataFrame({
    "order_id": np.arange(10001, 10001 + n),
    "order_date": dates.strftime("%Y-%m-%d"),
    "region": region, "category": category,
    "unit_price": price, "quantity": quantity, "discount": discount,
    "revenue": revenue, "profit": profit, "shipping_days": shipping,
})
df.loc[rng.choice(n, int(n * 0.04), replace=False), "shipping_days"] = np.nan       # missing values
messy = rng.choice(n, int(n * 0.03), replace=False)                                   # inconsistent categories
df.loc[messy, "region"] = df.loc[messy, "region"].str.lower() + " "
df = pd.concat([df, df.sample(15, random_state=1)], ignore_index=True)                # duplicates
df.to_csv("sample_data/retail_sales.csv", index=False)
print(df.shape)
