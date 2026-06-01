from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .common import ensure_outputs_dir, utc_now_iso
from .object_specs import MT5ObjectSpec


METRICS_PATH = "chart_metrics.json"


def _load(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save(path: Path, obj: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        pass


def update_chart_metrics(
    outputs_dir: Path,
    *,
    specs_created: List[MT5ObjectSpec],
    lifecycle_state: Optional[dict] = None,
    run_label: str = "plots_v2",
) -> dict:
    """Update `outputs/chart_metrics.json` with basic ecosystem telemetry.

    This file is intended for operator monitoring/debugging, not for trading decisions.
    """
    ensure_outputs_dir(outputs_dir)
    path = outputs_dir / METRICS_PATH
    cur = _load(path)

    by_state: dict[str, int] = {}
    if lifecycle_state:
        for _, rec in lifecycle_state.items():
            st = str(rec.get("state") or "UNKNOWN")
            by_state[st] = by_state.get(st, 0) + 1

    avg_strength = 0.0
    try:
        if specs_created:
            avg_strength = sum(float(s.strength or 0.0) for s in specs_created) / float(len(specs_created))
    except Exception:
        avg_strength = 0.0

    snap = {
        "timestamp_utc": utc_now_iso(),
        "run_label": run_label,
        "objects_created": int(len(specs_created)),
        "avg_strength": float(round(avg_strength, 4)),
        "states": by_state,
    }

    # Keep a compact history trail (last 100).
    history = list(cur.get("history") or [])
    history.append(snap)
    if len(history) > 100:
        history = history[-100:]

    cur["last"] = snap
    cur["history"] = history
    _save(path, cur)
    return cur

