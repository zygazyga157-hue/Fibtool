"""Harmonic autotrade evaluation and execution.

Mirrors candlestick_autotrade.py architecture:
 - HarmonicCandidate dataclass with mechanical gates
 - evaluate_harmonic_autotrade_candidate() returns eligible + reason
 - run_harmonic_autotrade_for_symbol() places the order via live_entry_bot_mt5
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import config as _default_cfg
except Exception:
    _default_cfg = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# State helpers (atomic write, same pattern as asia_sweep_london_mss)
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
# Candidate dataclass
# ---------------------------------------------------------------------------
@dataclass
class HarmonicCandidate:
    eligible: bool = False
    reason: str = ""
    symbol: str = ""
    side: str = ""
    entry: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    rr: float = 0.0
    risk: float = 0.0
    scale: int = 1
    tp_levels: List[float] = field(default_factory=list)
    rr_levels: List[float] = field(default_factory=list)
    regime: str = ""
    stress: str = ""
    resonance_strength: str = ""
    confirmations: int = 0
    squared: bool = False
    vol_phase: str = ""
    weighted_score: float = 0.0
    trade_setup: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------
def evaluate_harmonic_autotrade_candidate(
    symbol: str,
    result: Dict[str, Any],
    bid: float,
    ask: float,
    cfg: object = None,
) -> HarmonicCandidate:
    """Evaluate whether a harmonic signal qualifies for autotrade.

    Gates (in order):
      1. signal is BUY or SELL
      2. HARMONIC_AUTOTRADE_ENABLED
      3. regime not UNKNOWN (when HARMONIC_BLOCK_UNKNOWN_REGIME)
      4. vol_phase not EXTREME (when not HARMONIC_ALLOW_EXTREME)
      5. volume_confirmed
      6. RR >= HARMONIC_RR_MIN
      7. stress not HIGH
      8. cooldown check
    """
    _cfg = cfg or _default_cfg
    c = HarmonicCandidate(symbol=symbol)

    sig = result.get("signal") if isinstance(result, dict) else None
    if sig not in ("BUY", "SELL"):
        c.reason = "no_signal"
        return c
    c.side = "long" if sig == "BUY" else "short"

    # Gate 2: enabled
    enabled = bool(getattr(_cfg, "HARMONIC_AUTOTRADE_ENABLED", False)) if _cfg else False
    if not enabled:
        c.reason = "autotrade_disabled"
        return c

    context = result.get("context", {})
    meta = context.get("meta", {})
    gates = context.get("gates", {})
    structure = context.get("structure", {})

    c.regime = str(meta.get("regime", "UNKNOWN"))
    c.stress = str(meta.get("stress", "LOW"))
    c.resonance_strength = str(meta.get("resonance_strength", "WEAK"))
    c.confirmations = int(gates.get("confirmations", 0))
    c.squared = bool(gates.get("squared", False))
    c.vol_phase = str(gates.get("vol_phase", "UNKNOWN"))
    c.weighted_score = float(gates.get("weighted_score", 0))

    # Gate 3: regime
    block_unknown = bool(getattr(_cfg, "HARMONIC_BLOCK_UNKNOWN_REGIME", True)) if _cfg else True
    if block_unknown and c.regime == "UNKNOWN":
        c.reason = "regime_unknown"
        return c

    # Gate 4: extreme volatility
    allow_extreme = bool(getattr(_cfg, "HARMONIC_ALLOW_EXTREME", False)) if _cfg else False
    if c.vol_phase == "EXTREME" and not allow_extreme:
        c.reason = "vol_extreme"
        return c

    # Gate 5: volume confirmed
    if not bool(structure.get("volume_confirmed", False)):
        c.reason = "volume_not_confirmed"
        return c

    # Compute trade setup
    close = meta.get("close")
    atr = meta.get("atr")
    if close is None:
        c.reason = "no_close_price"
        return c

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
        c.reason = "no_harmonic_data"
        return c

    c.trade_setup = trade_setup
    c.entry = float(trade_setup.get("entry", 0))
    c.sl = float(trade_setup.get("sl", 0))
    c.risk = float(trade_setup.get("risk", 0))
    c.scale = int(trade_setup.get("scale", 1))
    c.tp_levels = list(trade_setup.get("tp_levels", []))
    c.rr_levels = list(trade_setup.get("rr_levels", []))

    # Select TP for the order
    tp_idx = max(0, int(getattr(_cfg, "HARMONIC_TP_LEVEL", 1) if _cfg else 1) - 1)
    tp_idx = min(tp_idx, len(c.tp_levels) - 1)
    c.tp = c.tp_levels[tp_idx] if c.tp_levels else 0
    c.rr = c.rr_levels[tp_idx] if c.rr_levels else 0

    # Gate 6: minimum RR
    rr_min = float(getattr(_cfg, "HARMONIC_RR_MIN", 1.0)) if _cfg else 1.0
    if c.rr < rr_min:
        c.reason = f"rr_too_low({c.rr}<{rr_min})"
        return c

    # Gate 7: stress
    if c.stress == "HIGH":
        c.reason = "stress_high"
        return c

    # Gate 8: cooldown
    cooldown = int(getattr(_cfg, "HARMONIC_AUTOTRADE_COOLDOWN_SECONDS", 3600)) if _cfg else 3600
    state_path = str(getattr(_cfg, "HARMONIC_AUTOTRADE_STATE_PATH", "outputs/harmonic_autotrade_state.json")) if _cfg else "outputs/harmonic_autotrade_state.json"
    state = _load_state(state_path)
    last_ts = state.get(symbol, {}).get("last_trade_ts")
    now = datetime.now(timezone.utc)
    if last_ts:
        try:
            last_dt = datetime.fromisoformat(last_ts)
            if (now - last_dt).total_seconds() < cooldown:
                c.reason = "cooldown"
                return c
        except Exception:
            pass

    c.eligible = True
    c.reason = "eligible"
    return c


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------
def run_harmonic_autotrade_for_symbol(
    symbol: str,
    result: Dict[str, Any],
    mt5_module: object,
    cfg: object = None,
    outputs_dir: str = "outputs",
) -> Dict[str, Any]:
    """Evaluate and optionally place a harmonic trade.

    Returns dict: {status, candidate, order_result}
    """
    _cfg = cfg or _default_cfg
    out: Dict[str, Any] = {"status": "skipped", "candidate": None, "order_result": None}

    # Get bid/ask from result context (best-effort)
    meta = result.get("context", {}).get("meta", {}) if isinstance(result, dict) else {}
    close = float(meta.get("close", 0))
    bid = close
    ask = close

    candidate = evaluate_harmonic_autotrade_candidate(symbol, result, bid, ask, cfg=_cfg)
    out["candidate"] = asdict(candidate)

    if not candidate.eligible:
        out["status"] = candidate.reason
        # Append audit even for non-eligible
        _append_audit(outputs_dir, candidate, None)
        return out

    # Place the order
    dry_run = bool(getattr(_cfg, "HARMONIC_AUTOTRADE_DRY_RUN", True)) if _cfg else True

    try:
        from live_entry_bot_mt5 import send_order

        # Read lot size from admin_settings
        lot = 0.1
        try:
            admin_path = os.path.join(outputs_dir, "admin_settings.json")
            if os.path.exists(admin_path):
                admin = json.loads(Path(admin_path).read_text(encoding="utf-8"))
                lot = float(admin.get("default_lot", 0.1))
        except Exception:
            pass

        order_result = send_order(
            symbol=symbol,
            side=candidate.side,
            volume=lot,
            price=candidate.entry,
            stop=candidate.sl,
            tp=candidate.tp,
            comment=f"harmonic_{candidate.side}",
            dry_run=dry_run,
            order_kind="market",
        )
        out["order_result"] = order_result
        out["status"] = "dry_run" if dry_run else "placed"
    except Exception as e:
        out["status"] = f"order_error: {e}"
        out["order_result"] = {"error": str(e)}

    # Update state
    state_path = str(getattr(_cfg, "HARMONIC_AUTOTRADE_STATE_PATH", "outputs/harmonic_autotrade_state.json")) if _cfg else "outputs/harmonic_autotrade_state.json"
    state = _load_state(state_path)
    now = datetime.now(timezone.utc)
    sym_state = state.get(symbol, {})
    sym_state["last_trade_ts"] = now.isoformat()
    sym_state["last_trade_side"] = candidate.side
    state[symbol] = sym_state
    _save_state(state_path, state)

    # Append audit
    _append_audit(outputs_dir, candidate, out.get("order_result"))

    return out


def _append_audit(outputs_dir: str, candidate: HarmonicCandidate, order_result: Any) -> None:
    try:
        os.makedirs(outputs_dir, exist_ok=True)
        audit_path = os.path.join(outputs_dir, "harmonic_autotrade_audit.jsonl")
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "candidate": asdict(candidate),
            "order_result": order_result,
        }
        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception:
        pass
