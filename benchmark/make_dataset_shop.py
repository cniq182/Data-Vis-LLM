"""Generate the second synthetic benchmark dataset: orders of a fictional online shop.

A different domain from bikes.csv, to test whether the system works beyond
trip-like data. Same ideas: no LLM has seen it, traps on purpose, fixed seed.

Traps:
- "items sold" (sum of quantity) vs revenue (sum of total): Clothing wins on
  items, Electronics wins on revenue.
- two years of dates (month vs yearmonth) and a Black-Friday peak in November.
- a `total` column and a `discount` column ("total discount" = sum of discount).
- delivery_days is empty for cancelled orders; some orders have no country.

Run from the repo root:
    python -m benchmark.make_dataset_shop
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 7
N_ORDERS = 4000
OUT_PATH = Path(__file__).parent / "datasets" / "shop.csv"

COUNTRIES = ["Denmark", "Sweden", "Germany", "Norway", "Finland"]
COUNTRY_PROBS = [0.35, 0.25, 0.20, 0.12, 0.08]
DELIVERY_MEAN = {"Denmark": 2, "Sweden": 3, "Germany": 3, "Norway": 5, "Finland": 4}

CATEGORIES = ["Clothing", "Electronics", "Home", "Books", "Toys"]
CATEGORY_PROBS = [0.35, 0.20, 0.20, 0.15, 0.10]
PRICE_MEAN = {"Clothing": 35, "Electronics": 220, "Home": 55, "Books": 15, "Toys": 28}
RETURN_RATE = {"Clothing": 0.20, "Electronics": 0.08, "Home": 0.06, "Books": 0.02, "Toys": 0.05}

# Orders peak in the evening (20 h) and a bit at lunch.
HOUR_WEIGHTS = np.array([
    1, 1, 1, 1, 1, 1, 2, 3, 4, 5, 5, 6,       # 0-11
    8, 7, 6, 6, 6, 7, 9, 12, 16, 13, 8, 4,    # 12-23
], dtype=float)


def make_orders(rng: np.random.Generator) -> pd.DataFrame:
    # --- When: 2023-2024, Black Friday peak in November, growth in 2024 ---
    days = pd.date_range("2023-01-01", "2024-12-31", freq="D")
    month = days.month.to_numpy()
    season = np.where(month == 11, 2.2, np.where(month == 12, 1.6, 1.0))
    growth = np.where(days.year == 2024, 1.3, 1.0)
    day_probs = season * growth
    day_probs = day_probs / day_probs.sum()
    day_idx = rng.choice(len(days), size=N_ORDERS, p=day_probs)
    hours = rng.choice(24, size=N_ORDERS, p=HOUR_WEIGHTS / HOUR_WEIGHTS.sum())
    minutes = rng.integers(0, 60, size=N_ORDERS)
    order_time = (
        days[day_idx]
        + pd.to_timedelta(hours, unit="h")
        + pd.to_timedelta(minutes, unit="m")
    )

    # --- Who and how --------------------------------------------------------
    country = rng.choice(COUNTRIES, size=N_ORDERS, p=COUNTRY_PROBS)
    category = rng.choice(CATEGORIES, size=N_ORDERS, p=CATEGORY_PROBS)
    channel = rng.choice(["web", "app"], size=N_ORDERS, p=[0.6, 0.4])
    payment = rng.choice(["card", "paypal", "invoice"], size=N_ORDERS, p=[0.55, 0.30, 0.15])
    customer_type = rng.choice(["new", "returning"], size=N_ORDERS, p=[0.4, 0.6])

    # --- What and how much ----------------------------------------------------
    # Clothing: many items per order; Electronics: few but expensive.
    qty_mean = np.where(category == "Clothing", 3.0,
                        np.where(category == "Books", 2.0, 1.3))
    quantity = 1 + rng.poisson(qty_mean - 1)
    price_mean = np.array([PRICE_MEAN[c] for c in category])
    unit_price = rng.gamma(shape=5.0, scale=price_mean / 5.0).round(2)
    subtotal = quantity * unit_price
    discount_rate = rng.choice([0.0, 0.10, 0.20], size=N_ORDERS, p=[0.6, 0.3, 0.1])
    # Returning customers get discounts more often.
    discount_rate = np.where((customer_type == "returning") & (discount_rate == 0)
                             & (rng.random(N_ORDERS) < 0.2), 0.10, discount_rate)
    discount = (subtotal * discount_rate).round(2)
    shipping_fee = np.where(subtotal - discount >= 100, 0.0, 4.99)
    total = (subtotal - discount + shipping_fee).round(2)

    # --- What happened to the order ------------------------------------------
    return_p = np.array([RETURN_RATE[c] for c in category])
    r = rng.random(N_ORDERS)
    status = np.where(r < 0.04, "cancelled",
                      np.where(r < 0.04 + return_p, "returned", "delivered"))
    delivery_mean = np.array([DELIVERY_MEAN[c] for c in country])
    delivery_days = (1 + rng.poisson(delivery_mean - 1)).astype(float)
    delivery_days[status == "cancelled"] = np.nan

    df = pd.DataFrame({
        "order_id": np.arange(1, N_ORDERS + 1),
        "order_time": order_time,
        "country": country,
        "category": category,
        "channel": channel,
        "payment": payment,
        "customer_type": customer_type,
        "quantity": quantity,
        "unit_price": unit_price,
        "discount": discount,
        "shipping_fee": shipping_fee,
        "total": total,
        "status": status,
        "delivery_days": delivery_days,
    })

    # A few orders without country.
    missing = rng.choice(N_ORDERS, size=25, replace=False)
    df.loc[missing, "country"] = None

    df = df.sort_values("order_time").reset_index(drop=True)
    df["order_id"] = np.arange(1001, 1001 + N_ORDERS)
    df["order_time"] = df["order_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df["delivery_days"] = df["delivery_days"].astype("Int64")
    return df


def main() -> None:
    rng = np.random.default_rng(SEED)
    df = make_orders(rng)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)

    print(f"Saved {len(df)} orders to {OUT_PATH}")
    print("Columns:", ", ".join(df.columns))
    print()
    print(df.head(3).to_string())


if __name__ == "__main__":
    main()