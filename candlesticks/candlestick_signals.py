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

        rr_cfg = _get_cfg_float("MSE_RR_BASE", 2.0)
        rr = float(rr if rr is not None else rr_cfg)
        if rr <= 0:
            rr = _get_cfg_float("MSE_RR_BASE", 2.0)

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


def compute_model_a_close(df: pd.DataFrame, signal: Dict[str, Optional[str]], *,
                          spread: Optional[float] = None,
                          rr: Optional[float] = None,
                          symbol: Optional[str] = None) -> Dict[str, object]:
    """Model A — Close Entry.

    Enter at the close of the signal candle.
    Returns dict with keys: method, entry, stop, tp, rr, buffer, profile, atr, risk, step.
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
        close = float(sig["close"])
        candle_range = max(0.0, high - low)

        profile = _model_b_profile(symbol or "")
        profile_key = profile.upper()

        atr = _compute_atr(df.tail(200), period=14)
        pip_size = _pip_size_for_symbol(symbol or "")
        step = _infer_step_from_prices(df.tail(200), pip_size)

        # Buffer computation (reuse Model B logic for consistency)
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
            sp = float(spread if spread is not None else spread_default)
            sm = float(safety_default)
            base_buffer = sp + sm

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

        rr_cfg = _get_cfg_float("MSE_RR_BASE", 2.0)
        rr = float(rr if rr is not None else rr_cfg)
        if rr <= 0:
            rr = _get_cfg_float("MSE_RR_BASE", 2.0)

        if side == "buy":
            entry = close
            stop = low - buffer
            risk = entry - stop
            if risk <= 0:
                return out
            tp = entry + risk * rr
        else:
            entry = close
            stop = high + buffer
            risk = stop - entry
            if risk <= 0:
                return out
            tp = entry - risk * rr

        step_f = float(step) if step else 0.0
        if step_f > 0:
            entry_r = _round_to_step(entry, step_f)
            if side == "buy":
                stop_r = _round_down_to_step(float(stop), step_f)
                risk_r = entry_r - stop_r
                if risk_r <= 0:
                    risk_r = step_f
                    stop_r = entry_r - risk_r
                tp_r = _round_up_to_step(entry_r + risk_r * rr, step_f)
            else:
                stop_r = _round_up_to_step(float(stop), step_f)
                risk_r = stop_r - entry_r
                if risk_r <= 0:
                    risk_r = step_f
                    stop_r = entry_r + risk_r
                tp_r = _round_down_to_step(entry_r - risk_r * rr, step_f)
        else:
            entry_r = float(entry)
            stop_r = float(stop)
            tp_r = float(tp)
            risk_r = abs(entry_r - stop_r)

        rr_effective = (abs(tp_r - entry_r) / risk_r) if risk_r > 0 else None

        out = {
            "method": "model_a_close",
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
        }
    except Exception:
        LOG.exception("compute_model_a_close failed")
    return out


def compute_model_c_retrace(df: pd.DataFrame, signal: Dict[str, Optional[str]], *,
                            spread: Optional[float] = None,
                            rr: Optional[float] = None,
                            retrace_ratio: Optional[float] = None,
                            symbol: Optional[str] = None) -> Dict[str, object]:
    """Model C — Retrace (Limit) Entry.

    Enter on a pullback into the signal candle at the retrace level.
    Returns dict with keys: method, entry, stop, tp, rr, buffer, profile, atr, risk, step, retrace_ratio.
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
        if candle_range <= 0:
            return out

        profile = _model_b_profile(symbol or "")
        profile_key = profile.upper()

        atr = _compute_atr(df.tail(200), period=14)
        pip_size = _pip_size_for_symbol(symbol or "")
        step = _infer_step_from_prices(df.tail(200), pip_size)

        # Retrace ratio: default 0.5, optionally 0.618 for deeper retracement
        retrace = float(retrace_ratio if retrace_ratio is not None
                        else _get_cfg_float("MODEL_C_RETRACE_RATIO", 0.5))

        # Buffer computation (reuse Model B logic)
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
            sp = float(spread if spread is not None else spread_default)
            sm = float(safety_default)
            base_buffer = sp + sm

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

        rr_cfg = _get_cfg_float("MSE_RR_BASE", 2.0)
        rr = float(rr if rr is not None else rr_cfg)
        if rr <= 0:
            rr = _get_cfg_float("MSE_RR_BASE", 2.0)

        if side == "buy":
            entry = low + retrace * candle_range
            stop = low - buffer
            risk = entry - stop
            if risk <= 0:
                return out
            tp = entry + risk * rr
        else:
            entry = high - retrace * candle_range
            stop = high + buffer
            risk = stop - entry
            if risk <= 0:
                return out
            tp = entry - risk * rr

        step_f = float(step) if step else 0.0
        if step_f > 0:
            if side == "buy":
                entry_r = _round_down_to_step(float(entry), step_f)
                stop_r = _round_down_to_step(float(stop), step_f)
                risk_r = entry_r - stop_r
                if risk_r <= 0:
                    risk_r = step_f
                    stop_r = entry_r - risk_r
                tp_r = _round_up_to_step(entry_r + risk_r * rr, step_f)
            else:
                entry_r = _round_up_to_step(float(entry), step_f)
                stop_r = _round_up_to_step(float(stop), step_f)
                risk_r = stop_r - entry_r
                if risk_r <= 0:
                    risk_r = step_f
                    stop_r = entry_r + risk_r
                tp_r = _round_down_to_step(entry_r - risk_r * rr, step_f)
        else:
            entry_r = float(entry)
            stop_r = float(stop)
            tp_r = float(tp)
            risk_r = abs(entry_r - stop_r)

        rr_effective = (abs(tp_r - entry_r) / risk_r) if risk_r > 0 else None

        out = {
            "method": "model_c_retrace",
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
            "retrace_ratio": retrace,
        }
    except Exception:
        LOG.exception("compute_model_c_retrace failed")
    return out


# ---------------------------------------------------------------------------
# Pattern classification helpers for the Model Selection Engine
# ---------------------------------------------------------------------------
# All 61 TA-Lib CDL* patterns classified into momentum, reversal, indecision.

_MOMENTUM_PATTERNS = frozenset([
    # Strong directional / continuation patterns
    "CDLMARUBOZU", "CDLCLOSINGMARUBOZU", "CDL3WHITESOLDIERS",
    "CDL3BLACKCROWS", "CDL3LINESTRIKE", "CDLKICKING",
    "CDLBELTHOLD", "CDLSEPARATINGLINES",
    # Continuation / breakout patterns
    "CDL3INSIDE", "CDL3OUTSIDE", "CDLBREAKAWAY",
    "CDLGAPSIDESIDEWHITE", "CDLKICKINGBYLENGTH", "CDLLONGLINE",
    "CDLMATHOLD", "CDLRISEFALL3METHODS", "CDLXSIDEGAP3METHODS",
    "CDLTASUKIGAP",
])

_REVERSAL_PATTERNS = frozenset([
    # Classic reversal signals
    "CDLDOJI", "CDLHAMMER", "CDLHARAMI", "CDLHARAMICROSS",
    "CDLTAKURI", "CDLDRAGONFLYDOJI", "CDLGRAVESTONEDOJI",
    "CDLINVERTEDHAMMER", "CDLMORNINGSTAR", "CDLMORNINGDOJISTAR",
    "CDLEVENINGSTAR", "CDLEVENINGDOJISTAR", "CDLABANDONEDBABY",
    "CDLPIERCING", "CDLDARKCLOUDCOVER", "CDLHANGINGMAN",
    "CDLSHOOTINGSTAR", "CDLENGULFING", "CDLHOMINGPIGEON",
    "CDLMATCHINGLOW",
    # Bearish reversal / exhaustion patterns
    "CDL2CROWS", "CDLADVANCEBLOCK", "CDLIDENTICAL3CROWS",
    "CDLSTALLEDPATTERN", "CDLUPSIDEGAP2CROWS",
    # Bullish reversal / bottoming patterns
    "CDL3STARSINSOUTH", "CDLCONCEALBABYSWALL", "CDLLADDERBOTTOM",
    "CDLSTICKSANDWICH", "CDLUNIQUE3RIVER",
    # Weak reversal / continuation-in-context patterns
    "CDLCOUNTERATTACK", "CDLDOJISTAR", "CDLINNECK",
    "CDLONNECK", "CDLTHRUSTING", "CDLTRISTAR",
])

_INDECISION_PATTERNS = frozenset([
    "CDLSPINNINGTOP", "CDLHIGHWAVE", "CDLRICKSHAWMAN",
    "CDLLONGLEGGEDDOJI",
    # Trap / ambiguous patterns
    "CDLHIKKAKE", "CDLHIKKAKEMOD", "CDLSHORTLINE",
])


def _count_pattern_class(hits: List[str], cls: frozenset) -> int:
    return sum(1 for h in hits if str(h).upper() in cls)


def _humanize_pattern(code: str) -> str:
    """Convert a CDL* pattern code to a human-readable name."""
    if not code:
        return str(code)
    s = str(code).upper()
    if s.startswith("CDL"):
        s = s[3:]
    _MAP = {
        "MARUBOZU": "Marubozu", "CLOSINGMARUBOZU": "Closing Marubozu",
        "3WHITESOLDIERS": "3 White Soldiers", "3BLACKCROWS": "3 Black Crows",
        "LONGLINE": "Long Line", "BELTHOLD": "Belt Hold",
        "KICKING": "Kicking", "KICKINGBYLENGTH": "Kicking (by length)",
        "SEPARATINGLINES": "Separating Lines", "3LINESTRIKE": "3 Line Strike",
        "GAPSIDESIDEWHITE": "Gap Side-by-Side White", "TASUKIGAP": "Tasuki Gap",
        "MATHOLD": "Mat Hold", "RISEFALL3METHODS": "Rise/Fall 3 Methods",
        "BREAKAWAY": "Breakaway", "XSIDEGAP3METHODS": "Side Gap 3 Methods",
        "3INSIDE": "3 Inside", "3OUTSIDE": "3 Outside",
        "DOJI": "Doji", "LONGLEGGEDDOJI": "Long-Legged Doji",
        "DRAGONFLYDOJI": "Dragonfly Doji", "GRAVESTONEDOJI": "Gravestone Doji",
        "HAMMER": "Hammer", "INVERTEDHAMMER": "Inverted Hammer",
        "TAKURI": "Takuri", "HANGINGMAN": "Hanging Man",
        "SHOOTINGSTAR": "Shooting Star", "ENGULFING": "Engulfing",
        "HARAMI": "Harami", "HARAMICROSS": "Harami Cross",
        "MORNINGSTAR": "Morning Star", "EVENINGSTAR": "Evening Star",
        "MORNINGDOJISTAR": "Morning Doji Star", "EVENINGDOJISTAR": "Evening Doji Star",
        "PIERCING": "Piercing Line", "DARKCLOUDCOVER": "Dark Cloud Cover",
        "ABANDONEDBABY": "Abandoned Baby", "HOMINGPIGEON": "Homing Pigeon",
        "MATCHINGLOW": "Matching Low", "2CROWS": "2 Crows",
        "ADVANCEBLOCK": "Advance Block", "IDENTICAL3CROWS": "Identical 3 Crows",
        "STALLEDPATTERN": "Stalled Pattern", "UPSIDEGAP2CROWS": "Upside Gap 2 Crows",
        "3STARSINSOUTH": "3 Stars In South", "CONCEALBABYSWALL": "Conceal Baby Swallow",
        "LADDERBOTTOM": "Ladder Bottom", "STICKSANDWICH": "Stick Sandwich",
        "UNIQUE3RIVER": "Unique 3 River", "COUNTERATTACK": "Counter Attack",
        "DOJISTAR": "Doji Star", "INNECK": "In Neck",
        "ONNECK": "On Neck", "THRUSTING": "Thrusting",
        "TRISTAR": "TriStar", "SPINNINGTOP": "Spinning Top",
        "HIGHWAVE": "High Wave", "RICKSHAWMAN": "Rickshaw Man",
        "HIKKAKE": "Hikkake", "HIKKAKEMOD": "Modified Hikkake",
        "SHORTLINE": "Short Line",
    }
    return _MAP.get(s, s.lower().capitalize())


def _build_signal_recommendation(
    side: str,
    pattern_hits: List[str],
    momentum: int,
    reversal: int,
    indecision: int,
) -> Dict[str, object]:
    """Derive a narrative recommendation from pattern classification.

    Returns dict:
        label: str           — "Probable reversal — bullish", "Momentum bias", etc.
        because: str         — humanized pattern names explaining why
        alignment: str       — "confirms" | "contradicts" | "neutral"
        suggested_side: str  — "buy" | "sell" | "wait"
    """
    side_lower = str(side or "").lower()
    total = momentum + reversal + indecision

    def _names(cls: frozenset, limit: int = 3) -> List[str]:
        return [_humanize_pattern(h) for h in pattern_hits
                if str(h).upper() in cls][:limit]

    # No patterns at all
    if total == 0:
        return {
            "label": "No pattern signal",
            "because": "no classified patterns detected",
            "alignment": "neutral",
            "suggested_side": side_lower or "wait",
        }

    # Indecision dominates
    if indecision > momentum and indecision > reversal:
        names = ", ".join(_names(_INDECISION_PATTERNS)) or "indecision candles"
        return {
            "label": "Market indecision",
            "because": f"{names} — no directional edge",
            "alignment": "neutral",
            "suggested_side": "wait",
        }

    # Reversal dominates
    if reversal > momentum:
        names = ", ".join(_names(_REVERSAL_PATTERNS)) or "reversal candles"
        if side_lower == "buy":
            return {
                "label": "Probable reversal — bullish",
                "because": f"{names} suggest bearish exhaustion",
                "alignment": "confirms",
                "suggested_side": "buy",
            }
        if side_lower == "sell":
            return {
                "label": "Probable reversal — bearish",
                "because": f"{names} suggest bullish exhaustion",
                "alignment": "confirms",
                "suggested_side": "sell",
            }
        return {
            "label": "Probable reversal",
            "because": f"{names} suggest a directional turn",
            "alignment": "neutral",
            "suggested_side": "wait",
        }

    # Momentum dominates (or equal with reversal)
    names = ", ".join(_names(_MOMENTUM_PATTERNS)) or "momentum candles"
    if side_lower == "buy":
        return {
            "label": "Momentum bias — bullish",
            "because": f"{names} support continuation higher",
            "alignment": "confirms",
            "suggested_side": "buy",
        }
    if side_lower == "sell":
        return {
            "label": "Momentum bias — bearish",
            "because": f"{names} support continuation lower",
            "alignment": "confirms",
            "suggested_side": "sell",
        }
    return {
        "label": "Momentum signal",
        "because": f"{names} — strong directional pressure",
        "alignment": "neutral",
        "suggested_side": "wait",
    }


def _classify_volatility(atr_ratio: Optional[float], cfg: object = None) -> str:
    """Classify ATR ratio into High / Medium / Low volatility state."""
    if atr_ratio is None:
        return "medium"
    _cfg = cfg or config
    high_thresh = float(getattr(_cfg, "MSE_ATR_RATIO_HIGH", 0.02))
    low_thresh = float(getattr(_cfg, "MSE_ATR_RATIO_LOW", 0.005))
    if atr_ratio >= high_thresh:
        return "high"
    if atr_ratio <= low_thresh:
        return "low"
    return "medium"


def _compute_breakout_score(df: pd.DataFrame, signal: Dict) -> float:
    """Compute a 0–1 breakout score from the signal candle.

    Components (each 0.0–1.0, equally weighted):
      body_ratio  – abs(close-open) / (high-low).  Full body → 1.0.
      close_pos   – how near the close is to the directional extreme.
      range_ratio – candle_range / ATR.  Capped at 2×ATR → 1.0.
    """
    try:
        if df is None or len(df) == 0 or not isinstance(signal, dict):
            return 0.0

        sig = df.iloc[-1]
        high = float(sig["high"])
        low = float(sig["low"])
        close = float(sig["close"])
        open_ = float(sig["open"])
        candle_range = high - low
        if candle_range <= 0:
            return 0.0

        side = signal.get("signal", "")

        # 1. Body ratio: decisive close = high body
        body_ratio = min(abs(close - open_) / candle_range, 1.0)

        # 2. Close position: buy → close near high, sell → close near low
        if side == "buy":
            close_pos = (close - low) / candle_range
        elif side == "sell":
            close_pos = (high - close) / candle_range
        else:
            close_pos = 0.5

        # 3. Range relative to ATR (wide candle = breakout)
        atr = _compute_atr(df.tail(200), period=14)
        if atr and atr > 0:
            range_ratio = min(candle_range / atr, 2.0) / 2.0
        else:
            range_ratio = 0.5

        return round((body_ratio + close_pos + range_ratio) / 3.0, 4)
    except Exception:
        return 0.0


def _compute_reflexive_rr(
    base_rr: float,
    *,
    score: float = 0.0,
    confidence: float = 0.60,
    volatility: str = "medium",
    model: str = "B",
    cfg: object = None,
) -> float:
    """Compute a context-adaptive RR from the base profile RR.

    Multipliers (each small, compounding):
      score_mult      – stronger signal → extend target.  [0.90 .. 1.15]
      confidence_mult – higher MSE confidence → wider.    [0.90 .. 1.10]
      volatility_mult – high vol → tighter, low → wider.  [0.90 .. 1.10]
      model_mult      – Model C gets best entry → wider.  A=1.0, B=1.0, C=1.10.

    Result clamped between MSE_RR_FLOOR and MSE_RR_CEILING.
    """
    _cfg = cfg or config
    rr_floor = float(getattr(_cfg, "MSE_RR_FLOOR", 1.2))
    rr_ceiling = float(getattr(_cfg, "MSE_RR_CEILING", 4.5))

    abs_score = abs(score)
    # Score factor: <2 → 0.90, 3.5 → 1.0, >=5 → 1.15 (linear interpolation)
    if abs_score <= 2.0:
        score_mult = 0.90
    elif abs_score >= 5.0:
        score_mult = 1.15
    else:
        score_mult = 0.90 + (abs_score - 2.0) * (0.25 / 3.0)

    # Confidence factor
    if confidence < 0.65:
        confidence_mult = 0.90
    elif confidence >= 0.80:
        confidence_mult = 1.10
    else:
        # Linear 0.65→1.0, 0.80→1.10
        confidence_mult = 1.0 + (confidence - 0.65) * (0.10 / 0.15)

    # Volatility factor: high vol → tighter targets (higher win rate),
    # low vol → extend targets (need more room to be worth it)
    vol_map = {"high": 0.90, "medium": 1.0, "low": 1.10}
    volatility_mult = vol_map.get(volatility, 1.0)

    # Model factor: retrace entry (C) gets a deeper entry → lower risk →
    # can afford a wider RR ratio
    model_map = {"A": 1.0, "B": 1.0, "C": 1.10}
    model_mult = model_map.get(model, 1.0)

    rr = base_rr * score_mult * confidence_mult * volatility_mult * model_mult
    return round(max(rr_floor, min(rr, rr_ceiling)), 4)


def select_model(
    *,
    score: float,
    strong_patterns_hit: List[str],
    breakout_score: Optional[float] = None,
    wyckoff_phase: Optional[str] = None,
    atr_ratio: Optional[float] = None,
    cfg: object = None,
) -> Dict[str, object]:
    """Model Selection Engine (MSE).

    Maps market conditions to the optimal entry model (A, B, or C).

    Returns dict with keys:
        model: str          — "A", "B", or "C"
        confidence: float   — 0.0–1.0
        backup_model: str|None
        reason: str
        volatility: str     — "high", "medium", or "low"
    """
    abs_score = abs(float(score)) if score is not None else 0.0
    momentum = _count_pattern_class(strong_patterns_hit, _MOMENTUM_PATTERNS)
    reversal = _count_pattern_class(strong_patterns_hit, _REVERSAL_PATTERNS)

    # Configurable thresholds
    _cfg = cfg or config
    score_a_threshold = float(getattr(_cfg, "MSE_SCORE_A_THRESHOLD", 3.5))
    score_b_threshold = float(getattr(_cfg, "MSE_SCORE_B_THRESHOLD", 2.0))
    breakout_score_threshold = float(getattr(_cfg, "MSE_BREAKOUT_SCORE_THRESHOLD", 0.6))

    bscore = float(breakout_score) if breakout_score is not None else 0.0
    wyckoff = str(wyckoff_phase or "").lower().strip()
    volatility = _classify_volatility(atr_ratio, _cfg)

    # Confidence modifier based on volatility alignment
    def _vol_adjust(base_conf: float, model: str) -> float:
        if volatility == "high" and model == "B":
            return min(base_conf + 0.05, 1.0)
        if volatility == "low" and model == "C":
            return min(base_conf + 0.05, 1.0)
        if volatility == "high" and model == "C":
            return max(base_conf - 0.05, 0.0)
        if volatility == "low" and model == "B":
            return max(base_conf - 0.05, 0.0)
        return base_conf

    # Decision cascade (matches model_selection_engine.md spec)
    if abs_score >= score_a_threshold and momentum > reversal:
        return {
            "model": "A",
            "confidence": _vol_adjust(0.85, "A"),
            "backup_model": "B",
            "reason": f"strong_score({abs_score:.2f})_momentum({momentum}>{reversal})",
            "volatility": volatility,
        }

    if bscore >= breakout_score_threshold:
        return {
            "model": "B",
            "confidence": _vol_adjust(0.75, "B"),
            "backup_model": "C",
            "reason": f"breakout_score({bscore:.2f})>={breakout_score_threshold}",
            "volatility": volatility,
        }

    if reversal >= momentum and reversal > 0:
        return {
            "model": "C",
            "confidence": _vol_adjust(0.70, "C"),
            "backup_model": "B",
            "reason": f"reversal({reversal})>=momentum({momentum})",
            "volatility": volatility,
        }

    if wyckoff in ("accumulation", "distribution"):
        return {
            "model": "C",
            "confidence": _vol_adjust(0.65, "C"),
            "backup_model": "B",
            "reason": f"wyckoff_{wyckoff}",
            "volatility": volatility,
        }

    # Default: use volatility to break the tie
    if volatility == "high":
        return {
            "model": "B",
            "confidence": _vol_adjust(0.60, "B"),
            "backup_model": "C",
            "reason": "default_high_vol_breakout",
            "volatility": volatility,
        }
    if volatility == "low":
        return {
            "model": "C",
            "confidence": _vol_adjust(0.60, "C"),
            "backup_model": "B",
            "reason": "default_low_vol_retrace",
            "volatility": volatility,
        }

    # Medium volatility default
    return {
        "model": "B",
        "confidence": 0.60,
        "backup_model": "C",
        "reason": "default_breakout",
        "volatility": volatility,
    }


def compute_selected_model(
    df: pd.DataFrame,
    signal: Dict[str, Optional[str]],
    *,
    strong_patterns_hit: Optional[List[str]] = None,
    breakout_score: Optional[float] = None,
    wyckoff_phase: Optional[str] = None,
    spread: Optional[float] = None,
    rr: Optional[float] = None,
    symbol: Optional[str] = None,
    cfg: object = None,
) -> Dict[str, object]:
    """Run the MSE and compute entry levels with the selected model.

    Returns a dict with:
        selection: dict     — output of select_model() + breakout_score
        primary: dict       — entry/stop/tp from the selected model
        backup: dict|None   — entry/stop/tp from the backup model (if available)
    """
    score = float(signal.get("score", 0.0)) if isinstance(signal, dict) else 0.0
    hits = list(strong_patterns_hit or [])

    # Compute ATR ratio = ATR / price for volatility classification
    atr_ratio = None
    try:
        atr_val = _compute_atr(df, period=14)
        if atr_val and len(df) > 0:
            price = float(df["close"].iloc[-1])
            if price > 0:
                atr_ratio = atr_val / price
    except Exception:
        pass

    # Auto-compute breakout_score from the signal candle when not provided
    if breakout_score is None:
        breakout_score = _compute_breakout_score(df, signal)

    selection = select_model(
        score=score,
        strong_patterns_hit=hits,
        breakout_score=breakout_score,
        wyckoff_phase=wyckoff_phase,
        atr_ratio=atr_ratio,
        cfg=cfg,
    )
    # Attach the computed breakout_score for audit visibility
    selection["breakout_score"] = breakout_score

    model = selection["model"]
    backup_model = selection.get("backup_model")

    # Compute reflexive RR from MSE context (unless caller passed an explicit rr)
    if rr is None:
        _cfg = cfg or config
        base_rr = float(getattr(_cfg, "MSE_RR_BASE", 2.0))
        reflexive_rr = _compute_reflexive_rr(
            base_rr,
            score=score,
            confidence=selection.get("confidence", 0.60),
            volatility=selection.get("volatility", "medium"),
            model=model,
            cfg=_cfg,
        )
        selection["reflexive_rr"] = reflexive_rr
    else:
        reflexive_rr = rr
        selection["reflexive_rr"] = reflexive_rr

    compute_fns = {
        "A": compute_model_a_close,
        "B": compute_model_b_breakout,
        "C": compute_model_c_retrace,
    }

    primary_fn = compute_fns.get(model, compute_model_b_breakout)
    primary = primary_fn(df, signal, spread=spread, rr=reflexive_rr, symbol=symbol)

    backup = None
    if backup_model and backup_model in compute_fns:
        backup_fn = compute_fns[backup_model]
        backup = backup_fn(df, signal, spread=spread, rr=reflexive_rr, symbol=symbol)

    return {
        "selection": selection,
        "primary": primary,
        "backup": backup,
    }


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

    # Closed-candle rule: drop the forming bar before pattern detection so that
    # incomplete candles never influence signals or MSE entry levels.
    if "time" in df.columns:
        from candlesticks.candlestick_autotrade import pick_last_closed_bar
        df_closed, _sig_idx, _dropped = pick_last_closed_bar(df)
        if df_closed is not None and not df_closed.empty:
            df = df_closed

    counts = summarize_latest_patterns(df, window=3)
    signal = generate_signal_from_summary(counts)

    # Run MSE to select model and compute primary + backup entry levels
    try:
        # derive symbol from bars_path early to pass into predictor
        try:
            symbol = os.path.basename(bars_path).split('_bars')[0]
        except Exception:
            symbol = None
        if getattr(config, 'MODEL_B_PREDICT_ENABLED', True) and isinstance(signal, dict):
            # Extract CDL pattern names from top_patterns so the MSE can
            # correctly score momentum vs reversal patterns (fixes dead path)
            pattern_hits: List[str] = []
            try:
                top_raw = signal.get('top_patterns') or ''
                for _item in str(top_raw).split(','):
                    _item = _item.strip()
                    if not _item:
                        continue
                    _name = _item.split(':')[0].strip().upper()
                    if _name:
                        pattern_hits.append(_name)
            except Exception:
                pass

            mse = compute_selected_model(
                df.tail(200), signal,
                strong_patterns_hit=pattern_hits,
                symbol=symbol,
            )
            if mse:
                signal['model_selection'] = mse.get('selection')
                primary = mse.get('primary')
                if primary:
                    signal.setdefault('predicted_entries', []).append(primary)
                # Append backup entry so traders see the alternative level
                backup = mse.get('backup')
                if backup:
                    signal.setdefault('predicted_entries', []).append(backup)

            # Attach pattern classification + narrative recommendation
            mom_c = _count_pattern_class(pattern_hits, _MOMENTUM_PATTERNS)
            rev_c = _count_pattern_class(pattern_hits, _REVERSAL_PATTERNS)
            ind_c = _count_pattern_class(pattern_hits, _INDECISION_PATTERNS)
            signal['pattern_classification'] = {
                'momentum': mom_c, 'reversal': rev_c, 'indecision': ind_c,
            }
            rec = _build_signal_recommendation(
                side=signal.get('signal'),
                pattern_hits=pattern_hits,
                momentum=mom_c, reversal=rev_c, indecision=ind_c,
            )
            signal['signal_recommendation'] = rec
            if rec.get('suggested_side') == 'wait':
                signal['classification_hold'] = True
    except Exception:
        LOG.exception("Model prediction failed (non-fatal)")

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

    humanize = _humanize_pattern

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

    # Model Selection Engine info
    try:
        msel = signal.get('model_selection') if isinstance(signal, dict) else None
        if msel and isinstance(msel, dict):
            m_name = {"A": "A (Close)", "B": "B (Breakout)", "C": "C (Retrace)"}.get(
                str(msel.get("model", "")), str(msel.get("model", ""))
            )
            m_conf = msel.get("confidence")
            m_backup = msel.get("backup_model")
            conf_str = f"{float(m_conf):.2f}" if m_conf is not None else "N/A"
            lines.append(f'🧠 <b>Model:</b> <code>{_escape_html(m_name)}</code>')
            lines.append(f'📊 <b>Confidence:</b> <code>{_escape_html(conf_str)}</code>')
            if m_backup:
                b_name = {"A": "A (Close)", "B": "B (Breakout)", "C": "C (Retrace)"}.get(
                    str(m_backup), str(m_backup)
                )
                lines.append(f'🔁 <b>Backup:</b> <code>{_escape_html(b_name)}</code>')
            m_vol = msel.get("volatility")
            if m_vol:
                vol_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(m_vol, "⚪")
                lines.append(f'{vol_icon} <b>Volatility:</b> <code>{_escape_html(m_vol.capitalize())}</code>')
            m_bscore = msel.get("breakout_score")
            if m_bscore is not None:
                lines.append(f'💥 <b>Breakout Score:</b> <code>{float(m_bscore):.2f}</code>')
            m_rrr = msel.get("reflexive_rr")
            if m_rrr is not None:
                lines.append(f'🎯 <b>RR (reflexive):</b> <code>{float(m_rrr):.2f}</code>')
    except Exception:
        pass

    # Signal recommendation (narrative from pattern classification)
    try:
        rec = signal.get('signal_recommendation') if isinstance(signal, dict) else None
        if rec and isinstance(rec, dict):
            align = rec.get('alignment', 'neutral')
            label = rec.get('label', '')
            because = rec.get('because', '')
            suggested = rec.get('suggested_side', '')
            icon = {'confirms': '✅', 'contradicts': '⚠️', 'neutral': '⚪'}.get(align, '⚪')
            lines.append(f'{icon} <b>{_escape_html(label)}</b> — <i>{_escape_html(because)}</i>')
            sig_side = str(signal.get('signal') or '').lower()
            if suggested == 'wait' or (suggested and suggested != sig_side):
                side_txt = suggested.upper() if suggested != 'wait' else 'WAIT / No trade'
                lines.append(f'💡 <b>Suggested side:</b> <code>{_escape_html(side_txt)}</code>')
    except Exception:
        pass

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
