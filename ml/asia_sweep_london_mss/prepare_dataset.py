"""Build a plan-aligned dataset for Asia Sweep (London MSS) ML filter.

This script replays TRUE M5 bars from:
  outputs/<symbol_slug>_m5.csv

and generates one row per *qualified* sweep->MSS confirmation event (t0).

Label (binary, session-bounded):
  y=1 if order fills and TP hits before SL before London end (same session day)
  y=0 otherwise (includes no-fill, SL-first, neither hit)

Worst-case rule:
  If TP and SL are both reachable in the same bar after fill, count as SL-first.

Output:
  A single combined CSV with columns:
    - t0 (UTC ISO)
    - symbol (string)
    - label (0/1)
    - feature columns (locked in PLAN.md)
    - optional debug columns (entry/stop/tp/etc)

Example:
  python -m ml.asia_sweep_london_mss.prepare_dataset --symbols EURUSD,GBPUSD --out ml/asia_sweep_london_mss/data/dataset.csv
"""

from __future__ import annotations

import argparse
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

try:
    import config as _cfg
except Exception:  # pragma: no cover
    _cfg = None


def _symbol_slug(symbol: str) -> str:
    try:
        return "".join(ch if ch.isalnum() else "_" for ch in str(symbol)).lower().strip("_")
    except Exception:
        return str(symbol).replace("/", "_").replace(" ", "_").lower()


def _cfg_get(name: str, default):
    try:
        if _cfg is not None and hasattr(_cfg, name):
            v = getattr(_cfg, name)
            return default if v is None else v
    except Exception:
        pass
    return default


def _to_utc_aware_index(idx: pd.Index) -> pd.DatetimeIndex:
    ts = pd.to_datetime(idx, errors="coerce")
    ts = pd.DatetimeIndex(ts).dropna()
    if getattr(ts, "tz", None) is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def load_m5_bars(outputs_dir: Path, symbol: str) -> Optional[pd.DataFrame]:
    path = outputs_dir / f"{_symbol_slug(symbol)}_m5.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["time"])
    if "time" not in df.columns:
        return None
    df = df.set_index("time").sort_index()
    # Stored times are UTC-naive; localize to UTC for correct timezone math.
    df.index = _to_utc_aware_index(df.index)
    return df


def _true_range(df: pd.DataFrame) -> pd.Series:
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    close = pd.to_numeric(df["close"], errors="coerce")
    prev_close = close.shift(1)
    tr1 = (high - low).abs()
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr


def compute_atr14(df: pd.DataFrame) -> pd.Series:
    tr = _true_range(df)
    return tr.rolling(window=14, min_periods=14).mean()


def compute_mss_flags(df: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """Close-based MSS flags per PLAN.md (bull: close > max(prev highs), bear: close < min(prev lows))."""
    lb = int(lookback)
    out = df.copy()
    bull = [False] * len(out)
    bear = [False] * len(out)
    if len(out) < lb + 1:
        out["bullMSS"] = bull
        out["bearMSS"] = bear
        return out

    highs = pd.to_numeric(out["high"], errors="coerce")
    lows = pd.to_numeric(out["low"], errors="coerce")
    closes = pd.to_numeric(out["close"], errors="coerce")
    for i in range(len(out)):
        if i < lb:
            continue
        prev_high = float(highs.iloc[i - lb : i].max())
        prev_low = float(lows.iloc[i - lb : i].min())
        c = float(closes.iloc[i])
        bull[i] = bool(c > prev_high)
        bear[i] = bool(c < prev_low)
    out["bullMSS"] = bull
    out["bearMSS"] = bear
    return out


@dataclass
class DayContext:
    session_day: object
    asia_high: float
    asia_low: float
    eqh_touch_count: int
    eql_touch_count: int
    sweep_high_time: Optional[pd.Timestamp]
    sweep_low_time: Optional[pd.Timestamp]


def compute_asia_range(day_df: pd.DataFrame, *, asia_start: str, asia_end: str) -> Optional[tuple[float, float, int, int]]:
    asia_df = day_df.between_time(asia_start, asia_end)
    if asia_df.empty:
        return None
    asia_high = float(pd.to_numeric(asia_df["high"], errors="coerce").max())
    asia_low = float(pd.to_numeric(asia_df["low"], errors="coerce").min())
    if not (math.isfinite(asia_high) and math.isfinite(asia_low)):
        return None
    tol = 1e-5
    eqh = int((pd.to_numeric(asia_df["high"], errors="coerce") >= asia_high - tol).sum())
    eql = int((pd.to_numeric(asia_df["low"], errors="coerce") <= asia_low + tol).sum())
    return asia_high, asia_low, eqh, eql


def find_sweep_events(day_df: pd.DataFrame, *, asia_high: float, asia_low: float, sweep_start: str, sweep_end: str) -> tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    win = day_df.between_time(sweep_start, sweep_end)
    if win.empty:
        return None, None
    sh = win[pd.to_numeric(win["high"], errors="coerce") > float(asia_high)]
    sl = win[pd.to_numeric(win["low"], errors="coerce") < float(asia_low)]
    sweep_high_time = sh.index[0] if not sh.empty else None
    sweep_low_time = sl.index[0] if not sl.empty else None
    return sweep_high_time, sweep_low_time


def choose_confirmation(
    london_df: pd.DataFrame,
    *,
    sweep_high_time: Optional[pd.Timestamp],
    sweep_low_time: Optional[pd.Timestamp],
    confirm_window_bars: int,
) -> Optional[tuple[str, pd.Timestamp]]:
    """Replicate strategy: first bull after sweep_low, first bear after sweep_high, then pick earliest confirm."""
    all_confirms = choose_all_confirmations(
        london_df, sweep_high_time=sweep_high_time, sweep_low_time=sweep_low_time,
        confirm_window_bars=confirm_window_bars,
    )
    return all_confirms[0] if all_confirms else None


def choose_all_confirmations(
    london_df: pd.DataFrame,
    *,
    sweep_high_time: Optional[pd.Timestamp],
    sweep_low_time: Optional[pd.Timestamp],
    confirm_window_bars: int,
) -> list[tuple[str, pd.Timestamp]]:
    """Return ALL qualifying (side, confirm_time) pairs for this day, sorted by time."""
    results = []
    win_bars = int(confirm_window_bars)
    if win_bars < 1:
        win_bars = 1

    if sweep_low_time is not None:
        win_end = sweep_low_time + pd.Timedelta(minutes=5 * win_bars)
        bull = london_df[(london_df.index >= sweep_low_time) & (london_df.index <= win_end) & (london_df["bullMSS"] == True)]
        if not bull.empty:
            results.append(("Long", bull.index[0]))

    if sweep_high_time is not None:
        win_end = sweep_high_time + pd.Timedelta(minutes=5 * win_bars)
        bear = london_df[(london_df.index >= sweep_high_time) & (london_df.index <= win_end) & (london_df["bearMSS"] == True)]
        if not bear.empty:
            results.append(("Short", bear.index[0]))

    results.sort(key=lambda x: x[1])
    return results


def infer_order_kind(side: str, *, entry: float, close_t0: float) -> str:
    side_l = str(side).strip().lower()
    if side_l == "long":
        return "buy_limit" if float(entry) <= float(close_t0) else "buy_stop"
    return "sell_limit" if float(entry) >= float(close_t0) else "sell_stop"


def simulate_label(
    df_london: pd.DataFrame,
    *,
    side: str,
    t0: pd.Timestamp,
    entry: float,
    stop: float,
    tp: float,
    london_end: str,
) -> tuple[int, Optional[pd.Timestamp]]:
    """Return (label, fill_time). Uses worst-case for TP/SL ambiguity."""
    # Horizon is London end of the same day.
    day = t0.date()
    # Create a horizon timestamp in the same tz as the df index.
    horizon = pd.Timestamp(f"{day.isoformat()} {london_end}", tz=t0.tz)

    future = df_london[(df_london.index > t0) & (df_london.index <= horizon)]
    if future.empty:
        return 0, None

    close_t0 = float(pd.to_numeric(df_london.loc[t0]["close"], errors="coerce"))
    kind = infer_order_kind(side, entry=entry, close_t0=close_t0)

    fill_time = None
    for ts, row in future.iterrows():
        hi = float(pd.to_numeric(row["high"], errors="coerce"))
        lo = float(pd.to_numeric(row["low"], errors="coerce"))
        if kind == "buy_limit":
            if lo <= float(entry):
                fill_time = ts
                break
        elif kind == "buy_stop":
            if hi >= float(entry):
                fill_time = ts
                break
        elif kind == "sell_limit":
            if hi >= float(entry):
                fill_time = ts
                break
        else:  # sell_stop
            if lo <= float(entry):
                fill_time = ts
                break

    if fill_time is None:
        return 0, None

    after_fill = df_london[(df_london.index >= fill_time) & (df_london.index <= horizon)]
    if after_fill.empty:
        return 0, fill_time

    side_l = str(side).strip().lower()
    for _, row in after_fill.iterrows():
        hi = float(pd.to_numeric(row["high"], errors="coerce"))
        lo = float(pd.to_numeric(row["low"], errors="coerce"))
        if side_l == "long":
            sl_hit = lo <= float(stop)
            tp_hit = hi >= float(tp)
        else:
            sl_hit = hi >= float(stop)
            tp_hit = lo <= float(tp)

        # worst-case: SL wins ties
        if sl_hit:
            return 0, fill_time
        if tp_hit:
            return 1, fill_time

    return 0, fill_time


FEATURE_COLS = [
    "asia_range",
    "atr14",
    "asia_range_atr",
    "eqh_touch_count",
    "eql_touch_count",
    "sweep_dir",
    "sweep_depth_atr",
    "minutes_from_london_open",
    "bars_from_sweep_to_mss",
    "bars_from_sweep_to_mss_norm",
    "confirm_range_atr",
    "entry_dist_atr",
    "rr",
    # --- v2 engineered features ---
    "day_of_week",               # 0=Mon..4=Fri, captures day-specific edge
    "sweep_depth_x_asia_atr",    # interaction: deep sweep in tight range -> cleaner
    "confirm_body_ratio",        # |close-open|/range of confirm candle (conviction)
    "rr_capped",                 # rr capped at 20 to remove outlier noise
    "sweep_velocity_atr",        # sweep_depth_atr / bars_from_sweep_to_mss (speed)
    "multi_touch",               # max(eqh, eql) – single vs multi-tested level
    "entry_stop_atr",            # |entry-stop|/atr – tightness of stop
]


def build_dataset_for_symbol(symbol: str, *, outputs_dir: Path, both_sides: bool = False) -> list[dict]:
    df_utc = load_m5_bars(outputs_dir, symbol)
    if df_utc is None or df_utc.empty:
        return []

    session_tz = str(_cfg_get("ASIA_SWEEP_SESSION_TIME_ZONE", "Europe/London"))
    asia_start = str(_cfg_get("ASIA_SWEEP_ASIA_START", "00:00"))
    asia_end = str(_cfg_get("ASIA_SWEEP_ASIA_END", "07:59"))
    london_start = str(_cfg_get("ASIA_SWEEP_LONDON_START", "08:00"))
    london_end = str(_cfg_get("ASIA_SWEEP_LONDON_END", "14:00"))
    sweep_start = str(_cfg_get("ASIA_SWEEP_SWEEP_START", london_start))
    sweep_end = str(_cfg_get("ASIA_SWEEP_SWEEP_END", london_end))
    mss_lookback = int(_cfg_get("ASIA_SWEEP_MSS_LOOKBACK", 3))
    confirm_window_bars = int(_cfg_get("ASIA_SWEEP_CONFIRM_WINDOW_BARS", 12))

    # Session-time view for day slicing and windows.
    df_sess = df_utc.copy()
    df_sess.index = df_utc.index.tz_convert(session_tz)
    df_sess.sort_index(inplace=True)

    # Precompute ATR on UTC series for stable indexing.
    atr14 = compute_atr14(df_utc[["high", "low", "close"]])
    atr14.name = "atr14"

    rows: list[dict] = []
    # iterate per session day
    for day, day_df in df_sess.groupby(df_sess.index.date):
        rng = compute_asia_range(day_df, asia_start=asia_start, asia_end=asia_end)
        if rng is None:
            continue
        asia_high, asia_low, eqh_count, eql_count = rng

        sweep_high_time, sweep_low_time = find_sweep_events(
            day_df, asia_high=asia_high, asia_low=asia_low, sweep_start=sweep_start, sweep_end=sweep_end
        )

        # MSS flags (computed on the full day slice so indices align)
        day_df_mss = compute_mss_flags(day_df[["open", "high", "low", "close"]], lookback=mss_lookback)
        london_df = day_df_mss.between_time(london_start, london_end)
        if london_df.empty:
            continue

        if both_sides:
            confirmations = choose_all_confirmations(
                london_df, sweep_high_time=sweep_high_time, sweep_low_time=sweep_low_time,
                confirm_window_bars=confirm_window_bars,
            )
        else:
            chosen = choose_confirmation(
                london_df, sweep_high_time=sweep_high_time, sweep_low_time=sweep_low_time,
                confirm_window_bars=confirm_window_bars,
            )
            confirmations = [chosen] if chosen is not None else []

        for side, t0 in confirmations:
            # confirmation candle
            c = london_df.loc[t0]
            c_low = float(c["low"])
            c_high = float(c["high"])
            c_close = float(c["close"])
            rng_c = c_high - c_low
            if not (math.isfinite(rng_c) and rng_c > 0):
                continue

            fib_ratio = 0.71
            if side == "Long":
                entry = c_low + (rng_c * fib_ratio)
                stop = c_low
                tp = asia_high
                sweep_time = sweep_low_time
                sweep_bar = day_df.loc[sweep_low_time] if sweep_low_time is not None and sweep_low_time in day_df.index else None
                sweep_dir = 1
            else:
                entry = c_high - (rng_c * fib_ratio)
                stop = c_high
                tp = asia_low
                sweep_time = sweep_high_time
                sweep_bar = day_df.loc[sweep_high_time] if sweep_high_time is not None and sweep_high_time in day_df.index else None
                sweep_dir = -1

            # ATR at t0 (use UTC index)
            t0_utc = t0.tz_convert("UTC")
            a = atr14.loc[:t0_utc].iloc[-1] if len(atr14.loc[:t0_utc]) else np.nan
            if a is None or not float(a) or not math.isfinite(float(a)) or float(a) <= 0:
                continue
            a = float(a)

            asia_range = float(asia_high - asia_low)
            asia_range_atr = asia_range / a if a > 0 else np.nan

            # Sweep depth
            sweep_depth_atr = np.nan
            if sweep_bar is not None:
                try:
                    if sweep_dir == 1:
                        sweep_depth_atr = (float(asia_low) - float(sweep_bar["low"])) / a
                    else:
                        sweep_depth_atr = (float(sweep_bar["high"]) - float(asia_high)) / a
                except Exception:
                    sweep_depth_atr = np.nan

            # minutes from London open normalized to [0,1] in the configured window length
            try:
                t0_time = t0.time()
                ls = pd.Timestamp(f"{t0.date().isoformat()} {london_start}", tz=t0.tz).time()
                le = pd.Timestamp(f"{t0.date().isoformat()} {london_end}", tz=t0.tz).time()
                mins_from_open = (t0_time.hour * 60 + t0_time.minute) - (ls.hour * 60 + ls.minute)
                total_mins = max(1, (le.hour * 60 + le.minute) - (ls.hour * 60 + ls.minute))
                minutes_from_london_open = float(mins_from_open) / float(total_mins)
                minutes_from_london_open = max(0.0, min(1.0, minutes_from_london_open))
            except Exception:
                minutes_from_london_open = 0.0

            # bars from sweep to mss
            bars_from_sweep = np.nan
            bars_from_sweep_norm = np.nan
            if sweep_time is not None:
                try:
                    dt_min = (t0 - sweep_time).total_seconds() / 60.0
                    bars_from_sweep = int(round(dt_min / 5.0))
                    bars_from_sweep_norm = float(bars_from_sweep) / float(max(1, int(confirm_window_bars)))
                except Exception:
                    pass

            confirm_range_atr = float(rng_c) / a if a > 0 else np.nan
            entry_dist_atr = abs(float(entry) - float(c_close)) / a if a > 0 else np.nan
            rr = np.nan
            try:
                rr = abs(float(tp) - float(entry)) / abs(float(entry) - float(stop)) if float(entry) != float(stop) else np.nan
            except Exception:
                rr = np.nan

            # --- v2 engineered features ---
            RR_CAP = 20.0
            rr_capped = min(float(rr), RR_CAP) if math.isfinite(float(rr)) else np.nan

            # day_of_week: 0=Mon..4=Fri
            try:
                day_of_week = int(t0.weekday())
            except Exception:
                day_of_week = 0

            # interaction: sweep_depth * asia_range_atr
            sweep_depth_x_asia_atr = np.nan
            if math.isfinite(float(sweep_depth_atr)) and math.isfinite(float(asia_range_atr)):
                sweep_depth_x_asia_atr = float(sweep_depth_atr) * float(asia_range_atr)

            # confirm candle body ratio: |close-open| / (high-low)
            try:
                c_open = float(c["open"])
                confirm_body_ratio = abs(c_close - c_open) / rng_c if rng_c > 0 else 0.0
            except Exception:
                confirm_body_ratio = 0.0

            # sweep velocity: depth / bars (fast sweeps may be cleaner)
            sweep_velocity_atr = np.nan
            if math.isfinite(float(sweep_depth_atr)) and bars_from_sweep is not None and float(bars_from_sweep) > 0:
                sweep_velocity_atr = float(sweep_depth_atr) / float(bars_from_sweep)

            # multi_touch: max of eqh/eql counts
            multi_touch = max(int(eqh_count), int(eql_count))

            # entry-stop distance in ATR
            entry_stop_atr = abs(float(entry) - float(stop)) / a if a > 0 else np.nan

            label, fill_time = simulate_label(
                london_df,
                side=side,
                t0=t0,
                entry=float(entry),
                stop=float(stop),
                tp=float(tp),
                london_end=london_end,
            )

            row = {
                "t0": t0_utc.isoformat(),
                "symbol": str(symbol),
                "label": int(label),
                # features (locked)
                "asia_range": asia_range,
                "atr14": a,
                "asia_range_atr": asia_range_atr,
                "eqh_touch_count": int(eqh_count),
                "eql_touch_count": int(eql_count),
                "sweep_dir": int(sweep_dir),
                "sweep_depth_atr": float(sweep_depth_atr) if sweep_depth_atr is not None else np.nan,
                "minutes_from_london_open": float(minutes_from_london_open),
                "bars_from_sweep_to_mss": float(bars_from_sweep) if bars_from_sweep is not None else np.nan,
                "bars_from_sweep_to_mss_norm": float(bars_from_sweep_norm) if bars_from_sweep_norm is not None else np.nan,
                "confirm_range_atr": float(confirm_range_atr),
                "entry_dist_atr": float(entry_dist_atr),
                "rr": float(rr) if rr is not None else np.nan,
                # v2 engineered features
                "day_of_week": day_of_week,
                "sweep_depth_x_asia_atr": float(sweep_depth_x_asia_atr) if sweep_depth_x_asia_atr is not None else np.nan,
                "confirm_body_ratio": float(confirm_body_ratio),
                "rr_capped": float(rr_capped) if rr_capped is not None else np.nan,
                "sweep_velocity_atr": float(sweep_velocity_atr) if sweep_velocity_atr is not None else np.nan,
                "multi_touch": int(multi_touch),
                "entry_stop_atr": float(entry_stop_atr) if entry_stop_atr is not None else np.nan,
                # debug
                "side": side,
                "entry": float(entry),
                "stop": float(stop),
                "tp": float(tp),
                "sweep_time": sweep_time.tz_convert("UTC").isoformat() if sweep_time is not None else None,
                "fill_time": fill_time.tz_convert("UTC").isoformat() if fill_time is not None else None,
            }
            rows.append(row)

    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", required=True, help="Comma-separated symbols (e.g. EURUSD,GBPUSD,BTCUSD)")
    ap.add_argument("--outputs-dir", default="outputs", help="Project outputs dir (default: outputs)")
    ap.add_argument("--out", default="ml/asia_sweep_london_mss/data/dataset.csv", help="Output CSV path")
    ap.add_argument("--both-sides", action="store_true", help="Emit both long AND short setups per day when both qualify (increases sample count)")
    args = ap.parse_args()

    symbols = [s.strip() for s in str(args.symbols).split(",") if s.strip()]
    outputs_dir = Path(args.outputs_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict] = []
    missing_m5: list[str] = []
    for sym in symbols:
        m5_path = outputs_dir / f"{_symbol_slug(sym)}_m5.csv"
        if not m5_path.exists():
            missing_m5.append(str(m5_path))
            continue
        rows = build_dataset_for_symbol(sym, outputs_dir=outputs_dir, both_sides=bool(args.both_sides))
        all_rows.extend(rows)

    if not all_rows:
        print("No rows generated (check M5 bars availability and date range).")
        if missing_m5:
            print("Missing required TRUE M5 bars files (expected by PLAN.md):")
            for p in missing_m5:
                print(f"  - {p}")
            print("Generate M5 bars via MT5 collector, for example:")
            print(f"  python asia_sweep_m5_collector.py --once --symbols {','.join(symbols)}")
            print("Then re-run this dataset build command.")
        else:
            print("M5 bars exist, but no qualified sweep->MSS confirmation events were found in this range.")
            print("Try increasing history (ASIA_SWEEP_M5_HISTORY_MONTHS), adding more symbols, or widening your sweep/confirm windows.")
        # Still write an empty CSV with header for reproducibility
        pd.DataFrame(columns=["t0", "symbol", "label"] + FEATURE_COLS).to_csv(out_path, index=False)
        return

    df = pd.DataFrame(all_rows)
    # Sort by t0 for time-splits downstream
    df["t0"] = pd.to_datetime(df["t0"], errors="coerce", utc=True)
    df = df.dropna(subset=["t0"])
    df = df.sort_values("t0").reset_index(drop=True)
    df.to_csv(out_path, index=False)
    print(f"Wrote dataset: {out_path} rows={len(df)}")


if __name__ == "__main__":
    main()
