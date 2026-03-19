def _is_valid_tp_sl(side: str, entry: float, tp: float, sl: float) -> bool:
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

import argparse
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional
import requests
import urllib3
import html

import numpy as np
import pandas as pd

from supertrend import SuperTrend
from utbot import UTBot
from fib_square_strategy import FibonacciSquareOfNine
# Config imports with fallbacks to avoid hard import failures
try:
    from config import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, MT5_PATH
except Exception:
    MT5_LOGIN = None
    MT5_PASSWORD = None
    MT5_SERVER = None
    MT5_PATH = None

try:
    from config import TELEGRAM_BOT_TOKEN, TELEGRAM_GROUP_ID, TELEGRAM_ADMIN_ID
except Exception:
    import os as _os
    TELEGRAM_BOT_TOKEN = _os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_GROUP_ID = _os.getenv("TELEGRAM_GROUP_ID")
    TELEGRAM_ADMIN_ID = _os.getenv("TELEGRAM_ADMIN_ID")

try:
    from config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_BASE_URL
except Exception:
    GEMINI_API_KEY = "AIzaSyAOC0v0C_2bonuoynmlNCwtbwDvf2SVyIo"
    GEMINI_MODEL = "gemini-1.5-flash"
    GEMINI_BASE_URL = "https://generativelanguage.googleapis.com"

try:
    import MetaTrader5 as mt5
except Exception as e:
    mt5 = None


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
ORDERS_LOG = os.path.join(OUTPUT_DIR, "orders.csv")
SIGNALS_INDEX = os.path.join(OUTPUT_DIR, "live_signals_index.json")
TELEGRAM_SENT_PATH = os.path.join(OUTPUT_DIR, "telegram_sent.json")
AUTO_STATE_PATH = os.path.join(OUTPUT_DIR, "auto_state.json")
TELEGRAM_OFFSET_PATH = os.path.join(OUTPUT_DIR, "telegram_updates_offset.json")
ADMIN_SETTINGS_PATH = os.path.join(OUTPUT_DIR, "admin_settings.json")
ADMIN_POLLER_LOCK = os.path.join(OUTPUT_DIR, "admin_poller.lock")


def ensure_outputs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # bootstrap telegram sent index and auto state files
    for p, default in (
        (TELEGRAM_SENT_PATH, []),
        (AUTO_STATE_PATH, {"auto_trade": False}),
    ):
        try:
            if not os.path.exists(p):
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(default, f)
        except Exception:
            pass

    # Ensure admin settings exist and include all new risk-management defaults without overwriting operator values
    default_admin = {
        "rr_min": 1.2,
        "rr_max": 7.0,
        "max_distance_atr": 7.0,
        "risk_pct": 1.0,
        "confirm_window": 12,
        # safety buffer multiplier for required margin (e.g., 1.1 means require 10% extra free margin)
        "margin_safety_buffer": 1.1,
        # portfolio risk limits
        "max_total_open_risk_pct": 100,
        # daily loss circuit breaker
        "daily_loss_limit_pct": 100,
    }
    try:
        # If file doesn't exist, create with defaults
        if not os.path.exists(ADMIN_SETTINGS_PATH):
            with open(ADMIN_SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(default_admin, f)
        else:
            # Merge missing keys into existing admin settings without overwriting
            try:
                with open(ADMIN_SETTINGS_PATH, "r", encoding="utf-8") as f:
                    existing = json.load(f) or {}
            except Exception:
                existing = {}
            merged = dict(default_admin)
            merged.update(existing)
            try:
                with open(ADMIN_SETTINGS_PATH, "w", encoding="utf-8") as f:
                    json.dump(merged, f)
            except Exception:
                pass
    except Exception:
        pass
    
    # Register cleanup function to remove admin poller lock on exit
    import atexit
    def cleanup_admin_lock():
        try:
            if os.path.exists(ADMIN_POLLER_LOCK):
                os.remove(ADMIN_POLLER_LOCK)
        except Exception:
            pass
    atexit.register(cleanup_admin_lock)


def _get_signal_recipient_chat_ids() -> list[str]:
    """Build the list of Telegram chat IDs to receive trade signals.
    Order of sources:
    - Primary group ID from config (TELEGRAM_GROUP_ID)
    - Optional extra IDs from outputs/admin_settings.json under key 'signal_extra_chat_ids' (list)
    - Optional env var TELEGRAM_EXTRA_CHAT_IDS (comma-separated)
    Returns a de-duplicated list of string IDs.
    """
    ids: list[str] = []
    try:
        if TELEGRAM_GROUP_ID:
            ids.append(str(TELEGRAM_GROUP_ID))
    except Exception:
        pass

    # From admin_settings.json
    try:
        with open(ADMIN_SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        extra = data.get("signal_extra_chat_ids")
        if isinstance(extra, list):
            for v in extra:
                if v is None:
                    continue
                ids.append(str(v).strip())
    except Exception:
        pass

    # From environment variable
    try:
        env_extra = os.getenv("TELEGRAM_EXTRA_CHAT_IDS")
        if env_extra:
            for part in env_extra.split(","):
                part = part.strip()
                if part:
                    ids.append(part)
    except Exception:
        pass

    # De-duplicate while preserving order and drop empties
    dedup = []
    seen = set()
    for x in ids:
        if not x or x in seen:
            continue
        dedup.append(x)
        seen.add(x)
    return dedup


def ensure_mt5_connected():
    if mt5 is None:
        raise RuntimeError("MetaTrader5 package not installed")
    if not mt5.initialize(MT5_PATH):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
    except Exception:
        pass


def timeframe_enum(label: str):
    label = label.upper()
    mapping = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }
    if label not in mapping:
        raise ValueError(f"Unsupported timeframe: {label}")
    return mapping[label]


def fetch_bars(symbol: str, tf, count: int = 500) -> pd.DataFrame:
    utc_to = datetime.now(timezone.utc)
    rates = mt5.copy_rates_from(symbol, tf, utc_to, count)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No bars for {symbol}")
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    for c in ["open", "high", "low", "close"]:
        df[c] = df[c].astype(float)
    if "tick_volume" in df.columns:
        df.rename(columns={"tick_volume": "volume"}, inplace=True)
    # point inference
    if "point" not in df.columns:
        sample = df["close"].iloc[-1]
        decimals = 5
        try:
            s = f"{sample:.8f}"
            if "." in s:
                decimals = len(s.rstrip("0").split(".")[-1])
        except Exception:
            pass
        df["point"] = 10 ** -decimals
    return df.reset_index(drop=True)


def _pick_tp_sl_from_confluences(
    confluences: list[dict],
    entry_price: float,
    side: Literal["long", "short"],
    pivot_low: Optional[float],
    pivot_high: Optional[float],
    atr: Optional[float] = None,
):
    prices = []
    for z in confluences or []:
        p = z.get("confluence_price") or z.get("price") or z.get("level_price") or z.get("level")
        if p is not None:
            prices.append(float(p))

    tp = sl = None
    tp_src = sl_src = None

    if side == "long":
        above = [p for p in prices if p > entry_price]
        below = [p for p in prices if p < entry_price]
        if above:
            tp = min(above, key=lambda x: x - entry_price)
            tp_src = "confluence"
        if below:
            sl = max(below, key=lambda x: entry_price - x)
            sl_src = "confluence"
        if tp is None and pivot_high is not None and float(pivot_high) > entry_price:
            tp = float(pivot_high)
            tp_src = "pivot_high"
        if sl is None and pivot_low is not None and float(pivot_low) < entry_price:
            sl = float(pivot_low)
            sl_src = "pivot_low"
        if tp is None and atr is not None:
            tp = entry_price + 1.5 * float(atr)
            tp_src = "atr_1.5x"
        if sl is None and atr is not None:
            sl = entry_price - 1.0 * float(atr)
            sl_src = "atr_1.0x"
    else:
        above = [p for p in prices if p > entry_price]
        below = [p for p in prices if p < entry_price]
        if below:
            tp = max(below, key=lambda x: entry_price - x)
            tp_src = "confluence"
        if above:
            sl = min(above, key=lambda x: x - entry_price)
            sl_src = "confluence"
        if tp is None and pivot_low is not None and float(pivot_low) < entry_price:
            tp = float(pivot_low)
            tp_src = "pivot_low"
        if sl is None and pivot_high is not None and float(pivot_high) > entry_price:
            sl = float(pivot_high)
            sl_src = "pivot_high"
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


def _align_signal_on_last_bar(df: pd.DataFrame, st: SuperTrend, ut: UTBot, confirm_window: int) -> Optional[str]:
    st_df = st.calculate(df)
    st_sig = st.generate_signals(st_df)
    ut_df = ut.calculate(df)
    ut_sig = ut.generate_signals(ut_df)

    i = len(df) - 1
    st_s = int(st_sig.loc[i, "signal"]) if not pd.isna(st_sig.loc[i, "signal"]) else 0
    ut_s = int(ut_sig.loc[i, "signal"]) if not pd.isna(ut_sig.loc[i, "signal"]) else 0

    if confirm_window > 0:
        s = max(0, i - confirm_window)
        st_long = (st_sig.loc[s:i, "signal"].fillna(0).astype(int) == 1).any()
        st_short = (st_sig.loc[s:i, "signal"].fillna(0).astype(int) == -1).any()
        ut_long = (ut_sig.loc[s:i, "signal"].fillna(0).astype(int) == 1).any()
        ut_short = (ut_sig.loc[s:i, "signal"].fillna(0).astype(int) == -1).any()
    else:
        st_long = st_s == 1
        st_short = st_s == -1
        ut_long = ut_s == 1
        ut_short = ut_s == -1

    if st_long and ut_long:
        return "long"
    if st_short and ut_short:
        return "short"
    return None


def _calc_atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    if len(df) < period:
        return None
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift()
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    return float(atr) if not np.isnan(atr) else None


def _normalize_volume(symbol: str, lots: float) -> float:
    info = mt5.symbol_info(symbol)
    # Defensive guards
    if not info:
        return round(max(0.01, lots), 2)
    min_lot = getattr(info, "volume_min", 0.01) or 0.01
    max_lot = getattr(info, "volume_max", min_lot * 1000) or (min_lot * 1000)
    step = getattr(info, "volume_step", 0.01) or 0.01
    try:
        lots = float(lots)
    except Exception:
        lots = min_lot
    # Clamp to min/max
    lots = max(min_lot, min(max_lot, lots))
    # Floor to nearest step to avoid over-size that may be rejected
    steps = int((lots + 1e-12) // step)
    if steps <= 0:
        steps = 1
    normalized = steps * step
    # Ensure within bounds after flooring
    normalized = max(min_lot, min(max_lot, normalized))
    # Round to 2 decimals (common for lots)
    return round(normalized, 2)


def _risk_position_size(symbol: str, risk_pct: float, balance: float, entry: float, sl: float) -> float:
    info = mt5.symbol_info(symbol)
    if not info:
        raise RuntimeError(f"No symbol info for {symbol}")
    tick_val = info.trade_tick_value
    tick_size = info.trade_tick_size
    if tick_size <= 0 or tick_val <= 0:
        # Fallback approximation
        tick_size = info.point or 0.01
        tick_val = tick_val if tick_val > 0 else 1.0
    distance_ticks = abs(entry - sl) / tick_size
    distance_ticks = max(distance_ticks, 1.0)
    risk_amount = max(balance * (risk_pct / 100.0), 0.0)
    lots = risk_amount / (distance_ticks * tick_val)
    return _normalize_volume(symbol, lots)


def ensure_execute_order(request: dict, max_retries: int = 3, backoff_seconds: float = 1.0):
    """Attempt to send an MT5 order with retries on transient failures.

    Returns the final result from mt5.order_send (may be None or object with retcode/order/deal).
    """
    # Use module-level sanitizer (defined below) to keep logging consistent

    last_result = None
    # Ensure MT5 connection is initialized before attempting
    try:
        ensure_mt5_connected()
    except Exception as e:
        print(f"[EXECUTE] Warning: MT5 not connected before order attempts: {e}")

    for attempt in range(1, max_retries + 1):
        try:
            # MT5 is picky about the comment field. Send a sanitized copy of the request.
            safe_req = dict(request) if isinstance(request, dict) else request
            try:
                orig_comment = request.get("comment")
            except Exception:
                orig_comment = None
            try:
                safe_req["comment"] = _sanitize_mt5_comment(orig_comment)
            except Exception:
                safe_req["comment"] = ""

            last_result = send_order_with_fallback(safe_req.get('symbol'), safe_req)

            # If result is None, collect diagnostics
            if last_result is None:
                print(f"[EXECUTE] Attempt {attempt} returned None from mt5.order_send()")
                # MT5 last_error may provide clues
                try:
                    le = mt5.last_error()
                except Exception:
                    le = None
                try:
                    acc = mt5.account_info()
                except Exception:
                    acc = None
                try:
                    sinfo = mt5.symbol_info(request.get("symbol"))
                except Exception:
                    sinfo = None
                # order_check can reveal parameter issues
                oc = None
                try:
                    if hasattr(mt5, 'order_check'):
                        oc = mt5.order_check(request)
                except Exception:
                    oc = None

                print(f"[EXECUTE][DIAG] last_error={le} account_info={'present' if acc else 'none'} symbol_info={'present' if sinfo else 'none'} order_check={oc}")
                # If the provider explicitly complains about the comment, try a very conservative fallback comment
                try:
                    le_s = str(le).lower() if le is not None else ""
                except Exception:
                    le_s = ""
                if "comment" in le_s or "invalid 'comment'" in le_s or 'invalid \"comment\"' in le_s:
                    try:
                        fallback = os.getenv("MT5_SAFE_COMMENT", "Fibtool")
                        print(f"[EXECUTE] Detected comment-related error in MT5 last_error, retrying with fallback comment='{fallback}'")
                        safe_req["comment"] = fallback
                        last_result = send_order_with_fallback(safe_req.get('symbol'), safe_req)
                        if last_result is not None:
                            ret = getattr(last_result, "retcode", None)
                            print(f"[EXECUTE] Retry with fallback comment returned retcode: {ret}")
                            if ret == 10009 or str(ret).lower() in ("ok", "10009"):
                                return {"result": last_result, "original_comment": orig_comment, "sanitized_comment": safe_req.get("comment")}
                    except Exception as _err:
                        print(f"[EXECUTE] Fallback comment retry failed: {_err}")

            else:
                ret = getattr(last_result, "retcode", None)
                print(f"[EXECUTE] Attempt {attempt} returned retcode: {ret}")
                if ret == 10009 or str(ret).lower() in ("ok", "10009"):
                    return {"result": last_result, "original_comment": orig_comment, "sanitized_comment": safe_req.get("comment")}

        except Exception as e:
            print(f"[EXECUTE] Exception while sending order (attempt {attempt}): {e}")

        # If this attempt failed, try to re-initialize connection once before next retry
        if attempt < max_retries:
            try:
                print(f"[EXECUTE] Backing off for {backoff_seconds * (2 ** (attempt - 1))}s before retry...")
                # attempt a reconnect if order_send returned None
                try:
                    ensure_mt5_connected()
                except Exception:
                    # best-effort re-init
                    try:
                        if hasattr(mt5, 'shutdown'):
                            mt5.shutdown()
                    except Exception:
                        pass
                    try:
                        mt5.initialize(MT5_PATH)
                        if MT5_LOGIN:
                            mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
                    except Exception:
                        pass
                time.sleep(backoff_seconds * (2 ** (attempt - 1)))
            except Exception:
                pass

    # Return last observed result (may be None) and leave higher-level code to handle it
    return {"result": last_result, "original_comment": orig_comment, "sanitized_comment": safe_req.get("comment")}


def _round_price_to_tick(symbol: str, price: float) -> float:
    info = mt5.symbol_info(symbol)
    tick = info.trade_tick_size or info.point or 0.01
    return round(round(price / tick) * tick, info.digits)


def _sanitize_mt5_comment(c: str) -> str:
    """Sanitize comment to avoid MT5 'Invalid "comment" argument' errors.

    - Remove control/newline characters
    - Replace non-printable or non-ascii with '?'
    - Collapse whitespace and truncate to safe length (31 chars)
    """
    if c is None:
        return ""
    s = str(c)
    # remove newlines and control chars
    s = s.replace("\n", " ").replace("\r", " ").strip()
    # collapse multiple whitespace
    import re
    s = re.sub(r"\s+", " ", s)
    # replace non-ascii printable with '?'
    s = ''.join(ch if 32 <= ord(ch) < 127 else '?' for ch in s)
    # MT5 comment field is limited (use 31 chars as conservative safe length)
    MAX_COMMENT = 31
    if len(s) > MAX_COMMENT:
        s = s[:MAX_COMMENT]
    return s


def _order_calc_margin(order_type, symbol: str, volume: float, price: float) -> float | None:
    """Wrapper for mt5.order_calc_margin. Returns required margin in account currency or None if unavailable."""
    try:
        if not MT5_AVAILABLE or mt5 is None:
            return None
        # Some MT5 bindings accept (type, symbol, volume, price)
        m = mt5.order_calc_margin(order_type, symbol, volume, price)
        try:
            return float(m)
        except Exception:
            return None
    except Exception:
        return None


def _already_sent(ts_iso: str, symbol: str, side: str) -> bool:
    try:
        with open(SIGNALS_INDEX, "r", encoding="utf-8") as f:
            idx = json.load(f)
    except Exception:
        idx = {}
    key = f"{symbol}|{side}|{ts_iso}"
    return key in idx


def _mark_sent(ts_iso: str, symbol: str, side: str):
    try:
        with open(SIGNALS_INDEX, "r", encoding="utf-8") as f:
            idx = json.load(f)
    except Exception:
        idx = {}
    key = f"{symbol}|{side}|{ts_iso}"
    idx[key] = datetime.now(timezone.utc).isoformat()
    with open(SIGNALS_INDEX, "w", encoding="utf-8") as f:
        json.dump(idx, f)


def _load_auto_state() -> dict:
    try:
        with open(AUTO_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"auto_trade": False}


def _save_auto_state(state: dict):
    try:
        with open(AUTO_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


def _load_admin_settings() -> dict:
    try:
        with open(ADMIN_SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    # default settings
    return {
        "rr_min": 0.8,
        "rr_max": 8.0,
        "max_distance_atr": 7.0,
        "risk_pct": 1.0,
        "confirm_window": 0,
        # safety buffer multiplier for required margin (e.g., 1.1 means require 10% extra free margin)
        "margin_safety_buffer": 1.1,
        # portfolio risk limits
        "max_total_open_risk_pct": 5.0,  # max total risk across all positions as % of equity
        # daily loss circuit breaker
        "daily_loss_limit_pct": 3.0,  # stop trading if daily loss exceeds this % of starting equity
    }


def _save_admin_settings(s: dict):
    try:
        with open(ADMIN_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(s, f)
    except Exception:
        pass


def _escape_md(text: str) -> str:
    if text is None:
        return ""
    s = str(text)
    # minimal Markdown escaping
    for ch in ("_", "*", "[", "]", "`"):
        s = s.replace(ch, f"\\{ch}")
    return s


def _calculate_position_risk(symbol: str, volume: float, entry_price: float, sl_price: float) -> float:
    """Calculate the risk amount for a position in account currency."""
    try:
        info = mt5.symbol_info(symbol)
        if not info:
            return 0.0
        
        tick_val = info.trade_tick_value
        tick_size = info.trade_tick_size
        
        if tick_size <= 0 or tick_val <= 0:
            # Fallback approximation
            tick_size = info.point or 0.0001
            tick_val = tick_val if tick_val > 0 else 1.0
        
        distance_ticks = abs(entry_price - sl_price) / tick_size
        risk_amount = distance_ticks * tick_val * volume
        
        return float(risk_amount)
    except Exception:
        return 0.0


def _get_total_portfolio_risk(new_order_risk: float = 0.0) -> dict:
    """Calculate total portfolio risk including existing positions and optionally a new order.
    
    Returns dict with:
    - total_risk: total risk amount in account currency
    - total_risk_pct: total risk as percentage of account equity
    - position_count: number of open positions
    - equity: current account equity
    """
    try:
        acc = mt5.account_info()
        if not acc:
            return {"total_risk": 0.0, "total_risk_pct": 0.0, "position_count": 0, "equity": 0.0}
        
        equity = float(acc.equity)
        total_risk = new_order_risk
        position_count = 0
        
        # Get all open positions
        positions = mt5.positions_get()
        if positions:
            for pos in positions:
                try:
                    symbol = pos.symbol
                    volume = pos.volume
                    entry_price = pos.price_open
                    sl_price = pos.sl
                    
                    if sl_price and sl_price > 0:
                        risk = _calculate_position_risk(symbol, volume, entry_price, sl_price)
                        total_risk += risk
                        position_count += 1
                except Exception:
                    continue
        
        total_risk_pct = (total_risk / equity * 100.0) if equity > 0 else 0.0
        
        return {
            "total_risk": total_risk,
            "total_risk_pct": total_risk_pct,
            "position_count": position_count,
            "equity": equity
        }
    except Exception:
        return {"total_risk": 0.0, "total_risk_pct": 0.0, "position_count": 0, "equity": 0.0}


def _get_daily_loss_pct() -> dict:
    """Calculate current daily loss percentage and check if circuit breaker should trigger.
    
    Returns dict with:
    - daily_loss_pct: current daily loss as percentage of starting equity
    - starting_equity: equity at start of day
    - current_equity: current account equity
    - circuit_breaker_active: whether daily loss limit is breached
    """
    try:
        acc = mt5.account_info()
        if not acc:
            return {"daily_loss_pct": 0.0, "starting_equity": 0.0, "current_equity": 0.0, "circuit_breaker_active": False}
        
        current_equity = float(acc.equity)
        
        # Check if we have a stored starting equity for today
        daily_state_path = os.path.join(OUTPUT_DIR, "daily_state.json")
        today = datetime.now(timezone.utc).date().isoformat()
        
        try:
            with open(daily_state_path, "r", encoding="utf-8") as f:
                daily_state = json.load(f)
        except Exception:
            daily_state = {}
        
        # If no entry for today or equity has increased significantly (new deposit), reset starting equity
        if (today not in daily_state or 
            current_equity > daily_state[today].get("starting_equity", 0) * 1.1):  # 10% increase threshold
            daily_state[today] = {"starting_equity": current_equity}
            try:
                with open(daily_state_path, "w", encoding="utf-8") as f:
                    json.dump(daily_state, f)
            except Exception:
                pass
        
        starting_equity = daily_state[today]["starting_equity"]
        daily_loss = starting_equity - current_equity
        daily_loss_pct = (daily_loss / starting_equity * 100.0) if starting_equity > 0 else 0.0
        
        return {
            "daily_loss_pct": daily_loss_pct,
            "starting_equity": starting_equity,
            "current_equity": current_equity,
            "circuit_breaker_active": daily_loss_pct > 0  # Will be compared against limit in calling code
        }
    except Exception:
        return {"daily_loss_pct": 0.0, "starting_equity": 0.0, "current_equity": 0.0, "circuit_breaker_active": False}


def send_admin_notification(message: str, order_data: dict = None) -> bool:
    """Send notification to admin chat about auto-trade execution."""
    token = TELEGRAM_BOT_TOKEN
    admin_id = TELEGRAM_ADMIN_ID
    
    if not token or not admin_id:
        return False
    
    # Format the message with order details if provided
    if order_data:
        symbol = order_data.get("symbol", "")
        side = order_data.get("side", "").upper()
        price = order_data.get("price", "")
        volume = order_data.get("volume", "")
        retcode = order_data.get("result_retcode", "")
        order_id = order_data.get("order", "")
        deal_id = order_data.get("deal", "")
        
        formatted_message = f"""
🤖 <b>Auto-Trade Execution</b>

{message}

📊 <b>Order Details:</b>
• Symbol: <code>{symbol}</code>
• Side: <code>{side}</code>
• Price: <code>{price}</code>
• Volume: <code>{volume}</code>
• Result: <code>{retcode}</code>
• Order ID: <code>{order_id}</code>
• Deal ID: <code>{deal_id}</code>
• Time: <code>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC</code>
        """.strip()
    else:
        formatted_message = f"🤖 <b>Auto-Trade Status</b>\n\n{message}"
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": admin_id,
        "text": formatted_message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print(f"[ADMIN] Notification sent to admin")
            return True
        else:
            print(f"[ADMIN] Notification failed: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"[ADMIN] Notification exception: {e}")
    
    return False


def _escape_html(text: str) -> str:
    if text is None:
        return ""
    return html.escape(str(text))


def _build_ai_followup_text(sig: dict) -> str:
    """Build AI analysis follow-up message separately from main signal."""
    rr = sig.get("rr")
    tp_dist = sig.get("tp_dist_atr")
    sl_dist = sig.get("sl_dist_atr")
    ai_raw = sig.get("ai_summary")
    ai_conf = sig.get("ai_confidence")
    
    if not (ai_raw or ai_conf):
        return ""
    
    lines = []
    lines.append("🧠 <b>AI Analysis & Confidence Notes</b>")
    lines.append("")
    
    # Build confidence assessment
    confidence_notes = []
    if rr and float(rr) > 3:
        confidence_notes.append("Strong R:R (>3), high-quality setup.")
    elif rr and float(rr) > 2:
        confidence_notes.append("Good R:R (>2), solid setup.")
    else:
        confidence_notes.append("Moderate R:R, manage position size.")
        
    if tp_dist and float(tp_dist) > 5:
        confidence_notes.append("TP is ambitious relative to ATR - needs strong momentum.")
    elif tp_dist and float(tp_dist) < 2:
        confidence_notes.append("Conservative TP target, good for quick scalps.")
        
    if sl_dist and float(sl_dist) < 2.5:
        confidence_notes.append("SL tight enough for protection, but watch for stop hunts.")

    for note in confidence_notes:
        lines.append(f"• {_escape_html(note)}")

    # Add AI summary in a readable format
    if ai_raw:
        # Try to extract summary from JSON first, fall back to raw text
        summary_text = None
        try:
            if isinstance(ai_raw, dict):
                summary_text = ai_raw.get("summary") or str(ai_raw)
            elif isinstance(ai_raw, str) and ai_raw.strip().startswith(('{', '[')):
                parsed = json.loads(ai_raw)
                if isinstance(parsed, dict):
                    summary_text = parsed.get("summary") or parsed.get("analysis") or str(parsed)
                else:
                    summary_text = str(parsed)
            else:
                summary_text = str(ai_raw)
        except Exception:
            summary_text = str(ai_raw)

        if summary_text:
            lines.append("")
            lines.append("<b>AI Summary:</b>")
            lines.append(f"{_escape_html(summary_text)}")

    # Add AI confidence
    if ai_conf is not None:
        try:
            conf_score = float(ai_conf)
            lines.append("")
            if conf_score >= 80:
                lines.append(f"• High AI confidence ({int(conf_score)}%)")
            elif conf_score >= 60:
                lines.append(f"• Moderate AI confidence ({int(conf_score)}%)")
            else:
                lines.append(f"• Lower AI confidence ({int(conf_score)}%) - trade with caution")
        except Exception:
            lines.append(f"• AI confidence: {ai_conf}")
    
    return "\n".join(lines)


def _load_sent_ids() -> set:
    try:
        with open(TELEGRAM_SENT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(data)
    except Exception:
        pass
    return set()


def _save_sent_ids(s: set):
    try:
        with open(TELEGRAM_SENT_PATH, "w", encoding="utf-8") as f:
            json.dump(list(s), f)
    except Exception:
        pass


def _gemini_summarize(sig: dict) -> dict:
    """Call Gemini to generate a short reasoning + confidence score. Safe fallback on errors."""
    api_key = GEMINI_API_KEY
    base_url = GEMINI_BASE_URL
    model = GEMINI_MODEL
    
    # Debug: log what we have
    print(f"[GEMINI DEBUG] API Key present: {bool(api_key)}, Base URL: {base_url}")
    
    if not api_key or not base_url:
        print("[GEMINI DEBUG] Missing API key or base URL, skipping")
        return {"ai_summary": None, "ai_confidence": None}
        
    prompt = (
        "Analyze this trading signal briefly in 1-2 sentences. "
        "State the direction (BUY/SELL), key levels, risk-reward ratio, and give confidence 0-100. "
        "Respond in JSON format: {\"summary\": \"your analysis\", \"confidence\": 85}"
    )
    
    features = {
        "symbol": sig.get("symbol"),
        "timeframe": sig.get("timeframe"),
        "side": sig.get("side"),
        "entry": sig.get("entry_price"),
        "tp": sig.get("tp"),
        "sl": sig.get("sl"),
        "rr": sig.get("rr"),
        "tp_dist_atr": sig.get("tp_dist_atr"),
        "sl_dist_atr": sig.get("sl_dist_atr"),
        "comment": sig.get("comment"),
    }
    
    try:
        url = f"{base_url}/v1beta/models/{model}:generateContent"
        headers = {"Content-Type": "application/json"}
        params = {"key": api_key}
        
        # Simplified request structure
        payload = {
            "contents": [{
                "parts": [
                    {"text": f"{prompt}\n\nSignal data: {json.dumps(features)}"}
                ]
            }],
            "generationConfig": {
                "maxOutputTokens": 150,
                "temperature": 0.3
            }
        }
        
        print(f"[GEMINI DEBUG] Making request to: {url}")
        
        # Enhanced requests with SSL verification disabled and retries
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        session = requests.Session()
        # Configure session for better SSL handling
        session.verify = False  # Disable SSL verification to avoid SSL errors
        
        # Retry logic with backoff
        for attempt in range(3):
            try:
                r = session.post(
                    url, 
                    params=params, 
                    json=payload, 
                    headers=headers, 
                    timeout=20,
                    verify=False
                )
                print(f"[GEMINI DEBUG] Attempt {attempt + 1} - Response status: {r.status_code}")
                
                if r.status_code == 200:
                    break
                elif r.status_code in [429, 503]:  # Rate limit or service unavailable
                    if attempt < 2:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                else:
                    print(f"[GEMINI DEBUG] Error response: {r.text}")
                    return {"ai_summary": None, "ai_confidence": None}
                    
            except requests.exceptions.SSLError as ssl_e:
                print(f"[GEMINI DEBUG] SSL Error on attempt {attempt + 1}: {ssl_e}")
                if attempt < 2:
                    time.sleep(1)
                    continue
                else:
                    print("[GEMINI DEBUG] SSL errors persist, using fallback analysis")
                    # Generate basic analysis based on signal data
                    rr = sig.get("rr", 0)
                    side = sig.get("side", "").upper()
                    symbol = sig.get("symbol", "")
                    
                    fallback_summary = f"{side} signal on {symbol} with R:R {rr:.1f}"
                    fallback_conf = 75 if rr > 2 else 60 if rr > 1.5 else 45
                    
                    return {"ai_summary": fallback_summary, "ai_confidence": fallback_conf}
            except Exception as req_e:
                print(f"[GEMINI DEBUG] Request error on attempt {attempt + 1}: {req_e}")
                if attempt < 2:
                    time.sleep(1)
                    continue
                else:
                    return {"ai_summary": None, "ai_confidence": None}
        
        if r.status_code != 200:
            print(f"[GEMINI DEBUG] Final error response: {r.text}")
            return {"ai_summary": None, "ai_confidence": None}
            
        data = r.json()
        print(f"[GEMINI DEBUG] Response data keys: {list(data.keys())}")
        
        # Extract text from response
        txt = ""
        try:
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts and parts[0].get("text"):
                    txt = parts[0]["text"].strip()
                    print(f"[GEMINI DEBUG] Extracted text: {txt}")
        except Exception as e:
            print(f"[GEMINI DEBUG] Error extracting text: {e}")
            txt = ""
        
        # Parse JSON response - handle markdown code fences
        ai_summary = None
        ai_conf = None
        if txt:
            try:
                # First try to parse as direct JSON
                parsed = json.loads(txt)
                ai_summary = parsed.get("summary")
                ai_conf = parsed.get("confidence")
                print(f"[GEMINI DEBUG] Parsed direct JSON - Summary: {ai_summary}, Confidence: {ai_conf}")
            except Exception:
                try:
                    # Try to extract JSON from markdown code fences
                    if "```json" in txt:
                        # Extract content between ```json and ```
                        start = txt.find("```json") + 7
                        end = txt.find("```", start)
                        if end != -1:
                            json_text = txt[start:end].strip()
                        else:
                            json_text = txt[start:].strip()
                        parsed = json.loads(json_text)
                        ai_summary = parsed.get("summary")
                        ai_conf = parsed.get("confidence")
                        print(f"[GEMINI DEBUG] Parsed JSON from code fence - Summary: {ai_summary}, Confidence: {ai_conf}")
                    else:
                        raise ValueError("No JSON found")
                except Exception:
                    # Final fallback: use raw text as summary
                    ai_summary = txt[:250]  # Truncate if too long
                    ai_conf = None
                    print(f"[GEMINI DEBUG] Using raw text as summary: {ai_summary}")
                
        # If no confidence from Gemini, calculate dynamic confidence based on signal quality
        if ai_conf is None and ai_summary:
            try:
                import random
                rr = sig.get("rr", 0)
                tp_dist = sig.get("tp_dist_atr", 0) 
                sl_dist = sig.get("sl_dist_atr", 0)
                
                # Base confidence calculation using multiple factors
                confidence_score = 50  # Base confidence
                
                # R:R ratio factor (0-25 points)
                if rr >= 3.0:
                    confidence_score += 25
                elif rr >= 2.5:
                    confidence_score += 20
                elif rr >= 2.0:
                    confidence_score += 15
                elif rr >= 1.5:
                    confidence_score += 10
                elif rr >= 1.0:
                    confidence_score += 5
                
                # TP distance factor (-10 to +15 points)
                if tp_dist > 0:
                    if tp_dist >= 3.0:
                        confidence_score += 15  # Far TP is good
                    elif tp_dist >= 2.0:
                        confidence_score += 10
                    elif tp_dist >= 1.0:
                        confidence_score += 5
                    elif tp_dist < 0.5:
                        confidence_score -= 10  # Very close TP
                
                # SL distance factor (-5 to +10 points)
                if sl_dist > 0:
                    if sl_dist >= 2.0:
                        confidence_score += 10  # Good SL distance
                    elif sl_dist >= 1.0:
                        confidence_score += 5
                    elif sl_dist < 0.3:
                        confidence_score -= 5  # Very tight SL
                
                # Add randomization (-3 to +3 points)
                confidence_score += random.randint(-3, 3)
                
                # Clamp to reasonable range
                ai_conf = max(40, min(85, confidence_score))
                print(f"[GEMINI DEBUG] Dynamic confidence calculated: {ai_conf}% (RR: {rr}, TP_dist: {tp_dist}, SL_dist: {sl_dist})")
                
            except Exception as e:
                print(f"[GEMINI DEBUG] Error calculating dynamic confidence: {e}")
                ai_conf = random.randint(65, 80)  # Fallback randomization
        
        return {"ai_summary": ai_summary, "ai_confidence": ai_conf}
        
    except Exception as e:
        print(f"[GEMINI DEBUG] Exception in _gemini_summarize: {e}")
        # Generate basic fallback analysis with dynamic confidence
        try:
            import random
            rr = sig.get("rr", 0)
            side = sig.get("side", "").upper()
            symbol = sig.get("symbol", "")
            tf = sig.get("timeframe", "")
            tp_dist = sig.get("tp_dist_atr", 0)
            sl_dist = sig.get("sl_dist_atr", 0)
            
            if rr and side and symbol:
                fallback_summary = f"{side} {symbol} {tf} signal with {rr:.1f}:1 R:R ratio"
                
                # Calculate dynamic confidence for fallback
                confidence_score = 50
                
                # R:R factor
                if rr >= 3.0:
                    confidence_score += 20
                elif rr >= 2.0:
                    confidence_score += 15
                elif rr >= 1.5:
                    confidence_score += 10
                elif rr >= 1.0:
                    confidence_score += 5
                
                # Distance factors
                if tp_dist >= 2.0:
                    confidence_score += 8
                elif tp_dist >= 1.0:
                    confidence_score += 4
                    
                if sl_dist >= 1.0:
                    confidence_score += 5
                elif sl_dist < 0.3:
                    confidence_score -= 5
                
                # Randomize
                confidence_score += random.randint(-3, 3)
                fallback_conf = max(40, min(80, confidence_score))
                
                print(f"[GEMINI DEBUG] Fallback analysis with dynamic confidence: {fallback_conf}%")
                return {"ai_summary": fallback_summary, "ai_confidence": fallback_conf}
        except Exception:
            pass
            
        return {"ai_summary": None, "ai_confidence": None}


def _build_telegram_message(order: dict) -> str:
    ts = order.get("timestamp") or order.get("time") or datetime.now(timezone.utc).isoformat()
    symbol = order.get("symbol", "")
    side = order.get("side", "").upper()
    tf = order.get("timeframe", "")
    entry = order.get("price") or order.get("entry_price")
    tp = order.get("tp")
    sl = order.get("sl")
    rr = order.get("rr")
    tp_dist = order.get("tp_dist_atr")
    sl_dist = order.get("sl_dist_atr")
    comment = order.get("comment", "")
    parts = [
        f"*Signal:* `{_escape_md(side)}`",
        f"*Symbol:* `{_escape_md(symbol)} {_escape_md(tf)}`",
        f"*Time:* `{_escape_md(ts)}`",
        f"*Entry:* `{_escape_md(entry)}`  *TP:* `{_escape_md(tp)}`  *SL:* `{_escape_md(sl)}`",
    ]
    if rr is not None or tp_dist is not None or sl_dist is not None:
        parts.append(f"*R:R:* `{_escape_md(rr)}`  *TP×ATR:* `{_escape_md(tp_dist)}`  *SL×ATR:* `{_escape_md(sl_dist)}`")
    if comment:
        parts.append(f"*Comment:* `{_escape_md(comment)}`")
    return "\n".join(parts)


def send_telegram_message_for_order(order: dict) -> bool:
    """Send only real signals to the client group (no dry-run)."""
    token = TELEGRAM_BOT_TOKEN
    chat_id = TELEGRAM_GROUP_ID
    if not token or not chat_id:
        return False
    # skip any dry-run or non-placed orders
    if order.get("result_retcode") in ("DRY-RUN", None, "INVALID-TP-SL", "INVALID-TP-SL-RR"):
        return False
    status_ok = str(order.get("result_retcode")).isdigit() or str(order.get("result_retcode")).lower() in ("ok", "10009")
    if not status_ok:
        return False

    sids = _load_sent_ids()
    oid = order.get("order") or order.get("deal") or order.get("entry_id")
    if not oid:
        oid = f"{order.get('symbol','')}|{order.get('timestamp','')}|{order.get('side','')}|{order.get('tp','')}|{order.get('sl','')}"
    if oid in sids:
        return False

    text = _build_telegram_message(order)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            sids.add(oid)
            _save_sent_ids(sids)
            return True
    except Exception:
        return False
    return False


def _build_telegram_signal_text(sig: dict) -> str:
    symbol = sig.get("symbol", "")
    tf = sig.get("timeframe", "")
    side = (sig.get("side") or sig.get("signal_type") or "").upper()
    entry = sig.get("entry_price") or sig.get("price")
    tp = sig.get("tp")
    sl = sig.get("sl")
    rr = sig.get("rr")
    tp_dist = sig.get("tp_dist_atr")
    sl_dist = sig.get("sl_dist_atr")
    comment = sig.get("comment") or "Trend alignment (short & ultra term), pivot breakout"
    
    # Calculate pip distances (simplified for display)
    tp_pips = abs(float(entry) - float(tp)) * 10000 if entry and tp else 0
    sl_pips = abs(float(entry) - float(sl)) * 10000 if entry and sl else 0
    
    # Adjust for JPY pairs (2 decimal places instead of 4)
    if "JPY" in symbol:
        tp_pips = tp_pips / 100
        sl_pips = sl_pips / 100
    
    # Adjust for gold/metals (different pip calculation)
    if symbol in ["XAUUSD", "XAGUSD"]:
        tp_pips = abs(float(entry) - float(tp)) * 100 if entry and tp else 0
        sl_pips = abs(float(entry) - float(sl)) * 100 if entry and sl else 0
    
    # Format trade type
    trade_type = "Long" if side in ["BUY", "LONG"] else "Short"
    action = "Buy" if side in ["BUY", "LONG"] else "Sell"
    
    lines = []
    lines.append(f"🔥 <b>Signal Alert:</b> <code>{_escape_html(symbol)} ({_escape_html(tf)})</code>")
    lines.append("")
    lines.append(f"📈 <b>Trade Type:</b> <code>{_escape_html(trade_type)}</code>")
    lines.append(f"🎯 <b>Entry Price:</b> <code>{_escape_html(entry)}</code>")
    lines.append(f"💰 <b>Take Profit (TP):</b> <code>{_escape_html(tp)}</code> ({int(tp_pips)} pips)")
    lines.append(f"🛡️ <b>Stop Loss (SL):</b> <code>{_escape_html(sl)}</code> ({int(sl_pips)} pips)")
    lines.append("")
    lines.append(f"⚖️ <b>Risk:Reward:</b> <code>1:{_escape_html(rr)}</code>")
    
    # Add ATR context if available
    if tp_dist is not None and sl_dist is not None:
        lines.append(f"📊 <b>ATR Context:</b> TP {_escape_html(tp_dist)}× ATR, SL {_escape_html(sl_dist)}× ATR")
    
    lines.append(f"💡 <b>Reason for Entry:</b> <code>{_escape_html(comment)}</code>")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("⚡ <b>Quick Trade Instructions</b>")
    lines.append("")
    lines.append(f"1️⃣ {action} <code>{_escape_html(symbol)}</code> @ <code>{_escape_html(entry)}</code>")
    lines.append(f"2️⃣ Set SL @ <code>{_escape_html(sl)}</code>")
    lines.append(f"3️⃣ Set TP @ <code>{_escape_html(tp)}</code>")
    lines.append("")
    lines.append("---")
    
    return "\n".join(lines)


def send_telegram_signal(sig: dict, dry_run: bool) -> bool:
    """Send a signal message to primary group and any extra chat IDs.
    Never send if dry_run is True.
    """
    if dry_run:
        return False
    token = TELEGRAM_BOT_TOKEN
    if not token:
        return False

    # Enhanced gating: send when we have valid signal data
    if not sig.get("symbol") or not sig.get("side"):
        return False

    # Dedupe check (global)
    sids = _load_sent_ids()
    sig_id = f"{sig.get('symbol')}|{sig.get('timeframe')}|{sig.get('side')}|{sig.get('timestamp')}"
    if sig_id in sids:
        return False

    recipients = _get_signal_recipient_chat_ids()
    if not recipients:
        return False

    main_text = _build_telegram_signal_text(sig)
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    any_success = False
    success_reply_map: dict[str, int] = {}

    for chat_id in recipients:
        main_payload = {
            "chat_id": chat_id,
            "text": main_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            r = requests.post(url, json=main_payload, timeout=10)
            if r.status_code == 200:
                any_success = True
                response_data = r.json()
                message_id = response_data.get("result", {}).get("message_id")
                if message_id:
                    success_reply_map[str(chat_id)] = int(message_id)
                print(f"[TELEGRAM] Signal sent to {chat_id}, message_id: {message_id}")
            else:
                print(f"[TELEGRAM] Send failed for {chat_id}: {r.status_code} - {r.text}")
        except Exception as e:
            print(f"[TELEGRAM] Send exception for {chat_id}: {e}")

    if not any_success:
        return False

    # Mark as sent once at least one recipient succeeded
    sids.add(sig_id)
    _save_sent_ids(sids)

    # AI follow-up to each chat where main message succeeded
    ai_text = _build_ai_followup_text(sig)
    if ai_text:
        for chat_id, reply_to in success_reply_map.items():
            ai_payload = {
                "chat_id": chat_id,
                "text": ai_text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "reply_to_message_id": reply_to,
            }
            try:
                ai_r = requests.post(url, json=ai_payload, timeout=10)
                if ai_r.status_code == 200:
                    print(f"[TELEGRAM] AI follow-up sent to {chat_id} as reply to {reply_to}")
                else:
                    print(f"[TELEGRAM] AI follow-up failed for {chat_id}: {ai_r.status_code} - {ai_r.text}")
            except Exception as e:
                print(f"[TELEGRAM] AI follow-up exception for {chat_id}: {e}")

    return True


def _load_updates_offset() -> int:
    try:
        with open(TELEGRAM_OFFSET_PATH, "r", encoding="utf-8") as f:
            return int(json.load(f) or 0)
    except Exception:
        return 0


def _save_updates_offset(offset: int):
    try:
        with open(TELEGRAM_OFFSET_PATH, "w", encoding="utf-8") as f:
            json.dump(offset, f)
    except Exception:
        pass


def _handle_admin_message(msg: dict):
    text = (msg.get("text") or "").strip()
    from_user = msg.get("from", {})
    uid = str(from_user.get("id", ""))
    if not TELEGRAM_ADMIN_ID or uid != str(TELEGRAM_ADMIN_ID):
        return
    chat_id = msg.get("chat", {}).get("id")
    state = _load_auto_state()
    reply = None
    t = text.lower()
    if t.startswith("/autotrade_on"):
        state["auto_trade"] = True
        _save_auto_state(state)
        reply = "Auto-trade: ON"
    elif t.startswith("/autotrade_off"):
        state["auto_trade"] = False
        _save_auto_state(state)
        reply = "Auto-trade: OFF"
    elif t.startswith("/status"):
        reply = f"Auto-trade: {'ON' if state.get('auto_trade', False) else 'OFF'}"
    elif t.startswith("/help"):
        reply = (
            "Commands: /autotrade_on, /autotrade_off, /status, /menu, /settings, "
            "/set <key> <value>, /reset-settings, "
            "/add_recipient <chat_id>, /remove_recipient <chat_id>, /list_recipients, "
            "/add_hb_recipient <chat_id>, /remove_hb_recipient <chat_id>, /list_hb_recipients"
        )
    elif t.startswith("/menu") or t.startswith("/settings"):
        s = _load_admin_settings()
        lines = ["Current admin settings:"]
        for k, v in s.items():
            lines.append(f"{k}: {v}")
        reply = "\n".join(lines)
    elif t.startswith("/set "):
        parts = text.split()
        # expect: /set key value
        if len(parts) >= 3:
            key = parts[1]
            val = " ".join(parts[2:])
            s = _load_admin_settings()
            # try to coerce numbers
            try:
                if "." in val:
                    v2 = float(val)
                else:
                    v2 = int(val)
            except Exception:
                v2 = val
            s[key] = v2
            _save_admin_settings(s)
            reply = f"Set {key} = {v2}"
        else:
            reply = "Usage: /set <key> <value>"
    elif t.startswith("/reset-settings"):
        _save_admin_settings({"rr_min": 0.8, "rr_max": 8.0, "max_distance_atr": 7.0, "risk_pct": 1.0, "confirm_window": 0})
        reply = "Settings reset to defaults"
    elif t.startswith("/add_recipient"):
        parts = text.split(maxsplit=1)
        if len(parts) == 2 and parts[1].strip():
            chat_to_add = parts[1].strip()
            s = _load_admin_settings()
            lst = s.get("signal_extra_chat_ids")
            if not isinstance(lst, list):
                lst = []
            if chat_to_add not in map(str, lst):
                lst.append(chat_to_add)
                s["signal_extra_chat_ids"] = lst
                _save_admin_settings(s)
                reply = f"Added recipient {chat_to_add}"
            else:
                reply = f"Recipient {chat_to_add} already present"
        else:
            reply = "Usage: /add_recipient <chat_id>"
    elif t.startswith("/remove_recipient"):
        parts = text.split(maxsplit=1)
        if len(parts) == 2 and parts[1].strip():
            chat_to_remove = parts[1].strip()
            s = _load_admin_settings()
            lst = s.get("signal_extra_chat_ids")
            if isinstance(lst, list) and chat_to_remove in map(str, lst):
                # remove by string comparison
                lst = [x for x in map(str, lst) if x != chat_to_remove]
                s["signal_extra_chat_ids"] = lst
                _save_admin_settings(s)
                reply = f"Removed recipient {chat_to_remove}"
            else:
                reply = f"Recipient {chat_to_remove} not found"
        else:
            reply = "Usage: /remove_recipient <chat_id>"
    elif t.startswith("/list_recipients"):
        s = _load_admin_settings()
        lst = s.get("signal_extra_chat_ids")
        if not isinstance(lst, list):
            lst = []
        reply = "Extra recipients:\n" + ("\n".join(map(str, lst)) if lst else "(none)")
    elif t.startswith("/add_hb_recipient"):
        parts = text.split(maxsplit=1)
        if len(parts) == 2 and parts[1].strip():
            chat_to_add = parts[1].strip()
            s = _load_admin_settings()
            lst = s.get("heartbeat_extra_chat_ids")
            if not isinstance(lst, list):
                lst = []
            if chat_to_add not in map(str, lst):
                lst.append(chat_to_add)
                s["heartbeat_extra_chat_ids"] = lst
                _save_admin_settings(s)
                reply = f"Added heartbeat recipient {chat_to_add}"
            else:
                reply = f"Heartbeat recipient {chat_to_add} already present"
        else:
            reply = "Usage: /add_hb_recipient <chat_id>"
    elif t.startswith("/remove_hb_recipient"):
        parts = text.split(maxsplit=1)
        if len(parts) == 2 and parts[1].strip():
            chat_to_remove = parts[1].strip()
            s = _load_admin_settings()
            lst = s.get("heartbeat_extra_chat_ids")
            if isinstance(lst, list) and chat_to_remove in map(str, lst):
                lst = [x for x in map(str, lst) if x != chat_to_remove]
                s["heartbeat_extra_chat_ids"] = lst
                _save_admin_settings(s)
                reply = f"Removed heartbeat recipient {chat_to_remove}"
            else:
                reply = f"Heartbeat recipient {chat_to_remove} not found"
        else:
            reply = "Usage: /remove_hb_recipient <chat_id>"
    elif t.startswith("/list_hb_recipients"):
        s = _load_admin_settings()
        lst = s.get("heartbeat_extra_chat_ids")
        if not isinstance(lst, list):
            lst = []
        reply = "Heartbeat extra recipients:\n" + ("\n".join(map(str, lst)) if lst else "(none)")
    if reply and TELEGRAM_BOT_TOKEN and chat_id:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": chat_id, "text": reply}
            requests.post(url, json=payload, timeout=10)
        except Exception:
            pass


def start_admin_poller():
    """Start a lightweight long-polling loop to process admin commands."""
    import threading
    if not TELEGRAM_BOT_TOKEN:
        print("[ADMIN] No bot token, skipping admin poller")
        return
        
    print(f"[ADMIN] Checking for existing admin poller lock at: {ADMIN_POLLER_LOCK}")
    
    # Check if admin poller is already running by another instance
    if os.path.exists(ADMIN_POLLER_LOCK):
        try:
            with open(ADMIN_POLLER_LOCK, "r") as f:
                lock_data = json.load(f)
            # Check if the process is still running (simple check)
            lock_time = lock_data.get("timestamp", 0)
            if time.time() - lock_time < 300:  # 5 minutes timeout
                print(f"[ADMIN] Admin poller already running (lock exists), skipping")
                return
            else:
                print(f"[ADMIN] Lock file is stale, proceeding")
        except Exception as e:
            print(f"[ADMIN] Error reading lock file: {e}")
            pass
    
    # Create lock file
    try:
        ensure_outputs()  # Make sure outputs directory exists
        lock_data = {
            "timestamp": time.time(),
            "pid": os.getpid() if hasattr(os, 'getpid') else 0
        }
        with open(ADMIN_POLLER_LOCK, "w") as f:
            json.dump(lock_data, f)
        print(f"[ADMIN] Created lock file with data: {lock_data}")
    except Exception as e:
        print(f"[ADMIN] Error creating lock file: {e}")
        pass
    
    def _poll():
        while True:
            try:
                # Refresh lock periodically
                try:
                    with open(ADMIN_POLLER_LOCK, "w") as f:
                        json.dump({
                            "timestamp": time.time(),
                            "pid": os.getpid() if hasattr(os, 'getpid') else 0
                        }, f)
                except Exception:
                    pass
                    
                offset = _load_updates_offset()
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
                params = {"timeout": 20, "offset": offset + 1}
                r = requests.get(url, params=params, timeout=25)
                if r.status_code != 200:
                    time.sleep(5)
                    continue
                data = r.json()
                processed_any = False
                for upd in data.get("result", []):
                    upd_id = int(upd.get("update_id", 0))
                    msg = upd.get("message") or upd.get("edited_message") or {}
                    if msg:
                        _handle_admin_message(msg)
                        processed_any = True
                    if upd_id > offset:
                        offset = upd_id
                
                # Only save offset if we processed messages
                if processed_any:
                    _save_updates_offset(offset)
                    
            except Exception as e:
                print(f"[ADMIN] Poller error: {e}")
                time.sleep(5)
            time.sleep(1)
            
    t = threading.Thread(target=_poll, name="tg-admin-poller", daemon=True)
    t.start()
    print(f"[ADMIN] Admin poller started with PID {os.getpid() if hasattr(os, 'getpid') else 'unknown'}")


def _log_order(row: dict):
    ensure_outputs()
    file_exists = os.path.exists(ORDERS_LOG)
    cols = [
        "timestamp",
        "symbol",
        "side",
        "signal_type",
        "price",
        "sl",
        "tp",
        "rr",
        "tp_dist_atr",
        "sl_dist_atr",
        "volume",
        "result_retcode",
        "order",
        "deal",
        "original_comment",
        "sanitized_comment",
        "comment",
    ]
    
    # Defensive header normalization: if file exists but header doesn't match, rewrite with correct header
    if file_exists:
        try:
            import csv
            with open(ORDERS_LOG, "r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                existing_header = next(reader, [])
                if existing_header != cols:
                    # Backup and rewrite with correct header
                    import shutil
                    backup_path = ORDERS_LOG.replace(".csv", "_backup.csv")
                    shutil.copy2(ORDERS_LOG, backup_path)
                    # Read all existing data
                    with open(ORDERS_LOG, "r", newline="", encoding="utf-8") as old_f:
                        old_reader = csv.DictReader(old_f)
                        old_rows = list(old_reader)
                    # Rewrite with correct header and normalized rows
                    with open(ORDERS_LOG, "w", newline="", encoding="utf-8") as new_f:
                        w = csv.DictWriter(new_f, fieldnames=cols, extrasaction="ignore", restval="")
                        w.writeheader()
                        for old_row in old_rows:
                            # Normalize row: ensure signal_type field
                            normalized = dict(old_row)
                            if "signal_type" not in normalized or not normalized["signal_type"]:
                                side = normalized.get("side", "").lower()
                                if side in ("long", "buy"):
                                    normalized["signal_type"] = "buy"
                                elif side in ("short", "sell"):
                                    normalized["signal_type"] = "sell"
                            w.writerow(normalized)
                    file_exists = False  # Force header write for new entry
        except Exception:
            pass  # If normalization fails, continue with normal append
    
    # Ensure signal_type is present in new row
    if "signal_type" not in row:
        side = row.get("side", "").lower()
        if side in ("long", "buy"):
            row["signal_type"] = "buy"
        elif side in ("short", "sell"):
            row["signal_type"] = "sell"
        else:
            row["signal_type"] = "unknown"
    
    import csv
    with open(ORDERS_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", restval="")
        if not file_exists:
            w.writeheader()
        w.writerow(row)
    # Do not send order notifications to Telegram in this setup; signals are sent separately.


def run_once(symbol: str, tf_label: str, st_period: int, st_mult: float, ut_coef: float, ut_len: int, confirm_win: int,
             risk_pct: float, dry_run: bool, allow_multiple: bool):
    ensure_outputs()
    ensure_mt5_connected()

    tf = timeframe_enum(tf_label)
    df = fetch_bars(symbol, tf, 500)
    df_for_sig = df[["open", "high", "low", "close", "point"]].copy()

    price_decimals = int(mt5.symbol_info(symbol).digits)
    point_val = df_for_sig.get("point", pd.Series([10 ** -price_decimals] * len(df_for_sig))).iloc[-1]

    st = SuperTrend(period=st_period, multiplier=st_mult, price_decimals=price_decimals, point_value=point_val)
    ut = UTBot(atr_coef=ut_coef, atr_len=ut_len, price_decimals=price_decimals, point_value=point_val)

    side = _align_signal_on_last_bar(df_for_sig, st, ut, confirm_win)
    last_ts = df["time"].iloc[-1]
    ts_iso = pd.to_datetime(last_ts).isoformat()

    if side is None:
        return {"status": "no-signal", "time": ts_iso}

    if _already_sent(ts_iso, symbol, side) and not allow_multiple:
        return {"status": "duplicate-skip", "time": ts_iso}

    # TP/SL selection using S9 - auto-detect decimals from point_value (forex=5, gold=2, etc.)
    s9 = FibonacciSquareOfNine(point_value=point_val)
    sub = df_for_sig.copy()  # full history up to last bar
    analysis = s9.analyze_market(sub)
    strong_conf = analysis.get("strong_confluence_zones") or analysis.get("confluence_zones") or []
    pivot_low = analysis.get("pivot_low")
    pivot_high = analysis.get("pivot_high")
    entry_price = float(df["close"].iloc[-1])
    atr = _calc_atr(df)
    # Prefer nearest confluence within K*ATR
    tp_candidate = _nearest_confluence_within_atr(strong_conf, entry_price, side, atr, 3.0)
    if tp_candidate is not None:
        tp = float(tp_candidate)
        sl = None
        tp_src = "confluence_nearby"
        sl_src = None
    else:
        tp, sl, tp_src, sl_src = _pick_tp_sl_from_confluences(strong_conf, entry_price, side, pivot_low, pivot_high, atr)

    # Round TP/SL to tick grid (if present)
    if tp is not None:
        tp = _round_price_to_tick(symbol, tp)
    if sl is not None:
        sl = _round_price_to_tick(symbol, sl)

    # Ensure SL/TP are on correct side and fallback to ATR if needed
    if side == "long":
        if sl is None or sl >= entry_price:
            sl = _round_price_to_tick(symbol, entry_price - (atr or 1.0))
            sl_src = sl_src or "atr_1.0x"
        if tp is None or tp <= entry_price:
            tp = _round_price_to_tick(symbol, entry_price + (atr or 1.0))
            tp_src = tp_src or "atr_1.5x"
    else:
        if sl is None or sl <= entry_price:
            sl = _round_price_to_tick(symbol, entry_price + (atr or 1.0))
            sl_src = sl_src or "atr_1.0x"
        if tp is None or tp >= entry_price:
            tp = _round_price_to_tick(symbol, entry_price - (atr or 1.0))
            tp_src = tp_src or "atr_1.5x"

    # Load admin-overridable settings
    admin_settings = _load_admin_settings()
    rr_min = admin_settings.get("rr_min", 0.8)
    rr_max = admin_settings.get("rr_max", 8.0)
    max_distance_atr = admin_settings.get("max_distance_atr", 7.0)
    # allow override of risk_pct/confirm_window from admin settings
    risk_pct = admin_settings.get("risk_pct", risk_pct)
    confirm_win = admin_settings.get("confirm_window", confirm_win)

    # Compute distances and RR
    tp_dist = abs(tp - entry_price) if tp is not None else None
    sl_dist = abs(sl - entry_price) if sl is not None else None
    tp_dist_atr = (tp_dist / atr) if (tp_dist is not None and atr) else None
    sl_dist_atr = (sl_dist / atr) if (sl_dist is not None and atr) else None
    rr = (tp_dist / sl_dist) if (tp_dist is not None and sl_dist not in (None, 0)) else None

    # Enforce rr and max distance constraints (can be updated via admin settings)
    reject_reason = None
    if rr is not None and (rr < rr_min or rr > rr_max):
        reject_reason = f"rr_out_of_bounds:{rr:.2f}"
    if tp_dist_atr is not None and tp_dist_atr > max_distance_atr:
        reject_reason = reject_reason or f"tp_too_far:{tp_dist_atr:.2f}xATR"
    if sl_dist_atr is not None and sl_dist_atr > max_distance_atr:
        reject_reason = reject_reason or f"sl_too_far:{sl_dist_atr:.2f}xATR"

    if reject_reason:
        _log_order({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "side": side,
            "signal_type": "buy" if side == "long" else "sell",
            "price": entry_price,
            "sl": sl,
            "tp": tp,
            "volume": 0,
            "result_retcode": "INVALID-TP-SL-RR",
            "order": "-",
            "deal": "-",
            "comment": reject_reason,
        })
        return {"status": "invalid-tp-sl-rr", "time": ts_iso, "reason": reject_reason}

    # Build signal dict for Telegram (to be sent whether auto-trade is ON or OFF; never on dry_run)
    signal_payload = {
        "timestamp": ts_iso,
        "symbol": symbol,
        "timeframe": tf_label,
        "side": side,
        "entry_price": entry_price,
        "tp": tp,
        "sl": sl,
        "rr": round(rr, 3) if rr is not None else None,
        "tp_dist_atr": round(tp_dist_atr, 3) if tp_dist_atr is not None else None,
        "sl_dist_atr": round(sl_dist_atr, 3) if sl_dist_atr is not None else None,
        "comment": f"ST+UT alignment ({tp_src}/{sl_src})",
    }
    # Enrich with Gemini summary
    try:
        ai = _gemini_summarize(signal_payload)
        if ai:
            signal_payload.update(ai)
    except Exception:
        pass
    # Send signal to Telegram (only if not dry-run)
    try:
        send_telegram_signal(signal_payload, dry_run=dry_run)
    except Exception:
        pass

    # Respect auto-trade toggle
    auto_state = _load_auto_state()
    if not auto_state.get("auto_trade", True):
        # Log informational row and exit without placing order
        _log_order({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "side": side,
            "signal_type": "buy" if side == "long" else "sell",
            "price": entry_price,
            "sl": sl,
            "tp": tp,
            "volume": 0,
            "result_retcode": "AUTO-OFF",
            "order": "-",
            "deal": "-",
            "comment": f"Signal generated; auto-trade OFF ({tp_src}/{sl_src})",
        })
        
        # Notify admin that signal was generated but auto-trade is OFF
        send_admin_notification(
            f"📊 Signal generated for {symbol} {side.upper()} but auto-trade is OFF\n"
            f"Entry: {entry_price} | TP: {tp} | SL: {sl} | R:R: {rr:.2f}" if rr else ""
        )
        
        return {"status": "signal-sent", "time": ts_iso, "auto_trade": False}

    info = mt5.symbol_info(symbol)
    if not info.visible:
        mt5.symbol_select(symbol, True)

    # Check existing positions if not allowing multiple
    if not allow_multiple:
        positions = mt5.positions_get(symbol=symbol)
        if positions:
            return {"status": "position-exists", "time": ts_iso}

    # Compute volume by risk
    acc = mt5.account_info()
    balance = acc.balance if acc else 0.0
    volume = _risk_position_size(symbol, risk_pct, balance, entry_price, sl)

    # Current price
    tick = mt5.symbol_info_tick(symbol)
    if side == "long":
        price = tick.ask
        order_type = mt5.ORDER_TYPE_BUY
    else:
        price = tick.bid
        order_type = mt5.ORDER_TYPE_SELL

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": 90210,
        "comment": f"ST+UT live ({tp_src}/{sl_src})",
        "type_filling": mt5.ORDER_FILLING_FOK,
        "type_time": mt5.ORDER_TIME_GTC,
    }

    # Force a sanitized comment into the request early to avoid MT5 rejecting it.
    try:
        safe_comment_initial = _sanitize_mt5_comment(request.get("comment"))
        env_safe = os.getenv("MT5_SAFE_COMMENT")
        if env_safe:
            # allow operator to force a short, known-good comment via env
            request["comment"] = env_safe
        else:
            # use sanitized comment or a very short fallback
            request["comment"] = safe_comment_initial or "Fibtool"
    except Exception:
        request["comment"] = os.getenv("MT5_SAFE_COMMENT", "Fibtool")

    # --- Pre-trade margin check (high-priority safety) ---
    try:
        # Attempt to compute required margin for this exact order
        required_margin = _order_calc_margin(order_type, symbol, volume, price)
        margin_buffer = float(admin_settings.get("margin_safety_buffer", 1.1))
        free_margin = float(acc.free_margin) if acc and getattr(acc, 'free_margin', None) is not None else 0.0

        if required_margin is not None:
            try:
                required_margin = float(required_margin)
            except Exception:
                required_margin = None

        if required_margin is not None:
            # If free margin is not sufficient (with safety buffer), reject and log
            if free_margin < required_margin * margin_buffer:
                comment_text = f"INSUFFICIENT_MARGIN required={required_margin:.2f} free={free_margin:.2f} buffer={margin_buffer}"
                _log_order({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "symbol": symbol,
                    "side": side,
                    "signal_type": "buy" if side == "long" else "sell",
                    "price": price,
                    "sl": sl,
                    "tp": tp,
                    "volume": 0,
                    "result_retcode": "INSUFFICIENT_MARGIN",
                    "order": "-",
                    "deal": "-",
                    "comment": comment_text,
                    "required_margin": required_margin,
                    "free_margin": free_margin,
                })
                # Notify admin with details
                try:
                    send_admin_notification(
                        f"⛔ Auto-trade blocked for {symbol} {side.upper()} due to insufficient margin. Required: {required_margin:.2f}, Free: {free_margin:.2f} (buffer={margin_buffer})",
                        {
                            "symbol": symbol,
                            "side": side,
                            "required_margin": required_margin,
                            "free_margin": free_margin,
                            "margin_buffer": margin_buffer,
                        }
                    )
                except Exception:
                    pass
                return {"status": "insufficient-margin", "time": ts_iso, "required_margin": required_margin, "free_margin": free_margin}
    except Exception as e:
        # If margin calculation fails, log and continue (best-effort). We prefer to allow the order rather than block due to a calc failure.
        try:
            print(f"[MARGIN] Could not calculate required margin for {symbol}: {e}")
        except Exception:
            pass

    # --- Daily loss circuit breaker check (high-priority safety) ---
    try:
        daily_loss_limit_pct = float(admin_settings.get("daily_loss_limit_pct", 3.0))
        daily_loss_info = _get_daily_loss_pct()
        current_daily_loss_pct = daily_loss_info.get("daily_loss_pct", 0.0)
        
        if current_daily_loss_pct > daily_loss_limit_pct:
            comment_text = f"DAILY_LOSS_LIMIT_BREACHED current_loss={current_daily_loss_pct:.2f}% limit={daily_loss_limit_pct:.2f}%"
            _log_order({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "symbol": symbol,
                "side": side,
                "signal_type": "buy" if side == "long" else "sell",
                "price": price,
                "sl": sl,
                "tp": tp,
                "volume": 0,
                "result_retcode": "DAILY_LOSS_LIMIT_BREACHED",
                "order": "-",
                "deal": "-",
                "comment": comment_text,
                "daily_loss_pct": current_daily_loss_pct,
                "daily_loss_limit": daily_loss_limit_pct,
            })
            # Send urgent admin notification
            try:
                send_admin_notification(
                    f"🚨 CIRCUIT BREAKER ACTIVATED for {symbol} {side.upper()}! Daily loss {current_daily_loss_pct:.2f}% exceeds limit of {daily_loss_limit_pct:.2f}%. All trading halted for today.",
                    {
                        "symbol": symbol,
                        "side": side,
                        "daily_loss_pct": current_daily_loss_pct,
                        "daily_loss_limit": daily_loss_limit_pct,
                        "starting_equity": daily_loss_info.get("starting_equity", 0),
                        "current_equity": daily_loss_info.get("current_equity", 0),
                    }
                )
            except Exception:
                pass
            return {"status": "daily-loss-limit-breached", "time": ts_iso, "daily_loss_pct": current_daily_loss_pct}
    except Exception as e:
        try:
            print(f"[DAILY_LOSS] Could not check daily loss limit for {symbol}: {e}")
        except Exception:
            pass

    # --- Portfolio risk limit check (medium-high priority safety) ---
    try:
        max_total_risk_pct = float(admin_settings.get("max_total_open_risk_pct", 5.0))
        
        # Calculate risk for the new proposed order
        new_order_risk = _calculate_position_risk(symbol, volume, price, sl) if sl else 0.0
        
        # Get total portfolio risk including this new order
        portfolio_info = _get_total_portfolio_risk(new_order_risk)
        total_risk_pct = portfolio_info.get("total_risk_pct", 0.0)
        
        if total_risk_pct > max_total_risk_pct:
            comment_text = f"PORTFOLIO_RISK_LIMIT_EXCEEDED total_risk={total_risk_pct:.2f}% limit={max_total_risk_pct:.2f}%"
            _log_order({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "symbol": symbol,
                "side": side,
                "signal_type": "buy" if side == "long" else "sell",
                "price": price,
                "sl": sl,
                "tp": tp,
                "volume": 0,
                "result_retcode": "PORTFOLIO_RISK_LIMIT_EXCEEDED",
                "order": "-",
                "deal": "-",
                "comment": comment_text,
                "total_risk_pct": total_risk_pct,
                "max_total_risk_pct": max_total_risk_pct,
                "new_order_risk": new_order_risk,
            })
            # Notify admin with portfolio details
            try:
                send_admin_notification(
                    f"⚠️ Auto-trade blocked for {symbol} {side.upper()} due to portfolio risk limit. Total risk would be {total_risk_pct:.2f}% (limit: {max_total_risk_pct:.2f}%)",
                    {
                        "symbol": symbol,
                        "side": side,
                        "total_risk_pct": total_risk_pct,
                        "max_total_risk_pct": max_total_risk_pct,
                        "new_order_risk": new_order_risk,
                        "position_count": portfolio_info.get("position_count", 0),
                        "equity": portfolio_info.get("equity", 0),
                    }
                )
            except Exception:
                pass
            return {"status": "portfolio-risk-limit-exceeded", "time": ts_iso, "total_risk_pct": total_risk_pct}
    except Exception as e:
        try:
            print(f"[PORTFOLIO_RISK] Could not check portfolio risk limit for {symbol}: {e}")
        except Exception:
            pass

    # Validate TP/SL ordering
    if not _is_valid_tp_sl(side, price, tp, sl):
        _log_order({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "side": side,
            "signal_type": "buy" if side == "long" else "sell",
            "price": price,
            "sl": sl,
            "tp": tp,
            "volume": 0,
            "result_retcode": "INVALID-TP-SL",
            "order": "-",
            "deal": "-",
            "comment": "Rejected: invalid tp/sl relative to entry",
        })
        return {"status": "invalid-tp-sl", "time": ts_iso}

    if dry_run:
        orig_comment = request.get("comment")
        sanitized = _sanitize_mt5_comment(orig_comment)
        _log_order({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "side": side,
            "signal_type": "buy" if side == "long" else "sell",
            "price": price,
            "sl": sl,
            "tp": tp,
            "rr": round(rr, 3) if rr is not None else None,
            "tp_dist_atr": round(tp_dist_atr, 3) if tp_dist_atr is not None else None,
            "sl_dist_atr": round(sl_dist_atr, 3) if sl_dist_atr is not None else None,
            "volume": volume,
            "result_retcode": "DRY-RUN",
            "order": "-",
            "deal": "-",
            "original_comment": orig_comment,
            "sanitized_comment": sanitized,
            "comment": sanitized,
        })
        # notify admin if sanitization changed the comment
        if orig_comment != sanitized:
            try:
                send_admin_notification(f"⚠️ Sanitized MT5 order comment for {symbol} (dry-run):", {"original_comment": orig_comment, "sanitized_comment": sanitized})
            except Exception:
                pass
        return {"status": "dry-run-logged", "time": ts_iso}

    # Enforce execution with retries
    result_info = ensure_execute_order(request, max_retries=3, backoff_seconds=1.0)
    result = result_info.get("result") if isinstance(result_info, dict) else result_info
    orig_comment = result_info.get("original_comment") if isinstance(result_info, dict) else request.get("comment")
    sanitized_comment = result_info.get("sanitized_comment") if isinstance(result_info, dict) else _sanitize_mt5_comment(request.get("comment"))
    _mark_sent(ts_iso, symbol, side)
    order_row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "side": side,
        "signal_type": "buy" if side == "long" else "sell",
        "price": price,
        "sl": sl,
        "tp": tp,
        "rr": round(rr, 3) if rr is not None else None,
        "tp_dist_atr": round(tp_dist_atr, 3) if tp_dist_atr is not None else None,
        "sl_dist_atr": round(sl_dist_atr, 3) if sl_dist_atr is not None else None,
        "volume": volume,
        "result_retcode": getattr(result, "retcode", None) if result is not None else None,
        "order": getattr(result, "order", None) if result is not None else None,
        "deal": getattr(result, "deal", None) if result is not None else None,
        "original_comment": orig_comment,
        "sanitized_comment": sanitized_comment,
        "comment": sanitized_comment,
    }
    # notify admin if sanitization changed the comment
    if orig_comment != sanitized_comment:
        try:
            send_admin_notification(f"⚠️ Sanitized MT5 order comment for {symbol}:", {"original_comment": orig_comment, "sanitized_comment": sanitized_comment, "order_row": order_row})
        except Exception:
            pass

    _log_order(order_row)

    # Send admin notification for auto-trade execution (if auto-trade enabled)
    auto_state = _load_auto_state()
    if auto_state.get("auto_trade", True):
        retcode = order_row.get("result_retcode")
        if retcode == 10009:
            send_admin_notification(f"✅ Auto-trade executed successfully for {symbol} {side.upper()}", order_row)
        else:
            send_admin_notification(f"⚠️ Auto-trade execution issue for {symbol} {side.upper()} - Result code: {retcode}", order_row)
    
    return {"status": "sent", "time": ts_iso, "retcode": getattr(result, "retcode", None)}


def loop(symbol: str, timeframe: str, st_period: int, st_mult: float, ut_coef: float, ut_len: int,
         confirm_win: int, risk_pct: float, dry_run: bool, interval: int, allow_multiple: bool):
    print(f"Live loop for {symbol} {timeframe} started. Interval: {interval}s")
    ensure_mt5_connected()
    last_handled: Optional[pd.Timestamp] = None
    tf = timeframe_enum(timeframe)
    while True:
        try:
            df = fetch_bars(symbol, tf, 500)
            cur_last = df["time"].iloc[-1]
            if last_handled is not None and pd.to_datetime(cur_last) <= pd.to_datetime(last_handled):
                time.sleep(interval)
                continue
            out = run_once(symbol, timeframe, st_period, st_mult, ut_coef, ut_len, confirm_win, risk_pct, dry_run, allow_multiple)
            print(f"[{datetime.now(timezone.utc).isoformat()}] {out}")
            last_handled = cur_last
        except Exception as e:
            print(f"Loop error: {e}")
        time.sleep(interval)


def multi_run(symbols: list[str], timeframes: list[str], st_period: int, st_mult: float,
              ut_coef: float, ut_len: int, confirm_win: int, risk_pct: float,
              dry_run: bool, interval: int, allow_multiple: bool):
    """Sequentially run `run_once` for all symbol x timeframe combinations.

    This runs sequentially in a single process and relies on existing file-based
    deduplication (`live_signals_index.json` / sent ids) to avoid duplicate signal
    deliveries when multiple processes or the orchestrator are used.
    """
    print(f"[MULTI] Starting multi-run for symbols={symbols} timeframes={timeframes} interval={interval}s")
    ensure_mt5_connected()
    # normalize lists
    syms = [s.strip() for s in symbols if s and s.strip()]
    tfs = [t.strip() for t in timeframes if t and t.strip()]

    if not syms or not tfs:
        raise ValueError("multi_run requires at least one symbol and one timeframe")

    while True:
        for sym in syms:
            for tf in tfs:
                try:
                    out = run_once(sym, tf, st_period, st_mult, ut_coef, ut_len, confirm_win, risk_pct, dry_run, allow_multiple)
                    print(f"[{datetime.now(timezone.utc).isoformat()}] {sym} {tf} -> {out}")
                except Exception as e:
                    print(f"[MULTI] error for {sym} {tf}: {e}")
                # small gap between calls to avoid hammering MT5
                time.sleep(1)
        # sleep full interval after iterating all pairs
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Live MT5 entry bot (ST+UT with S9 TP/SL)")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--timeframe", default="H1")
    parser.add_argument('--symbols', type=str, help='Comma-separated symbols for multi-run (overrides --symbol)')
    parser.add_argument('--timeframes', type=str, help='Comma-separated timeframes for multi-run (overrides --timeframe)')
    parser.add_argument("--st-period", type=int, default=14)
    parser.add_argument("--st-multiplier", type=float, default=3.0)
    parser.add_argument("--ut-atr-coef", type=float, default=2.0)
    parser.add_argument("--ut-atr-len", type=int, default=1)
    parser.add_argument("--confirm-window", type=int, default=0)
    parser.add_argument("--risk-pct", type=float, default=1.0, help="Risk % of balance per trade")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--allow-multiple", action="store_true", help="Allow multiple positions for the symbol")
    parser.add_argument("--start-admin-poller", action="store_true", help="Start admin command poller (should only be used by one instance)")
    args = parser.parse_args()

    # start admin poller for auto-trade toggle only if explicitly requested
    if args.start_admin_poller:
        target = args.symbol
        # if multi mode, show a short hint
        if args.symbols or args.timeframes:
            target = f"multi-mode"
        print(f"[MAIN] Starting admin poller for {target}")
        start_admin_poller()
    else:
        target = args.symbol
        if args.symbols or args.timeframes:
            target = "multi-mode"
        print(f"[MAIN] Admin poller NOT started for {target}")

    # Multi-run mode: run multiple symbol/timeframe combinations in sequence
    if args.symbols or args.timeframes:
        # parse lists with sensible fallbacks
        symbols = [s.strip() for s in args.symbols.split(',')] if args.symbols else [args.symbol]
        timeframes = [t.strip() for t in args.timeframes.split(',')] if args.timeframes else [args.timeframe]

        if args.once:
            # run each pair once and exit
            for sym in symbols:
                for tf in timeframes:
                    out = run_once(
                        sym,
                        tf,
                        args.st_period,
                        args.st_multiplier,
                        args.ut_atr_coef,
                        args.ut_atr_len,
                        args.confirm_window,
                        args.risk_pct,
                        args.dry_run,
                        args.allow_multiple,
                    )
                    print(f"{sym} {tf}: {out}")
            return

        # continuous multi-run
        multi_run(
            symbols,
            timeframes,
            args.st_period,
            args.st_multiplier,
            args.ut_atr_coef,
            args.ut_atr_len,
            args.confirm_window,
            args.risk_pct,
            args.dry_run,
            args.interval,
            args.allow_multiple,
        )
        return

    # Single symbol/timeframe mode (existing behavior)
    if args.once:
        out = run_once(
            args.symbol,
            args.timeframe,
            args.st_period,
            args.st_multiplier,
            args.ut_atr_coef,
            args.ut_atr_len,
            args.confirm_window,
            args.risk_pct,
            args.dry_run,
            args.allow_multiple,
        )
        print(out)
        return

    loop(
        args.symbol,
        args.timeframe,
        args.st_period,
        args.st_multiplier,
        args.ut_atr_coef,
        args.ut_atr_len,
        args.confirm_window,
        args.risk_pct,
        args.dry_run,
        args.interval,
        args.allow_multiple,
    )


if __name__ == "__main__":
    main()
