import argparse
import csv
import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

import numpy as np
import pandas as pd

from supertrend import SuperTrend
from utbot import UTBot
from fib_square_strategy import FibonacciSquareOfNine


DEFAULT_BARS_CSV = os.path.join("outputs", "xauusd_bars.csv")
ENTRIES_CSV = os.path.join("outputs", "entries.csv")


@dataclass
class Entry:
    timestamp: str
    symbol: str
    timeframe: str
    side: Literal["long", "short"]
    entry_price: float
    tp: float
    sl: float
    atr: Optional[float]
    st_trend: Optional[int]
    ut_signal: Optional[int]
    st_up: Optional[float]
    st_down: Optional[float]
    comment: str = ""
    pivot_low: Optional[float] = None
    pivot_high: Optional[float] = None
    tp_source: Optional[str] = None
    sl_source: Optional[str] = None
    signal_type: Optional[str] = None
    rr: Optional[float] = None
    tp_dist_atr: Optional[float] = None
    sl_dist_atr: Optional[float] = None

    def id(self) -> str:
        base = f"{self.timestamp}|{self.symbol}|{self.timeframe}|{self.side}|{round(self.entry_price, 5)}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()


def _ensure_outputs_dir():
    os.makedirs("outputs", exist_ok=True)


def _load_bars(csv_path: str) -> pd.DataFrame:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Bars CSV not found: {csv_path}. Run mt5_bg_collector.py to generate it.")
    df = pd.read_csv(csv_path)
    # Normalize columns
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # Parse time
    if "time" in df.columns:
        if np.issubdtype(df["time"].dtype, np.number):
            # likely epoch seconds
            df["time"] = pd.to_datetime(df["time"], unit="s")
        else:
            df["time"] = pd.to_datetime(df["time"], errors="coerce")
    else:
        # Create an index-based time if missing
        df["time"] = pd.RangeIndex(start=0, stop=len(df), step=1)
    # Point value
    if "point" not in df.columns or df["point"].isna().all():
        # Infer price decimals from data
        price_decimals = 2 if df["close"].max() > 100 else 5
        df["point"] = 10 ** (-price_decimals)
    return df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)


def _pick_tp_sl_from_confluences(
    confluences: list[dict],
    entry_price: float,
    side: Literal["long", "short"],
    pivot_low: Optional[float],
    pivot_high: Optional[float],
    atr: Optional[float] = None,
    max_distance_atr: float = 5.0,
    nearest_multiplier: float = 3.0,
):
    # Extract price field robustly
    prices = []
    for z in confluences or []:
        p = (
            z.get("confluence_price")
            or z.get("price")
            or z.get("level_price")
            or z.get("level")
        )
        if p is not None:
            prices.append(float(p))

    tp = None
    sl = None
    tp_src = None
    sl_src = None

    if side == "long":
        above = [p for p in prices if p > entry_price]
        below = [p for p in prices if p < entry_price]
        if above:
            tp = min(above, key=lambda x: x - entry_price)
            tp_src = "confluence"
        if below:
            sl = max(below, key=lambda x: entry_price - x)
            sl_src = "confluence"
        # Fallbacks
        if tp is None and pivot_high is not None and float(pivot_high) > entry_price:
            tp = float(pivot_high)
            tp_src = "pivot_high"
        if sl is None and pivot_low is not None and float(pivot_low) < entry_price:
            sl = float(pivot_low)
            sl_src = "pivot_low"
        # ATR fallback if still missing or invalid side
        if tp is None and atr is not None:
            tp = entry_price + 1.5 * float(atr)
            tp_src = "atr_1.5x"
        if sl is None and atr is not None:
            sl = entry_price - 1.0 * float(atr)
            sl_src = "atr_1.0x"
    else:
        # short
        above = [p for p in prices if p > entry_price]
        below = [p for p in prices if p < entry_price]
        if below:
            tp = max(below, key=lambda x: entry_price - x)
            tp_src = "confluence"
        if above:
            sl = min(above, key=lambda x: x - entry_price)
            sl_src = "confluence"
        # Fallbacks
        if tp is None and pivot_low is not None and float(pivot_low) < entry_price:
            tp = float(pivot_low)
            tp_src = "pivot_low"
        if sl is None and pivot_high is not None and float(pivot_high) > entry_price:
            sl = float(pivot_high)
            sl_src = "pivot_high"
        # ATR fallback if still missing or invalid side
        if tp is None and atr is not None:
            tp = entry_price - 1.5 * float(atr)
            tp_src = "atr_1.5x"
        if sl is None and atr is not None:
            sl = entry_price + 1.0 * float(atr)
            sl_src = "atr_1.0x"

    return tp, sl, tp_src, sl_src


def _nearest_confluence_within_atr(confluences: list[dict], entry: float, side: str, atr: Optional[float], multiplier: float):
    if not confluences or atr is None:
        return None
    max_dist = atr * multiplier
    candidates = []
    for z in confluences:
        p = z.get("confluence_price") or z.get("price") or z.get("level_price") or z.get("level")
        if p is None:
            continue
        try:
            p = float(p)
        except Exception:
            continue
        if side == "long" and p <= entry:
            continue
        if side == "short" and p >= entry:
            continue
        dist = abs(p - entry)
        if dist <= max_dist:
            candidates.append((dist, p))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def _load_existing_ids(entries_path: str) -> set[str]:
    if not os.path.exists(entries_path):
        return set()
    try:
        df = pd.read_csv(entries_path)
        if "entry_id" in df.columns:
            return set(df["entry_id"].astype(str).tolist())
        # Backward compat build ids
        required = {"timestamp", "symbol", "timeframe", "side", "entry_price"}
        if required.issubset(df.columns):
            built = set()
            for _, r in df.iterrows():
                base = f"{r['timestamp']}|{r['symbol']}|{r['timeframe']}|{r['side']}|{round(float(r['entry_price']),5)}"
                built.add(hashlib.sha1(base.encode("utf-8")).hexdigest())
            return built
    except Exception:
        return set()
    return set()


def _append_entries(entries: list[Entry]):
    _ensure_outputs_dir()
    existing_ids = _load_existing_ids(ENTRIES_CSV)

    fieldnames = [
        "entry_id",
        "timestamp",
        "symbol",
        "timeframe",
        "side",
        "entry_price",
        "tp",
        "sl",
        "atr",
        "st_trend",
        "ut_signal",
        "st_up",
        "st_down",
        "signal_type",
        "rr",
        "tp_dist_atr",
        "sl_dist_atr",
        "pivot_low",
        "pivot_high",
        "tp_source",
        "sl_source",
        "comment",
    ]

    write_header = not os.path.exists(ENTRIES_CSV)
    with open(ENTRIES_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        added = 0
        for e in entries:
            eid = e.id()
            if eid in existing_ids:
                continue
            # Validate TP/SL ordering vs side
            def _is_valid_tp_sl(side, entry, tp, sl):
                try:
                    entry = float(entry)
                    tp = float(tp)
                    sl = float(sl)
                except Exception:
                    return False
                if side == "long":
                    return (sl < entry) and (tp > entry)
                else:
                    return (sl > entry) and (tp < entry)

            if not _is_valid_tp_sl(e.side, e.entry_price, e.tp if e.tp is not None else e.entry_price, e.sl if e.sl is not None else e.entry_price):
                # Log rejected entry for audit
                rej_path = os.path.join("outputs", "entries_rejected.csv")
                write_rej_header = not os.path.exists(rej_path)
                with open(rej_path, "a", newline="", encoding="utf-8") as rf:
                    import csv as _csv
                    rfields = ["timestamp","symbol","timeframe","side","entry_price","tp","sl","atr","reason"]
                    rw = _csv.DictWriter(rf, fieldnames=rfields)
                    if write_rej_header:
                        rw.writeheader()
                    rw.writerow({"timestamp": e.timestamp, "symbol": e.symbol, "timeframe": e.timeframe, "side": e.side, "entry_price": e.entry_price, "tp": e.tp, "sl": e.sl, "atr": e.atr, "reason": "invalid-tp-sl"})
                continue
            row = {
                "entry_id": eid,
                "timestamp": e.timestamp,
                "symbol": e.symbol,
                "timeframe": e.timeframe,
                "side": e.side,
                "entry_price": round(e.entry_price, 5),
                "tp": round(e.tp, 5) if e.tp is not None else None,
                "sl": round(e.sl, 5) if e.sl is not None else None,
                "atr": round(e.atr, 5) if e.atr is not None else None,
                "st_trend": e.st_trend,
                "ut_signal": e.ut_signal,
                "st_up": round(e.st_up, 5) if e.st_up is not None else None,
                "st_down": round(e.st_down, 5) if e.st_down is not None else None,
                "signal_type": "buy" if e.side == "long" else "sell",
                "rr": round(e.rr, 3) if (getattr(e, 'rr', None) is not None) else None,
                "tp_dist_atr": round(e.tp_dist_atr, 3) if (getattr(e, 'tp_dist_atr', None) is not None) else None,
                "sl_dist_atr": round(e.sl_dist_atr, 3) if (getattr(e, 'sl_dist_atr', None) is not None) else None,
                "pivot_low": round(e.pivot_low, 5) if e.pivot_low is not None else None,
                "pivot_high": round(e.pivot_high, 5) if e.pivot_high is not None else None,
                "tp_source": e.tp_source,
                "sl_source": e.sl_source,
                "comment": e.comment,
            }
            writer.writerow(row)
            existing_ids.add(eid)
            added += 1
    return True


def detect_entries(
    df: pd.DataFrame,
    symbol: str = "XAUUSD",
    timeframe: str = "H1",
    st_period: int = 10,
    st_multiplier: float = 3.0,
    ut_atr_coef: float = 2.0,
    ut_atr_len: int = 1,
    confirmation_window: int = 0,
    rr_min: float = 1.2,
    rr_max: float = 6.0,
    max_distance_atr: float = 5.0,
    nearest_multiplier: float = 3.0,
) -> list[Entry]:
    """
    Detect entries where SuperTrend AND UTBot agree on the same bar.

    confirmation_window: if >0, allow confirmation within N previous bars (0 = same bar only).
    """
    # Prepare indicators - infer decimals from price range (forex=5, gold=2, etc.)
    price_decimals = 2 if df["close"].max() > 100 else 5
    point_val = df.get("point", pd.Series([10 ** -price_decimals] * len(df))).iloc[-1]

    st = SuperTrend(period=st_period, multiplier=st_multiplier, price_decimals=price_decimals, point_value=point_val)
    ut = UTBot(atr_coef=ut_atr_coef, atr_len=ut_atr_len, price_decimals=price_decimals, point_value=point_val)

    st_df = st.calculate(df)
    st_sig = st.generate_signals(st_df)
    ut_df = ut.calculate(df)
    ut_sig = ut.generate_signals(ut_df)

    # Merge for convenience
    merged = df.copy()
    merged = merged.join(st_df[["atr", "supertrend_up", "supertrend_down", "supertrend_trend"]])
    merged = merged.join(st_sig[["signal" ]].rename(columns={"signal": "st_signal"}))
    merged = merged.join(ut_sig[["signal"]].rename(columns={"signal": "ut_signal"}))

    entries: list[Entry] = []

    s9 = FibonacciSquareOfNine()

    for i in range(len(merged)):
        st_s = int(merged.loc[i, "st_signal"]) if not pd.isna(merged.loc[i, "st_signal"]) else 0
        ut_s = int(merged.loc[i, "ut_signal"]) if not pd.isna(merged.loc[i, "ut_signal"]) else 0

        # Allow lookback confirmation across the last N bars including current
        if confirmation_window > 0:
            start_idx = max(0, i - confirmation_window)
            st_window = merged.loc[start_idx: i, "st_signal"].fillna(0).astype(int)
            ut_window = merged.loc[start_idx: i, "ut_signal"].fillna(0).astype(int)
            st_long = (st_window == 1).any()
            st_short = (st_window == -1).any()
            ut_long = (ut_window == 1).any()
            ut_short = (ut_window == -1).any()
        else:
            st_long = st_s == 1
            st_short = st_s == -1
            ut_long = ut_s == 1
            ut_short = ut_s == -1

        side: Optional[str] = None
        if st_long and ut_long:
            side = "long"
        elif st_short and ut_short:
            side = "short"

        if side is None:
            continue

        sub = df.iloc[: i + 1].copy()
        try:
            analysis = s9.analyze_market(sub)
        except Exception:
            analysis = {}

        strong_conf = analysis.get("strong_confluence_zones") or analysis.get("confluence_zones") or []
        pivot_low = analysis.get("pivot_low")
        pivot_high = analysis.get("pivot_high")

        entry_price = float(df.loc[i, "close"])
        # Use current bar ATR for robust fallback
        cur_atr = float(merged.loc[i, "atr"]) if not pd.isna(merged.loc[i, "atr"]) else None
        # Prefer nearest confluence within K*ATR
        tp_candidate = _nearest_confluence_within_atr(strong_conf, entry_price, "long" if side == "long" else "short", cur_atr, nearest_multiplier)
        if tp_candidate is None:
            # fallback to broad picker logic
            tp, sl, tp_src, sl_src = _pick_tp_sl_from_confluences(
                strong_conf, entry_price, side, pivot_low, pivot_high, cur_atr
            )
        else:
            # If we found a nearby confluence, pick it as TP for long, or TP for short accordingly
            if side == "long":
                tp = float(tp_candidate)
                sl = None
            else:
                tp = float(tp_candidate)
                sl = None
            tp_src = "confluence_nearby"
            sl_src = None

        # If SL or TP still missing, apply ATR fallback as before
        if (tp is None or sl is None):
            tp, sl, tp_src_f, sl_src_f = _pick_tp_sl_from_confluences(strong_conf, entry_price, side, pivot_low, pivot_high, cur_atr)
            # fill any missing
            if tp is None:
                tp = tp or tp_src_f
                tp_src = tp_src or tp_src_f
            if sl is None:
                sl = sl or sl_src_f
                sl_src = sl_src or sl_src_f

        # Compute distances in ATR units and rr
        try:
            tp_dist = abs(tp - entry_price)
        except Exception:
            tp_dist = None
        try:
            sl_dist = abs(sl - entry_price)
        except Exception:
            sl_dist = None
        tp_dist_atr = (tp_dist / cur_atr) if (tp_dist is not None and cur_atr) else None
        sl_dist_atr = (sl_dist / cur_atr) if (sl_dist is not None and cur_atr) else None
        rr = (tp_dist / sl_dist) if (tp_dist is not None and sl_dist not in (None, 0)) else None

        # Enforce rr and max distance constraints
        reject_reason = None
        if rr is not None and (rr < rr_min or rr > rr_max):
            reject_reason = f"rr_out_of_bounds:{rr:.2f}"
        if tp_dist_atr is not None and tp_dist_atr > max_distance_atr:
            reject_reason = reject_reason or f"tp_too_far:{tp_dist_atr:.2f}xATR"
        if sl_dist_atr is not None and sl_dist_atr > max_distance_atr:
            reject_reason = reject_reason or f"sl_too_far:{sl_dist_atr:.2f}xATR"

        if reject_reason:
            # Log rejection
            rej_path = os.path.join("outputs", "entries_rejected.csv")
            write_rej_header = not os.path.exists(rej_path)
            with open(rej_path, "a", newline="", encoding="utf-8") as rf:
                import csv as _csv
                rfields = ["timestamp","symbol","timeframe","side","entry_price","tp","sl","atr","reason","rr","tp_dist_atr","sl_dist_atr"]
                rw = _csv.DictWriter(rf, fieldnames=rfields)
                if write_rej_header:
                    rw.writeheader()
                # compute timestamp string for this row
                ts_val_local = sub.loc[i, "time"]
                if isinstance(ts_val_local, (np.integer, int, float)):
                    ts_local = datetime.utcfromtimestamp(float(ts_val_local)).isoformat()
                else:
                    try:
                        ts_local = pd.to_datetime(ts_val_local).isoformat()
                    except Exception:
                        ts_local = str(ts_val_local)
                rw.writerow({
                    "timestamp": ts_local,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "side": side,
                    "entry_price": entry_price,
                    "tp": tp,
                    "sl": sl,
                    "atr": cur_atr,
                    "reason": reject_reason,
                    "rr": rr,
                    "tp_dist_atr": tp_dist_atr,
                    "sl_dist_atr": sl_dist_atr,
                })
            continue

        ts_val = sub.loc[i, "time"]
        if isinstance(ts_val, (np.integer, int, float)):
            # epoch seconds
            ts = datetime.utcfromtimestamp(float(ts_val)).isoformat()
        else:
            try:
                ts = pd.to_datetime(ts_val).isoformat()
            except Exception:
                ts = str(ts_val)

        e = Entry(
            timestamp=ts,
            symbol=symbol,
            timeframe=timeframe,
            side=side,
            entry_price=entry_price,
            tp=tp if tp is not None else entry_price,  # avoid None
            sl=sl if sl is not None else entry_price,
            atr=float(merged.loc[i, "atr"]) if not pd.isna(merged.loc[i, "atr"]) else None,
            st_trend=int(merged.loc[i, "supertrend_trend"]) if not pd.isna(merged.loc[i, "supertrend_trend"]) else None,
            ut_signal=int(merged.loc[i, "ut_signal"]) if not pd.isna(merged.loc[i, "ut_signal"]) else None,
            st_up=float(merged.loc[i, "supertrend_up"]) if not pd.isna(merged.loc[i, "supertrend_up"]) else None,
            st_down=float(merged.loc[i, "supertrend_down"]) if not pd.isna(merged.loc[i, "supertrend_down"]) else None,
            comment="ST+UT alignment",
            pivot_low=float(pivot_low) if pivot_low is not None else None,
            pivot_high=float(pivot_high) if pivot_high is not None else None,
            tp_source=tp_src,
            sl_source=sl_src,
            signal_type=("buy" if side == "long" else "sell"),
            rr=rr,
            tp_dist_atr=tp_dist_atr,
            sl_dist_atr=sl_dist_atr,
        )
        entries.append(e)

    return entries


def main():
    parser = argparse.ArgumentParser(description="Detect entries using SuperTrend + UTBot with S9 TP/SL")
    parser.add_argument("--bars", default=DEFAULT_BARS_CSV, help="Path to OHLCV CSV (default: outputs/xauusd_bars.csv)")
    parser.add_argument("--symbol", default="XAUUSD", help="Symbol name for logging")
    parser.add_argument("--timeframe", default="H1", help="Timeframe label for logging")
    parser.add_argument("--st-period", type=int, default=14)
    parser.add_argument("--st-multiplier", type=float, default=3.0)
    parser.add_argument("--ut-atr-coef", type=float, default=2.0)
    parser.add_argument("--ut-atr-len", type=int, default=1)
    parser.add_argument("--confirm-window", type=int, default=0, help="Bars to allow confirmation across (0=same bar)")
    parser.add_argument("--dry-run", action="store_true", help="Print number of entries without saving")
    parser.add_argument("--report", action="store_true", help="Print diagnostics about signals and alignment")
    args = parser.parse_args()

    df = _load_bars(args.bars)
    entries = detect_entries(
        df,
        symbol=args.symbol,
        timeframe=args.timeframe,
        st_period=args.st_period,
        st_multiplier=args.st_multiplier,
        ut_atr_coef=args.ut_atr_coef,
        ut_atr_len=args.ut_atr_len,
        confirmation_window=args.confirm_window,
    )

    if args.report:
        # Build indicators for reporting - infer decimals from price range
        price_decimals = 2 if df["close"].max() > 100 else 5
        point_val = df.get("point", pd.Series([10 ** -price_decimals] * len(df))).iloc[-1]
        st = SuperTrend(period=args.st_period, multiplier=args.st_multiplier, price_decimals=price_decimals, point_value=point_val)
        ut = UTBot(atr_coef=args.ut_atr_coef, atr_len=args.ut_atr_len, price_decimals=price_decimals, point_value=point_val)
        st_df = st.calculate(df)
        st_sig = st.generate_signals(st_df)
        ut_df = ut.calculate(df)
        ut_sig = ut.generate_signals(ut_df)

        rep = pd.DataFrame({
            "time": df.get("time", pd.RangeIndex(len(df))),
            "close": df["close"],
            "st_signal": st_sig["signal"],
            "st_trend": st_df["supertrend_trend"],
            "ut_signal": ut_sig["signal"],
        })
        st_buys = int((rep["st_signal"] == 1).sum())
        st_sells = int((rep["st_signal"] == -1).sum())
        ut_buys = int((rep["ut_signal"] == 1).sum())
        ut_sells = int((rep["ut_signal"] == -1).sum())

        # Intersection on same bar
        same_long = int(((rep["st_signal"] == 1) & (rep["ut_signal"] == 1)).sum())
        same_short = int(((rep["st_signal"] == -1) & (rep["ut_signal"] == -1)).sum())

        print("--- Entry diagnostics ---")
        print(f"Rows: {len(rep)}")
        print(f"SuperTrend signals -> buys: {st_buys}, sells: {st_sells}")
        print(f"UTBot signals      -> buys: {ut_buys}, sells: {ut_sells}")
        print(f"Same-bar alignment -> long: {same_long}, short: {same_short}")
        if args.confirm_window > 0:
            # Compute windowed alignment stats
            win = args.confirm_window
            long_count = 0
            short_count = 0
            st_sig_vals = rep["st_signal"].fillna(0).astype(int).to_numpy()
            ut_sig_vals = rep["ut_signal"].fillna(0).astype(int).to_numpy()
            for i in range(len(rep)):
                s = max(0, i - win)
                st_long = (st_sig_vals[s:i+1] == 1).any()
                st_short = (st_sig_vals[s:i+1] == -1).any()
                ut_long = (ut_sig_vals[s:i+1] == 1).any()
                ut_short = (ut_sig_vals[s:i+1] == -1).any()
                if st_long and ut_long:
                    long_count += 1
                if st_short and ut_short:
                    short_count += 1
            print(f"Window({win}) alignment -> long: {long_count}, short: {short_count}")

        print("Last 10 bars (time, close, st_signal, st_trend, ut_signal):")
        tail = rep.tail(10)
        for _, r in tail.iterrows():
            tval = r["time"]
            try:
                tdisp = pd.to_datetime(tval).isoformat()
            except Exception:
                tdisp = str(tval)
            print(f"{tdisp} | close={r['close']:.5f} | ST={int(r['st_signal'])} (trend={int(r['st_trend'])}) | UT={int(r['ut_signal'])}")

    if args.dry_run:
        print(f"Detected {len(entries)} entries (dry-run)")
        # Preview last 5
        for e in entries[-5:]:
            print(e)
        return

    _append_entries(entries)
    print(f"Saved entries: {len(entries)} -> {ENTRIES_CSV}")


if __name__ == "__main__":
    main()
