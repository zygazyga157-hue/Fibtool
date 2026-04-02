"""Quick analysis of the Asia Sweep ML dataset."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pandas as pd

path = os.path.join(os.path.dirname(__file__), "..", "ml", "asia_sweep_london_mss", "data", "dataset.csv")
df = pd.read_csv(path)
print("=" * 60)
print(f"DATASET: {path}")
print(f"Rows: {len(df)}")
print(f"Columns: {list(df.columns)}")
print(f"\nLabel distribution:")
print(df["label"].value_counts().to_string())
print(f"\nPositive rate: {df['label'].mean():.4f}")
print(f"\nSymbols: {df['symbol'].unique().tolist()}")
print(f"\nt0 range: {df['t0'].min()} to {df['t0'].max()}")
print(f"\nFeature stats:")
feat_cols = ["asia_range","atr14","asia_range_atr","eqh_touch_count","eql_touch_count",
             "sweep_dir","sweep_depth_atr","minutes_from_london_open",
             "bars_from_sweep_to_mss","bars_from_sweep_to_mss_norm",
             "confirm_range_atr","entry_dist_atr","rr"]
for c in feat_cols:
    if c in df.columns:
        s = df[c]
        print(f"  {c:35s} mean={s.mean():10.4f}  std={s.std():10.4f}  min={s.min():10.4f}  max={s.max():10.4f}  nan={s.isna().sum()}")

print(f"\nNaN counts per column:")
for c in df.columns:
    n = df[c].isna().sum()
    if n > 0:
        print(f"  {c}: {n}")

if "side" in df.columns:
    print(f"\nSide distribution:")
    print(df["side"].value_counts().to_string())
    print(f"\nWin rate by side:")
    for side in df["side"].unique():
        s = df[df["side"] == side]
        print(f"  {side}: {s['label'].mean():.4f} ({int(s['label'].sum())}/{len(s)})")

print(f"\nWin rate by symbol:")
for sym in df["symbol"].unique():
    s = df[df["symbol"] == sym]
    print(f"  {sym}: {s['label'].mean():.4f} ({int(s['label'].sum())}/{len(s)})")

# Correlation with label
print(f"\nFeature correlation with label:")
for c in feat_cols:
    if c in df.columns:
        corr = df[c].corr(df["label"])
        print(f"  {c:35s} r={corr:+.4f}")
print("=" * 60)
