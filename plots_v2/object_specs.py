from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import ENGINE_VERSION
from .common import dumps_compact, ensure_outputs_dir, json_serialize, parse_iso_dt, utc_now_iso


PRIORITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")


@dataclass(frozen=True)
class AnchorPoint:
    time_utc: str
    price: float
    kind: str = ""  # e.g. pivot_low / pivot_high / derived


@dataclass(frozen=True)
class ObjectLevel:
    value: float
    text: str = ""
    color: str = ""  # MQL color constant name (e.g., clrDodgerBlue) or empty = default
    style: str = ""  # MQL ENUM_LINE_STYLE (e.g., STYLE_SOLID)
    width: int = 1


@dataclass(frozen=True)
class ObjectContext:
    label: str = ""
    sources: List[str] = field(default_factory=list)  # e.g. ["anchor:auto_pivots","asia_sweep"]


@dataclass
class MT5ObjectSpec:
    object_id: str
    symbol: str
    timeframe: str
    object_type: str  # e.g. OBJ_FIBO / OBJ_GANNFAN
    engine_version: str = ENGINE_VERSION
    created_ts_utc: str = field(default_factory=utc_now_iso)

    # Multi-engine version traceability (additive; safe default = {})
    engine_metadata: Dict[str, Any] = field(default_factory=dict)
    # Priority controls chart load + rendering selection (CRITICAL/HIGH/MEDIUM/LOW)
    priority: str = "MEDIUM"
    # Relationships enable parent deletion / grouped cleanup (spec-level)
    parent_object_id: Optional[str] = None
    related_object_ids: List[str] = field(default_factory=list)
    # Multi-timeframe intelligence fields (optional)
    source_tf: Optional[str] = None
    parent_tf: Optional[str] = None
    alignment_score: float = 0.0

    anchor_1: Optional[AnchorPoint] = None
    anchor_2: Optional[AnchorPoint] = None
    anchor_3: Optional[AnchorPoint] = None

    levels: List[ObjectLevel] = field(default_factory=list)
    strength: float = 0.0
    context: ObjectContext = field(default_factory=ObjectContext)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def compute_object_id(
        *,
        symbol: str,
        timeframe: str,
        object_type: str,
        anchors: List[AnchorPoint],
        levels: List[ObjectLevel],
        engine_version: str = ENGINE_VERSION,
        engine_metadata: Optional[Dict[str, Any]] = None,
        priority: str = "MEDIUM",
        parent_object_id: Optional[str] = None,
        related_object_ids: Optional[List[str]] = None,
        source_tf: Optional[str] = None,
        parent_tf: Optional[str] = None,
    ) -> str:
        payload = dumps_compact(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "object_type": object_type,
                "engine_version": engine_version,
                "engine_metadata": engine_metadata or {},
                "priority": priority,
                "parent_object_id": parent_object_id,
                "related_object_ids": related_object_ids or [],
                "source_tf": source_tf,
                "parent_tf": parent_tf,
                "anchors": [asdict(a) for a in anchors],
                "levels": [asdict(l) for l in levels],
            }
        )
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "MT5ObjectSpec":
        def _ap(v: Any) -> Optional[AnchorPoint]:
            if not v:
                return None
            try:
                return AnchorPoint(time_utc=str(v.get("time_utc")), price=float(v.get("price")), kind=str(v.get("kind", "")))
            except Exception:
                return None

        def _lv(v: Any) -> ObjectLevel:
            return ObjectLevel(
                value=float(v.get("value")),
                text=str(v.get("text", "")),
                color=str(v.get("color", "")),
                style=str(v.get("style", "")),
                width=int(v.get("width", 1) or 1),
            )

        ctxd = d.get("context") or {}
        ctx = ObjectContext(label=str(ctxd.get("label", "")), sources=list(ctxd.get("sources") or []))
        out = MT5ObjectSpec(
            object_id=str(d.get("object_id", "")),
            symbol=str(d.get("symbol", "")),
            timeframe=str(d.get("timeframe", "")),
            object_type=str(d.get("object_type", "")),
            engine_version=str(d.get("engine_version", ENGINE_VERSION)),
            created_ts_utc=str(d.get("created_ts_utc", "")) or utc_now_iso(),
            engine_metadata=dict(d.get("engine_metadata") or {}),
            priority=str(d.get("priority", "MEDIUM") or "MEDIUM"),
            parent_object_id=(str(d.get("parent_object_id")) if d.get("parent_object_id") else None),
            related_object_ids=list(d.get("related_object_ids") or []),
            source_tf=(str(d.get("source_tf")) if d.get("source_tf") else None),
            parent_tf=(str(d.get("parent_tf")) if d.get("parent_tf") else None),
            alignment_score=float(d.get("alignment_score", 0.0) or 0.0),
            anchor_1=_ap(d.get("anchor_1")),
            anchor_2=_ap(d.get("anchor_2")),
            anchor_3=_ap(d.get("anchor_3")),
            levels=[_lv(x) for x in (d.get("levels") or [])],
            strength=float(d.get("strength", 0.0) or 0.0),
            context=ctx,
            metadata=dict(d.get("metadata") or {}),
        )
        # Normalize priority to known set
        if out.priority not in PRIORITIES:
            out.priority = "MEDIUM"
        # Default source_tf to timeframe if missing
        if not out.source_tf:
            out.source_tf = out.timeframe
        if not out.object_id:
            anchors = [a for a in (out.anchor_1, out.anchor_2, out.anchor_3) if a]
            out.object_id = MT5ObjectSpec.compute_object_id(
                symbol=out.symbol,
                timeframe=out.timeframe,
                object_type=out.object_type,
                anchors=anchors,
                levels=out.levels,
                engine_version=out.engine_version,
                engine_metadata=out.engine_metadata,
                priority=out.priority,
                parent_object_id=out.parent_object_id,
                related_object_ids=out.related_object_ids,
                source_tf=out.source_tf,
                parent_tf=out.parent_tf,
            )
        return out


JSONL_NAME = "mt5_objects_v2.jsonl"
CSV_NAME = "mt5_objects_v2.csv"


def append_specs(outputs_dir: Path, specs: List[MT5ObjectSpec]) -> None:
    ensure_outputs_dir(outputs_dir)
    jsonl_path = outputs_dir / JSONL_NAME
    csv_path = outputs_dir / CSV_NAME

    # Append JSONL
    with open(jsonl_path, "a", encoding="utf-8") as f:
        for s in specs:
            f.write(json.dumps(s.to_dict(), default=json_serialize, ensure_ascii=False) + "\n")

    # Append CSV (flattened)
    fieldnames = [
        "object_id",
        "symbol",
        "timeframe",
        "object_type",
        "engine_version",
        "engine_metadata_json",
        "priority",
        "parent_object_id",
        "related_object_ids_json",
        "source_tf",
        "parent_tf",
        "alignment_score",
        "created_ts_utc",
        "anchor_1_time",
        "anchor_1_price",
        "anchor_2_time",
        "anchor_2_price",
        "anchor_3_time",
        "anchor_3_price",
        "levels_json",
        "strength",
        "context",
        "metadata_json",
    ]
    def _ensure_header(path: Path, desired_fields: list[str]) -> None:
        if not path.exists():
            return
        try:
            with open(path, "r", newline="", encoding="utf-8") as rf:
                r = csv.reader(rf)
                try:
                    existing_header = next(r)
                except StopIteration:
                    existing_header = []
            if existing_header == desired_fields:
                return
            # rewrite preserving old data
            with open(path, "r", newline="", encoding="utf-8") as rf:
                old_reader = csv.DictReader(rf, fieldnames=existing_header)
                rows = list(old_reader)
            # drop header row if it was included as data
            if rows and existing_header and all(k == v for k, v in zip(existing_header, rows[0].values())):
                rows = rows[1:]
            with open(path, "w", newline="", encoding="utf-8") as wf:
                w = csv.DictWriter(wf, fieldnames=desired_fields)
                w.writeheader()
                for row in rows:
                    new_row = {k: row.get(k, "") for k in desired_fields}
                    w.writerow(new_row)
        except Exception:
            return

    _ensure_header(csv_path, fieldnames)
    file_exists = csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            w.writeheader()
        for s in specs:
            w.writerow(
                {
                    "object_id": s.object_id,
                    "symbol": s.symbol,
                    "timeframe": s.timeframe,
                    "object_type": s.object_type,
                    "engine_version": s.engine_version,
                    "engine_metadata_json": dumps_compact(s.engine_metadata),
                    "priority": s.priority,
                    "parent_object_id": s.parent_object_id or "",
                    "related_object_ids_json": dumps_compact(list(s.related_object_ids or [])),
                    "source_tf": s.source_tf or "",
                    "parent_tf": s.parent_tf or "",
                    "alignment_score": s.alignment_score,
                    "created_ts_utc": s.created_ts_utc,
                    "anchor_1_time": (s.anchor_1.time_utc if s.anchor_1 else ""),
                    "anchor_1_price": (s.anchor_1.price if s.anchor_1 else ""),
                    "anchor_2_time": (s.anchor_2.time_utc if s.anchor_2 else ""),
                    "anchor_2_price": (s.anchor_2.price if s.anchor_2 else ""),
                    "anchor_3_time": (s.anchor_3.time_utc if s.anchor_3 else ""),
                    "anchor_3_price": (s.anchor_3.price if s.anchor_3 else ""),
                    "levels_json": dumps_compact([asdict(l) for l in s.levels]),
                    "strength": s.strength,
                    "context": dumps_compact(asdict(s.context)),
                    "metadata_json": dumps_compact(s.metadata),
                }
            )


def iter_specs(outputs_dir: Path) -> List[MT5ObjectSpec]:
    path = outputs_dir / JSONL_NAME
    if not path.exists():
        return []
    out: List[MT5ObjectSpec] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if isinstance(d, dict):
                try:
                    out.append(MT5ObjectSpec.from_dict(d))
                except Exception:
                    continue
    return out


def latest_batch_for(outputs_dir: Path, symbol: str, timeframe: str) -> List[MT5ObjectSpec]:
    """Return the latest specs for a symbol/timeframe, based on created_ts_utc datetime parsing."""
    all_specs = iter_specs(outputs_dir)
    sym_u = str(symbol).upper()
    tf_u = str(timeframe).upper()
    filtered = [s for s in all_specs if str(s.symbol).upper() == sym_u and str(s.timeframe).upper() == tf_u]
    if not filtered:
        return []
    best_dt: Optional[datetime] = None
    for s in filtered:
        dt = parse_iso_dt(s.created_ts_utc)
        if dt is None:
            continue
        if best_dt is None or dt > best_dt:
            best_dt = dt
    if best_dt is None:
        return []
    return [s for s in filtered if parse_iso_dt(s.created_ts_utc) == best_dt]
