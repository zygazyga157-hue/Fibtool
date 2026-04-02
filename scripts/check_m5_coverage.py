"""Analyze M5 data coverage per symbol."""
import pandas as pd
import os

for f in sorted(os.listdir("outputs")):
    if f.endswith("_m5.csv"):
        df = pd.read_csv(f"outputs/{f}", parse_dates=["time"])
        t_min = df["time"].min()
        t_max = df["time"].max()
        days = (t_max - t_min).days
        print(f"{f:25s}  rows={len(df):6d}  from={t_min}  to={t_max}  days={days}")
