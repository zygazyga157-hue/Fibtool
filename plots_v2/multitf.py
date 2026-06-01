from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from .anchor_engine import AnchorSelection
from .common import clamp, load_bars


_TF_ORDER = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"]
_TF_RANK = {k: i for i, k in enumerate(_TF_ORDER)}


def pick_parent_tf(timeframes: Sequence[str], tf: str) -> Optional[str]:
    """Pick the next-higher timeframe available in the provided list."""
    tf_u = str(tf).upper()
    cur = _TF_RANK.get(tf_u)
    if cur is None:
        return None
    candidates = []
    for t in timeframes:
        tu = str(t).upper()
        r = _TF_RANK.get(tu)
        if r is None:
            continue
        if r > cur:
            candidates.append((r, tu))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def pick_available_parent_tf(
    outputs_dir: Path,
    symbol: str,
    timeframes: Sequence[str],
    tf: str,
    *,
    asof_utc: str | None = None,
) -> Optional[str]:
    """Pick the next higher timeframe, preferring the CLI list but falling back to stored bars."""
    configured_parent = pick_parent_tf(timeframes, tf)
    if configured_parent:
        return configured_parent

    tf_u = str(tf).upper()
    cur = _TF_RANK.get(tf_u)
    if cur is None:
        return None
    for rank, candidate in sorted((rank, name) for name, rank in _TF_RANK.items() if rank > cur):
        bars = load_bars(outputs_dir, symbol, candidate, asof_utc=asof_utc)
        if not bars.empty:
            return candidate
    return None


def compute_alignment_score(child: AnchorSelection, parent: AnchorSelection) -> float:
    """Return 0..1 alignment score based on range containment/overlap (price-only MVP)."""
    try:
        c_lo = float(min(child.a.price, child.b.price))
        c_hi = float(max(child.a.price, child.b.price))
        p_lo = float(min(parent.a.price, parent.b.price))
        p_hi = float(max(parent.a.price, parent.b.price))
        child_len = max(1e-12, c_hi - c_lo)
        inter_lo = max(c_lo, p_lo)
        inter_hi = min(c_hi, p_hi)
        inter = max(0.0, inter_hi - inter_lo)
        overlap_ratio = inter / child_len
        contained = 1.0 if (c_lo >= p_lo and c_hi <= p_hi) else 0.0
        score = 0.65 * overlap_ratio + 0.35 * contained
        return float(clamp(score, 0.0, 1.0))
    except Exception:
        return 0.0
