from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from .common import calc_atr, clamp, detect_pivots, infer_point, load_bars, parse_iso_dt
from .object_specs import AnchorPoint
from .common import load_jsonl_latest


@dataclass(frozen=True)
class AnchorSelection:
    a: AnchorPoint
    b: AnchorPoint
    kind: str  # e.g. "auto_pivots" or "asia_sweep_hint"
    atr: Optional[float]
    point: float
    confidence: float = 0.0
    confidence_components: dict = None  # type: ignore[assignment]


@dataclass(frozen=True)
class AnchorCandidate:
    a: AnchorPoint
    b: AnchorPoint
    pivot_quality: float
    atr_multiple: float
    liquidity_sweep_score: float
    mss_alignment: float
    session_weight: float
    recency_weight: float
    score: float


def _to_anchor(ts: pd.Timestamp, price: float, kind: str) -> AnchorPoint:
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    ts_iso = ts.tz_convert("UTC").to_pydatetime().replace(tzinfo=timezone.utc).isoformat()
    return AnchorPoint(time_utc=ts_iso, price=float(price), kind=kind)


def _pivot_points(df: pd.DataFrame) -> list[tuple[pd.Timestamp, float, str]]:
    pts: list[tuple[pd.Timestamp, float, str]] = []
    if df.empty:
        return pts
    for _, r in df.iterrows():
        t = r.get("time")
        if pd.isna(t):
            continue
        ts = pd.Timestamp(t)
        try:
            pl = float(r.get("pivot_low") or 0.0)
        except Exception:
            pl = 0.0
        try:
            ph = float(r.get("pivot_high") or 0.0)
        except Exception:
            ph = 0.0
        if pl and pl > 0:
            pts.append((ts, pl, "pivot_low"))
        if ph and ph > 0:
            pts.append((ts, ph, "pivot_high"))
    pts.sort(key=lambda x: x[0])
    return pts


def _session_weight(ts: pd.Timestamp) -> float:
    """Simple UTC session weighting (MVP)."""
    try:
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        h = int(ts.tz_convert("UTC").hour)
        # crude session buckets by UTC hour
        if 0 <= h < 7:
            return 0.7  # Asia-ish
        if 7 <= h < 13:
            return 1.0  # London-ish
        if 13 <= h < 17:
            return 1.2  # NY-ish
        return 0.5  # dead-ish
    except Exception:
        return 1.0


def _recency_weight(ts: pd.Timestamp, *, now: pd.Timestamp) -> float:
    """Exponential recency weight (half-life ~48h)."""
    try:
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        dt_hours = float((now - ts).total_seconds() / 3600.0)
        if dt_hours < 0:
            dt_hours = 0.0
        return float(pow(0.5, dt_hours / 48.0))
    except Exception:
        return 0.5


def _pivot_quality_score(df: pd.DataFrame, ts: pd.Timestamp, kind: str, atr: Optional[float]) -> float:
    """Approximate 'pivot quality' by measuring extremeness vs recent window in ATR multiples."""
    if df.empty:
        return 0.5
    try:
        # locate nearest bar index by time
        t = pd.to_datetime(df["time"], utc=True, errors="coerce")
        # use integer index distance on nearest match
        idx = int((t - ts).abs().idxmin())
        w = 30
        lo = max(0, idx - w)
        hi = min(len(df), idx + w + 1)
        window = df.iloc[lo:hi]
        if window.empty:
            return 0.5
        p = None
        # approximate pivot price from kind by using local low/high at idx
        if kind == "pivot_low":
            p = float(df.iloc[idx]["low"])
            extreme = float(window["low"].min())
            # closer to min is better
            dist = abs(p - extreme)
        else:
            p = float(df.iloc[idx]["high"])
            extreme = float(window["high"].max())
            dist = abs(p - extreme)
        if atr and atr > 0:
            q = 1.0 / (1.0 + (dist / atr))
        else:
            q = 1.0 / (1.0 + (dist / max(1.0, abs(p) * 0.001)))
        return float(clamp(q, 0.0, 1.0))
    except Exception:
        return 0.5


def rank_anchor_candidates(
    df: pd.DataFrame,
    pts: list[tuple[pd.Timestamp, float, str]],
    *,
    atr: Optional[float],
    now: pd.Timestamp,
    max_pairs: int = 25,
    asia_sweep: Optional[dict] = None,
) -> list[AnchorCandidate]:
    """Generate and score multiple anchor candidates, then return best-first list."""
    if len(pts) < 2:
        return []

    # gather alternating pairs from the tail
    candidates: list[AnchorCandidate] = []
    tail = pts[-max(10, max_pairs * 2) :]
    # consider pairs in the tail (order preserved)
    for j in range(len(tail) - 1, 0, -1):
        b = tail[j]
        for i in range(j - 1, -1, -1):
            a = tail[i]
            if a[2] == b[2]:
                continue
            swing = abs(b[1] - a[1])
            atr_mult = (swing / atr) if atr and atr > 0 else 0.0
            pq_a = _pivot_quality_score(df, a[0], a[2], atr)
            pq_b = _pivot_quality_score(df, b[0], b[2], atr)
            pivot_quality = float(clamp((pq_a + pq_b) / 2.0, 0.0, 1.0))

            # liquidity sweep alignment (MVP): if asia sweep exists, reward anchors near asia_high/low
            sweep_score = 0.0
            mss_align = 0.0
            if asia_sweep:
                try:
                    lo = float(asia_sweep.get("asia_low") or 0.0)
                    hi = float(asia_sweep.get("asia_high") or 0.0)
                    if lo > 0 and hi > 0:
                        # if pivot kind matches and price is close to asia range boundary, score it
                        tol = (atr * 0.5) if atr and atr > 0 else max(1e-9, abs(hi - lo) * 0.05)
                        if a[2] == "pivot_low" and abs(a[1] - lo) <= tol:
                            sweep_score += 0.5
                        if a[2] == "pivot_high" and abs(a[1] - hi) <= tol:
                            sweep_score += 0.5
                        if b[2] == "pivot_low" and abs(b[1] - lo) <= tol:
                            sweep_score += 0.5
                        if b[2] == "pivot_high" and abs(b[1] - hi) <= tol:
                            sweep_score += 0.5
                        sweep_score = float(clamp(sweep_score, 0.0, 1.0))
                    if bool(asia_sweep.get("sweep_high")) or bool(asia_sweep.get("sweep_low")):
                        mss_align = 0.5  # placeholder until explicit MSS fields exist
                except Exception:
                    sweep_score = 0.0
                    mss_align = 0.0

            sw = float(clamp((_session_weight(a[0]) + _session_weight(b[0])) / 2.0, 0.5, 1.2))
            rw = float(clamp((_recency_weight(a[0], now=now) + _recency_weight(b[0], now=now)) / 2.0, 0.0, 1.0))

            # combine: pivot_quality dominates; atr_multiple is capped; sweep/MSS provide bonuses
            atr_score = float(clamp((atr_mult / 6.0) if atr_mult else 0.3, 0.0, 1.0))
            score = (
                0.35 * pivot_quality
                + 0.25 * atr_score
                + 0.15 * sweep_score
                + 0.05 * mss_align
                + 0.10 * (sw / 1.2)  # normalize
                + 0.10 * rw
            )
            score = float(clamp(score, 0.0, 1.0))

            candidates.append(
                AnchorCandidate(
                    a=_to_anchor(a[0], a[1], a[2]),
                    b=_to_anchor(b[0], b[1], b[2]),
                    pivot_quality=pivot_quality,
                    atr_multiple=float(atr_mult) if atr_mult else 0.0,
                    liquidity_sweep_score=sweep_score,
                    mss_alignment=mss_align,
                    session_weight=sw,
                    recency_weight=rw,
                    score=score,
                )
            )
            if len(candidates) >= max_pairs:
                break
        if len(candidates) >= max_pairs:
            break

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates


def select_anchors(
    outputs_dir: Path,
    symbol: str,
    timeframe: str,
    *,
    pivot_left: int = 5,
    pivot_right: int = 5,
    swing_min_atr_mult: float = 1.5,
    prefer_asia_sweep: bool = True,
    asof_utc: str | None = None,
) -> Optional[AnchorSelection]:
    df = load_bars(outputs_dir, symbol, timeframe, asof_utc=asof_utc)
    if df.empty:
        df = load_bars(outputs_dir, symbol, None, asof_utc=asof_utc)
    if df.empty:
        return None

    point = infer_point(df)
    atr = calc_atr(df, period=14)
    if asof_utc:
        dt = parse_iso_dt(asof_utc)
        now = pd.Timestamp(dt) if dt is not None else pd.Timestamp.now(tz="UTC")
    else:
        now = pd.Timestamp.now(tz="UTC")

    # Optional anchor hint from asia_mss_signals.jsonl
    asia_sig = None
    if prefer_asia_sweep:
        sig = load_jsonl_latest(outputs_dir / "asia_mss_signals.jsonl", symbol=symbol, asof_utc=asof_utc)
        asia_sig = sig
        if sig:
            try:
                if bool(sig.get("sweep_high")) or bool(sig.get("sweep_low")):
                    lo = float(sig.get("asia_low"))
                    hi = float(sig.get("asia_high"))
                    ts = parse_iso_dt(sig.get("timestamp") or sig.get("timestamp_session") or sig.get("timestamp_local"))
                    if ts and lo > 0 and hi > 0:
                        # represent as a synthetic swing on the signal timestamp
                        t = pd.Timestamp(ts)
                        a = _to_anchor(t, lo, "asia_low")
                        b = _to_anchor(t, hi, "asia_high")
                        if atr:
                            if abs(b.price - a.price) >= swing_min_atr_mult * atr:
                                return AnchorSelection(a=a, b=b, kind="asia_sweep_hint", atr=atr, point=point)
                        else:
                            return AnchorSelection(a=a, b=b, kind="asia_sweep_hint", atr=atr, point=point)
            except Exception:
                pass

    piv = detect_pivots(df, left=pivot_left, right=pivot_right)
    pts = _pivot_points(piv)
    if len(pts) < 2:
        return None

    min_swing = (swing_min_atr_mult * atr) if atr else None

    ranked = rank_anchor_candidates(piv, pts, atr=atr, now=now, asia_sweep=asia_sig)
    for cand in ranked:
        if min_swing is not None and abs(cand.b.price - cand.a.price) < min_swing:
            continue
        comps = {
            "pivot_quality": cand.pivot_quality,
            "atr_multiple": cand.atr_multiple,
            "liquidity_sweep_score": cand.liquidity_sweep_score,
            "mss_alignment": cand.mss_alignment,
            "session_weight": cand.session_weight,
            "recency_weight": cand.recency_weight,
            "score": cand.score,
        }
        return AnchorSelection(
            a=cand.a,
            b=cand.b,
            kind="confidence_ranked",
            atr=atr,
            point=point,
            confidence=cand.score,
            confidence_components=comps,
        )
    return None


def select_abc(
    outputs_dir: Path,
    symbol: str,
    timeframe: str,
    *,
    pivot_left: int = 5,
    pivot_right: int = 5,
    swing_min_atr_mult: float = 1.5,
    asof_utc: str | None = None,
) -> Optional[tuple[AnchorSelection, AnchorPoint]]:
    """Select A-B-C anchors from last 3 alternating pivots. Returns (A-B selection, C)."""
    df = load_bars(outputs_dir, symbol, timeframe, asof_utc=asof_utc)
    if df.empty:
        df = load_bars(outputs_dir, symbol, None, asof_utc=asof_utc)
    if df.empty:
        return None

    point = infer_point(df)
    atr = calc_atr(df, period=14)
    piv = detect_pivots(df, left=pivot_left, right=pivot_right)
    pts = _pivot_points(piv)
    if len(pts) < 3:
        return None

    min_swing = (swing_min_atr_mult * atr) if atr else None

    # find last 3 alternating pivot points
    chosen: list[tuple[pd.Timestamp, float, str]] = []
    for p in reversed(pts):
        if not chosen:
            chosen.append(p)
            continue
        if p[2] == chosen[-1][2]:
            continue
        chosen.append(p)
        if len(chosen) == 3:
            break
    if len(chosen) < 3:
        return None
    c, b, a = chosen[0], chosen[1], chosen[2]
    if min_swing is not None:
        if abs(b[1] - a[1]) < min_swing:
            return None
        if abs(c[1] - b[1]) < min_swing * 0.5:
            # allow smaller BC than AB but still non-trivial
            return None
    sel = AnchorSelection(a=_to_anchor(a[0], a[1], a[2]), b=_to_anchor(b[0], b[1], b[2]), kind="auto_pivots_abc", atr=atr, point=point)
    c_anchor = _to_anchor(c[0], c[1], c[2])
    return sel, c_anchor
