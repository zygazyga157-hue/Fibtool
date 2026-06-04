from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd

try:
    from candlesticks.candlestick_signals import (
        _INDECISION_PATTERNS,
        _MOMENTUM_PATTERNS,
        _REVERSAL_PATTERNS,
        _count_pattern_class,
        generate_signal_from_summary,
        summarize_latest_patterns,
    )
except Exception:  # pragma: no cover
    summarize_latest_patterns = None  # type: ignore[assignment]
    generate_signal_from_summary = None  # type: ignore[assignment]
    _count_pattern_class = None  # type: ignore[assignment]
    _MOMENTUM_PATTERNS = frozenset()
    _REVERSAL_PATTERNS = frozenset()
    _INDECISION_PATTERNS = frozenset()


STRUCTURAL_FEATURE_COLS: list[str] = [
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
    "day_of_week",
    "sweep_depth_x_asia_atr",
    "confirm_body_ratio",
    "rr_capped",
    "sweep_velocity_atr",
    "multi_touch",
    "entry_stop_atr",
]

CANDLE_FEATURE_COLS: list[str] = [
    "m5_candle_score",
    "m5_candle_dir",
    "m5_candle_alignment",
    "m5_candle_abs_score",
    "m5_candle_age_bars",
    "m5_candle_recent_count",
    "m5_candle_momentum_count",
    "m5_candle_reversal_count",
    "m5_candle_indecision_count",
    "m5_confirm_body_atr",
    "m5_confirm_upper_wick_atr",
    "m5_confirm_lower_wick_atr",
    "m5_confirm_range_atr",
    "m15_candle_score",
    "m15_candle_dir",
    "m15_candle_alignment",
    "m15_candle_abs_score",
    "m15_candle_age_bars",
    "m15_candle_recent_count",
    "m15_candle_momentum_count",
    "m15_candle_reversal_count",
    "m15_candle_indecision_count",
]

FEATURE_COLS: list[str] = STRUCTURAL_FEATURE_COLS + CANDLE_FEATURE_COLS


@dataclass
class FeatureBundle:
    features: dict[str, float]
    diagnostics: dict[str, Any]


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return float(default)
    return out if math.isfinite(out) else float(default)


def _true_range(df: pd.DataFrame) -> pd.Series:
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    close = pd.to_numeric(df["close"], errors="coerce")
    prev_close = close.shift(1)
    return pd.concat([(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)


def atr_at(df: pd.DataFrame, t0: pd.Timestamp, period: int = 14) -> Optional[float]:
    try:
        if df is None or df.empty:
            return None
        work = df[["high", "low", "close"]].copy().sort_index()
        t = pd.to_datetime(t0)
        if getattr(work.index, "tz", None) is not None:
            if getattr(t, "tz", None) is None:
                t = t.tz_localize(work.index.tz)
            else:
                t = t.tz_convert(work.index.tz)
        work = work.loc[:t]
        if len(work) < max(2, int(period)):
            return None
        atr = _true_range(work).rolling(window=int(period), min_periods=int(period)).mean().iloc[-1]
        out = _finite_float(atr, default=0.0)
        return out if out > 0 else None
    except Exception:
        return None


def _bars_until(df: Optional[pd.DataFrame], t0: pd.Timestamp) -> Optional[pd.DataFrame]:
    if df is None or df.empty:
        return None
    try:
        out = df.copy().sort_index()
        t = pd.to_datetime(t0)
        if getattr(out.index, "tz", None) is not None:
            if getattr(t, "tz", None) is None:
                t = t.tz_localize(out.index.tz)
            else:
                t = t.tz_convert(out.index.tz)
        out = out.loc[:t].copy()
        if out.empty:
            return None
        out = out.reset_index()
        first = out.columns[0]
        if first != "time":
            out = out.rename(columns={first: "time"})
        return out
    except Exception:
        return None


def _direction_from_signal(signal: Optional[str]) -> int:
    sig = str(signal or "").strip().lower()
    if sig == "buy":
        return 1
    if sig == "sell":
        return -1
    return 0


def _pattern_names_from_top(top_patterns: Any) -> list[str]:
    out: list[str] = []
    for item in str(top_patterns or "").split(","):
        item = item.strip()
        if not item:
            continue
        out.append(item.split(":", 1)[0].strip().upper())
    return out


def _candle_context(
    df: Optional[pd.DataFrame],
    t0: pd.Timestamp,
    *,
    side_dir: int,
    prefix: str,
    window: int,
    enabled: bool,
) -> tuple[dict[str, float], dict[str, Any]]:
    values = {
        f"{prefix}_candle_score": 0.0,
        f"{prefix}_candle_dir": 0.0,
        f"{prefix}_candle_alignment": 0.0,
        f"{prefix}_candle_abs_score": 0.0,
        f"{prefix}_candle_age_bars": 999.0,
        f"{prefix}_candle_recent_count": 0.0,
        f"{prefix}_candle_momentum_count": 0.0,
        f"{prefix}_candle_reversal_count": 0.0,
        f"{prefix}_candle_indecision_count": 0.0,
    }
    diag: dict[str, Any] = {"enabled": bool(enabled), "missing": False, "signal": None, "score": 0.0}
    if not enabled:
        return values, diag

    bars = _bars_until(df, t0)
    if bars is None or len(bars) < 3 or summarize_latest_patterns is None or generate_signal_from_summary is None:
        diag["missing"] = True
        return values, diag

    try:
        summary = summarize_latest_patterns(bars, window=int(window))
        signal = generate_signal_from_summary(summary)
        score = _finite_float(signal.get("score") if isinstance(signal, dict) else 0.0)
        candle_dir = _direction_from_signal(signal.get("signal") if isinstance(signal, dict) else None)
        alignment = float(candle_dir * int(side_dir)) if candle_dir else 0.0
        top_names = _pattern_names_from_top(signal.get("top_patterns") if isinstance(signal, dict) else "")
        recent_count = 0
        last_idx = -1
        for meta in summary.values():
            bull = int(meta.get("bull_count", 0) or 0)
            bear = int(meta.get("bear_count", 0) or 0)
            recent_count += abs(bull) + abs(bear)
            try:
                last_idx = max(last_idx, int(meta.get("last_idx", -1) or -1))
            except Exception:
                pass
        age = (len(bars) - 1 - last_idx) if last_idx >= 0 else 999
        if _count_pattern_class is not None:
            momentum = _count_pattern_class(top_names, _MOMENTUM_PATTERNS)
            reversal = _count_pattern_class(top_names, _REVERSAL_PATTERNS)
            indecision = _count_pattern_class(top_names, _INDECISION_PATTERNS)
        else:
            momentum = reversal = indecision = 0

        values.update(
            {
                f"{prefix}_candle_score": float(score),
                f"{prefix}_candle_dir": float(candle_dir),
                f"{prefix}_candle_alignment": float(alignment),
                f"{prefix}_candle_abs_score": abs(float(score)),
                f"{prefix}_candle_age_bars": float(age),
                f"{prefix}_candle_recent_count": float(recent_count),
                f"{prefix}_candle_momentum_count": float(momentum),
                f"{prefix}_candle_reversal_count": float(reversal),
                f"{prefix}_candle_indecision_count": float(indecision),
            }
        )
        diag.update(
            {
                "signal": signal.get("signal") if isinstance(signal, dict) else None,
                "score": float(score),
                "alignment": float(alignment),
                "age_bars": float(age),
                "top_patterns": signal.get("top_patterns") if isinstance(signal, dict) else "",
                "recent_count": float(recent_count),
                "momentum": int(momentum),
                "reversal": int(reversal),
                "indecision": int(indecision),
            }
        )
    except Exception as exc:
        diag["missing"] = True
        diag["error"] = str(exc)
    return values, diag


def _confirm_shape_features(row: pd.Series, atr14: float) -> dict[str, float]:
    try:
        o = _finite_float(row["open"])
        h = _finite_float(row["high"])
        l = _finite_float(row["low"])
        c = _finite_float(row["close"])
        rng = max(0.0, h - l)
        body = abs(c - o)
        upper = h - max(o, c)
        lower = min(o, c) - l
        denom = float(atr14) if atr14 and atr14 > 0 else 1.0
        return {
            "m5_confirm_body_atr": body / denom,
            "m5_confirm_upper_wick_atr": max(0.0, upper) / denom,
            "m5_confirm_lower_wick_atr": max(0.0, lower) / denom,
            "m5_confirm_range_atr": rng / denom,
        }
    except Exception:
        return {
            "m5_confirm_body_atr": 0.0,
            "m5_confirm_upper_wick_atr": 0.0,
            "m5_confirm_lower_wick_atr": 0.0,
            "m5_confirm_range_atr": 0.0,
        }


def build_asia_sweep_feature_bundle(
    *,
    symbol: str,
    side: str,
    t0: pd.Timestamp,
    m5_session: pd.DataFrame,
    asia_high: float,
    asia_low: float,
    eqh_count: int,
    eql_count: int,
    sweep_time: Optional[pd.Timestamp],
    entry: float,
    stop: float,
    tp: Optional[float],
    confirm_window_bars: int,
    london_start: str,
    london_end: str,
    m15_utc: Optional[pd.DataFrame] = None,
    candle_features_enabled: bool = True,
    m15_context_enabled: bool = True,
) -> FeatureBundle:
    t0 = pd.to_datetime(t0)
    m5 = m5_session.copy().sort_index()
    m5_until = m5.loc[:t0].copy()
    if m5_until.empty:
        raise RuntimeError("No M5 bars available at t0")
    confirm_row = m5.loc[t0] if t0 in m5.index else m5_until.iloc[-1]
    atr14 = atr_at(m5, t0)
    if atr14 is None:
        raise RuntimeError("ATR14 unavailable for ML features")
    atr14 = float(atr14)

    side_n = str(side or "").strip().lower()
    is_long = side_n.startswith("long")
    side_dir = 1 if is_long else -1
    close_t0 = _finite_float(confirm_row.get("close"))
    c_high = _finite_float(confirm_row.get("high"))
    c_low = _finite_float(confirm_row.get("low"))
    confirm_range = max(0.0, c_high - c_low)
    asia_range = _finite_float(asia_high) - _finite_float(asia_low)

    sweep_depth_atr = 0.0
    if sweep_time is not None:
        try:
            st = pd.to_datetime(sweep_time)
            sweep_row = m5.loc[st] if st in m5.index else m5.loc[:st].iloc[-1]
            if is_long:
                sweep_depth_atr = (_finite_float(asia_low) - _finite_float(sweep_row["low"])) / atr14
            else:
                sweep_depth_atr = (_finite_float(sweep_row["high"]) - _finite_float(asia_high)) / atr14
        except Exception:
            sweep_depth_atr = 0.0

    try:
        ls = pd.Timestamp(f"{t0.date().isoformat()} {london_start}", tz=t0.tz).time()
        le = pd.Timestamp(f"{t0.date().isoformat()} {london_end}", tz=t0.tz).time()
        mins_from_open = (t0.time().hour * 60 + t0.time().minute) - (ls.hour * 60 + ls.minute)
        total_mins = max(1, (le.hour * 60 + le.minute) - (ls.hour * 60 + ls.minute))
        minutes_from_london_open = max(0.0, min(1.0, float(mins_from_open) / float(total_mins)))
    except Exception:
        minutes_from_london_open = 0.0

    bars_from_sweep = 0.0
    if sweep_time is not None:
        try:
            bars_from_sweep = float(int(round((t0 - pd.to_datetime(sweep_time)).total_seconds() / 300.0)))
        except Exception:
            bars_from_sweep = 0.0

    rr = 0.0
    try:
        rr = abs(float(tp) - float(entry)) / abs(float(entry) - float(stop)) if tp is not None and float(entry) != float(stop) else 0.0
    except Exception:
        rr = 0.0

    features = {
        "asia_range": float(asia_range),
        "atr14": float(atr14),
        "asia_range_atr": float(asia_range / atr14) if atr14 else 0.0,
        "eqh_touch_count": float(int(eqh_count)),
        "eql_touch_count": float(int(eql_count)),
        "sweep_dir": float(side_dir),
        "sweep_depth_atr": float(sweep_depth_atr),
        "minutes_from_london_open": float(minutes_from_london_open),
        "bars_from_sweep_to_mss": float(bars_from_sweep),
        "bars_from_sweep_to_mss_norm": float(bars_from_sweep) / float(max(1, int(confirm_window_bars))),
        "confirm_range_atr": float(confirm_range / atr14) if atr14 else 0.0,
        "entry_dist_atr": abs(float(entry) - float(close_t0)) / atr14 if atr14 else 0.0,
        "rr": float(rr),
        "day_of_week": float(t0.weekday()),
        "sweep_depth_x_asia_atr": float(sweep_depth_atr) * (float(asia_range / atr14) if atr14 else 0.0),
        "confirm_body_ratio": abs(float(close_t0) - _finite_float(confirm_row.get("open"))) / confirm_range if confirm_range > 0 else 0.0,
        "rr_capped": min(float(rr), 20.0),
        "sweep_velocity_atr": float(sweep_depth_atr) / float(bars_from_sweep) if bars_from_sweep > 0 else 0.0,
        "multi_touch": float(max(int(eqh_count), int(eql_count))),
        "entry_stop_atr": abs(float(entry) - float(stop)) / atr14 if atr14 else 0.0,
    }
    features.update(_confirm_shape_features(confirm_row, atr14))

    m5_candle_features, m5_diag = _candle_context(
        m5, t0, side_dir=side_dir, prefix="m5", window=3, enabled=bool(candle_features_enabled)
    )
    m15_candle_features, m15_diag = _candle_context(
        m15_utc, t0, side_dir=side_dir, prefix="m15", window=3,
        enabled=bool(candle_features_enabled and m15_context_enabled),
    )
    features.update(m5_candle_features)
    features.update(m15_candle_features)

    clean = {col: _finite_float(features.get(col), 0.0) for col in FEATURE_COLS}
    diagnostics = {
        "features_version": "v4_candles_m5_m15",
        "symbol": str(symbol),
        "side": "Long" if is_long else "Short",
        "t0": t0.isoformat() if hasattr(t0, "isoformat") else str(t0),
        "m5": m5_diag,
        "m15": m15_diag,
    }
    return FeatureBundle(features=clean, diagnostics=diagnostics)


def evaluate_candlestick_hard_block(
    diagnostics: dict[str, Any],
    *,
    enabled: bool,
    min_score: float,
    allow_neutral: bool,
) -> dict[str, Any]:
    out = {"enabled": bool(enabled), "blocked": False, "reason": None}
    if not enabled:
        return out
    m5 = diagnostics.get("m5") if isinstance(diagnostics, dict) else {}
    m15 = diagnostics.get("m15") if isinstance(diagnostics, dict) else {}
    contexts = [c for c in (m5, m15) if isinstance(c, dict) and c.get("enabled") and not c.get("missing")]
    if not contexts:
        if allow_neutral:
            out["reason"] = "neutral_allowed_no_candle_context"
            return out
        out.update({"blocked": True, "reason": "no_candle_context"})
        return out

    for ctx in contexts:
        alignment = _finite_float(ctx.get("alignment"), 0.0)
        score = abs(_finite_float(ctx.get("score"), 0.0))
        if alignment < 0:
            out.update({"blocked": True, "reason": "contradictory_candlestick"})
            return out
        if alignment == 0 and not allow_neutral:
            out.update({"blocked": True, "reason": "neutral_candlestick"})
            return out
        if alignment != 0 and score < float(min_score):
            out.update({"blocked": True, "reason": "candlestick_score_below_min"})
            return out
    out["reason"] = "passed"
    return out
