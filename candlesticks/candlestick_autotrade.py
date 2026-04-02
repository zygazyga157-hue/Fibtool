"""
candlesticks.candlestick_autotrade

Mechanical, balanced auto-trade gates for the candlestick pattern strategy.

This module is intentionally:
- "closed-bar only" (avoids trading on the forming candle)
- fail-fast with a single reason string
- MT5-aware (spread, open/pending exposure, order kind classification)
- auditable (writes JSONL rows for every evaluation run)

It is designed to be called from mt5_bg_collector.py after bars are saved.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from candlesticks.candlestick_signals import (
    compute_model_b_breakout,
    compute_model_a_close,
    compute_model_c_retrace,
    compute_selected_model,
    select_model,
    generate_signal_from_summary,
    summarize_latest_patterns,
    _model_b_profile,
    _pip_size_for_symbol,
    _count_pattern_class,
    _build_signal_recommendation,
    _MOMENTUM_PATTERNS,
    _REVERSAL_PATTERNS,
    _INDECISION_PATTERNS,
)


# Default "required patterns" are intentionally:
# - directional (not indecision-only like HIGHWAVE/SPINNINGTOP/DOJI-only gates)
# - ranked strong in the original notebook, plus a few widely-used staples (engulfing/hammer)
# - balanced across long/short so either side can qualify
DEFAULT_REQUIRED_PATTERNS = [
    # Top-ranked / strong set from the notebook ranking table
    "CDL3LINESTRIKE",
    "CDL3BLACKCROWS",
    "CDL3WHITESOLDIERS",
    "CDLEVENINGSTAR",
    "CDLEVENINGDOJISTAR",
    "CDLMORNINGSTAR",
    "CDLMORNINGDOJISTAR",
    "CDLABANDONEDBABY",
    "CDLBREAKAWAY",
    "CDLPIERCING",
    "CDLDARKCLOUDCOVER",
    "CDLINVERTEDHAMMER",
    "CDLMATCHINGLOW",
    "CDLHOMINGPIGEON",
    "CDLIDENTICAL3CROWS",
    "CDL3INSIDE",
    "CDL3OUTSIDE",
    # Common, reliable staples (even if lower-ranked in the table)
    "CDLENGULFING",
    "CDLHAMMER",
    "CDLSHOOTINGSTAR",
    "CDLHANGINGMAN",
    "CDLHARAMI",
    "CDLHARAMICROSS",
    "CDLKICKING",
]


def _cfg_get(cfg: Any, name: str, default: Any) -> Any:
    try:
        return getattr(cfg, name, default)
    except Exception:
        return default


def _detect_wyckoff_phase(df: pd.DataFrame, lookback: int = 100) -> Optional[str]:
    """Lightweight Wyckoff phase detector.

    Returns 'accumulation', 'distribution', or None.
    Mirrors the logic in FibSquareStrategy.detect_wyckoff_patterns but without
    the class dependency so it can be used inline here.
    """
    try:
        if df is None or len(df) < lookback:
            return None
        section = df.iloc[-lookback:]
        price_range = float(section["high"].max() - section["low"].min())
        low_min = float(section["low"].min())
        if low_min <= 0:
            return None
        range_pct = price_range / low_min * 100.0
        is_sideways = range_pct < 5.0
        if not is_sideways:
            return None

        # Trend: compare first close to close 20 bars ago
        is_downtrend = float(section["close"].iloc[0]) > float(section["close"].iloc[-20])

        # Higher lows / lower highs across 3 equal segments
        seg = len(section) // 3
        if seg < 5:
            return None
        lows = [float(section.iloc[i * seg:(i + 1) * seg]["low"].min()) for i in range(3)]
        highs = [float(section.iloc[i * seg:(i + 1) * seg]["high"].max()) for i in range(3)]
        higher_lows = lows[0] < lows[1] < lows[2]
        lower_highs = highs[0] > highs[1] > highs[2]

        if is_downtrend and higher_lows:
            return "accumulation"
        if not is_downtrend and lower_highs:
            return "distribution"
        return None
    except Exception:
        return None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_parent_dir(path: str) -> None:
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
    except Exception:
        pass


def _load_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json_atomic(path: str, data: Any) -> None:
    _ensure_parent_dir(path)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=True)
        os.replace(tmp, path)
    except Exception:
        # best-effort fallback
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=True)
        except Exception:
            pass


def _append_jsonl(path: str, row: dict) -> None:
    _ensure_parent_dir(path)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=True, default=str) + "\n")
    except Exception:
        pass


def _load_admin_settings(admin_path: str) -> dict:
    # Keep aligned with live_entry_bot_mt5 defaults.
    defaults = {
        "rr_min": 0.8,
        "rr_max": 8.0,
        "max_distance_atr": 7.0,
        "risk_pct": 1.0,
        "confirm_window": 0,
        "margin_safety_buffer": 1.1,
        "max_total_open_risk_pct": 5.0,
        "daily_loss_limit_pct": 3.0,
        "default_lot": 0.1,
    }
    try:
        d = _load_json(admin_path, None)
        if isinstance(d, dict):
            defaults.update(d)
    except Exception:
        pass
    return defaults


def _compute_atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    try:
        if df is None or len(df) < max(2, period + 1):
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


def _infer_timeframe_seconds(times: pd.Series) -> Optional[int]:
    try:
        t = pd.to_datetime(times, errors="coerce")
        t = t.dropna()
        if len(t) < 3:
            return None
        # Use median delta across the last ~50 bars.
        tail = t.iloc[-50:]
        deltas = tail.diff().dropna().dt.total_seconds().astype(float)
        deltas = deltas[deltas > 0]
        if deltas.empty:
            return None
        sec = int(round(float(deltas.median())))
        return sec if sec > 0 else None
    except Exception:
        return None


def _as_utc_dt_naive_to_aware(v: Any) -> Optional[datetime]:
    """Treat naive timestamps as UTC; return tz-aware UTC datetime."""
    try:
        dt = pd.to_datetime(v, errors="coerce")
        if pd.isna(dt):
            return None
        if isinstance(dt, pd.Timestamp):
            if dt.tzinfo is None:
                return dt.to_pydatetime().replace(tzinfo=timezone.utc)
            return dt.to_pydatetime().astimezone(timezone.utc)
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        # fallback: try datetime.fromisoformat
        dt2 = datetime.fromisoformat(str(v))
        if dt2.tzinfo is None:
            return dt2.replace(tzinfo=timezone.utc)
        return dt2.astimezone(timezone.utc)
    except Exception:
        return None


def pick_last_closed_bar(df: pd.DataFrame, grace_seconds: int = 5) -> Tuple[pd.DataFrame, int, Optional[int]]:
    """Return (df_closed, signal_idx, dropped_last_idx_or_none).

    signal_idx is the last index in df_closed. If the newest bar appears unclosed, it is dropped.
    """
    if df is None or df.empty:
        return df, -1, None
    if "time" not in df.columns:
        return df, len(df) - 1, None

    tf_sec = _infer_timeframe_seconds(df["time"])
    if not tf_sec:
        return df, len(df) - 1, None

    last_time = _as_utc_dt_naive_to_aware(df["time"].iloc[-1])
    if not last_time:
        return df, len(df) - 1, None

    now = _utcnow()
    # If we are before candle-close, treat last bar as forming and drop it.
    closes_at = last_time + timedelta(seconds=int(tf_sec))
    if now < (closes_at - timedelta(seconds=int(grace_seconds))):
        if len(df) >= 2:
            return df.iloc[:-1].reset_index(drop=True), len(df) - 2, len(df) - 1
    return df.reset_index(drop=True), len(df) - 1, None


def _in_time_window(local_dt: datetime, start_hhmm: str, end_hhmm: str) -> bool:
    """Time window on same day; no cross-midnight support needed for our defaults."""
    try:
        s_h, s_m = [int(x) for x in str(start_hhmm).split(":")]
        e_h, e_m = [int(x) for x in str(end_hhmm).split(":")]
        start = local_dt.replace(hour=s_h, minute=s_m, second=0, microsecond=0)
        end = local_dt.replace(hour=e_h, minute=e_m, second=0, microsecond=0)
        return start <= local_dt <= end
    except Exception:
        return True


def _is_in_liquid_session(now_utc: datetime, profile: str, cfg: Any) -> bool:
    if profile == "crypto":
        return True

    # DST-safe local time windows.
    try:
        from zoneinfo import ZoneInfo  # py3.9+
    except Exception:
        ZoneInfo = None

    london_tz = _cfg_get(cfg, "CANDLE_AUTOTRADE_LONDON_TZ", "Europe/London")
    ny_tz = _cfg_get(cfg, "CANDLE_AUTOTRADE_NY_TZ", "America/New_York")
    london_start = _cfg_get(cfg, "CANDLE_AUTOTRADE_LONDON_START", "07:00")
    london_end = _cfg_get(cfg, "CANDLE_AUTOTRADE_LONDON_END", "17:00")
    ny_start = _cfg_get(cfg, "CANDLE_AUTOTRADE_NY_START", "08:00")
    ny_end = _cfg_get(cfg, "CANDLE_AUTOTRADE_NY_END", "12:00")

    if ZoneInfo is None:
        # If tz support missing, fail-open rather than silently suppress trades.
        return True

    try:
        london_local = now_utc.astimezone(ZoneInfo(str(london_tz)))
        ny_local = now_utc.astimezone(ZoneInfo(str(ny_tz)))
        in_london = _in_time_window(london_local, str(london_start), str(london_end))
        in_ny = _in_time_window(ny_local, str(ny_start), str(ny_end))
        return bool(in_london or in_ny)
    except Exception:
        return True


def choose_order_kind_for_breakout(
    side: str, entry: float, bid: float, ask: float, buffer: float, late_mult: float
) -> Tuple[Optional[str], str]:
    """Return (order_kind, reason). order_kind is one of: stop, market, None (skip)."""
    side_n = (side or "").strip().lower()
    if side_n in ("buy", "long"):
        side_n = "long"
    elif side_n in ("sell", "short"):
        side_n = "short"

    try:
        bid_f = float(bid)
        ask_f = float(ask)
        entry_f = float(entry)
        buf = abs(float(buffer or 0.0))
    except Exception:
        return None, "bad_prices"

    mid = (bid_f + ask_f) / 2.0
    max_slip = buf * float(late_mult)

    if side_n == "long":
        if entry_f > ask_f:
            return "stop", "pending_stop_ok"
        # breakout already happened
        if abs(mid - entry_f) <= max_slip:
            return "market", "late_market_ok"
        return None, "late_entry"

    if side_n == "short":
        if entry_f < bid_f:
            return "stop", "pending_stop_ok"
        if abs(mid - entry_f) <= max_slip:
            return "market", "late_market_ok"
        return None, "late_entry"

    return None, "bad_side"


def _mt5_has_exposure(mt5: Any, symbol: str) -> bool:
    """True when any open position or pending order exists for symbol."""
    if mt5 is None:
        return False
    try:
        pos = None
        if hasattr(mt5, "positions_get"):
            try:
                pos = mt5.positions_get(symbol=symbol)
            except TypeError:
                pos = mt5.positions_get()
        if pos and len(pos) > 0:
            return True
    except Exception:
        pass
    try:
        orders = None
        if hasattr(mt5, "orders_get"):
            try:
                orders = mt5.orders_get(symbol=symbol)
            except TypeError:
                orders = mt5.orders_get()
        if orders and len(orders) > 0:
            return True
    except Exception:
        pass
    return False


@dataclass
class AutotradeCandidate:
    eligible: bool
    reason: str
    symbol: str
    bar_time: Optional[str] = None
    profile: Optional[str] = None
    side: Optional[str] = None  # long/short
    score: Optional[float] = None
    strong_patterns_hit: Optional[list] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    spread: Optional[float] = None
    spread_pips: Optional[float] = None
    atr: Optional[float] = None
    range_atr: Optional[float] = None
    entry: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    buffer: Optional[float] = None
    rr: Optional[float] = None
    tp_dist_atr: Optional[float] = None
    sl_dist_atr: Optional[float] = None
    entry_dist_atr: Optional[float] = None
    order_kind_chosen: Optional[str] = None  # stop/market
    wyckoff_phase: Optional[str] = None  # accumulation/distribution/None
    model_selected: Optional[str] = None  # A/B/C
    model_confidence: Optional[float] = None
    model_backup: Optional[str] = None
    model_reason: Optional[str] = None
    breakout_score: Optional[float] = None
    reflexive_rr: Optional[float] = None

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__.keys()}


def evaluate_autotrade_candidate(
    *,
    symbol: str,
    bars_df: pd.DataFrame,
    bid: float,
    ask: float,
    cfg: Any,
    outputs_dir: str = "outputs",
    grace_seconds: int = 5,
) -> AutotradeCandidate:
    # Defaults / knobs
    min_bars = int(_cfg_get(cfg, "CANDLE_AUTOTRADE_MIN_BARS", 60))
    sig_window = int(_cfg_get(cfg, "CANDLE_SIGNAL_WINDOW_BARS", 3))
    min_abs_score = float(_cfg_get(cfg, "CANDLE_AUTOTRADE_MIN_ABS_SCORE", 1.0))
    fresh_bars = int(_cfg_get(cfg, "CANDLE_AUTOTRADE_FRESH_BARS", 1))
    min_range_atr = float(_cfg_get(cfg, "CANDLE_AUTOTRADE_MIN_RANGE_ATR", 0.25))
    max_spread_pips_fx = float(_cfg_get(cfg, "CANDLE_AUTOTRADE_MAX_SPREAD_PIPS_FX", 2.5))
    max_spread_atr_frac = float(_cfg_get(cfg, "CANDLE_AUTOTRADE_MAX_SPREAD_ATR_FRAC", 0.08))
    max_entry_dist_atr = float(_cfg_get(cfg, "CANDLE_AUTOTRADE_MAX_ENTRY_DISTANCE_ATR", 1.5))
    late_mult = float(_cfg_get(cfg, "CANDLE_AUTOTRADE_LATE_ENTRY_MAX_BUFFER_MULT", 1.0))
    cooldown_s = int(_cfg_get(cfg, "CANDLE_AUTOTRADE_COOLDOWN_SECONDS", 3600))
    required = _cfg_get(cfg, "CANDLE_AUTOTRADE_REQUIRED_PATTERNS", DEFAULT_REQUIRED_PATTERNS)
    if not required:
        required = DEFAULT_REQUIRED_PATTERNS
    required = [str(x).strip().upper() for x in required if str(x).strip()]

    admin_path = os.path.join(outputs_dir, "admin_settings.json")
    state_path = _cfg_get(cfg, "CANDLE_AUTOTRADE_STATE_PATH", os.path.join(outputs_dir, "candlestick_autotrade_state.json"))

    cand = AutotradeCandidate(eligible=False, reason="init", symbol=symbol)

    # Bar integrity
    if bars_df is None or len(bars_df) < min_bars:
        cand.reason = "not_enough_bars"
        return cand

    df = bars_df.copy()
    df = df.rename(columns={c: str(c).lower() for c in df.columns})
    if "time" not in df.columns:
        cand.reason = "missing_time"
        return cand
    for c in ("open", "high", "low", "close"):
        if c not in df.columns:
            cand.reason = f"missing_{c}"
            return cand

    # Closed-bar selection
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df = df.dropna(subset=["time"]).reset_index(drop=True)
    df_closed, sig_idx, dropped = pick_last_closed_bar(df, grace_seconds=grace_seconds)
    if df_closed is None or df_closed.empty or sig_idx < 0:
        cand.reason = "no_closed_bar"
        return cand

    sig_row = df_closed.iloc[sig_idx]
    bar_time_utc = _as_utc_dt_naive_to_aware(sig_row["time"])
    cand.bar_time = bar_time_utc.isoformat() if bar_time_utc else str(sig_row["time"])

    # New-bar dedupe + cooldown
    state = _load_json(str(state_path), {}) or {}
    sym_state = state.get(symbol, {}) if isinstance(state, dict) else {}
    if isinstance(sym_state, dict):
        if sym_state.get("last_bar_time") == cand.bar_time:
            cand.reason = "dedupe_same_bar"
            return cand
        # cooldown check uses last_trade_time only
        try:
            last_trade = sym_state.get("last_trade_time")
            if last_trade:
                lt = datetime.fromisoformat(str(last_trade))
                if lt.tzinfo is None:
                    lt = lt.replace(tzinfo=timezone.utc)
                if (_utcnow() - lt).total_seconds() < cooldown_s:
                    cand.reason = "cooldown"
                    return cand
        except Exception:
            pass

    # Profile + session gate
    profile = str(_model_b_profile(symbol or "") or "other").lower()
    cand.profile = profile
    if not _is_in_liquid_session(_utcnow(), profile, cfg):
        cand.reason = "outside_liquid_session"
        # mark last_bar_time so we don't repeatedly re-evaluate the same closed bar
        if isinstance(state, dict):
            state[symbol] = {"last_bar_time": cand.bar_time, **(sym_state if isinstance(sym_state, dict) else {})}
            _save_json_atomic(str(state_path), state)
        return cand

    # Signal gates
    counts = summarize_latest_patterns(df_closed, window=sig_window)
    sig = generate_signal_from_summary(counts)
    action = (sig.get("signal") if isinstance(sig, dict) else None) if sig else None
    score = float(sig.get("score")) if isinstance(sig, dict) and sig.get("score") is not None else None
    cand.score = score

    if action not in ("buy", "sell"):
        cand.reason = "no_signal"
        if isinstance(state, dict):
            state[symbol] = {"last_bar_time": cand.bar_time, **(sym_state if isinstance(sym_state, dict) else {})}
            _save_json_atomic(str(state_path), state)
        return cand

    if score is None or abs(float(score)) < min_abs_score:
        cand.reason = "score_too_low"
        if isinstance(state, dict):
            state[symbol] = {"last_bar_time": cand.bar_time, **(sym_state if isinstance(sym_state, dict) else {})}
            _save_json_atomic(str(state_path), state)
        return cand

    side = "long" if action == "buy" else "short"
    cand.side = side

    # Strong-pattern requirement (directional + fresh)
    last_idx = len(df_closed) - 1
    hits = []
    for pname in required:
        meta = counts.get(pname) if isinstance(counts, dict) else None
        if not isinstance(meta, dict):
            continue
        bcnt = int(meta.get("bull_count", 0) or 0)
        scnt = int(meta.get("bear_count", 0) or 0)
        p_last_idx = int(meta.get("last_idx", -1) or -1)
        fresh_ok = p_last_idx >= (last_idx - fresh_bars)
        if not fresh_ok:
            continue
        if side == "long" and bcnt > 0:
            hits.append(pname)
        if side == "short" and scnt > 0:
            hits.append(pname)
    cand.strong_patterns_hit = hits
    if not hits:
        cand.reason = "no_strong_pattern"
        if isinstance(state, dict):
            state[symbol] = {"last_bar_time": cand.bar_time, **(sym_state if isinstance(sym_state, dict) else {})}
            _save_json_atomic(str(state_path), state)
        return cand

    # Classification hold: suppress trades when indecision dominates
    if bool(_cfg_get(cfg, "CANDLE_AUTOTRADE_CLASSIFICATION_HOLD", True)):
        _mom = _count_pattern_class(hits, _MOMENTUM_PATTERNS)
        _rev = _count_pattern_class(hits, _REVERSAL_PATTERNS)
        _ind = _count_pattern_class(hits, _INDECISION_PATTERNS)
        _rec = _build_signal_recommendation(
            side=action, pattern_hits=hits,
            momentum=_mom, reversal=_rev, indecision=_ind,
        )
        cand.signal_recommendation = _rec
        if _rec.get("suggested_side") == "wait":
            cand.reason = "classification_hold_indecision"
            if isinstance(state, dict):
                state[symbol] = {"last_bar_time": cand.bar_time, **(sym_state if isinstance(sym_state, dict) else {})}
                _save_json_atomic(str(state_path), state)
            return cand

    # Market condition gates
    try:
        bid_f = float(bid)
        ask_f = float(ask)
    except Exception:
        cand.reason = "missing_tick"
        return cand
    if bid_f <= 0 or ask_f <= 0 or ask_f < bid_f:
        cand.reason = "bad_tick"
        return cand

    spread = ask_f - bid_f
    mid = (bid_f + ask_f) / 2.0
    cand.bid = bid_f
    cand.ask = ask_f
    cand.spread = float(spread)

    atr = _compute_atr(df_closed.tail(200), period=14)
    cand.atr = float(atr) if atr else None

    pip = _pip_size_for_symbol(symbol or "")
    if pip:
        cand.spread_pips = float(spread) / float(pip) if float(pip) > 0 else None
        if cand.spread_pips is not None and cand.spread_pips > max_spread_pips_fx:
            cand.reason = "spread_too_wide"
            if isinstance(state, dict):
                state[symbol] = {"last_bar_time": cand.bar_time, **(sym_state if isinstance(sym_state, dict) else {})}
                _save_json_atomic(str(state_path), state)
            return cand
    else:
        if atr and (float(spread) > float(atr) * max_spread_atr_frac):
            cand.reason = "spread_too_wide"
            if isinstance(state, dict):
                state[symbol] = {"last_bar_time": cand.bar_time, **(sym_state if isinstance(sym_state, dict) else {})}
                _save_json_atomic(str(state_path), state)
            return cand

    try:
        candle_range = float(sig_row["high"]) - float(sig_row["low"])
    except Exception:
        candle_range = None
    if atr and candle_range is not None and candle_range >= 0:
        cand.range_atr = float(candle_range) / float(atr) if float(atr) > 0 else None
        if cand.range_atr is not None and cand.range_atr < min_range_atr:
            cand.reason = "impulse_too_small"
            if isinstance(state, dict):
                state[symbol] = {"last_bar_time": cand.bar_time, **(sym_state if isinstance(sym_state, dict) else {})}
                _save_json_atomic(str(state_path), state)
            return cand

    # Trade construction via Model Selection Engine
    wyckoff_phase = _detect_wyckoff_phase(df_closed.tail(200))
    cand.wyckoff_phase = wyckoff_phase

    mse_signal = {"signal": action, "score": score}
    mse_result = compute_selected_model(
        df_closed.tail(200),
        mse_signal,
        strong_patterns_hit=hits,
        wyckoff_phase=wyckoff_phase,
        spread=spread,
        symbol=symbol,
        cfg=cfg,
    )
    sel = mse_result.get("selection", {})
    pred = mse_result.get("primary", {})

    cand.model_selected = sel.get("model")
    cand.model_confidence = sel.get("confidence")
    cand.model_backup = sel.get("backup_model")
    cand.model_reason = sel.get("reason")
    cand.breakout_score = sel.get("breakout_score")
    cand.reflexive_rr = sel.get("reflexive_rr")

    if not pred:
        cand.reason = "model_missing"
        if isinstance(state, dict):
            state[symbol] = {"last_bar_time": cand.bar_time, **(sym_state if isinstance(sym_state, dict) else {})}
            _save_json_atomic(str(state_path), state)
        return cand

    entry = pred.get("entry")
    sl = pred.get("stop")
    tp = pred.get("tp")
    buf = pred.get("buffer") or 0.0
    atr_pred = pred.get("atr")

    try:
        entry_f = float(entry)
        sl_f = float(sl)
        tp_f = float(tp)
        buf_f = float(buf or 0.0)
    except Exception:
        cand.reason = "model_bad_levels"
        if isinstance(state, dict):
            state[symbol] = {"last_bar_time": cand.bar_time, **(sym_state if isinstance(sym_state, dict) else {})}
            _save_json_atomic(str(state_path), state)
        return cand

    if atr is None and atr_pred:
        try:
            atr = float(atr_pred)
            cand.atr = atr
        except Exception:
            pass

    risk = abs(entry_f - sl_f)
    if risk <= 0:
        cand.reason = "bad_risk"
        if isinstance(state, dict):
            state[symbol] = {"last_bar_time": cand.bar_time, **(sym_state if isinstance(sym_state, dict) else {})}
            _save_json_atomic(str(state_path), state)
        return cand

    # Entry distance gate
    if atr and float(atr) > 0:
        entry_dist_atr = abs(entry_f - mid) / float(atr)
        cand.entry_dist_atr = float(entry_dist_atr)
        if entry_dist_atr > max_entry_dist_atr:
            cand.reason = "entry_too_far"
            if isinstance(state, dict):
                state[symbol] = {"last_bar_time": cand.bar_time, **(sym_state if isinstance(sym_state, dict) else {})}
                _save_json_atomic(str(state_path), state)
            return cand

    # RR/Distance gates (admin)
    admin = _load_admin_settings(admin_path)
    rr_min = float(admin.get("rr_min", 0.8))
    rr_max = float(admin.get("rr_max", 8.0))
    max_dist_atr = float(admin.get("max_distance_atr", 7.0))

    tp_dist = abs(tp_f - entry_f)
    sl_dist = abs(entry_f - sl_f)
    rr = (tp_dist / sl_dist) if sl_dist not in (0.0, None) else None
    cand.rr = float(rr) if rr is not None else None

    if rr is not None and (rr < rr_min or rr > rr_max):
        cand.reason = "rr_out_of_bounds"
        if isinstance(state, dict):
            state[symbol] = {"last_bar_time": cand.bar_time, **(sym_state if isinstance(sym_state, dict) else {})}
            _save_json_atomic(str(state_path), state)
        return cand

    if atr and float(atr) > 0:
        cand.tp_dist_atr = float(tp_dist) / float(atr)
        cand.sl_dist_atr = float(sl_dist) / float(atr)
        if cand.tp_dist_atr is not None and cand.tp_dist_atr > max_dist_atr:
            cand.reason = "tp_too_far"
            if isinstance(state, dict):
                state[symbol] = {"last_bar_time": cand.bar_time, **(sym_state if isinstance(sym_state, dict) else {})}
                _save_json_atomic(str(state_path), state)
            return cand
        if cand.sl_dist_atr is not None and cand.sl_dist_atr > max_dist_atr:
            cand.reason = "sl_too_far"
            if isinstance(state, dict):
                state[symbol] = {"last_bar_time": cand.bar_time, **(sym_state if isinstance(sym_state, dict) else {})}
                _save_json_atomic(str(state_path), state)
            return cand

    # Order kind classification — model-aware
    selected_model = sel.get("model", "B")
    if selected_model == "A":
        # Model A: immediate entry at close — always market order
        order_kind = "market"
    elif selected_model == "C":
        # Model C: retrace/limit entry — limit order
        order_kind = "limit"
    else:
        # Model B: breakout — stop or market depending on where price is
        order_kind, ok_reason = choose_order_kind_for_breakout(side, entry_f, bid_f, ask_f, buf_f, late_mult)
        if order_kind is None:
            cand.reason = ok_reason
            if isinstance(state, dict):
                state[symbol] = {"last_bar_time": cand.bar_time, **(sym_state if isinstance(sym_state, dict) else {})}
                _save_json_atomic(str(state_path), state)
            return cand

    # Success: fill candidate details
    cand.eligible = True
    cand.reason = "eligible"
    cand.entry = float(entry_f)
    cand.sl = float(sl_f)
    cand.tp = float(tp_f)
    cand.buffer = float(buf_f)
    cand.order_kind_chosen = order_kind

    # Update last_bar_time in state so we don't re-evaluate the same closed bar.
    if isinstance(state, dict):
        merged = dict(sym_state) if isinstance(sym_state, dict) else {}
        merged["last_bar_time"] = cand.bar_time
        state[symbol] = merged
        _save_json_atomic(str(state_path), state)

    return cand


def run_autotrade_for_symbol(
    *,
    symbol: str,
    bars_path: str,
    mt5: Any,
    cfg: Any,
    outputs_dir: str = "outputs",
) -> dict:
    """Evaluate + (optionally) execute a candlestick auto-trade for one symbol.

    Returns a dict with evaluation + execution result, and appends a JSONL audit row.
    """
    audit_path = os.path.join(outputs_dir, "candlestick_autotrade_audit.jsonl")
    admin_path = os.path.join(outputs_dir, "admin_settings.json")
    state_path = _cfg_get(cfg, "CANDLE_AUTOTRADE_STATE_PATH", os.path.join(outputs_dir, "candlestick_autotrade_state.json"))

    dry_run = bool(_cfg_get(cfg, "CANDLE_AUTOTRADE_DRY_RUN", True) or _cfg_get(cfg, "TEST_MODE", False))

    out: dict = {"symbol": symbol, "bars_path": bars_path, "time": _utcnow().isoformat(), "dry_run": dry_run}

    # System toggles
    if not bool(_cfg_get(cfg, "CANDLE_AUTOTRADE_ENABLED", False)):
        out.update({"status": "disabled"})
        return out

    def _audit_early(status: str, reason: str, *, execution: Optional[dict] = None, extra: Optional[dict] = None) -> dict:
        row = {
            "time": _utcnow().isoformat(),
            "symbol": symbol,
            "eligible": False,
            "status": status,
            "reason": reason,
            "bar_time": None,
            "profile": None,
            "side": None,
            "score": None,
            "strong_patterns_hit": None,
            "bid": None,
            "ask": None,
            "spread": None,
            "spread_pips": None,
            "atr": None,
            "range_atr": None,
            "entry": None,
            "sl": None,
            "tp": None,
            "buffer": None,
            "rr": None,
            "tp_dist_atr": None,
            "sl_dist_atr": None,
            "entry_dist_atr": None,
            "order_kind_chosen": None,
            "wyckoff_phase": None,
            "model_selected": None,
            "model_confidence": None,
            "model_backup": None,
            "model_reason": None,
            "dry_run": dry_run,
            "execution": execution,
        }
        if extra and isinstance(extra, dict):
            row.update(extra)
        _append_jsonl(audit_path, row)
        out.update({"status": status, "reason": reason, "execution": execution})
        if extra and isinstance(extra, dict):
            out.update(extra)
        return out

    try:
        auto_state = _load_json(os.path.join(outputs_dir, "auto_state.json"), {"auto_trade": False})
        if not (isinstance(auto_state, dict) and auto_state.get("auto_trade", False)):
            return _audit_early("auto_off", "auto_state_off")
    except Exception:
        return _audit_early("auto_off", "auto_state_read_failed")

    # MT5 tick + select
    try:
        if mt5 is None:
            return _audit_early("mt5_missing", "mt5_missing")
        try:
            sel_ok = mt5.symbol_select(symbol, True)
            if sel_ok is False:
                return _audit_early("symbol_select_failed", "symbol_select_failed")
        except Exception:
            pass
        tick = mt5.symbol_info_tick(symbol) if hasattr(mt5, "symbol_info_tick") else None
        bid = float(getattr(tick, "bid", 0.0)) if tick is not None else 0.0
        ask = float(getattr(tick, "ask", 0.0)) if tick is not None else 0.0
        if bid <= 0 or ask <= 0:
            return _audit_early("no_tick", "no_tick")
    except Exception as e:
        return _audit_early("tick_error", "tick_error", extra={"error": str(e)})

    # Exposure gate
    if _mt5_has_exposure(mt5, symbol):
        return _audit_early("skip_exposure", "skip_exposure", extra={"bid": bid, "ask": ask})

    # Load bars
    try:
        df = pd.read_csv(bars_path)
    except Exception as e:
        return _audit_early("bars_load_failed", "bars_load_failed", extra={"error": str(e), "bid": bid, "ask": ask})

    cand = evaluate_autotrade_candidate(
        symbol=symbol,
        bars_df=df,
        bid=bid,
        ask=ask,
        cfg=cfg,
        outputs_dir=outputs_dir,
    )
    out["candidate"] = cand.to_dict()

    # Audit row (always when called)
    audit_row = {
        "time": _utcnow().isoformat(),
        "symbol": symbol,
        "eligible": cand.eligible,
        "reason": cand.reason,
        "status": "eligible" if cand.eligible else "ineligible",
        "bar_time": cand.bar_time,
        "profile": cand.profile,
        "side": cand.side,
        "score": cand.score,
        "strong_patterns_hit": cand.strong_patterns_hit,
        "bid": cand.bid,
        "ask": cand.ask,
        "spread": cand.spread,
        "spread_pips": cand.spread_pips,
        "atr": cand.atr,
        "range_atr": cand.range_atr,
        "entry": cand.entry,
        "sl": cand.sl,
        "tp": cand.tp,
        "buffer": cand.buffer,
        "rr": cand.rr,
        "tp_dist_atr": cand.tp_dist_atr,
        "sl_dist_atr": cand.sl_dist_atr,
        "entry_dist_atr": cand.entry_dist_atr,
        "order_kind_chosen": cand.order_kind_chosen,
        "wyckoff_phase": cand.wyckoff_phase,
        "model_selected": cand.model_selected,
        "model_confidence": cand.model_confidence,
        "model_backup": cand.model_backup,
        "model_reason": cand.model_reason,
        "dry_run": dry_run,
    }

    exec_res: Optional[dict] = None
    if cand.eligible:
        # Determine price parameter for live_entry_bot: pending uses entry, market uses current ask/bid.
        try:
            from live_entry_bot_mt5 import send_order
        except Exception as e:
            exec_res = {"status": "send_order_import_failed", "error": str(e)}
        else:
            try:
                volume = float(_load_admin_settings(admin_path).get("default_lot", 0.1))
            except Exception:
                volume = 0.1

            order_kind = cand.order_kind_chosen
            price = cand.entry
            if order_kind == "market":
                price = ask if cand.side == "long" else bid
            model_tag = (cand.model_selected or "b").lower()
            comment = f"candle_model{model_tag}_{order_kind}"

            try:
                exec_res = send_order(
                    symbol=symbol,
                    side=cand.side,
                    volume=volume,
                    price=float(price),
                    stop=float(cand.sl) if cand.sl is not None else None,
                    tp=float(cand.tp) if cand.tp is not None else None,
                    comment=comment,
                    dry_run=dry_run,
                    order_kind=str(order_kind),
                )
            except Exception as e:
                exec_res = {"status": "send_order_failed", "error": str(e)}

        # Update trade time in state on attempted execution (including dry-run), so cooldown works.
        try:
            state = _load_json(str(state_path), {}) or {}
            sym_state = state.get(symbol, {}) if isinstance(state, dict) else {}
            merged = dict(sym_state) if isinstance(sym_state, dict) else {}
            merged["last_trade_time"] = _utcnow().isoformat()
            # keep last_bar_time already written by evaluator
            if cand.bar_time:
                merged["last_bar_time"] = cand.bar_time
            state[symbol] = merged
            _save_json_atomic(str(state_path), state)
        except Exception:
            pass

    out["execution"] = exec_res
    audit_row["execution"] = exec_res
    _append_jsonl(audit_path, audit_row)

    out["status"] = "eligible" if cand.eligible else "ineligible"
    return out
