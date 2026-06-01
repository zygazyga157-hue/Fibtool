from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from plots_v2.anchor_engine import select_anchors
from plots_v2.cli import build_parser, parse_cfg, run_loop, RunConfig
from plots_v2.common import calc_atr, infer_point, load_bars
from plots_v2.object_lifecycle import update_lifecycle
from plots_v2.object_specs import AnchorPoint, MT5ObjectSpec, ObjectContext, append_specs
from plots_v2.mt5_script_generator import write_scripts
from plots_v2.telemetry import update_chart_metrics
from plots_v2.descriptions import build_description_metadata


def _next_bar_time(df: pd.DataFrame) -> str:
    if df.empty or "time" not in df.columns:
        return datetime.now(timezone.utc).isoformat()
    t_last = pd.to_datetime(df["time"].iloc[-1], utc=True, errors="coerce")
    if pd.isna(t_last):
        return datetime.now(timezone.utc).isoformat()
    if len(df) >= 2:
        t_prev = pd.to_datetime(df["time"].iloc[-2], utc=True, errors="coerce")
        if pd.notna(t_prev):
            step = t_last - t_prev
            if step.total_seconds() > 0:
                return (t_last + step).to_pydatetime().isoformat()
    return (t_last + pd.Timedelta(hours=1)).to_pydatetime().isoformat()


def _compute_scale(df: pd.DataFrame, *, unit_mode: str) -> float:
    if unit_mode == "point":
        pt = infer_point(df)
        return float(pt) * 100.0
    atr = calc_atr(df, period=14)
    if atr is None or atr <= 0:
        pt = infer_point(df)
        return float(pt) * 100.0
    return float(atr) * 0.25


def run_once(cfg: RunConfig, *, unit_mode: str) -> None:
    outdir = cfg.outputs_dir
    for sym in cfg.symbols:
        for tf in cfg.timeframes:
            sel = select_anchors(
                outdir,
                sym,
                tf,
                pivot_left=cfg.pivot_left,
                pivot_right=cfg.pivot_right,
                asof_utc=cfg.replay_utc,
            )
            if not sel:
                print(f"[V2][GRID] No anchors for {sym} {tf}")
                continue
            bars = load_bars(outdir, sym, tf, asof_utc=cfg.replay_utc)
            if bars.empty:
                bars = load_bars(outdir, sym, None, asof_utc=cfg.replay_utc)
            if bars.empty:
                print(f"[V2][GRID] No bars for {sym} {tf}")
                continue

            pivot = sel.b
            t2 = _next_bar_time(bars)
            a2 = AnchorPoint(time_utc=t2, price=float(pivot.price), kind="next_bar")

            direction_desc = pivot.kind == "pivot_high"
            scale = _compute_scale(bars, unit_mode=unit_mode)

            spec = MT5ObjectSpec(
                object_id="",
                symbol=sym,
                timeframe=tf,
                object_type="OBJ_GANNGRID",
                engine_metadata={"anchor_version": "2.1", "gann_version": "2.0"},
                priority="MEDIUM",
                source_tf=tf,
                anchor_1=pivot,
                anchor_2=a2,
                strength=0.6,
                context=ObjectContext(label="gann_grid", sources=[f"anchor:{sel.kind}"]),
                metadata={
                    **build_description_metadata(
                        "gann_grid",
                        score=0.6,
                        anchor_source=sel.kind,
                        components=["pivot", "price_time_grid", unit_mode],
                    ),
                    "scale": scale,
                    "direction_descending": direction_desc,
                    "color": "clrSilver",
                    "unit_mode": unit_mode,
                },
            )
            spec.object_id = MT5ObjectSpec.compute_object_id(
                symbol=spec.symbol,
                timeframe=spec.timeframe,
                object_type=spec.object_type,
                anchors=[spec.anchor_1, spec.anchor_2],
                levels=[],
                engine_version=spec.engine_version,
                engine_metadata=spec.engine_metadata,
                priority=spec.priority,
                parent_object_id=spec.parent_object_id,
                related_object_ids=spec.related_object_ids,
                source_tf=spec.source_tf,
                parent_tf=spec.parent_tf,
            )

            append_specs(outdir, [spec])
            lifecycle = update_lifecycle(outdir, bars, [spec], ttl_hours=cfg.ttl_hours)
            update_chart_metrics(outdir, specs_created=[spec], lifecycle_state=lifecycle, run_label="gann_grid_v2")

            if cfg.emit_spec_only:
                print(f"[V2][GRID] Spec only: {sym} {tf} id={spec.object_id}")
                continue
            apply_path, cleanup_path = write_scripts(
                sym,
                tf,
                [spec],
                tool_label="GannGrid",
                mt5_data_folder=cfg.mt5_data_folder,
                max_objects=cfg.max_objects,
            )
            print(f"[V2][GRID] Wrote {apply_path.name} + {cleanup_path.name} for {sym} {tf}")


def main() -> None:
    p = build_parser(description="Plots V2 Tool 4 — Gann Grid (OBJ_GANNGRID)")
    p.add_argument("--unit-mode", choices=("atr", "point"), default="atr", help="Gann scale unit mode")
    args = p.parse_args()
    cfg = parse_cfg(args)
    run_loop(lambda c: run_once(c, unit_mode=str(args.unit_mode)), cfg)


if __name__ == "__main__":
    main()
