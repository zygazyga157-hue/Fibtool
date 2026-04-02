# Asia Sweep (London MSS) — ML Filter (Plan-Aligned)

This folder implements the **exact PLAN.md** for a PyTorch trade-quality filter on top of the mechanical Asia Sweep → London MSS strategy.

Key design: **the strategy still generates trades** (sweep→MSS + 0.71 levels). The ML model is a **second-stage gate** that predicts whether the trade will **fill and reach TP before SL before London end** (same session day).

## Data Source (True M5)
The dataset is built from TRUE M5 bars saved by the collector:

- `outputs/<symbol_slug>_m5.csv`

This is intentionally separate from the M15 collector file (`outputs/<symbol_slug>_bars.csv`) so the rest of Fibtool can stay on M15 while Asia MSS stays mechanically correct on M5.

Generate/refresh TRUE M5 bars with the dedicated collector:

```bash
python asia_sweep_m5_collector.py --once --symbols EURUSD,GBPUSD,BTCUSD
```

## Quickstart

1) Build an event dataset (one row per qualified confirmation candle `t0`):

```bash
python -m ml.asia_sweep_london_mss.prepare_dataset --symbols EURUSD,GBPUSD,BTCUSD --out ml/asia_sweep_london_mss/data/dataset.csv
```

2) Train the plan-aligned classifier (symbol embedding + LayerNorm MLP):

```bash
python -m ml.asia_sweep_london_mss.train --data ml/asia_sweep_london_mss/data/dataset.csv --out outputs/models/asia_sweep_mss/v1_YYYYMMDD_HHMMSS --activate-root outputs/models/asia_sweep_mss
```

Artifacts written (per PLAN.md):
- `outputs/models/asia_sweep_mss/v1_*/model.pt`
- `outputs/models/asia_sweep_mss/v1_*/feature_stats.json`
- `outputs/models/asia_sweep_mss/v1_*/symbol_map.json`
- `outputs/models/asia_sweep_mss/v1_*/metrics.json`

Hot reload convention:
- Model root: `outputs/models/asia_sweep_mss/`
- Pointer: `outputs/models/asia_sweep_mss/current.json` with `active_dir` pointing to a `v1_*` folder.
- If you run live with `python scripts/run_asia_sweep.py --ml`, the runner manages the pointer automatically.

## Features (Locked)
The feature set is explicitly defined (see `ml/asia_sweep_london_mss/torch_dataset.py:FEATURE_COLS`) and matches PLAN.md:

- `asia_range`, `atr14`, `asia_range_atr`
- `eqh_touch_count`, `eql_touch_count`
- `sweep_dir`, `sweep_depth_atr`
- `minutes_from_london_open`
- `bars_from_sweep_to_mss`, `bars_from_sweep_to_mss_norm`
- `confirm_range_atr`, `entry_dist_atr`, `rr`
- plus categorical `symbol_id` via embedding (from `symbol_map.json`)

## Labels (Locked)
Binary label per PLAN.md:
- `1`: order fills and TP hits before SL before London end (same session day)
- `0`: otherwise (includes no-fill, SL-first, neither hit)

Worst-case tie rule:
- If TP and SL are both reachable in the same bar after fill, count as SL-first.

## Inference Helper
Use `ml.asia_sweep_london_mss.inference.score_probability(...)` to get a probability for a single trade setup using the saved artifacts.

This is what the live `asia_sweep_london_mss.py` integration will call when `ASIA_SWEEP_ML_ENABLED=True`.

