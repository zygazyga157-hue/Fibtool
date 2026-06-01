from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

from .anchor_engine import select_anchors
from .common import calc_atr, clamp, infer_point, load_bars


@dataclass(frozen=True)
class Confluence:
    fib_ratio: float
    fib_price: float
    s9_degree: float
    s9_price: float
    distance: float
    strength: float  # 0..100


def fib_prices(a: float, b: float, ratios: List[float]) -> List[tuple[float, float]]:
    rng = b - a
    out: list[tuple[float, float]] = []
    for r in ratios:
        try:
            out.append((float(r), a + rng * float(r)))
        except Exception:
            continue
    return out


def s9_levels_from_pivot_price(pivot: float) -> List[tuple[float, float]]:
    """Compute S9 levels from `fib_square_strategy.FibonacciSquareOfNine`."""
    try:
        from fib_square_strategy import FibonacciSquareOfNine
    except Exception:
        return []
    fs9 = FibonacciSquareOfNine()
    try:
        lv = fs9.calculate_s9_levels(float(pivot))
    except Exception:
        return []
    out: list[tuple[float, float]] = []
    for deg, price in lv.items():
        try:
            out.append((float(deg), float(price)))
        except Exception:
            continue
    out.sort(key=lambda x: x[0])
    return out


def find_confluences(
    *,
    fib_levels: List[tuple[float, float]],
    s9_levels: List[tuple[float, float]],
    tolerance: float,
    atr: Optional[float],
    score_weight: float = 1.0,
) -> List[Confluence]:
    if not fib_levels or not s9_levels:
        return []
    out: list[Confluence] = []
    for fib_ratio, fib_p in fib_levels:
        # nearest s9
        deg, s9_p = min(s9_levels, key=lambda x: abs(x[1] - fib_p))
        dist = abs(float(s9_p) - float(fib_p))
        if dist > tolerance:
            continue
        atr_norm = (dist / atr) if atr and atr > 0 else dist / max(1.0, abs(fib_p) * 0.001)
        degree_weight = 1.0 if abs(deg) in (45.0, 90.0, 180.0, 360.0) else 0.8
        fib_weight = 1.0 if fib_ratio in (0.5, 0.618, 0.786, 1.0, 1.618) else 0.9
        score = 100.0 * clamp((degree_weight * fib_weight) / (1.0 + atr_norm), 0.0, 1.0)
        score = clamp(score * float(score_weight or 1.0), 0.0, 100.0)
        out.append(
            Confluence(
                fib_ratio=float(fib_ratio),
                fib_price=float(fib_p),
                s9_degree=float(deg),
                s9_price=float(s9_p),
                distance=float(dist),
                strength=float(round(score, 2)),
            )
        )
    out.sort(key=lambda c: (-c.strength, c.distance))
    return out
