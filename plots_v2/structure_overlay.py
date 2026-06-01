from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from .common import load_jsonl_latest, parse_iso_dt
from .descriptions import build_description_metadata
from .object_specs import AnchorPoint, MT5ObjectSpec, ObjectContext


def build_structure_overlay_specs(
    outputs_dir: Path,
    symbol: str,
    timeframe: str,
    *,
    lookback_hours: int = 24,
    asof_utc: str | None = None,
) -> list[MT5ObjectSpec]:
    """Build overlay specs from `outputs/asia_mss_signals.jsonl` (MVP).

    Produces:
    - Asia range rectangle (OBJ_RECTANGLE)
    - Sweep markers (OBJ_ARROW) when sweep_high/low
    - Status label (OBJ_TEXT)
    """
    sig = load_jsonl_latest(outputs_dir / "asia_mss_signals.jsonl", symbol=symbol, asof_utc=asof_utc)
    if not sig:
        return []

    ts = parse_iso_dt(sig.get("timestamp") or sig.get("timestamp_session") or sig.get("timestamp_local"))
    if ts is None:
        return []
    now = parse_iso_dt(asof_utc) if asof_utc else datetime.now(timezone.utc)
    if lookback_hours is not None:
        if now - ts > timedelta(hours=int(lookback_hours)):
            return []

    asia_high = float(sig.get("asia_high") or 0.0)
    asia_low = float(sig.get("asia_low") or 0.0)
    if asia_high <= 0 or asia_low <= 0:
        return []

    # Use a generous time span for rectangle (past 100 bars, future 200 bars) conceptually:
    # since we do not know MT5 bar period at runtime, approximate with +/- 12 hours.
    t1 = (ts - timedelta(hours=12)).isoformat()
    t2 = (ts + timedelta(hours=12)).isoformat()

    rect = MT5ObjectSpec(
        object_id="",
        symbol=symbol,
        timeframe=timeframe,
        object_type="OBJ_RECTANGLE",
        engine_metadata={"structure_overlay_version": "2.0"},
        priority="LOW",
        source_tf=timeframe,
        anchor_1=AnchorPoint(time_utc=t1, price=asia_high, kind="asia_high"),
        anchor_2=AnchorPoint(time_utc=t2, price=asia_low, kind="asia_low"),
        strength=0.5,
        context=ObjectContext(label="asia_range", sources=["asia_mss_signals"]),
        metadata={
            **build_description_metadata(
                "asia_range",
                score=0.5,
                anchor_source="asia_mss_signals",
                components=["asia_high", "asia_low", "session_range"],
            ),
            "color": "clrLightSteelBlue",
            "back": True,
        },
    )

    specs: list[MT5ObjectSpec] = [rect]

    status_text = f"ASIA range {asia_low:.5g}-{asia_high:.5g}"
    if bool(sig.get("sweep_high")):
        status_text += " | SWEEP HIGH"
    if bool(sig.get("sweep_low")):
        status_text += " | SWEEP LOW"

    label = MT5ObjectSpec(
        object_id="",
        symbol=symbol,
        timeframe=timeframe,
        object_type="OBJ_TEXT",
        engine_metadata={"structure_overlay_version": "2.0"},
        priority="LOW",
        source_tf=timeframe,
        parent_object_id=None,  # will be set after rect id is computed
        anchor_1=AnchorPoint(time_utc=ts.isoformat(), price=asia_high, kind="label"),
        strength=0.6,
        context=ObjectContext(label="asia_status", sources=["asia_mss_signals"]),
        metadata={
            **build_description_metadata(
                "asia_range",
                score=0.6,
                anchor_source="asia_mss_signals",
                components=["asia_high", "asia_low", "session_status"],
            ),
            "text": status_text,
            "color": "clrWhite",
            "font_size": 9,
        },
    )
    specs.append(label)

    if bool(sig.get("sweep_high")):
        specs.append(
            MT5ObjectSpec(
                object_id="",
                symbol=symbol,
                timeframe=timeframe,
                object_type="OBJ_ARROW",
                engine_metadata={"structure_overlay_version": "2.0"},
                priority="LOW",
                source_tf=timeframe,
                parent_object_id=None,
                anchor_1=AnchorPoint(time_utc=ts.isoformat(), price=asia_high, kind="sweep_high"),
                strength=0.7,
                context=ObjectContext(label="sweep_high", sources=["asia_mss_signals"]),
                metadata={
                    **build_description_metadata(
                        "sweep_high",
                        score=0.7,
                        anchor_source="asia_mss_signals",
                        components=["asia_high", "liquidity_sweep"],
                    ),
                    "color": "clrRed",
                    "arrow_code": 234,
                },
            )
        )
    if bool(sig.get("sweep_low")):
        specs.append(
            MT5ObjectSpec(
                object_id="",
                symbol=symbol,
                timeframe=timeframe,
                object_type="OBJ_ARROW",
                engine_metadata={"structure_overlay_version": "2.0"},
                priority="LOW",
                source_tf=timeframe,
                parent_object_id=None,
                anchor_1=AnchorPoint(time_utc=ts.isoformat(), price=asia_low, kind="sweep_low"),
                strength=0.7,
                context=ObjectContext(label="sweep_low", sources=["asia_mss_signals"]),
                metadata={
                    **build_description_metadata(
                        "sweep_low",
                        score=0.7,
                        anchor_source="asia_mss_signals",
                        components=["asia_low", "liquidity_sweep"],
                    ),
                    "color": "clrDodgerBlue",
                    "arrow_code": 233,
                },
            )
        )

    # Fill object_id deterministically now that we have anchors.
    # Compute rect id first, then attach relationships.
    rect.object_id = MT5ObjectSpec.compute_object_id(
        symbol=rect.symbol,
        timeframe=rect.timeframe,
        object_type=rect.object_type,
        anchors=[a for a in (rect.anchor_1, rect.anchor_2) if a],
        levels=rect.levels,
        engine_version=rect.engine_version,
        engine_metadata=rect.engine_metadata,
        priority=rect.priority,
        parent_object_id=rect.parent_object_id,
        related_object_ids=rect.related_object_ids,
        source_tf=rect.source_tf,
        parent_tf=rect.parent_tf,
    )
    # children
    child_ids: list[str] = []
    for s in specs:
        if s is rect:
            continue
        s.parent_object_id = rect.object_id
        anchors = [a for a in (s.anchor_1, s.anchor_2, s.anchor_3) if a]
        s.object_id = MT5ObjectSpec.compute_object_id(
            symbol=s.symbol,
            timeframe=s.timeframe,
            object_type=s.object_type,
            anchors=anchors,
            levels=s.levels,
            engine_version=s.engine_version,
            engine_metadata=s.engine_metadata,
            priority=s.priority,
            parent_object_id=s.parent_object_id,
            related_object_ids=s.related_object_ids,
            source_tf=s.source_tf,
            parent_tf=s.parent_tf,
        )
        child_ids.append(s.object_id)
    rect.related_object_ids = child_ids
    return specs
