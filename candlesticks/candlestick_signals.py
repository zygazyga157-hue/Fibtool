"""candlesticks.candlestick_signals
Lightweight candlestick pattern detector + Telegram reporter for this project.

Features:
- Try to use TA-Lib if installed for many patterns.
- Fallback to a few simple pattern detectors if TA-Lib is not available (Doji, Bull/Bear Engulfing, Hammer).
- Generate a simple buy/sell suggestion based on latest patterns.
- Send a report to Telegram using the bot token in `config.py`.

Usage (from repo root):
  python -m candlesticks.candlestick_signals --bars outputs/xauusd_bars.csv --chat-id <chat_id>

Notes:
- This module intentionally avoids making trading executions. It only suggests signals.
"""

from __future__ import annotations

import argparse
import math
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import requests
import html

try:
    import talib
    TALIB_AVAILABLE = True
except Exception:
    talib = None
    TALIB_AVAILABLE = False

import config

LOG = logging.getLogger("candlestick_signals")
LOG.setLevel(logging.INFO)


def _is_fx_symbol(sym: str) -> bool:
    """Heuristic to detect FX pairs (e.g., EURUSD, GBPUSD, USDJPY).
    Treat as FX only when both sides are known fiat currency ISO codes.
    """
    try:
        s = str(sym).upper()
        # common fiat currency ISO codes
        fiat = {"USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"}
        if len(s) == 6:
            a, b = s[:3], s[3:]
            return a in fiat and b in fiat
        return False
    except Exception:
        return False


def _pip_size_for_symbol(sym: str) -> Optional[float]:
    """Return pip size for FX symbol: 0.0001 for non-JPY, 0.01 for JPY pairs.
    Returns None for non-FX symbols.
    """
    try:
        s = str(sym).upper()
        if not _is_fx_symbol(s):
            return None
        return 0.01 if ("JPY" in s) else 0.0001
    except Exception:
        return None


def _round_to_step(price: float, step: Optional[float]) -> float:
    try:
        st = float(step) if step else None
        if not st or st <= 0:
            return float(price)
        return round(round(float(price) / st) * st, 8)
    except Exception:
        return float(price)


def _round_up_to_step(price: float, step: Optional[float]) -> float:
    """Round up to the next valid price step."""
    try:
        st = float(step) if step else None
        if not st or st <= 0:
            return float(price)
        units_f = float(price) / st
        units = math.ceil(units_f - 1e-9)
        return round(units * st, 8)
    except Exception:
        return float(price)


def _round_down_to_step(price: float, step: Optional[float]) -> float:
    """Round down to the previous valid price step."""
    try:
        st = float(step) if step else None
        if not st or st <= 0:
            return float(price)
        units_f = float(price) / st
        units = math.floor(units_f + 1e-9)
        return round(units * st, 8)
    except Exception:
        return float(price)


def _model_b_profile(symbol: str) -> str:
    """Return one of: fx, metals, crypto, indices, other."""
    s = str(symbol or "").upper()
    if _is_fx_symbol(s):
        return "fx"

    sym = s.replace("-", "_").replace("/", "_").replace(" ", "_")
    if any(k in sym for k in ("XAU", "XAG", "GOLD", "SILVER")):
        return "metals"
    if any(k in sym for k in ("BTC", "ETH", "XRP", "SOL", "ADA", "DOGE", "LTC", "BNB", "CRYPTO")):
        return "crypto"
    if any(k in sym for k in ("INDEX", "WALL_STREET", "US_", "UK_", "GER", "DAX", "NAS", "SP", "DJ", "USTEC", "US30", "US500", "JP")):
        return "indices"
    return "other"


def _get_cfg_float(name: str, default: float) -> float:
    try:
        return float(getattr(config, name, default))
    except Exception:
        return float(default)


def _infer_step_from_prices(df: pd.DataFrame, pip_size: Optional[float]) -> float:
    """Infer display/rounding step from recent prices when no pip-size is available."""
    try:
        if pip_size:
            return float(pip_size)
    except Exception:
        pass

    try:
        closes = pd.to_numeric(df.get("close"), errors="coerce").dropna().tail(200)
        if closes.empty:
            return 0.01

        decimals = 0
        for v in closes.values:
            s = f"{float(v):.10f}".rstrip("0").rstrip(".")
            if "." in s:
                decimals = max(decimals, len(s.split(".")[1]))
        if decimals <= 0:
            return 1.0
        decimals = min(decimals, 6)
        return float(10 ** (-decimals))
    except Exception:
        return 0.01


def _compute_atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    try:
        if df is None or len(df) < 2:
            return None
        high = pd.to_numeric(df["high"], errors="coerce")
        low = pd.to_numeric(df["low"], errors="coerce")
        close = pd.to_numeric(df["close"], errors="coerce")
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(int(period)).mean().iloc[-1]
        if pd.isna(atr):
            return None
        atr_f = float(atr)
        return atr_f if atr_f > 0 else None
    except Exception:
        return None


def compute_model_b_breakout(df: pd.DataFrame, signal: Dict[str, Optional[str]], *,
                            spread: Optional[float] = None,
                            safety_margin: Optional[float] = None,
                            rr: Optional[float] = None,
                            symbol: Optional[str] = None) -> Dict[str, object]:
    """
    Non-invasive Model B breakout price suggestion.
    Returns dict with keys: method, entry, stop, tp, rr, buffer
    Uses the last candle in `df` as the signal candle.
    """
    out: Dict[str, object] = {}
    try:
        if not signal or not isinstance(signal, dict):
            return out
        side = signal.get("signal")
        if side not in ("buy", "sell"):
            return out

        if df is None or len(df) == 0:
            return out

        sig = df.iloc[-1]
        high = float(sig["high"])
        low = float(sig["low"])
        candle_range = max(0.0, high - low)

        profile = _model_b_profile(symbol or "")
        profile_key = profile.upper()

        # Dynamic context from recent bars.
        atr = _compute_atr(df.tail(200), period=14)

        # Prefer pip-aware buffers for FX symbols; fallback to profile-aware price-unit buffers otherwise.
        pip_size = _pip_size_for_symbol(symbol or "")
        step = _infer_step_from_prices(df.tail(200), pip_size)

        if pip_size:
            spread_pips = float(getattr(config, "MODEL_B_SPREAD_PIPS_FX", 2.0))
            safety_pips = float(getattr(config, "MODEL_B_SAFETY_PIPS_FX", 1.0))
            base_buffer = (spread_pips + safety_pips) * pip_size
        else:
            spread_default = _get_cfg_float(
                f"MODEL_B_ESTIMATED_SPREAD_{profile_key}",
                _get_cfg_float("MODEL_B_ESTIMATED_SPREAD", 0.02),
            )
            safety_default = _get_cfg_float(
                f"MODEL_B_SAFETY_MARGIN_{profile_key}",
                _get_cfg_float("MODEL_B_SAFETY_MARGIN", 0.0),
            )
            spread = float(spread if spread is not None else spread_default)
            safety_margin = float(safety_margin if safety_margin is not None else safety_default)
            base_buffer = spread + safety_margin

        atr_buffer_mult = _get_cfg_float(
            f"MODEL_B_ATR_BUFFER_MULT_{profile_key}",
            _get_cfg_float("MODEL_B_ATR_BUFFER_MULT_DEFAULT", 0.12),
        )
        min_buffer_ticks = int(_get_cfg_float(
            f"MODEL_B_MIN_BUFFER_TICKS_{profile_key}",
            _get_cfg_float("MODEL_B_MIN_BUFFER_TICKS_DEFAULT", 2),
        ))
        atr_component = (atr * atr_buffer_mult) if atr else 0.0
        tick_component = max(0.0, float(step) * max(1, min_buffer_ticks))
        buffer = max(float(base_buffer), atr_component, tick_component)

        rr_cfg = _get_cfg_float(
            f"MODEL_B_RR_{profile_key}",
            _get_cfg_float("MODEL_B_RR", 2.0),
        )
        rr = float(rr if rr is not None else rr_cfg)
        if rr <= 0:
            rr = _get_cfg_float("MODEL_B_RR", 2.0)

        min_risk_atr_mult = _get_cfg_float(
            f"MODEL_B_MIN_RISK_ATR_MULT_{profile_key}",
            _get_cfg_float("MODEL_B_MIN_RISK_ATR_MULT_DEFAULT", 0.35),
        )
        min_risk_ticks = int(_get_cfg_float(
            f"MODEL_B_MIN_RISK_TICKS_{profile_key}",
            _get_cfg_float("MODEL_B_MIN_RISK_TICKS_DEFAULT", 8),
        ))

        if side == "buy":
            entry = high + buffer
            stop = low - buffer
            risk = entry - stop
            min_risk = max((atr * min_risk_atr_mult) if atr else 0.0, float(step) * max(1, min_risk_ticks))
            if risk < min_risk:
                risk = float(min_risk)
                stop = entry - risk
            tp = entry + risk * rr
        else:
            entry = low - buffer
            stop = high + buffer
            risk = stop - entry
            min_risk = max((atr * min_risk_atr_mult) if atr else 0.0, float(step) * max(1, min_risk_ticks))
            if risk < min_risk:
                risk = float(min_risk)
                stop = entry + risk
            tp = entry - risk * rr

        # Directional step rounding:
        # - keep breakout/stop direction intact
        # - derive TP from rounded risk so effective RR remains stable after rounding
        step_f = float(step) if step else 0.0
        if step_f > 0:
            if side == "buy":
                entry_r = _round_up_to_step(float(entry), step_f)
                stop_r = _round_down_to_step(float(stop), step_f)
                risk_r = entry_r - stop_r
                if risk_r <= 0:
                    risk_r = step_f
                    stop_r = entry_r - risk_r
                tp_target = entry_r + risk_r * rr
                tp_r = _round_up_to_step(tp_target, step_f)
            else:
                entry_r = _round_down_to_step(float(entry), step_f)
                stop_r = _round_up_to_step(float(stop), step_f)
                risk_r = stop_r - entry_r
                if risk_r <= 0:
                    risk_r = step_f
                    stop_r = entry_r + risk_r
                tp_target = entry_r - risk_r * rr
                tp_r = _round_down_to_step(tp_target, step_f)
        else:
            entry_r = float(entry)
            stop_r = float(stop)
            tp_r = float(tp)
            risk_r = abs(entry_r - stop_r)

        rr_effective = (abs(tp_r - entry_r) / risk_r) if risk_r > 0 else None

        out = {
            "method": "model_b_breakout",
            "entry": entry_r,
            "stop": stop_r,
            "tp": tp_r,
            "rr": rr,
            "rr_effective": round(float(rr_effective), 6) if rr_effective is not None else None,
            "buffer": round(buffer, 8),
            "profile": profile,
            "atr": round(float(atr), 8) if atr else None,
            "risk": round(float(risk_r), 8),
            "step": round(float(step), 8),
            "candle_range": round(float(candle_range), 8),
            "buffer_components": {
                "base": round(float(base_buffer), 8),
                "atr": round(float(atr_component), 8),
                "tick": round(float(tick_component), 8),
            },
        }
    except Exception:
        LOG.exception("compute_model_b_breakout failed")
    return out


def _load_bars(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Bars CSV not found: {path}")
    df = pd.read_csv(path)
    # Normalize column names
    df = df.rename(columns={c: c.lower() for c in df.columns})
    for col in ("open", "high", "low", "close"):
        if col not in df.columns:
            raise RuntimeError(f"Missing column '{col}' in bars CSV")
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # Ensure time present
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], errors="coerce")
    else:
        df["time"] = pd.RangeIndex(start=0, stop=len(df), step=1)
    return df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)


def detect_patterns_with_talib(df: pd.DataFrame) -> pd.DataFrame:
    """Compute talib pattern functions for all available pattern-recognition
    functions and return a DataFrame with one column per pattern.
    """
    results: Dict[str, np.ndarray] = {}
    op = df["open"].values
    hi = df["high"].values
    lo = df["low"].values
    cl = df["close"].values

    # Try to get canonical list from talib; fallback to a small subset if unavailable
    try:
        group = talib.get_function_groups().get("Pattern Recognition", [])
    except Exception:
        group = ["CDLDOJI", "CDLENGULFING", "CDLHAMMER", "CDLDRAGONFLYDOJI", "CDLMORNINGSTAR", "CDLEVENINGSTAR"]

    for name in group:
        fn = getattr(talib, name, None)
        if fn is None:
            continue
        try:
            results[name] = fn(op, hi, lo, cl)
        except Exception:
            results[name] = np.zeros(len(df), dtype=int)

    out = pd.DataFrame(results, index=df.index)
    return out


# Pattern ranking table ported from the notebook (uses '<PATTERN>_Bull' / '_Bear' keys)
candle_rankings = {
    "CDL3LINESTRIKE_Bull": 1,
    "CDL3LINESTRIKE_Bear": 2,
    "CDL3BLACKCROWS_Bull": 3,
    "CDL3BLACKCROWS_Bear": 3,
    "CDLEVENINGSTAR_Bull": 4,
    "CDLEVENINGSTAR_Bear": 4,
    "CDLTASUKIGAP_Bull": 5,
    "CDLTASUKIGAP_Bear": 5,
    "CDLINVERTEDHAMMER_Bull": 6,
    "CDLINVERTEDHAMMER_Bear": 6,
    "CDLMATCHINGLOW_Bull": 7,
    "CDLMATCHINGLOW_Bear": 7,
    "CDLABANDONEDBABY_Bull": 8,
    "CDLABANDONEDBABY_Bear": 8,
    "CDLBREAKAWAY_Bull": 10,
    "CDLBREAKAWAY_Bear": 10,
    "CDLMORNINGSTAR_Bull": 12,
    "CDLMORNINGSTAR_Bear": 12,
    "CDLPIERCING_Bull": 13,
    "CDLPIERCING_Bear": 13,
    "CDLSTICKSANDWICH_Bull": 14,
    "CDLSTICKSANDWICH_Bear": 14,
    "CDLTHRUSTING_Bull": 15,
    "CDLTHRUSTING_Bear": 15,
    "CDLINNECK_Bull": 17,
    "CDLINNECK_Bear": 17,
    "CDL3INSIDE_Bull": 20,
    "CDL3INSIDE_Bear": 56,
    "CDLHOMINGPIGEON_Bull": 21,
    "CDLHOMINGPIGEON_Bear": 21,
    "CDLDARKCLOUDCOVER_Bull": 22,
    "CDLDARKCLOUDCOVER_Bear": 22,
    "CDLIDENTICAL3CROWS_Bull": 24,
    "CDLIDENTICAL3CROWS_Bear": 24,
    "CDLMORNINGDOJISTAR_Bull": 25,
    "CDLMORNINGDOJISTAR_Bear": 25,
    "CDLXSIDEGAP3METHODS_Bull": 27,
    "CDLXSIDEGAP3METHODS_Bear": 26,
    "CDLTRISTAR_Bull": 28,
    "CDLTRISTAR_Bear": 76,
    "CDLGAPSIDESIDEWHITE_Bull": 46,
    "CDLGAPSIDESIDEWHITE_Bear": 29,
    "CDLEVENINGDOJISTAR_Bull": 30,
    "CDLEVENINGDOJISTAR_Bear": 30,
    "CDL3WHITESOLDIERS_Bull": 32,
    "CDL3WHITESOLDIERS_Bear": 32,
    "CDLONNECK_Bull": 33,
    "CDLONNECK_Bear": 33,
    "CDL3OUTSIDE_Bull": 34,
    "CDL3OUTSIDE_Bear": 39,
    "CDLRICKSHAWMAN_Bull": 35,
    "CDLRICKSHAWMAN_Bear": 35,
    "CDLSEPARATINGLINES_Bull": 36,
    "CDLSEPARATINGLINES_Bear": 40,
    "CDLLONGLEGGEDDOJI_Bull": 37,
    "CDLLONGLEGGEDDOJI_Bear": 37,
    "CDLHARAMI_Bull": 38,
    "CDLHARAMI_Bear": 72,
    "CDLLADDERBOTTOM_Bull": 41,
    "CDLLADDERBOTTOM_Bear": 41,
    "CDLCLOSINGMARUBOZU_Bull": 70,
    "CDLCLOSINGMARUBOZU_Bear": 43,
    "CDLTAKURI_Bull": 47,
    "CDLTAKURI_Bear": 47,
    "CDLDOJISTAR_Bull": 49,
    "CDLDOJISTAR_Bear": 51,
    "CDLHARAMICROSS_Bull": 50,
    "CDLHARAMICROSS_Bear": 80,
    "CDLADVANCEBLOCK_Bull": 54,
    "CDLADVANCEBLOCK_Bear": 54,
    "CDLSHOOTINGSTAR_Bull": 55,
    "CDLSHOOTINGSTAR_Bear": 55,
    "CDLMARUBOZU_Bull": 71,
    "CDLMARUBOZU_Bear": 57,
    "CDLUNIQUE3RIVER_Bull": 60,
    "CDLUNIQUE3RIVER_Bear": 60,
    "CDL2CROWS_Bull": 61,
    "CDL2CROWS_Bear": 61,
    "CDLBELTHOLD_Bull": 62,
    "CDLBELTHOLD_Bear": 63,
    "CDLHAMMER_Bull": 65,
    "CDLHAMMER_Bear": 65,
    "CDLHIGHWAVE_Bull": 67,
    "CDLHIGHWAVE_Bear": 67,
    "CDLSPINNINGTOP_Bull": 69,
    "CDLSPINNINGTOP_Bear": 73,
    "CDLUPSIDEGAP2CROWS_Bull": 74,
    "CDLUPSIDEGAP2CROWS_Bear": 74,
    "CDLGRAVESTONEDOJI_Bull": 77,
    "CDLGRAVESTONEDOJI_Bear": 77,
    "CDLHIKKAKEMOD_Bull": 82,
    "CDLHIKKAKEMOD_Bear": 81,
    "CDLHIKKAKE_Bull": 85,
    "CDLHIKKAKE_Bear": 83,
    "CDLENGULFING_Bull": 84,
    "CDLENGULFING_Bear": 91,
    "CDLMATHOLD_Bull": 86,
    "CDLMATHOLD_Bear": 86,
    "CDLHANGINGMAN_Bull": 87,
    "CDLHANGINGMAN_Bear": 87,
    "CDLRISEFALL3METHODS_Bull": 94,
    "CDLRISEFALL3METHODS_Bear": 89,
    "CDLKICKING_Bull": 96,
    "CDLKICKING_Bear": 102,
    "CDLDRAGONFLYDOJI_Bull": 98,
    "CDLDRAGONFLYDOJI_Bear": 98,
    "CDLCONCEALBABYSWALL_Bull": 101,
    "CDLCONCEALBABYSWALL_Bear": 101,
    "CDL3STARSINSOUTH_Bull": 103,
    "CDL3STARSINSOUTH_Bear": 103,
    "CDLDOJI_Bull": 104,
    "CDLDOJI_Bear": 104,
}

_MAX_RANK = max(candle_rankings.values()) if candle_rankings else 1


def _is_doji(row, thresh=0.0015):
    # Very simple doji heuristic: small body relative to range
    body = abs(row["close"] - row["open"])
    rng = row["high"] - row["low"]
    if rng <= 0:
        return False
    return (body / rng) <= thresh


def _is_bull_engulfing(prev, cur) -> bool:
    return (prev["close"] < prev["open"]) and (cur["close"] > cur["open"]) and (cur["close"] > prev["open"]) and (cur["open"] < prev["close"])


def _is_bear_engulfing(prev, cur) -> bool:
    return (prev["close"] > prev["open"]) and (cur["close"] < cur["open"]) and (cur["open"] > prev["close"]) and (cur["close"] < prev["open"])


def detect_patterns_fallback(df: pd.DataFrame) -> pd.DataFrame:
    # simple fallback detectors
    n = len(df)
    out = pd.DataFrame(index=df.index)
    out["DOJI"] = [_is_doji(df.loc[i]) for i in df.index]
    out["BULL_ENGULFING"] = [False] * n
    out["BEAR_ENGULFING"] = [False] * n
    for i in range(1, n):
        prev = df.loc[i - 1]
        cur = df.loc[i]
        out.at[i, "BULL_ENGULFING"] = _is_bull_engulfing(prev, cur)
        out.at[i, "BEAR_ENGULFING"] = _is_bear_engulfing(prev, cur)
    out = out.astype(int)
    return out


def summarize_latest_patterns(df: pd.DataFrame, window: int = 10) -> Dict[str, Dict[str, Optional[str]]]:
    """Return a summary of recent pattern activity.

    Returns a mapping: { pattern_name: { 'count': int, 'last_idx': int, 'last_time': str|None } }
    """
    out: Dict[str, Dict[str, Optional[str]]] = {}
    if TALIB_AVAILABLE:
        pat = detect_patterns_with_talib(df)
        recent = pat.tail(window)
        for col in pat.columns:
            # full series to preserve directionality (+/- values)
            series = pat[col].to_numpy()
            recent_arr = recent[col].to_numpy()
            # counts in recent window by sign
            recent_bull = int((recent_arr > 0).sum())
            recent_bear = int((recent_arr < 0).sum())
            # last index of any non-zero detection
            nonzero = np.nonzero(series)[0]
            last_idx = int(nonzero[-1]) if len(nonzero) else -1
            last_time = str(df.loc[last_idx, "time"]) if (last_idx >= 0 and "time" in df.columns) else None
            # net count (bull - bear) for quick compatibility
            net = recent_bull - recent_bear
            out[col] = {"count": int(net), "bull_count": recent_bull, "bear_count": recent_bear, "last_idx": last_idx, "last_time": last_time}
        return out
    else:
        pat = detect_patterns_fallback(df)
        recent = pat.tail(window)
        for col in pat.columns:
            arr = recent[col].to_numpy()
            cnt = int(arr.sum())
            series = pat[col]
            nonzero = np.nonzero(series.to_numpy())[0]
            last_idx = int(nonzero[-1]) if len(nonzero) else -1
            last_time = str(df.loc[last_idx, "time"] ) if (last_idx >= 0 and "time" in df.columns) else None
            # For simple fallback detectors, infer direction from the column name where possible
            name = col.upper()
            bull = 0
            bear = 0
            if 'BULL' in name or name.endswith('_BULL') or 'BULL_ENGULF' in name:
                bull = cnt
            elif 'BEAR' in name or name.endswith('_BEAR') or 'BEAR_ENGULF' in name:
                bear = cnt
            else:
                # neutral patterns like DOJI - report as neutral net but keep count
                pass
            net = bull - bear if (bull or bear) else cnt
            out[col] = {"count": int(net), "bull_count": bull, "bear_count": bear, "last_idx": last_idx, "last_time": last_time}
        return out


def generate_signal_from_summary(summary: Dict[str, Dict[str, Optional[str]]]) -> Dict[str, Optional[str]]:
    """Score patterns and produce a suggested action.

    Uses simple name-based sign detection, and optional weighting from `candle_rankings`.
    Returns a dict with 'signal', 'score', 'top_patterns', 'reason'.
    """
    score = 0.0
    reasons: List[str] = []
    scored_patterns: List[tuple] = []

    for name, meta in summary.items():
        # prefer directional counts when present
        bull = int(meta.get('bull_count', 0) or 0)
        bear = int(meta.get('bear_count', 0) or 0)
        if bull == 0 and bear == 0:
            # fallback to neutral count
            cnt = int(meta.get("count", 0) or 0)
            # infer sign from name
            n = name.upper()
            if any(k in n for k in ("BULL", "MORNING", "PIERCING", "ENGULF", "HAMMER", "RISE", "PIERCE")):
                bull = cnt
            elif any(k in n for k in ("BEAR", "EVENING", "DRAGON", "DARK", "FALL")):
                bear = cnt
            else:
                # neutral
                pass

        # determine ranking weight if available
        weight = 1.0
        rk = None
        try_keys = [f"{name}_Bull", f"{name}_Bear", name]
        for k in try_keys:
            if k in candle_rankings:
                rk = candle_rankings.get(k)
                break
        if rk is not None:
            weight = (_MAX_RANK + 1 - rk) / float(_MAX_RANK)

        # contribution = weighted bulls - weighted bears
        contrib = bull * weight - bear * weight
        score += contrib
        reasons.append(f"{name}:+{bull} -{bear} *{weight:.2f}")
        scored_patterns.append((name, bull - bear, weight, contrib))

    # format top patterns
    scored_patterns.sort(key=lambda x: abs(x[2] * x[1]), reverse=True)
    top_patterns = [f"{n}:{c}*{w:.2f}" for n, c, w, _ in scored_patterns][:8]

    # decide signal
    if score > 0.5:
        sig = "buy"
    elif score < -0.5:
        sig = "sell"
    else:
        sig = None

    return {
        "signal": sig,
        "score": float(score),
        "top_patterns": ", ".join(top_patterns),
        "reason": ", ".join(reasons) if reasons else None,
    }


def send_telegram(token: str, chat_id: str, text: str, parse_mode: str = "Markdown") -> bool:
    def _normalize_chat_ids(c):
        if not c:
            return []
        if isinstance(c, (list, tuple)):
            return [str(x) for x in c if x]
        # comma-separated
        return [x.strip() for x in str(c).split(',') if x.strip()]

    if not token or not chat_id:
        LOG.warning("Telegram token or chat_id not provided; skipping send")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    # Accept multiple chat ids (comma-separated or list)
    chat_ids = _normalize_chat_ids(chat_id)
    if not chat_ids:
        LOG.warning("No valid chat ids parsed from chat_id=%s", chat_id)
        return False

    # send to each chat id; return True if any succeeded
    any_ok = False
    for cid in chat_ids:
        body = {"chat_id": cid, "text": text}
        if parse_mode:
            body["parse_mode"] = parse_mode
        LOG.debug("Telegram send url=%s chat_id=%s text_len=%d", url, cid, len(text))
        try:
            r = requests.post(url, json=body, timeout=10)
            try:
                LOG.info("Telegram response %s: %s", r.status_code, r.text)
            except Exception:
                LOG.debug("Telegram response received (failed to read text)")
            r.raise_for_status()
            any_ok = True
            continue
        except requests.exceptions.HTTPError as he:
            try:
                LOG.error("Telegram HTTP error %s: %s", r.status_code, r.text)
            except Exception:
                LOG.exception("Telegram HTTP error and failed to read response")
            # Try fallback plain-text retry
            try:
                safe_body = {"chat_id": cid, "text": text}
                LOG.debug("Telegram retry plain text to chat_id=%s", cid)
                r2 = requests.post(url, json=safe_body, timeout=8)
                LOG.info("Telegram retry response %s: %s", r2.status_code, r2.text)
                r2.raise_for_status()
                any_ok = True
                continue
            except Exception:
                LOG.exception("Telegram fallback send also failed for chat_id=%s", cid)
                continue
        except Exception as e:
            LOG.exception("Telegram send failed for chat_id=%s: %s", cid, e)
            continue

    return any_ok


def _load_sent_index(path: str):
    try:
        import json, shutil
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # If the stored data is already a dict, return it.
            if isinstance(data, dict):
                return data
            # If it's a list or other type, back it up and return an empty dict to avoid crashes
            try:
                bak = path + '.bak'
                shutil.copy2(path, bak)
            except Exception:
                pass
            return {}
    except Exception:
        return {}
    return {}


def _save_sent_index(path: str, data: dict):
    try:
        import json
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # write atomically
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            # best-effort fallback
            import json
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception:
            pass


def _should_send_and_update(sym_key: str, signal_obj: dict, persist_path: str, min_seconds: int, min_score_delta: float, force: bool) -> bool:
    """Decide whether to send a report for `sym_key` and update the persist index when sending.

    `signal_obj` is the dict returned by `generate_signal_from_summary`.
    Returns True when send should occur (and updates the persist file), False to skip sending.
    """
    try:
        import json
        now = datetime.utcnow()
        idx = _load_sent_index(persist_path) or {}
        last = idx.get(sym_key)
        current_score = float(signal_obj.get('score') or 0.0)

        if force:
            # always send and record
            idx[sym_key] = {'ts': now.isoformat(), 'score': current_score, 'signal': signal_obj.get('signal'), 'top': signal_obj.get('top_patterns')}
            _save_sent_index(persist_path, idx)
            return True

        if not last:
            idx[sym_key] = {'ts': now.isoformat(), 'score': current_score, 'signal': signal_obj.get('signal'), 'top': signal_obj.get('top_patterns')}
            _save_sent_index(persist_path, idx)
            return True

        # parse last timestamp
        try:
            last_ts = datetime.fromisoformat(last.get('ts'))
        except Exception:
            last_ts = None

        if last_ts is not None:
            age = (now - last_ts).total_seconds()
            if age < min_seconds:
                # too soon since last message
                return False

        last_score = float(last.get('score') or 0.0)
        if abs(current_score - last_score) < float(min_score_delta):
            # not a meaningful score change
            return False

        # otherwise update and send
        idx[sym_key] = {'ts': now.isoformat(), 'score': current_score, 'signal': signal_obj.get('signal'), 'top': signal_obj.get('top_patterns')}
        _save_sent_index(persist_path, idx)
        return True
    except Exception:
        # Fail-open: if decision logic errors, allow send (but don't raise)
        try:
            idx = _load_sent_index(persist_path) or {}
            now = datetime.utcnow()
            idx[sym_key] = {'ts': now.isoformat(), 'score': float(signal_obj.get('score') or 0.0), 'signal': signal_obj.get('signal'), 'top': signal_obj.get('top_patterns')}
            _save_sent_index(persist_path, idx)
        except Exception:
            pass
        return True


def run_report_for_bars(bars_path: str, chat_id: str, bot_token: str, *, persist_path: str = None, min_seconds: int = 3600, min_score_delta: float = 0.5, force: bool = False, dry_run: bool = False) -> dict:
    """Programmatic entrypoint: analyze bars CSV and optionally send Telegram report.

    Returns a dict with keys: `sent` (bool), `signal` (dict), `report` (str).
    """
    try:
        df = _load_bars(bars_path)
    except Exception as e:
        return {'sent': False, 'error': f'load_failed: {e}'}

    counts = summarize_latest_patterns(df, window=3)
    signal = generate_signal_from_summary(counts)

    # Attach Model B predicted entry (non-invasive) when enabled
    try:
        # derive symbol from bars_path early to pass into predictor
        try:
            symbol = os.path.basename(bars_path).split('_bars')[0]
        except Exception:
            symbol = None
        if getattr(config, 'MODEL_B_PREDICT_ENABLED', True) and isinstance(signal, dict):
            pred = compute_model_b_breakout(df.tail(200), signal, symbol=symbol)
            if pred:
                # attach under a new list so multiple predictors can co-exist
                signal.setdefault('predicted_entries', []).append(pred)
    except Exception:
        LOG.exception("Model B prediction failed (non-fatal)")

    report = build_report(df.tail(200), counts, signal)

    # prepare persist path
    if persist_path is None:
        persist_path = os.path.join('outputs', 'telegram_sent.json')

    # symbol key
    try:
        sym_key = os.path.basename(bars_path).split('_bars')[0]
    except Exception:
        sym_key = bars_path

    if dry_run:
        return {'sent': False, 'signal': signal, 'report': report}

    should = _should_send_and_update(sym_key, signal, persist_path, min_seconds, min_score_delta, force)
    if not should:
        return {'sent': False, 'signal': signal, 'report': report, 'reason': 'dedupe_skip'}

    # Build richer HTML message for BUY/SELL signals inspired by live_entry_bot
    action = signal.get('signal')
    sent_any = False
    # Determine recipients: main chat_id plus extras from config
    recipients = [chat_id] if chat_id else []
    try:
        extra_env = getattr(config, 'TELEGRAM_EXTRA_CHAT_IDS', '')
        if extra_env:
            recipients += [x.strip() for x in str(extra_env).split(',') if x.strip()]
    except Exception:
        pass

    # Use HTML formatted detailed message for explicit buy/sell signals
    if action in ('buy', 'sell'):
        html_msg = _build_html_signal_from_summary(bars_path, signal, report)
        for rcpt in recipients:
            ok = send_telegram(bot_token, rcpt, html_msg, parse_mode="HTML")
            sent_any = sent_any or bool(ok)
    else:
        # neutral messages: send the plain text report (Markdown) to main recipient only
        ok = send_telegram(bot_token, chat_id, report, parse_mode="Markdown")
        sent_any = bool(ok)

    return {'sent': sent_any, 'signal': signal, 'report': report}


def build_report(df: pd.DataFrame, counts: Dict[str, int], signal: Dict[str, Optional[str]]) -> str:
    now = datetime.utcnow().isoformat()
    rows = []
    rows.append(f"*Candlestick Pattern Report* — {now} UTC")
    rows.append(f"Rows scanned: {len(df)}")
    rows.append("")
    sig = signal.get("signal") if isinstance(signal, dict) else None
    if sig:
        rows.append(f"*Suggested action:* `{sig.upper()}`  (score={signal.get('score')})")
        if signal.get("top_patterns"):
            rows.append(f"*Top patterns:* {signal.get('top_patterns')}")
        if signal.get("reason"):
            rows.append(f"*Reasons:* {signal.get('reason')}")
    else:
        rows.append("No clear signal detected")
    rows.append("")
    rows.append("*Pattern summary (recent):*")
    # counts is a mapping of pattern -> {count,last_idx,last_time}
    for k, v in counts.items():
        rows.append(f"- {k}: count={v.get('count',0)} last_time={v.get('last_time')}")
    # Include predicted entries (plain-text) if present
    try:
        preds = signal.get('predicted_entries') if isinstance(signal, dict) else None
        if preds:
            rows.append("")
            rows.append("Predicted Entries:")
            for p in preds:
                e = p.get('entry')
                tp = p.get('tp')
                stop = p.get('stop')
                m = p.get('method')
                rr = p.get('rr')
                rows.append(f"- Entry: {e}  TP: {tp}  SL: {stop}  method: {m}  RR={rr}")
    except Exception:
        pass
    return "\n".join(rows)


def _escape_html(text: str) -> str:
    if text is None:
        return ""
    return html.escape(str(text))


def _build_html_signal_from_summary(bars_path: str, signal: dict, report_text: str) -> str:
    """Construct an HTML-formatted signal message similar to `live_entry_bot_mt5`.

    Includes symbol (from bars filename), suggested action, score, top patterns, reasons and a short excerpt of the report.
    """
    try:
        sym = os.path.basename(bars_path).split('_bars')[0].upper()
    except Exception:
        sym = 'UNKNOWN'
    sig = signal.get('signal') or 'NEUTRAL'
    score = signal.get('score')
    top = signal.get('top_patterns')
    reason = signal.get('reason')

    def humanize(code: str) -> str:
        if not code:
            return code
        s = str(code).upper()
        if s.startswith('CDL'):
            s = s[3:]
        # common mappings for nicer display
        common = {
            'LONGLEGGEDDOJI': 'LongLeggedDoji',
            'DOJI': 'Doji',
            'HARAMI': 'Harami',
            'HARAMICROSS': 'HaramiCross',
            'TAKURI': 'Takuri',
            'HAMMER': 'Hammer',
            'CLOSINGMARUBOZU': 'ClosingMarubozu',
            'ENGULFING': 'Engulfing',
            'DRAGONFLYDOJI': 'DragonflyDoji',
            'SPINNINGTOP': 'SpinningTop',
            'MORNINGSTAR': 'MorningStar',
            'EVENINGSTAR': 'EveningStar',
            'PIERCING': 'Piercing',
            'HANGINGMAN': 'HangingMan',
            'SHOOTINGSTAR': 'ShootingStar',
            'MARUBOZU': 'Marubozu',
            'TAKURI': 'Takuri',
            'HAMMER': 'Hammer',
        }
        if s in common:
            return common[s]
        # fallback: title-case the lower string
        return s.lower().capitalize()

    # extract rows scanned from report_text
    rows_scanned = None
    try:
        for l in report_text.splitlines():
            if l.strip().startswith('Rows scanned:'):
                parts = l.split(':', 1)
                rows_scanned = int(parts[1].strip()) if len(parts) > 1 else None
                break
    except Exception:
        rows_scanned = None

    # count pattern lines in the report (lines starting with '- ')
    patterns_scanned = 0
    for l in report_text.splitlines():
        if l.strip().startswith('- '):
            patterns_scanned += 1

    nowstr = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    action = str(sig).upper() if sig and sig != 'NEUTRAL' else 'NEUTRAL'
    score_display = f"{float(score):.2f}" if score is not None else 'N/A'

    lines = []
    lines.append('🔥 <b>SIGNAL ALERT</b>')
    lines.append(f'📉 <b>Symbol:</b> <code>{_escape_html(sym)}</code>')
    lines.append(f'📊 <b>Action:</b> <b><code>{_escape_html(action)}</code></b>')
    lines.append(f'🏆 <b>Score:</b> <code>{_escape_html(score_display)}</code>')
    lines.append(f'🕒 <b>Time:</b> <code>{_escape_html(nowstr)}</code>')
    lines.append("")
    # Top patterns numbered
    lines.append('⭐ <b>Top Patterns</b>')
    if top:
        try:
            items = [x.strip() for x in str(top).split(',') if x.strip()]
            for i, item in enumerate(items[:6], start=1):
                # expected format NAME:count*weight or NAME:count*weight
                try:
                    name_part, rest = item.split(':', 1)
                    cnt_part, weight_part = rest.split('*', 1)
                    cnt = int(cnt_part)
                    weight = float(weight_part)
                except Exception:
                    name_part = item
                    cnt = 0
                    weight = 0.0
                sign = f'+{cnt}' if cnt > 0 else str(cnt)
                human = humanize(name_part)
                lines.append(f"{i}) {human} → <code>{_escape_html(sign)} · {weight:.2f}</code>")
        except Exception:
            lines.append(f"<code>{_escape_html(top)}</code>")
    else:
        lines.append('<code>None</code>')

    lines.append("")
    # Reason summary: use top 5 patterns and mark check/cross based on counts
    reason_items = []
    if top:
        try:
            items = [x.strip() for x in str(top).split(',') if x.strip()]
            for item in items[:5]:
                try:
                    name_part, rest = item.split(':', 1)
                    cnt_part = rest.split('*', 1)[0]
                    cnt = int(cnt_part)
                except Exception:
                    name_part = item
                    cnt = 0
                human = humanize(name_part)
                mark = '✔' if cnt > 0 else '✖'
                reason_items.append(f"{human} {mark}")
        except Exception:
            pass

    if reason_items:
        lines.append('📌 <b>Reason Summary:</b>')
        lines.append('<code>' + ' | '.join(reason_items) + '</code>')

    lines.append("")
    # Pattern coverage
    coverage_parts = []
    coverage_parts.append(f"{patterns_scanned} patterns scanned")
    if rows_scanned is not None:
        coverage_parts.append(f"{rows_scanned} rows")
    lines.append('<code>' + ' · '.join(coverage_parts) + '</code>')

    # If predicted entries attached, include a short summary
    try:
        preds = signal.get('predicted_entries') if isinstance(signal, dict) else None
        if preds:
            lines.append("")
            lines.append('📌 <b>Predicted Entries</b>')
            for p in preds:
                e = p.get('entry')
                tp = p.get('tp')
                stop = p.get('stop')
                m = p.get('method')
                rr = p.get('rr')
                # Format: Entry bold, TP and SL labeled, include method and RR
                entry_txt = f"<b>Entry:</b> <code>{_escape_html(str(e))}</code>"
                tp_txt = f"TP: <code>{_escape_html(str(tp))}</code>"
                sl_txt = f"SL: <code>{_escape_html(str(stop))}</code>"
                meta_txt = f"<i>{_escape_html(str(m))}{', RR=' + str(rr) if rr is not None else ''}</i>"
                lines.append(f"• {entry_txt} — {tp_txt} · {sl_txt} — {meta_txt}")
    except Exception:
        pass

    lines.append("")
    lines.append('⚠️ <i>Signals are suggestions only — manage risk and verify before trading.</i>')

    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run candlestick pattern detection and report to Telegram")
    parser.add_argument("--bars", default=os.path.join("outputs", "xauusd_bars.csv"), help="Path to OHLCV CSV")
    parser.add_argument("--chat-id", default=config.TELEGRAM_GROUP_ID or config.TELEGRAM_ADMIN_ID, help="Telegram chat id to send to")
    parser.add_argument("--bot-token", default=config.TELEGRAM_BOT_TOKEN, help="Telegram bot token (overrides config)")
    parser.add_argument("--window", type=int, default=3, help="How many recent bars to summarise")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        df = _load_bars(args.bars)
    except Exception as e:
        LOG.exception("Failed to load bars: %s", e)
        return 2

    counts = summarize_latest_patterns(df, window=args.window)
    signal = generate_signal_from_summary(counts)
    report = build_report(df.tail(200), counts, signal)

    if args.dry_run:
        print(report)
        return 0

    # Deduplication: avoid sending identical signals repeatedly for the same bars file/symbol
    sent_index_path = os.path.join("outputs", "telegram_sent.json")
    sent_index = _load_sent_index(sent_index_path)
    # derive a simple symbol key from bars filename
    try:
        sym_key = os.path.basename(args.bars).split("_bars")[0]
    except Exception:
        sym_key = args.bars
    signature = f"{signal.get('signal')}|{signal.get('top_patterns')}|{signal.get('score')}"
    last = sent_index.get(sym_key)
    if last and last.get("signature") == signature:
        LOG.info("No change in signal for %s; skipping Telegram post", sym_key)
        return 0

    ok = send_telegram(args.bot_token, args.chat_id, report)
    if not ok:
        LOG.error("Failed to send Telegram message")
        return 3

    # record signature
    try:
        import time
        sent_index[sym_key] = {"signature": signature, "sent_at": time.time()}
        _save_sent_index(sent_index_path, sent_index)
    except Exception:
        pass

    LOG.info("Report sent to Telegram chat %s", args.chat_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
