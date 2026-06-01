from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from .common import calc_atr, ensure_outputs_dir, parse_iso_dt, utc_now_iso
from .object_specs import MT5ObjectSpec


STATE_FILENAME = "mt5_object_state_v2.json"


def _load_state(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_state(path: Path, state: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        pass


def _spec_group_key(spec: MT5ObjectSpec) -> str:
    return f"{spec.symbol.upper()}|{spec.timeframe.upper()}|{spec.object_type}"


def _level_prices(spec: MT5ObjectSpec) -> list[float]:
    """Best-effort compute level prices for touch detection.

    For OBJ_FIBO we interpret levels as ratios between anchor_1 and anchor_2.
    For OBJ_HLINE levels are the anchor price.
    For rectangle we use both anchors.
    """
    if spec.object_type == "OBJ_HLINE":
        return [float(spec.anchor_1.price)] if spec.anchor_1 else []
    if spec.object_type == "OBJ_RECTANGLE":
        if spec.anchor_1 and spec.anchor_2:
            return [float(spec.anchor_1.price), float(spec.anchor_2.price)]
        return []
    if spec.object_type in ("OBJ_FIBO", "OBJ_FIBOTIMES"):
        if not (spec.anchor_1 and spec.anchor_2):
            return []
        a = float(spec.anchor_1.price)
        b = float(spec.anchor_2.price)
        rng = b - a
        prices: list[float] = []
        for lv in spec.levels:
            try:
                prices.append(a + rng * float(lv.value))
            except Exception:
                continue
        return prices
    # For OBJ_EXPANSION (A-B-C) we do not try to replicate MT5's internal mapping yet.
    return []


def _touched(bars: pd.DataFrame, prices: list[float]) -> bool:
    if bars.empty or not prices:
        return False
    try:
        lo = bars["low"].astype(float)
        hi = bars["high"].astype(float)
        for p in prices:
            if ((lo <= p) & (hi >= p)).any():
                return True
    except Exception:
        return False
    return False


def update_lifecycle(
    outputs_dir: Path,
    bars_df: pd.DataFrame,
    specs: List[MT5ObjectSpec],
    *,
    ttl_hours: int = 72,
    touch_window_bars: int = 500,
    respected_reaction_atr_mult: float = 0.75,
    failed_break_atr_mult: float = 0.25,
) -> dict:
    """Update and persist lifecycle state based on newly created specs."""
    ensure_outputs_dir(outputs_dir)
    state_path = outputs_dir / STATE_FILENAME
    state = _load_state(state_path)

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    # Track which group got a new spec so we can expire older ones.
    new_by_group: dict[str, str] = {}
    for s in specs:
        gk = _spec_group_key(s)
        new_by_group[gk] = s.object_id

    # Touch evaluation on recent bars only
    recent = bars_df.tail(int(touch_window_bars)) if not bars_df.empty else bars_df
    atr = calc_atr(recent, period=14) if not recent.empty else None

    for s in specs:
        rec = state.get(s.object_id, {})
        if not rec:
            rec = {
                "object_id": s.object_id,
                "symbol": s.symbol,
                "timeframe": s.timeframe,
                "object_type": s.object_type,
                "first_seen_ts": now_iso,
                "last_seen_ts": now_iso,
                "hit_count": 0,
                "state": "ACTIVE",
                "group_key": _spec_group_key(s),
            }
        else:
            rec["last_seen_ts"] = now_iso
            rec["state"] = rec.get("state") or "ACTIVE"

        # --- V2 lifecycle: ACTIVE -> TESTED -> RESPECTED / FAILED ---
        state_now = str(rec.get("state") or "ACTIVE")
        if state_now not in ("ACTIVE", "TESTED", "RESPECTED", "FAILED", "EXPIRED", "BROKEN"):
            state_now = "ACTIVE"

        prices = _level_prices(s)
        tested = False
        if prices and _touched(recent, prices):
            rec["hit_count"] = int(rec.get("hit_count", 0) or 0) + 1
            tested = True
            if state_now == "ACTIVE":
                state_now = "TESTED"

        # Reaction-based promotion to RESPECTED, and break-based FAILED.
        # MVP heuristics:
        # - reaction: after touch, price moves away from level/zone mid by >= X*ATR within next 10 bars
        # - failure: after touch, close moves beyond zone far edge by > Y*ATR (rectangles), or beyond level by > Y*ATR (lines)
        if atr and atr > 0 and state_now in ("TESTED", "RESPECTED"):
            try:
                tail = recent.tail(120)  # compute on a reasonable recent slice
                hi = tail["high"].astype(float)
                lo = tail["low"].astype(float)
                close = tail["close"].astype(float)

                if s.object_type == "OBJ_RECTANGLE" and s.anchor_1 and s.anchor_2:
                    top = float(max(s.anchor_1.price, s.anchor_2.price))
                    bot = float(min(s.anchor_1.price, s.anchor_2.price))
                    mid = (top + bot) / 2.0
                    # failure if close breaks outside zone by > failed_break_atr_mult*ATR
                    if ((close > top + failed_break_atr_mult * atr) | (close < bot - failed_break_atr_mult * atr)).any():
                        state_now = "FAILED"
                    else:
                        # respected if max excursion away from mid exceeds respected threshold
                        away = (close - mid).abs().max()
                        if away >= respected_reaction_atr_mult * atr:
                            state_now = "RESPECTED"

                elif s.object_type in ("OBJ_FIBO", "OBJ_HLINE"):
                    # pick representative line level (for fib, use 0.5 if present else first)
                    lvl = None
                    if s.object_type == "OBJ_HLINE" and s.anchor_1:
                        lvl = float(s.anchor_1.price)
                    elif s.object_type == "OBJ_FIBO" and s.anchor_1 and s.anchor_2 and s.levels:
                        a = float(s.anchor_1.price)
                        b = float(s.anchor_2.price)
                        rng = b - a
                        # prefer 0.618 for reaction measurement if present
                        ratios = [float(x.value) for x in s.levels if x and x.value is not None]
                        pick = 0.618 if any(abs(r - 0.618) < 1e-6 for r in ratios) else (ratios[0] if ratios else 0.5)
                        lvl = a + rng * pick
                    if lvl is not None:
                        # failure if closes drift beyond line by > failed_break_atr_mult*ATR for extended period
                        if (close - float(lvl)).abs().max() > (failed_break_atr_mult * atr * 4.0):
                            # very conservative "failed" for lines (avoid flapping)
                            state_now = state_now
                        # respected if excursion away from line is meaningful
                        away = (close - float(lvl)).abs().max()
                        if away >= respected_reaction_atr_mult * atr:
                            state_now = "RESPECTED"
            except Exception:
                pass

        rec["state"] = state_now
        state[s.object_id] = rec

    # Expire older specs in groups that were regenerated
    ttl = timedelta(hours=int(ttl_hours))
    for obj_id, rec in list(state.items()):
        try:
            gk = rec.get("group_key")
            if not gk:
                continue
            # expire if replaced by newer of same group
            if gk in new_by_group and new_by_group[gk] != obj_id:
                if rec.get("state") in ("ACTIVE", "TESTED"):
                    rec["state"] = "EXPIRED"
                    state[obj_id] = rec
                    continue
            # expire by age
            first = parse_iso_dt(rec.get("first_seen_ts"))
            if first and (now - first) > ttl and rec.get("state") in ("ACTIVE", "TESTED"):
                rec["state"] = "EXPIRED"
                state[obj_id] = rec
        except Exception:
            continue

    _save_state(state_path, state)
    return state


def mark_broken(outputs_dir: Path, object_id: str) -> bool:
    ensure_outputs_dir(outputs_dir)
    state_path = outputs_dir / STATE_FILENAME
    state = _load_state(state_path)
    if object_id not in state:
        return False
    state[object_id]["state"] = "BROKEN"
    state[object_id]["last_seen_ts"] = utc_now_iso()
    _save_state(state_path, state)
    return True
