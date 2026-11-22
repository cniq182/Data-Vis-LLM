import seaborn as sns

df = sns.load_dataset("taxis")
flights = sns.load_dataset("flights")


def show_top(series, label):
    """Print the top 3 values of a series, largest first."""
    print(f"\n{label}")
    print(series.sort_values(ascending=False).head(3).round(2).to_string())


# Practice task (flights)
show_top(flights.groupby("year")["passengers"].sum(), "P: total passengers per year")

# T1: trips per pickup borough
show_top(df["pickup_borough"].value_counts(), "T1: trips per pickup borough")

# T2: average fare per taxi color
show_top(df.groupby("color")["fare"].mean(), "T2: average fare per color")

# T3: trips per pickup hour
show_top(df["pickup"].dt.hour.value_counts(), "T3: trips per pickup hour")

# T4: average tip per pickup borough, credit card only (count shows group size)
card = df[df["payment"] == "credit card"]
t4 = card.groupby("pickup_borough")["tip"].agg(["mean", "count"])
print("\nT4: average tip (credit card) per pickup borough")
print(t4.sort_values("mean", ascending=False).round(2).to_string())

# T5: trips per drop-off borough that  only started in Brooklyn
brooklyn = df[df["pickup_borough"] == "Brooklyn"]
show_top(brooklyn["dropoff_borough"].value_counts(), "T5: drop-off borough, trips from Brooklyn")

# Missing values (empty boroughs can change the answers)
print("\nMissing values per column:")
print(df.isna().sum().to_string())

import seaborn as sns
sns.load_dataset("flights").to_csv("Evaluation/flights.csv", index=False)