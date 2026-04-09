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


# ---------------------------------------------------------------------------
# HTML message builder
# ---------------------------------------------------------------------------
def _build_html_harmonic_signal(
    symbol: str,
    signal: str,
    context: Dict[str, Any],
    trade_setup: Dict[str, Any],
) -> str:
    """Build a rich HTML Telegram message for a harmonic signal."""
    meta = context.get("meta", {})
    gates = context.get("gates", {})
    structure = context.get("structure", {})

    side_emoji = "🟢" if signal == "BUY" else "🔴"
    regime = meta.get("regime", "?")
    vol_phase = gates.get("vol_phase", "?")
    stress = meta.get("stress", "?")
    resonance = meta.get("resonance_strength", "?")
    session = meta.get("timeframe", "H1")
    close = meta.get("close", 0)
    atr = meta.get("atr")
    confirmations = gates.get("confirmations", 0)
    weighted_score = gates.get("weighted_score", 0)
    squared = gates.get("squared", False)
    bars_elapsed = meta.get("bars_elapsed", 0)
    anchor_kind = meta.get("anchor_kind", "?")

    entry = trade_setup.get("entry", close)
    sl = trade_setup.get("sl", 0)
    risk = trade_setup.get("risk", 0)
    scale = trade_setup.get("scale", 1)
    tp_levels = trade_setup.get("tp_levels", [])
    rr_levels = trade_setup.get("rr_levels", [])
    be_trigger = trade_setup.get("be_trigger_0618", 0)
    base_h = trade_setup.get("base_harmonics", [])
    multiples = trade_setup.get("common_multiples", [])

    zone_lo = structure.get("zone_low")
    zone_mid = structure.get("zone_mid")
    zone_hi = structure.get("zone_high")

    # Build TP lines
    tp_lines = []
    for i, (tp, rr) in enumerate(zip(tp_levels, rr_levels)):
        marker = " ◀" if i == 0 else ""
        tp_lines.append(f"  TP{i+1}: <b>{tp}</b>  (RR {rr}){marker}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    parts = [
        f"🔥 <b>HARMONIC SIGNAL</b>",
        f"",
        f"{side_emoji} <b>{signal}</b>  {symbol}",
        f"🕒 {now}",
        f"",
        f"📐 Regime: <b>{regime}</b>  |  Vol: {vol_phase}",
        f"🌡 Stress: {stress}  |  Resonance: {resonance}",
        f"🔮 Squared: {'✅' if squared else '❌'}  (bars: {bars_elapsed}, anchor: {anchor_kind})",
        f"📊 Confirmations: {confirmations}  |  Score: {weighted_score:.2f}",
    ]

    if zone_mid is not None:
        parts.append(f"")
        parts.append(f"📍 Zone: {zone_lo} │ <b>{zone_mid}</b> │ {zone_hi}")

    parts.append(f"")
    parts.append(f"💰 Entry: <b>{entry}</b>  (zone-acceptance close)")
    parts.append(f"🛑 SL: <b>{sl}</b>  (risk: {risk})")

    if tp_lines:
        parts.append(f"")
        parts.append(f"🎯 <b>TP Ladder</b>  (scale={scale})")
        parts.extend(tp_lines)

    if be_trigger:
        parts.append(f"")
        parts.append(f"📐 Breakeven at <b>{be_trigger}</b>  (+0.618R)")

    if base_h or multiples:
        parts.append(f"")
        parts.append(f"💥 Harmonics: {base_h}  ×  {multiples}")

    if atr:
        parts.append(f"📏 ATR: {atr:.6g}")

    parts.append(f"")
    parts.append(f"⚠️ <i>Not financial advice. Trade at your own risk.</i>")

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
        levels = meta.get("harmonic_levels", [])
        if levels:
            point = float(levels[0].get("tolerance", 0.01)) or 0.01
    except Exception:
        pass

    # Compute trade setup
    k_atr = float(getattr(_cfg, "HARMONIC_K_ATR", 0.25)) if _cfg else 0.25
    try:
        from harmonic_trader import get_harmonic_trade_setup
        trade_setup = get_harmonic_trade_setup(symbol, sig, float(close), float(atr or 0), point, k_atr=k_atr)
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
        html = _build_html_harmonic_signal(symbol, sig, context, trade_setup)
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
            "sent": out["sent"],
        }
        with open(jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception:
        pass

    out["reason"] = "sent" if out["sent"] else "telegram_disabled"
    return out
