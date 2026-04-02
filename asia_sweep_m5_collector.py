"""Asia Sweep London MSS: Dedicated TRUE M5 bars collector (MT5 -> outputs/*_m5.csv).

Why this exists:
- The generic `mt5_bg_collector.py` is for broader Fibtool analysis and should stay simple.
- The Asia Sweep London MSS strategy + ML dataset require TRUE M5 bars written to:
    outputs/<symbol_slug>_m5.csv

Usage:
  # one-off backfill + write
  python asia_sweep_m5_collector.py --once --symbols EURUSD,GBPUSD,BTCUSD

  # loop (recommended interval ~300s)
  python asia_sweep_m5_collector.py --symbols EURUSD,GBPUSD,BTCUSD --interval 300
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None

try:
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover
    mt5 = None

try:
    import config as _cfg
except Exception:  # pragma: no cover
    _cfg = None


ROOT = Path(__file__).resolve().parent
OUTPUTS_DIR = ROOT / "outputs"
AUDIT_JSONL = OUTPUTS_DIR / "asia_sweep_m5_collector.jsonl"

MAX_BATCH_BARS = 500_000  # safety cap


def _cfg_get(name: str, default):
    try:
        if _cfg is not None and hasattr(_cfg, name):
            v = getattr(_cfg, name)
            return default if v is None else v
    except Exception:
        pass
    return default


def symbol_slug(symbol: str) -> str:
    try:
        return "".join(ch if ch.isalnum() else "_" for ch in str(symbol)).lower().strip("_")
    except Exception:
        return str(symbol).replace("/", "_").replace(" ", "_").lower()


def _append_jsonl(path: Path, record: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception:
        pass


def _estimate_m5_bars_for_months(months: int) -> int:
    days = int(max(0, int(months)) * 30)
    # 12 M5 bars per hour
    return min(max(0, days * 24 * 12), MAX_BATCH_BARS)


def ensure_mt5_connected() -> None:
    if mt5 is None:
        raise RuntimeError("MetaTrader5 package not installed (pip install MetaTrader5)")

    # Prefer config.py values, but allow falling back to env-driven MT5 initialize.
    mt5_path = _cfg_get("MT5_PATH", None)
    mt5_login = _cfg_get("MT5_LOGIN", None)
    mt5_password = _cfg_get("MT5_PASSWORD", None)
    mt5_server = _cfg_get("MT5_SERVER", None)

    if mt5_path:
        ok = mt5.initialize(str(mt5_path))
    else:
        ok = mt5.initialize()
    if not ok:
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")

    # Many terminals are already logged-in; login is best-effort.
    try:
        if mt5_login and mt5_password and mt5_server:
            _ = mt5.login(int(mt5_login), password=str(mt5_password), server=str(mt5_server))
    except Exception:
        pass


def _normalize_bars_for_storage(df: "pd.DataFrame") -> "pd.DataFrame":
    out = df.copy()
    if "time" not in out.columns:
        out = out.reset_index()
        if "time" not in out.columns and len(out.columns) > 0:
            out.rename(columns={out.columns[0]: "time"}, inplace=True)
    if "time" not in out.columns:
        return pd.DataFrame(columns=["time"])

    # Normalize time to UTC and store as UTC-naive timestamps for compatibility with the strategy/dataset.
    out["time"] = pd.to_datetime(out["time"], errors="coerce", utc=True)
    out = out.dropna(subset=["time"])
    out["time"] = out["time"].dt.tz_convert("UTC").dt.tz_localize(None)

    out.sort_values("time", inplace=True)
    out.drop_duplicates(subset=["time"], keep="last", inplace=True)

    preferred = ["time", "open", "high", "low", "close", "volume", "point", "spread", "real_volume"]
    ordered = [c for c in preferred if c in out.columns]
    ordered.extend([c for c in out.columns if c not in ordered])
    out = out[ordered]
    out.reset_index(drop=True, inplace=True)
    return out


def upsert_bars_csv(
    df: "pd.DataFrame",
    *,
    out_path: Path,
    keep_rows: int,
) -> int:
    incoming = _normalize_bars_for_storage(df)
    if incoming.empty:
        return 0

    existing = pd.DataFrame()
    if out_path.exists():
        try:
            existing = pd.read_csv(out_path, parse_dates=["time"])
            existing = _normalize_bars_for_storage(existing)
        except Exception:
            existing = pd.DataFrame()

    if existing.empty:
        merged = incoming
    else:
        merged = pd.concat([existing, incoming], ignore_index=True, sort=False)
        merged = _normalize_bars_for_storage(merged)

    keep_rows = int(max(len(incoming), int(keep_rows)))
    if keep_rows > 0 and len(merged) > keep_rows:
        merged = merged.iloc[-keep_rows:].reset_index(drop=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out_path, index=False, date_format="%Y-%m-%d %H:%M:%S")
    return int(len(incoming))


def _infer_point(symbol: str) -> float:
    pt = None
    try:
        info = mt5.symbol_info(symbol)
        if info is not None:
            pt = getattr(info, "trade_tick_size", None) or getattr(info, "point", None)
    except Exception:
        pt = None
    if pt is None:
        return 0.0
    try:
        return float(pt)
    except Exception:
        return 0.0


def fetch_m5_bars(symbol: str, count: int) -> "pd.DataFrame":
    if pd is None:
        raise RuntimeError("pandas is required (pip install pandas)")
    if mt5 is None:
        raise RuntimeError("MetaTrader5 package not installed (pip install MetaTrader5)")

    try:
        mt5.symbol_select(symbol, True)
    except Exception:
        pass

    utc_to = datetime.now(timezone.utc)
    rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_M5, utc_to, int(count))
    if rates is None or len(rates) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(rates)
    # time (seconds) -> datetime
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)

    # Standardize columns expected by the rest of the toolchain.
    if "tick_volume" in df.columns and "volume" not in df.columns:
        df.rename(columns={"tick_volume": "volume"}, inplace=True)

    for c in ("open", "high", "low", "close"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(float)

    if "point" not in df.columns:
        df["point"] = float(_infer_point(symbol))

    return df


@dataclass
class CollectorConfig:
    symbols: list[str]
    interval_s: int = 300
    history_months: int = 3
    fetch_bars_per_cycle: int = 2000


def run_once(cfg: CollectorConfig) -> None:
    ensure_mt5_connected()

    keep_rows = _estimate_m5_bars_for_months(int(cfg.history_months))
    if keep_rows <= 0:
        keep_rows = 10_000  # safe-ish default

    for sym in cfg.symbols:
        started = datetime.now(timezone.utc)
        slug = symbol_slug(sym)
        out_path = OUTPUTS_DIR / f"{slug}_m5.csv"
        first_run = not out_path.exists()
        requested = keep_rows if first_run else int(cfg.fetch_bars_per_cycle)
        status = "ok"
        err = None
        fetched_rows = 0
        written_incoming = 0

        try:
            df = fetch_m5_bars(sym, requested)
            fetched_rows = int(len(df)) if hasattr(df, "__len__") else 0
            if (first_run and fetched_rows == 0) and requested != int(cfg.fetch_bars_per_cycle):
                # Fallback for terminals that can't serve a large initial backfill in one request.
                df = fetch_m5_bars(sym, int(cfg.fetch_bars_per_cycle))
                fetched_rows = int(len(df)) if hasattr(df, "__len__") else 0
            if fetched_rows > 0:
                written_incoming = upsert_bars_csv(df, out_path=out_path, keep_rows=keep_rows)
        except Exception as e:
            status = "error"
            err = str(e)

        finished = datetime.now(timezone.utc)
        _append_jsonl(
            AUDIT_JSONL,
            {
                "time": finished.isoformat(),
                "symbol": sym,
                "path": str(out_path),
                "status": status,
                "first_run": bool(first_run),
                "requested": int(requested),
                "fetched_rows": int(fetched_rows),
                "written_incoming": int(written_incoming),
                "elapsed_s": (finished - started).total_seconds(),
                "error": err,
            },
        )

        if status == "ok":
            print(f"[asia_m5] {sym}: fetched={fetched_rows} upserted={written_incoming} keep_rows={keep_rows} -> {out_path.name}")
        else:
            print(f"[asia_m5] {sym}: ERROR {err}")

    try:
        mt5.shutdown()
    except Exception:
        pass


def _default_symbols() -> list[str]:
    # Prefer symbols_timeframes.json when present (same behavior as scripts/run_asia_sweep.py)
    st_path = ROOT / "symbols_timeframes.json"
    if st_path.exists():
        try:
            data = json.loads(st_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("symbols"), list):
                return [s for s in data["symbols"] if isinstance(s, str) and s.strip()]
        except Exception:
            pass

    # Fallback
    return ["EURUSD", "GBPUSD", "USDJPY"]


def main() -> None:
    ap = argparse.ArgumentParser(description="Asia Sweep London MSS M5 bars collector")
    ap.add_argument("--once", action="store_true", help="Run a single fetch/upsert cycle and exit")
    ap.add_argument("--interval", type=int, default=300, help="Loop interval seconds (default 300)")
    ap.add_argument("--symbols", type=str, default="", help="Comma-separated symbols (default from symbols_timeframes.json)")
    ap.add_argument("--history-months", type=int, default=None, help="Backfill history months for *_m5.csv (default from config or 3)")
    ap.add_argument("--fetch-bars", type=int, default=None, help="Bars per cycle after first run (default from config or 2000)")
    args = ap.parse_args()

    symbols = []
    if str(args.symbols or "").strip():
        symbols = [s.strip() for s in str(args.symbols).split(",") if s.strip()]
    if not symbols:
        symbols = _default_symbols()

    history_months = int(args.history_months) if args.history_months is not None else int(_cfg_get("ASIA_SWEEP_M5_HISTORY_MONTHS", 3))
    fetch_n = int(args.fetch_bars) if args.fetch_bars is not None else int(_cfg_get("ASIA_SWEEP_M5_FETCH_BARS_PER_CYCLE", 2000))

    cfg = CollectorConfig(symbols=symbols, interval_s=int(args.interval), history_months=history_months, fetch_bars_per_cycle=fetch_n)

    if args.once:
        run_once(cfg)
        return

    while True:
        try:
            run_once(cfg)
        except KeyboardInterrupt:
            break
        except Exception as e:
            _append_jsonl(AUDIT_JSONL, {"time": datetime.now(timezone.utc).isoformat(), "status": "fatal", "error": str(e)})
        time.sleep(max(1, int(cfg.interval_s)))


if __name__ == "__main__":
    main()
