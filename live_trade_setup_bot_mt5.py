import argparse
import csv
import json
import os
import time
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

from fib_square_strategy import FibonacciSquareOfNine
from config import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, MT5_PATH

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
ORDERS_LOG = os.path.join(OUTPUT_DIR, "orders.csv")
INDEX_PATH = os.path.join(OUTPUT_DIR, "trade_setup_index.json")


def symbol_slug(symbol: str) -> str:
    """Filesystem-safe slug for a symbol (fallback for this module)."""
    try:
        return ''.join(ch if ch.isalnum() else '_' for ch in str(symbol)).lower().strip('_')
    except Exception:
        return str(symbol).replace('/', '_').replace(' ', '_').lower()


def ensure_outputs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _order_debug_dump(symbol: str, request: dict, result, tag: str = "order_debug"):
    """Write a compact debug JSON for order checks/sends."""
    try:
        ensure_outputs()
    except Exception:
        pass
    try:
        mt5_last = None
        if mt5 is not None:
            try:
                mt5_last = mt5.last_error()
            except Exception:
                mt5_last = None
        out = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "tag": tag,
            "request": request,
            "result": {
                "retcode": getattr(result, "retcode", None),
                "comment": getattr(result, "comment", None),
                "order": getattr(result, "order", None),
                "deal": getattr(result, "deal", None),
            },
            "mt5_last_error": mt5_last,
        }
        fn = os.path.join(OUTPUT_DIR, f"{symbol_slug(symbol)}_{tag}_{int(time.time())}.json")
        with open(fn, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, default=str)
    except Exception:
        pass


def send_order_with_fallback(symbol: str, request: dict):
    """Try the request as-is, fall back to IOC then FOK if needed. Returns mt5.order_send result."""
    # ensure outputs and symbol selected
    try:
        ensure_outputs()
    except Exception:
        pass
    try:
        if mt5 is not None:
            try:
                mt5.symbol_select(symbol, True)
            except Exception:
                pass
    except Exception:
        pass

    # determine preferred modes (preserve provided one first)
    preferred = []
    if request.get("type_filling") is not None:
        preferred.append(request.get("type_filling"))
    # add IOC then FOK as fallbacks
    if mt5 is not None:
        try:
            preferred += [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK]
        except Exception:
            pass

    last_exc = None
    for mode in preferred:
        req = dict(request)
        req["type_filling"] = mode
        # pre-check when available
        try:
            if mt5 is not None and hasattr(mt5, 'order_check'):
                check = mt5.order_check(req)
                _order_debug_dump(symbol, req, check, tag=f"check_{mode}")
                # many wrappers use retcode==0 for OK
                if getattr(check, "retcode", None) not in (None, 0):
                    # order_check returned non-zero — try next mode
                    last_exc = check
                    continue
        except Exception as e:
            last_exc = e
            # continue to attempt send below
        # attempt send
        try:
            res = mt5.order_send(req)
            _order_debug_dump(symbol, req, res, tag=f"send_{mode}")
            return res
        except Exception as e:
            last_exc = e
            # log and continue
            _order_debug_dump(symbol, req, type("R", (), {"retcode": None, "comment": str(e)}), tag=f"send_exc_{mode}")
            continue

    # final unconditional attempt with IOC if nothing succeeded
    try:
        req = dict(request)
        if mt5 is not None:
            req["type_filling"] = mt5.ORDER_FILLING_IOC
        res = mt5.order_send(req)
        _order_debug_dump(symbol, req, res, tag="final_ioc")
        return res
    except Exception as e:
        _order_debug_dump(symbol, request, type("R", (), {"retcode": None, "comment": str(e)}), tag="final_exc")
        raise


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


def fetch_bars(symbol: str, tf, count: int = 200) -> pd.DataFrame:
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
    # Ensure correct tick size (point) from MT5 symbol metadata
    if "point" not in df.columns:
        pt = None
        try:
            info = mt5.symbol_info(symbol)
            if info is not None:
                pt = getattr(info, "trade_tick_size", None) or getattr(info, "point", None)
        except Exception:
            pt = None
        if pt is None:
            # Fallback to decimal inference only if metadata unavailable
            sample = df["close"].iloc[-1]
            decimals = 5
            try:
                s = f"{sample:.8f}"
                if "." in s:
                    decimals = len(s.rstrip("0").split(".")[-1])
            except Exception:
                pass
            pt = 10 ** -decimals
        try:
            df["point"] = float(pt)
        except Exception:
            df["point"] = pt
    return df.reset_index(drop=True)


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


def _round_price_to_tick(symbol: str, price: float) -> float:
    info = mt5.symbol_info(symbol)
    tick = info.trade_tick_size or info.point or 0.01
    return round(round(price / tick) * tick, info.digits)


def _normalize_volume(symbol: str, lots: float) -> float:
    info = mt5.symbol_info(symbol)
    if not info:
        return round(max(0.01, lots), 2)
    min_lot = getattr(info, "volume_min", 0.01) or 0.01
    max_lot = getattr(info, "volume_max", min_lot * 1000) or (min_lot * 1000)
    step = getattr(info, "volume_step", 0.01) or 0.01
    try:
        lots = float(lots)
    except Exception:
        lots = min_lot
    lots = max(min_lot, min(max_lot, lots))
    steps = int((lots + 1e-12) // step)
    if steps <= 0:
        steps = 1
    normalized = steps * step
    normalized = max(min_lot, min(max_lot, normalized))
    return round(normalized, 2)


def _risk_position_size(symbol: str, risk_pct: float, balance: float, entry: float, sl: float) -> float:
    info = mt5.symbol_info(symbol)
    tick_val = info.trade_tick_value
    tick_size = info.trade_tick_size
    if tick_size <= 0 or tick_val <= 0:
        tick_size = info.point or 0.01
        tick_val = tick_val if tick_val > 0 else 1.0
    distance_ticks = abs(entry - sl) / tick_size
    distance_ticks = max(distance_ticks, 1.0)
    risk_amount = max(balance * (risk_pct / 100.0), 0.0)
    lots = risk_amount / (distance_ticks * tick_val)
    return _normalize_volume(symbol, lots)


def _load_index() -> dict:
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_index(idx: dict):
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(idx, f)


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
        "volume",
        "result_retcode",
        "order",
        "deal",
        "comment",
    ]
    with open(ORDERS_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if not file_exists:
            w.writeheader()
        w.writerow(row)


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


def run_once(symbol: str, timeframe: str, min_rr: float, min_confs: int, max_slippage_points: float,
             risk_pct: float, dry_run: bool, allow_multiple: bool,
             require_wyckoff: bool, wyckoff_bias: str, debug: bool = False):
    ensure_outputs()
    ensure_mt5_connected()

    tf = timeframe_enum(timeframe)
    df = fetch_bars(symbol, tf, 500)
    strat_df = df[["open", "high", "low", "close", "point"]].copy()

    # S9 analysis - use MT5 metadata for tick size and digits
    try:
        info = mt5.symbol_info(symbol)
    except Exception:
        info = None
    if info is not None:
        price_decimals = int(getattr(info, "digits", 5))
        point_value = getattr(info, "trade_tick_size", None) or getattr(info, "point", None)
    else:
        price_decimals = 5
        try:
            point_value = float(strat_df.get("point", pd.Series([10 ** -price_decimals] * len(strat_df))).iloc[-1])
        except Exception:
            point_value = 10 ** -price_decimals
    # Ensure strategy dataframe carries consistent point value
    try:
        strat_df["point"] = float(point_value)
    except Exception:
        strat_df["point"] = point_value
    s9 = FibonacciSquareOfNine(point_value=point_value)

    # Use the full window pivots similar to collector
    pivot_low = strat_df["low"].min()
    pivot_high = strat_df["high"].max()
    analysis = s9.analyze_market(strat_df, pivot_low=pivot_low, pivot_high=pivot_high)

    ts_iso = pd.to_datetime(df["time"].iloc[-1]).isoformat()
    setup = analysis.get("trade_setup", {}) or {}
    valid = bool(setup.get("valid", False))
    if not valid:
        # If debug requested, dump analysis for inspection
        if debug:
            try:
                ensure_outputs()
                dump_path = os.path.join(OUTPUT_DIR, f"{symbol_slug(symbol)}_analysis_debug_{ts_iso.replace(':','-')}.json")
                with open(dump_path, 'w', encoding='utf-8') as dfp:
                    json.dump(analysis, dfp, default=str, indent=2)
                print(f"[DEBUG] Analysis dumped to: {dump_path}")
                # Print short summary to stdout for quick inspection
                try:
                    ts = ts_iso
                    setup_preview = analysis.get('trade_setup') or {}
                    wy = analysis.get('wyckoff_analysis') or {}
                    confs = analysis.get('strong_confluence_zones') or []
                    print(f"[DEBUG] symbol={symbol} time={ts} valid={bool(setup_preview.get('valid'))} rr={setup_preview.get('rr_ratio')} confluences={len(confs)} wyckoff_detected={wy.get('detected')}")
                except Exception:
                    pass
            except Exception as e:
                print(f"[DEBUG] Failed to write analysis dump: {e}")
        return {"status": "no-setup", "time": ts_iso}

    # Wyckoff filters
    wyckoff = analysis.get("wyckoff_analysis", {}) or {}
    wyckoff_detected = bool(wyckoff.get("detected", False))
    is_accum = wyckoff.get("is_accumulation", None)
    pattern = wyckoff.get("pattern")

    if require_wyckoff and not wyckoff_detected:
        return {"status": "wyckoff-required", "time": ts_iso}

    # If a specific bias is requested, require detection and matching
    if wyckoff_bias in ("accumulation", "distribution"):
        if not wyckoff_detected:
            return {"status": "wyckoff-bias-filter", "reason": "not-detected", "time": ts_iso}
        want_accum = (wyckoff_bias == "accumulation")
        if (is_accum is True) != want_accum:
            return {"status": "wyckoff-bias-filter", "reason": pattern or "mismatch", "time": ts_iso}

    # Threshold filters
    rr = setup.get("rr_ratio")
    if rr is None or float(rr) < float(min_rr):
        return {"status": "rr-filter", "rr": rr, "time": ts_iso}

    strong_confs = analysis.get("strong_confluence_zones", [])
    if len(strong_confs) < int(min_confs):
        return {"status": "confs-filter", "count": len(strong_confs), "time": ts_iso}

    side = setup.get("type")
    # If wyckoff_bias is auto and detected, enforce side alignment with Wyckoff
    if wyckoff_bias == "auto" and wyckoff_detected and is_accum is not None:
        want_side = "long" if is_accum else "short"
        if side != want_side:
            return {"status": "wyckoff-side-filter", "pattern": pattern, "want": want_side, "have": side, "time": ts_iso}
    entry = float(setup.get("entry")) if setup.get("entry") is not None else float(df["close"].iloc[-1])
    sl = float(setup.get("stop_loss")) if setup.get("stop_loss") is not None else float(df["close"].iloc[-1])
    tp = float(setup.get("take_profit")) if setup.get("take_profit") is not None else float(df["close"].iloc[-1])

    # Prefer nearest confluence within K*ATR (if available)
    strong_confs = analysis.get("strong_confluence_zones", [])
    atr = _calc_atr(strat_df)
    def _nearest_confluence(confs, entry, side, atr_val, mult=3.0):
        if not confs or atr_val is None:
            return None
        max_d = atr_val * mult
        cand = []
        for z in confs:
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
            d = abs(p - entry)
            if d <= max_d:
                cand.append((d, p))
        if not cand:
            return None
        cand.sort(key=lambda x: x[0])
        return cand[0][1]

    tp_cand = _nearest_confluence(strong_confs, entry, side, atr, 3.0)
    if tp_cand is not None:
        tp = float(tp_cand)

    # Round and ensure sides as before
    point = mt5.symbol_info(symbol).point or 0.01
    entry_exec = ask if side == "long" else bid
    sl = _round_price_to_tick(symbol, sl)
    tp = _round_price_to_tick(symbol, tp)

    if side == "long":
        if sl >= entry_exec:
            sl = _round_price_to_tick(symbol, entry_exec - (atr or point))
        if tp <= entry_exec:
            tp = _round_price_to_tick(symbol, entry_exec + (atr or point))
    else:
        if sl <= entry_exec:
            sl = _round_price_to_tick(symbol, entry_exec + (atr or point))
        if tp >= entry_exec:
            tp = _round_price_to_tick(symbol, entry_exec - (atr or point))

    # Compute distances and rr
    tp_dist = abs(tp - entry_exec) if tp is not None else None
    sl_dist = abs(sl - entry_exec) if sl is not None else None
    tp_dist_atr = (tp_dist / atr) if (tp_dist is not None and atr) else None
    sl_dist_atr = (sl_dist / atr) if (sl_dist is not None and atr) else None
    rr_calc = (tp_dist / sl_dist) if (tp_dist is not None and sl_dist not in (None, 0)) else None

    rr_min = 1.2
    rr_max = 6.0
    max_distance_atr = 5.0
    reject_reason = None
    if rr_calc is not None and (rr_calc < rr_min or rr_calc > rr_max):
        reject_reason = f"rr_out_of_bounds:{rr_calc:.2f}"
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
            "price": entry,
            "sl": sl,
            "tp": tp,
            "volume": 0,
            "result_retcode": "INVALID-TP-SL-RR",
            "order": "-",
            "deal": "-",
            "comment": reject_reason,
        })
        return {"status": "invalid-tp-sl-rr", "time": ts_iso, "reason": reject_reason}

    # Validate TP/SL ordering
    if not _is_valid_tp_sl(side, entry, tp, sl):
        _log_order({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "side": side,
            "signal_type": "buy" if side == "long" else "sell",
            "price": entry,
            "sl": sl,
            "tp": tp,
            "volume": 0,
            "result_retcode": "INVALID-TP-SL",
            "order": "-",
            "deal": "-",
            "comment": "Rejected: invalid tp/sl relative to entry",
        })
        return {"status": "invalid-tp-sl", "time": ts_iso}

    # Current prices
    tick = mt5.symbol_info_tick(symbol)
    bid, ask = tick.bid, tick.ask
    last = float(df["close"].iloc[-1])

    # Entry slippage filter: skip if suggested entry too far from current
    info = mt5.symbol_info(symbol)
    point = info.point or 0.01
    max_dev = max_slippage_points * point
    if abs(entry - last) > max_dev:
        return {"status": "slippage-filter", "entry": entry, "last": last, "time": ts_iso}

    # Round SL/TP to tick and validate side
    entry_exec = ask if side == "long" else bid
    sl = _round_price_to_tick(symbol, sl)
    tp = _round_price_to_tick(symbol, tp)

    if side == "long":
        if sl >= entry_exec:
            sl = _round_price_to_tick(symbol, entry_exec - (_calc_atr(df) or point))
        if tp <= entry_exec:
            tp = _round_price_to_tick(symbol, entry_exec + (_calc_atr(df) or point))
    else:
        if sl <= entry_exec:
            sl = _round_price_to_tick(symbol, entry_exec + (_calc_atr(df) or point))
        if tp >= entry_exec:
            tp = _round_price_to_tick(symbol, entry_exec - (_calc_atr(df) or point))

    # Dedupe per bar + side
    idx = _load_index()
    key = f"{symbol}|{timeframe}|{side}|{ts_iso}"
    if key in idx and not allow_multiple:
        return {"status": "duplicate-skip", "time": ts_iso}

    # Positions gate if not allowing multiple
    if not allow_multiple:
        positions = mt5.positions_get(symbol=symbol)
        if positions:
            return {"status": "position-exists", "time": ts_iso}

    # Risk sizing
    acc = mt5.account_info()
    balance = acc.balance if acc else 0.0
    volume = _risk_position_size(symbol, risk_pct, balance, entry_exec, sl)

    order_type = mt5.ORDER_TYPE_BUY if side == "long" else mt5.ORDER_TYPE_SELL
    price = entry_exec
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": 77665,
        "comment": f"FS9 setup RR={rr}",
        "type_filling": mt5.ORDER_FILLING_FOK,
        "type_time": mt5.ORDER_TIME_GTC,
    }

    if dry_run:
        _log_order({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "side": side,
            "price": price,
            "sl": sl,
            "tp": tp,
            "volume": volume,
            "result_retcode": "DRY-RUN",
            "order": "-",
            "deal": "-",
            "comment": request["comment"],
        })
        return {"status": "dry-run-logged", "time": ts_iso}

    try:
        result = send_order_with_fallback(symbol, request)
    except Exception as e:
        # Log and return failure
        _log_order({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "side": side,
            "price": price,
            "sl": sl,
            "tp": tp,
            "volume": volume,
            "result_retcode": None,
            "order": None,
            "deal": None,
            "comment": f"send_exception: {e}",
        })
        return {"status": "send_exception", "time": ts_iso, "error": str(e)}
    idx[key] = datetime.now(timezone.utc).isoformat()
    _save_index(idx)
    _log_order({
    "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "side": side,
        "price": price,
        "sl": sl,
        "tp": tp,
        "volume": volume,
        "result_retcode": getattr(result, "retcode", None),
        "order": getattr(result, "order", None),
        "deal": getattr(result, "deal", None),
        "comment": request["comment"],
    })
    return {"status": "sent", "time": ts_iso, "retcode": getattr(result, "retcode", None)}


def loop(symbol: str, timeframe: str, min_rr: float, min_confs: int, max_slippage_points: float, risk_pct: float,
         dry_run: bool, interval: int, allow_multiple: bool, require_wyckoff: bool, wyckoff_bias: str):
    print(f"FS9 live loop for {symbol} {timeframe} started. Interval: {interval}s")
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
            out = run_once(symbol, timeframe, min_rr, min_confs, max_slippage_points, risk_pct, dry_run, allow_multiple, require_wyckoff, wyckoff_bias)
            print(f"[{datetime.now(timezone.utc).isoformat()}] {out}")
            last_handled = cur_last
        except Exception as e:
            print(f"Loop error: {e}")
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Live bot: execute valid FibonacciSquareOfNine trade setups")
    parser.add_argument("--symbol", default="XAUUSD", help="Single symbol to track (overrides symbols file)")
    parser.add_argument("--symbols", default=None, help="Comma-separated list of symbols to track (overrides --symbol and --symbols-file)")
    parser.add_argument("--symbols-file", default=os.path.join(os.path.dirname(__file__), 'symbols_timeframes.json'), help="JSON file with symbols/timeframes to track")
    parser.add_argument("--timeframe", default="H1")
    parser.add_argument("--min-rr", type=float, default=1.5, help="Minimum RR to accept")
    parser.add_argument("--min-confs", type=int, default=3, help="Minimum strong confluence zones")
    parser.add_argument("--max-entry-slippage-points", type=float, default=50.0, help="Max distance from suggested entry in points")
    parser.add_argument("--risk-pct", type=float, default=1.0)
    parser.add_argument("--require-wyckoff", action="store_true", help="Require Wyckoff pattern detection")
    parser.add_argument("--wyckoff-bias", choices=["auto", "accumulation", "distribution", "any"], default="auto",
                        help="Bias enforcement: auto=enforce side if detected; accumulation/distribution require that pattern; any=ignore")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--debug", action="store_true", help="Dump analysis JSON to outputs when no setup is found")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--allow-multiple", action="store_true")
    args = parser.parse_args()

    # Determine symbols to track (priority: --symbols > --symbols-file > --symbol)
    symbols_list = []
    if args.symbols:
        symbols_list = [s.strip() for s in str(args.symbols).split(',') if s.strip()]
    else:
        # try load symbols from json file
        try:
            if os.path.exists(args.symbols_file):
                with open(args.symbols_file, 'r', encoding='utf-8') as f:
                    j = json.load(f)
                symbols_list = j.get('symbols') or []
        except Exception:
            symbols_list = []

    if not symbols_list:
        symbols_list = [args.symbol]

    # Run once for each symbol when requested
    if args.once:
        results = {}
        for sym in symbols_list:
            try:
                out = run_once(
                    sym,
                    args.timeframe,
                    args.min_rr,
                    args.min_confs,
                    args.max_entry_slippage_points,
                    args.risk_pct,
                    args.dry_run,
                    args.allow_multiple,
                    args.require_wyckoff,
                    args.wyckoff_bias,
                    args.debug,
                )
                results[sym] = out
                print(f"{sym}: {out}")
            except Exception as e:
                results[sym] = {'error': str(e)}
                print(f"{sym}: error: {e}")
        return

    # Continuous mode: cycle through symbols sequentially, running run_once for each
    print(f"Tracking symbols: {symbols_list}")
    while True:
        for sym in symbols_list:
            try:
                out = run_once(
                    sym,
                    args.timeframe,
                    args.min_rr,
                    args.min_confs,
                    args.max_entry_slippage_points,
                    args.risk_pct,
                    args.dry_run,
                    args.allow_multiple,
                    args.require_wyckoff,
                    args.wyckoff_bias,
                    args.debug,
                )
                print(f"[{datetime.now(timezone.utc).isoformat()}] {sym}: {out}")
            except Exception as e:
                print(f"Loop error for {sym}: {e}")
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
