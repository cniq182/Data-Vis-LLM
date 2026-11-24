"""Generate the synthetic benchmark dataset: bike-share trips in a fictional city.

Why synthetic?
- No LLM has seen it, so it cannot answer "from memory".
- We control the traps on purpose (a `total` column, two years of dates,
  a fare-vs-total divergence, some missing values).
- A fixed random seed makes the file identical every time it is generated.

Run from the repo root:
    python -m benchmark.make_dataset
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_TRIPS = 5000
OUT_PATH = Path(__file__).parent / "datasets" / "bikes.csv"

# Fictional districts of the fictional city "Valdora" (with clear winners).
DISTRICTS = ["Old Town", "Harbour", "University", "Riverside", "Hillside"]
START_PROBS = [0.40, 0.22, 0.18, 0.13, 0.07]

# Hour of day when trips start: morning peak at 8, bigger evening peak at 17.
HOUR_WEIGHTS = np.array([
    1, 1, 1, 1, 1, 2, 4, 9, 14, 8, 5, 5,      # 0-11
    6, 6, 5, 6, 10, 17, 12, 7, 4, 3, 2, 1,    # 12-23
], dtype=float)


def make_trips(rng: np.random.Generator) -> pd.DataFrame:
    # --- When: 2023-2024, more trips in summer and more in 2024 -----------
    days = pd.date_range("2023-01-01", "2024-12-31", freq="D")
    season = 1 + 0.6 * np.sin((days.dayofyear.to_numpy() - 100) / 365 * 2 * np.pi)
    growth = np.where(days.year == 2024, 1.4, 1.0)
    day_probs = season * growth
    day_probs = day_probs / day_probs.sum()
    day_idx = rng.choice(len(days), size=N_TRIPS, p=day_probs)
    hours = rng.choice(24, size=N_TRIPS, p=HOUR_WEIGHTS / HOUR_WEIGHTS.sum())
    minutes = rng.integers(0, 60, size=N_TRIPS)
    start_time = (
        days[day_idx]
        + pd.to_timedelta(hours, unit="h")
        + pd.to_timedelta(minutes, unit="m")
    )

    # --- What kind of bike and rider ------------------------------------
    bike_type = rng.choice(["classic", "electric"], size=N_TRIPS, p=[0.6, 0.4])
    user_type = rng.choice(["member", "casual"], size=N_TRIPS, p=[0.7, 0.3])

    # Classic rides are longer; electric rides are shorter but pay an unlock fee.
    duration = np.where(
        bike_type == "classic",
        rng.gamma(shape=4.0, scale=5.0, size=N_TRIPS),   # mean ~20 min
        rng.gamma(shape=4.0, scale=3.0, size=N_TRIPS),   # mean ~12 min
    ).round(1) + 1.0
    speed_kmh = np.where(bike_type == "classic", 13, 18) + rng.normal(0, 2, N_TRIPS)
    distance_km = (duration / 60 * speed_kmh).clip(0.2).round(2)

    # Trap: mean(fare) is higher for classic, mean(total) is higher for electric.
    fare = (1.0 + 0.20 * duration).round(2)
    unlock_fee = np.where(bike_type == "electric", 3.00, 0.00)
    late_fee = np.where(duration > 45, 5.00, 0.00)
    discount = np.where(user_type == "member", -0.5, 0.0)
    total = (fare + unlock_fee + late_fee + discount).clip(0).round(2)

    # --- Where ---------------------------------------------------------
    start_district = rng.choice(DISTRICTS, size=N_TRIPS, p=START_PROBS)
    end_district = rng.choice(DISTRICTS, size=N_TRIPS, p=[0.30, 0.30, 0.15, 0.15, 0.10])
    # Most trips that start in Riverside end in University (for a filter case).
    from_riverside = start_district == "Riverside"
    end_district[from_riverside] = rng.choice(
        DISTRICTS, size=from_riverside.sum(), p=[0.15, 0.10, 0.55, 0.15, 0.05]
    )

    # Payment: casual users pay more often with card, members with the app.
    payment = np.where(
        user_type == "member",
        rng.choice(["app", "card"], size=N_TRIPS, p=[0.85, 0.15]),
        rng.choice(["app", "card", "cash"], size=N_TRIPS, p=[0.35, 0.50, 0.15]),
    )

    df = pd.DataFrame({
        "trip_id": np.arange(1, N_TRIPS + 1),
        "start_time": start_time,
        "end_time": start_time + pd.to_timedelta(duration, unit="m"),
        "start_district": start_district,
        "end_district": end_district,
        "bike_type": bike_type,
        "user_type": user_type,
        "duration_min": duration,
        "distance_km": distance_km,
        "fare": fare,
        "unlock_fee": unlock_fee,
        "late_fee": late_fee,
        "total": total,
        "payment": payment,
    })

    # A few missing values, like in the taxis data.
    missing_start = rng.choice(N_TRIPS, size=30, replace=False)
    df.loc[missing_start, "start_district"] = None
    missing_pay = rng.choice(N_TRIPS, size=40, replace=False)
    df.loc[missing_pay, "payment"] = None

    df = df.sort_values("start_time").reset_index(drop=True)
    df["trip_id"] = np.arange(1, N_TRIPS + 1)
    df["start_time"] = df["start_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df["end_time"] = pd.to_datetime(df["end_time"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    return df


def main() -> None:
    rng = np.random.default_rng(SEED)
    df = make_trips(rng)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)

    # Short summary so we can check the file looks right.
    print(f"Saved {len(df)} trips to {OUT_PATH}")
    print("Columns:", ", ".join(df.columns))
    print()
    print(df.head(3).to_string())


if __name__ == "__main__":
    main()