"""Harmonic signal Telegram formatter and dispatcher.

Mirrors the candlestick_signals.py pipeline:
 - Builds rich HTML Telegram messages from analyze_symbol_live() output
 - Sends to TELEGRAM_GROUP_ID + TELEGRAM_EXTRA_CHAT_IDS
 - Persists signals to outputs/harmonic_signals.jsonl
 - Deduplicates via cooldown state file
"""
from __future__ import annotations

import json
import os
import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import config as _default_cfg
except Exception:
    _default_cfg = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Telegram send (reuse candlestick_signals implementation)
# ---------------------------------------------------------------------------
def _send_telegram(token: str, chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
    try:
        from candlesticks.candlestick_signals import send_telegram
        return send_telegram(token, chat_id, text, parse_mode=parse_mode)
    except Exception:
        pass
    # minimal fallback if import fails
    try:
        import requests
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        ids = [c.strip() for c in str(chat_id).split(",") if c.strip()]
        ok = False
        for cid in ids:
            try:
                r = requests.post(url, json={"chat_id": cid, "text": text, "parse_mode": parse_mode}, timeout=10)
                r.raise_for_status()
                ok = True
            except Exception:
                continue
        return ok
    except Exception:
        return False


# ---------------------------------------------------------------------------
# State file helpers (cooldown dedupe)
# ---------------------------------------------------------------------------
def _load_state(path: str) -> dict:
    try:
        if os.path.exists(path):
            return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_state(path: str, state: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        Path(tmp).write_text(json.dumps(state, default=str, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        pass


def _html_escape(value: Any) -> str:
    return html.escape(str(value), quote=False)


def _fmt_num(value: Any, digits: int = 2, default: str = "N/A") -> str:
    try:
        if value is None:
            return default
        return f"{float(value):.{int(digits)}f}"
    except Exception:
        return default


def _fmt_price(value: Any, default: str = "N/A") -> str:
    try:
        if value is None:
            return default
        v = float(value)
        if abs(v) >= 100:
            return f"{v:.2f}"
        if abs(v) >= 10:
            return f"{v:.3f}"
        return f"{v:.6f}".rstrip("0").rstrip(".")
    except Exception:
        return default


def _fmt_bool(value: Any, true_text: str, false_text: str) -> str:
    return true_text if bool(value) else false_text


def _fmt_time(value: Any, default: str = "N/A") -> str:
    if not value:
        return default
    try:
        s = str(value).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(value)


def _signal_grade(weighted_score: Any) -> str:
    try:
        score = float(weighted_score or 0.0)
    except Exception:
        score = 0.0
    if score >= 1.5:
        return "A+"
    if score >= 1.2:
        return "A"
    if score >= 0.9:
        return "B"
    return "C"


def _load_previous_harmonic_signal(outputs_dir: str, symbol: str) -> Optional[dict]:
    path = Path(outputs_dir) / "harmonic_signals.jsonl"
    if not path.exists():
        return None
    wanted = str(symbol).upper()
    latest: Optional[dict] = None
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if str(rec.get("symbol", "")).upper() == wanted:
                    latest = rec
    except Exception:
        return None
    return latest


def _build_active_harmonics(meta: Dict[str, Any]) -> list[str]:
    levels = meta.get("harmonic_levels") or []
    hit = str(meta.get("harmonic_hit_harmonic") or "")
    out: list[str] = []
    if not isinstance(levels, list):
        return out
    for lvl in levels[:6]:
        if not isinstance(lvl, dict):
            continue
        harmonic = str(lvl.get("harmonic", "?"))
        level = _fmt_price(lvl.get("level"))
        marker = " → HIT ✅" if hit and harmonic == hit else ""
        out.append(f"{_html_escape(harmonic)} @ <b>{_html_escape(level)}</b>{marker}")
    return out


def _build_market_evolution(previous: Optional[dict], current_meta: Dict[str, Any], signal: str) -> Optional[dict]:
    if not previous:
        return None
    prev_meta = previous.get("context_meta") or previous.get("context", {}).get("meta", {}) or {}
    try:
        prev_anchor = float(prev_meta.get("anchor_price"))
        cur_anchor = float(current_meta.get("anchor_price"))
    except Exception:
        return None

    side = str(signal).upper()
    favorable = (side == "BUY" and cur_anchor > prev_anchor) or (side == "SELL" and cur_anchor < prev_anchor)
    structure = "Higher Low Formed ✅" if side == "BUY" and cur_anchor > prev_anchor else (
        "Lower High Formed ✅" if side == "SELL" and cur_anchor < prev_anchor else "Anchor Updated"
    )
    prev_signal = str(previous.get("signal", "")).upper()
    status = "Trend Continuation" if favorable and prev_signal == side else "Structure Updated"

    def _f(v: Any) -> Optional[float]:
        try:
            return float(v)
        except Exception:
            return None

    prev_exp = _f(prev_meta.get("price_move_points"))
    cur_exp = _f(current_meta.get("price_move_points"))
    prev_hit = _f(prev_meta.get("harmonic_hit_level"))
    cur_hit = _f(current_meta.get("harmonic_hit_level"))

    return {
        "previous_anchor": prev_anchor,
        "current_anchor": cur_anchor,
        "structure": structure,
        "status": status,
        "previous_expansion_points": prev_exp,
        "current_expansion_points": cur_exp,
        "previous_harmonic_level": prev_hit,
        "current_harmonic_level": cur_hit,
    }


# ---------------------------------------------------------------------------
# HTML message builder
# ---------------------------------------------------------------------------
def _build_html_harmonic_signal(
    symbol: str,
    signal: str,
    context: Dict[str, Any],
    trade_setup: Dict[str, Any],
    previous_signal: Optional[dict] = None,
) -> str:
    """Build a rich HTML Telegram message for a harmonic signal."""
    meta = context.get("meta", {})
    gates = context.get("gates", {})
    structure = context.get("structure", {})

    side_emoji = "🟢" if signal == "BUY" else "🔴"
    timeframe = meta.get("timeframe", "H1")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    regime = _html_escape(meta.get("regime", "UNKNOWN"))
    vol_phase = _html_escape(gates.get("vol_phase", "UNKNOWN"))
    stress = _html_escape(meta.get("stress", "UNKNOWN"))
    resonance = _html_escape(meta.get("resonance_strength", "UNKNOWN"))
    close = meta.get("close")
    atr = meta.get("atr")
    confirmations = int(gates.get("confirmations", 0) or 0)
    weighted_score = float(gates.get("weighted_score", 0) or 0)
    grade = _signal_grade(weighted_score)

    entry = trade_setup.get("entry", close)
    sl = trade_setup.get("sl")
    scale = trade_setup.get("scale", 1)
    method = trade_setup.get("method", "MULTIPLES")
    invalidation_price = trade_setup.get("invalidation_price")
    sl_buffer = trade_setup.get("sl_buffer")
    trail_atr_mult = trade_setup.get("trail_atr_mult")
    trail_after = trade_setup.get("trail_after")
    be_trigger_r = trade_setup.get("be_trigger_r", 0.618)
    tp_levels = trade_setup.get("tp_levels", [])
    rr_levels = trade_setup.get("rr_levels", [])
    be_trigger = trade_setup.get("be_trigger_0618")
    base_h = trade_setup.get("base_harmonics", [])
    multiples = trade_setup.get("common_multiples", [])
    k_atr = trade_setup.get("k_atr")
    point = float(trade_setup.get("point", 0) or 0)
    if point <= 0:
        point = 1.0
    try:
        last_bar_points = abs(float(meta.get("price_move_last_bar", 0) or 0)) / point
    except Exception:
        last_bar_points = 0.0

    zone_lo = structure.get("zone_low")
    zone_mid = structure.get("zone_mid")
    zone_hi = structure.get("zone_high")

    tp_lines: list[str] = []
    for i, (tp, rr) in enumerate(zip(tp_levels, rr_levels)):
        tp_lines.append(f"🎯 TP{i + 1}: <b>{_html_escape(_fmt_price(tp))}</b> ({_html_escape(_fmt_num(rr, 2))}R)")

    active_lines = _build_active_harmonics(meta)
    evolution = _build_market_evolution(previous_signal, meta, signal)
    separator = "━━━━━━━━━━━━━━━━━━"

    parts = [
        "🔥 <b>HARMONIC SIGNAL</b>",
        "",
        f"{side_emoji} Symbol: <b>{_html_escape(symbol)}</b>",
        f"📊 Action: <b>{_html_escape(signal)}</b>",
        f"🕒 Time: {_html_escape(now)}",
        f"⏰ Timeframe: <b>{_html_escape(timeframe)}</b>",
        "",
        separator,
        "",
        "🎯 <b>Signal Quality</b>",
        "",
        f"🏅 Signal Grade: <b>{grade}</b>",
        f"⭐ Weighted Score: <b>{_fmt_num(weighted_score, 2)}</b>",
        f"✅ Confirmations: <b>{confirmations}</b>",
        "",
        f"🔷 Resonance: <b>{resonance}</b>",
        f"📈 Regime: <b>{regime}</b>",
        f"🌡 Stress: <b>{stress}</b>",
        f"📦 Volatility Phase: <b>{vol_phase}</b>",
        "",
        separator,
        "",
        "📍 <b>Harmonic Structure</b>",
        "",
        f"⚓ Anchor: <b>{_html_escape(str(meta.get('anchor_kind', 'N/A')).replace('_', ' ').title())}</b>",
        f"📌 Anchor Price: <b>{_html_escape(_fmt_price(meta.get('anchor_price')))}</b>",
        f"🕒 Anchor Time: {_html_escape(_fmt_time(meta.get('anchor_time')))}",
        "",
        f"🎵 Harmonic Hit: <b>{_html_escape(meta.get('harmonic_hit_harmonic', 'N/A'))}</b>",
        f"🎯 Harmonic Level: <b>{_html_escape(_fmt_price(meta.get('harmonic_hit_level')))}</b>",
        f"📏 Distance To Hit: <b>{_html_escape(_fmt_num(meta.get('harmonic_hit_distance'), 6))}</b>",
        f"🔧 Detection Method: <b>{_html_escape(meta.get('harmonic_hit_method', 'N/A'))}</b>",
        "",
        f"📈 Price Expansion: <b>{_html_escape(_fmt_num(meta.get('price_move_points'), 0))} pts</b>",
        f"📊 Last Bar Expansion: <b>{_html_escape(_fmt_num(last_bar_points, 0))} pts</b>",
        f"⏳ Bars Since Anchor: <b>{_html_escape(meta.get('bars_elapsed', 'N/A'))}</b>",
        "",
        separator,
        "",
        "🏗 <b>Acceptance Structure</b>",
        "",
        f"Zone Low : {_html_escape(_fmt_price(zone_lo))}",
        f"Zone Mid : <b>{_html_escape(_fmt_price(zone_mid))}</b>",
        f"Zone High: {_html_escape(_fmt_price(zone_hi))}",
        "",
        _fmt_bool(structure.get("buy_acceptance"), "✅ Buy Acceptance Confirmed", "❌ Buy Acceptance"),
        _fmt_bool(structure.get("sell_rejection"), "✅ Sell Rejection Confirmed", "❌ Sell Rejection"),
        _fmt_bool(structure.get("volume_confirmed"), "✅ Volume Confirmed", "❌ Volume Confirmation"),
        "",
        f"Volume: {_html_escape(_fmt_num(meta.get('volume'), 0))}",
        f"Average Volume: {_html_escape(_fmt_num(meta.get('avg_volume'), 1))}",
        "",
        separator,
        "",
        "💰 <b>Trade Plan</b>",
        "",
        f"Method: <b>{_html_escape(method)}</b>",
        f"Entry : <b>{_html_escape(_fmt_price(entry))}</b>",
        f"SL    : <b>{_html_escape(_fmt_price(sl))}</b>",
        f"Scale : <b>{_html_escape(_fmt_num(scale, 2))}</b>",
    ]

    if invalidation_price is not None:
        parts.append(f"Invalidation: <b>{_html_escape(_fmt_price(invalidation_price))}</b>")
    if sl_buffer is not None:
        parts.append(f"SL Buffer   : {_html_escape(_fmt_price(sl_buffer))}")

    if tp_lines:
        parts.append("")
        parts.extend(tp_lines)
    if be_trigger is not None:
        parts.extend([
            "",
            "📌 <b>Breakeven Trigger</b>",
            f"{_html_escape(_fmt_price(be_trigger))} (+{_html_escape(_fmt_num(be_trigger_r, 2))}R)",
        ])
    if trail_after and trail_atr_mult is not None:
        parts.extend([
            "",
            f"Trail: after {_html_escape(trail_after)} with {_html_escape(_fmt_num(trail_atr_mult, 2))} ATR",
        ])

    parts.extend([
        "",
        separator,
        "",
        "🎵 <b>Harmonic Framework</b>",
        "",
        f"Base Harmonics: {_html_escape(' • '.join(str(x) for x in base_h) if base_h else 'N/A')}",
        f"Active Multiples: {_html_escape(' • '.join(str(x) for x in multiples) if multiples else 'N/A')}",
        f"kATR: {_html_escape(_fmt_num(k_atr, 2))}",
        f"ATR : {_html_escape(_fmt_num(atr, 9))}",
    ])

    if active_lines:
        parts.extend(["", separator, "", "🎼 <b>Active Harmonics</b>", ""])
        parts.extend(active_lines)

    if evolution:
        parts.extend([
            "",
            separator,
            "",
            "🧭 <b>Market Evolution</b>",
            "",
            f"Previous Anchor: {_html_escape(_fmt_price(evolution.get('previous_anchor')))}",
            f"Current Anchor : <b>{_html_escape(_fmt_price(evolution.get('current_anchor')))}</b>",
            "",
            f"Structure: {_html_escape(evolution.get('structure', 'N/A'))}",
            f"Expansion: {_html_escape(_fmt_num(evolution.get('previous_expansion_points'), 0))} pts → <b>{_html_escape(_fmt_num(evolution.get('current_expansion_points'), 0))} pts</b>",
            f"Harmonic Level: {_html_escape(_fmt_price(evolution.get('previous_harmonic_level')))} → <b>{_html_escape(_fmt_price(evolution.get('current_harmonic_level')))}</b>",
            f"Status: <b>{_html_escape(evolution.get('status', 'N/A'))}</b>",
        ])

    parts.extend([
        "",
        separator,
        "",
        "🚦 <b>Gate Status</b>",
        "",
        _fmt_bool(gates.get("harmonic_hit"), "✅ Harmonic Hit", "❌ Harmonic Hit"),
        _fmt_bool(gates.get("squared"), "✅ Squared", "❌ Market Not Squared"),
        _fmt_bool(structure.get("buy_acceptance"), "✅ Buy Acceptance", "❌ Buy Acceptance"),
        _fmt_bool(structure.get("sell_rejection"), "✅ Sell Rejection", "❌ Sell Rejection"),
        _fmt_bool(structure.get("volume_confirmed"), "✅ Volume Confirmation", "❌ Volume Confirmation"),
        _fmt_bool(weighted_score >= 0.7, "✅ Resonance Filter", "❌ Resonance Filter"),
        "",
        separator,
        "",
        "⚠️ <i>Harmonic resonance signal only. Always verify risk before entry.</i>",
    ])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main signal dispatcher
# ---------------------------------------------------------------------------
def run_harmonic_signal_for_symbol(
    symbol: str,
    result: Dict[str, Any],
    cfg: object = None,
    outputs_dir: str = "outputs",
) -> Dict[str, Any]:
    """Orchestrate harmonic signal: compute trade setup, send Telegram, persist.

    Parameters
    ----------
    symbol : symbol name
    result : output of analyze_symbol_live()
    cfg    : config module (defaults to config)
    outputs_dir : directory for JSONL + state files

    Returns
    -------
    dict with keys: sent, signal, trade_setup, reason
    """
    _cfg = cfg or _default_cfg
    out: Dict[str, Any] = {"sent": False, "signal": None, "trade_setup": {}, "reason": ""}

    sig = result.get("signal") if isinstance(result, dict) else None
    if sig not in ("BUY", "SELL"):
        out["reason"] = "no_signal"
        return out
    out["signal"] = sig

    context = result.get("context", {})
    meta = context.get("meta", {})
    close = meta.get("close")
    atr = meta.get("atr")
    if close is None:
        out["reason"] = "no_close_price"
        return out

    # Instrument point
    point = 0.01
    try:
        if meta.get("point") is not None:
            point = float(meta.get("point")) or 0.01
        else:
            levels = meta.get("harmonic_levels", [])
            if levels:
                point = float(levels[0].get("tolerance", 0.01)) or 0.01
    except Exception:
        pass

    # Compute trade setup
    k_atr = float(getattr(_cfg, "HARMONIC_K_ATR", 0.25)) if _cfg else 0.25
    method = str(getattr(_cfg, "HARMONIC_TP_SL_METHOD", "MULTIPLES")) if _cfg else "MULTIPLES"
    sl_atr_buffer = float(getattr(_cfg, "HARMONIC_SWING_SL_ATR_BUFFER", 0.55)) if _cfg else 0.55
    min_risk_atr = float(getattr(_cfg, "HARMONIC_SWING_MIN_RISK_ATR", 1.0)) if _cfg else 1.0
    be_trigger_r = float(getattr(_cfg, "HARMONIC_SWING_BE_TRIGGER_R", 1.0)) if _cfg else 1.0
    trail_atr_mult = float(getattr(_cfg, "HARMONIC_SWING_TRAIL_ATR_MULT", 2.0)) if _cfg else 2.0
    try:
        from harmonic_trader import get_harmonic_trade_setup
        trade_setup = get_harmonic_trade_setup(
            symbol,
            sig,
            float(close),
            float(atr or 0),
            point,
            k_atr=k_atr,
            method=method,
            context=context,
            sl_atr_buffer=sl_atr_buffer,
            min_risk_atr=min_risk_atr,
            be_trigger_r=be_trigger_r,
            trail_atr_mult=trail_atr_mult,
        )
    except Exception:
        trade_setup = {}

    if not trade_setup or not trade_setup.get("tp_levels"):
        out["reason"] = "no_harmonic_data_for_symbol"
        return out
    out["trade_setup"] = trade_setup

    # RR gate
    rr_min = float(getattr(_cfg, "HARMONIC_RR_MIN", 1.0)) if _cfg else 1.0
    tp_idx = max(0, int(getattr(_cfg, "HARMONIC_TP_LEVEL", 1) if _cfg else 1) - 1)
    tp_idx = min(tp_idx, len(trade_setup.get("rr_levels", [])) - 1)
    selected_rr = trade_setup["rr_levels"][tp_idx] if trade_setup.get("rr_levels") else 0
    if selected_rr < rr_min:
        out["reason"] = f"rr_too_low({selected_rr}<{rr_min})"
        return out

    previous_signal = _load_previous_harmonic_signal(outputs_dir, symbol)
    signal_grade = _signal_grade(context.get("gates", {}).get("weighted_score", 0))
    market_evolution = _build_market_evolution(previous_signal, meta, sig)

    # Cooldown dedupe
    cooldown = int(getattr(_cfg, "HARMONIC_AUTOTRADE_COOLDOWN_SECONDS", 3600)) if _cfg else 3600
    state_path = str(getattr(_cfg, "HARMONIC_AUTOTRADE_STATE_PATH", "outputs/harmonic_autotrade_state.json")) if _cfg else "outputs/harmonic_autotrade_state.json"
    state = _load_state(state_path)
    last_ts = state.get(symbol, {}).get("last_signal_ts")
    now = datetime.now(timezone.utc)
    if last_ts:
        try:
            last_dt = datetime.fromisoformat(last_ts)
            if (now - last_dt).total_seconds() < cooldown:
                out["reason"] = "cooldown"
                return out
        except Exception:
            pass

    # Check if Telegram sending is enabled
    send_enabled = bool(getattr(_cfg, "HARMONIC_SIGNALS_TELEGRAM", False)) if _cfg else False
    token = str(getattr(_cfg, "TELEGRAM_BOT_TOKEN", "")) if _cfg else ""
    chat_id = str(getattr(_cfg, "TELEGRAM_GROUP_ID", "") or getattr(_cfg, "TELEGRAM_ADMIN_ID", "")) if _cfg else ""
    extra = str(getattr(_cfg, "TELEGRAM_EXTRA_CHAT_IDS", "")) if _cfg else ""
    if extra:
        chat_id = f"{chat_id},{extra}" if chat_id else extra

    if send_enabled and token and chat_id:
        html = _build_html_harmonic_signal(symbol, sig, context, trade_setup, previous_signal=previous_signal)
        sent = _send_telegram(token, chat_id, html, parse_mode="HTML")
        out["sent"] = sent

    # Update state
    sym_state = state.get(symbol, {})
    sym_state["last_signal_ts"] = now.isoformat()
    sym_state["last_signal"] = sig
    state[symbol] = sym_state
    _save_state(state_path, state)

    # Persist to JSONL
    try:
        os.makedirs(outputs_dir, exist_ok=True)
        jsonl_path = os.path.join(outputs_dir, "harmonic_signals.jsonl")
        record = {
            "timestamp": now.isoformat(),
            "symbol": symbol,
            "signal": sig,
            "trade_setup": trade_setup,
            "context_meta": meta,
            "gates": context.get("gates", {}),
            "structure": context.get("structure", {}),
            "signal_grade": signal_grade,
            "market_evolution": market_evolution,
            "sent": out["sent"],
        }
        with open(jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception:
        pass

    out["reason"] = "sent" if out["sent"] else "telegram_disabled"
    return out
