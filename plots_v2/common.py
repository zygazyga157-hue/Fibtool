from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

import pandas as pd


def symbol_slug(symbol: str) -> str:
    try:
        return "".join(ch if ch.isalnum() else "_" for ch in str(symbol)).lower().strip("_")
    except Exception:
        return str(symbol).replace("/", "_").replace(" ", "_").lower()


def symbol_tf_slug(symbol: str, timeframe: str | None) -> str:
    base = symbol_slug(symbol)
    if timeframe:
        return f"{base}_{str(timeframe).lower()}"
    return base


def ensure_outputs_dir(outputs_dir: Path) -> None:
    outputs_dir.mkdir(parents=True, exist_ok=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        s = str(value).strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def load_jsonl_latest(path: Path, *, symbol: str | None = None, asof_utc: str | None = None) -> Optional[dict]:
    if not path.exists():
        return None
    wanted = str(symbol).upper() if symbol else None
    asof_dt = parse_iso_dt(asof_utc) if asof_utc else None
    latest: Optional[dict] = None
    latest_dt: Optional[datetime] = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if wanted and str(rec.get("symbol", "")).upper() != wanted:
                continue
            dt = parse_iso_dt(rec.get("timestamp") or rec.get("created_ts_utc") or rec.get("created_ts"))
            if dt is None:
                continue
            if asof_dt is not None and dt > asof_dt:
                continue
            if latest is None or latest_dt is None or dt > latest_dt:
                latest = rec
                latest_dt = dt
    return latest


def load_bars(
    outputs_dir: Path,
    symbol: str,
    timeframe: str | None = None,
    *,
    asof_utc: str | None = None,
) -> pd.DataFrame:
    """Load bars for symbol/timeframe from outputs.

    Supports:
    - outputs/<symbol>_<timeframe>_bars.csv (legacy V1 V2 slug style)
    - outputs/<symbol>_bars.csv
    """
    slug_tf = symbol_tf_slug(symbol, timeframe)
    slug = symbol_slug(symbol)
    candidates: list[Path] = []
    if timeframe:
        candidates.extend(
            [
                outputs_dir / f"{slug_tf}_bars.csv",
                outputs_dir / f"{slug}_{str(timeframe).lower()}_bars.csv",
            ]
        )
    candidates.append(outputs_dir / f"{slug}_bars.csv")

    chosen: Optional[Path] = next((p for p in candidates if p.exists()), None)
    if not chosen:
        return pd.DataFrame()

    df = pd.read_csv(chosen)
    if "time" not in df.columns and "timestamp" in df.columns:
        df = df.rename(columns={"timestamp": "time"})

    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    else:
        # minimal fallback
        df["time"] = pd.NaT

    for c in ("open", "high", "low", "close", "volume"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.dropna(subset=["time", "open", "high", "low", "close"]).sort_values("time").reset_index(drop=True)

    # Replay/as-of support: truncate future candles.
    if asof_utc:
        dt = parse_iso_dt(asof_utc)
        if dt is not None:
            try:
                cutoff = pd.Timestamp(dt)
                df = df[df["time"] <= cutoff].reset_index(drop=True)
            except Exception:
                pass
    return df


def infer_point(df: pd.DataFrame) -> float:
    """Infer instrument point (tick size) from bars or decimals."""
    try:
        if "point" in df.columns and df["point"].notna().any():
            return float(df["point"].dropna().iloc[-1])
    except Exception:
        pass
    try:
        if not df.empty and "close" in df.columns:
            sample = float(df["close"].iloc[-1])
            s = f"{sample:.10f}"
            if "." in s:
                dec = len(s.rstrip("0").split(".")[-1])
                dec = min(max(dec, 1), 10)
                return 10 ** (-dec)
    except Exception:
        pass
    return 0.01


def calc_atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    try:
        if df.empty or len(df) < period + 1:
            return None
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        close = df["close"].astype(float)
        prev_close = close.shift(1)
        tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        atr = tr.rolling(int(period)).mean().iloc[-1]
        return float(atr) if pd.notna(atr) else None
    except Exception:
        return None


def detect_pivots(df: pd.DataFrame, left: int = 5, right: int = 5) -> pd.DataFrame:
    """Mark pivot highs/lows similarly to `plots/degree_factor_angles_plot.py`."""
    if df.empty or len(df) < left + right + 1:
        return df
    out = df.copy()
    out["pivot_low"] = 0.0
    out["pivot_high"] = 0.0
    for i in range(left, len(out) - right):
        ch = float(out.loc[i, "high"])
        cl = float(out.loc[i, "low"])
        is_h = True
        is_l = True
        for j in range(i - left, i):
            if float(out.loc[j, "high"]) > ch:
                is_h = False
            if float(out.loc[j, "low"]) < cl:
                is_l = False
        if is_h:
            for j in range(i + 1, i + right + 1):
                if float(out.loc[j, "high"]) > ch:
                    is_h = False
                    break
        if is_l:
            for j in range(i + 1, i + right + 1):
                if float(out.loc[j, "low"]) < cl:
                    is_l = False
                    break
        if is_h:
            out.loc[i, "pivot_high"] = ch
        if is_l:
            out.loc[i, "pivot_low"] = cl
    return out


def json_serialize(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, (datetime,)):
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=timezone.utc)
        return obj.isoformat()
    return obj


def dumps_compact(obj: Any) -> str:
    return json.dumps(obj, default=json_serialize, separators=(",", ":"), ensure_ascii=False)


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))
