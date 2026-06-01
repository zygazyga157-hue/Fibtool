from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from plots_v2.anchor_engine import select_anchors
from plots_v2.cli import build_parser, parse_cfg, run_loop, RunConfig
from plots_v2.common import load_bars
from plots_v2.object_lifecycle import update_lifecycle
from plots_v2.object_specs import MT5ObjectSpec, ObjectContext, ObjectLevel, append_specs
from plots_v2.mt5_script_generator import write_scripts
from plots_v2.telemetry import update_chart_metrics
from plots_v2.descriptions import build_description_metadata


DEFAULT_TIME_LEVELS = [1, 2, 3, 5, 8, 13, 21]


def run_once(cfg: RunConfig) -> None:
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
                print(f"[V2][FTIME] No anchors for {sym} {tf}")
                continue
            levels = [ObjectLevel(value=float(x), text=str(x)) for x in DEFAULT_TIME_LEVELS]
            spec = MT5ObjectSpec(
                object_id="",
                symbol=sym,
                timeframe=tf,
                object_type="OBJ_FIBOTIMES",
                engine_metadata={"anchor_version": "2.1", "fib_time_version": "2.0"},
                priority="LOW",
                source_tf=tf,
                anchor_1=sel.a,
                anchor_2=sel.b,
                levels=levels,
                strength=0.55,
                context=ObjectContext(label="fib_time", sources=[f"anchor:{sel.kind}"]),
                metadata={
                    **build_description_metadata(
                        "fib_time",
                        score=0.55,
                        anchor_source=sel.kind,
                        components=["swing_time", "fib_time_ratios"],
                    ),
                    "time_levels": DEFAULT_TIME_LEVELS,
                    "atr": sel.atr,
                    "point": sel.point,
                },
            )
            spec.object_id = MT5ObjectSpec.compute_object_id(
                symbol=spec.symbol,
                timeframe=spec.timeframe,
                object_type=spec.object_type,
                anchors=[spec.anchor_1, spec.anchor_2],
                levels=levels,
                engine_version=spec.engine_version,
                engine_metadata=spec.engine_metadata,
                priority=spec.priority,
                parent_object_id=spec.parent_object_id,
                related_object_ids=spec.related_object_ids,
                source_tf=spec.source_tf,
                parent_tf=spec.parent_tf,
            )

            append_specs(outdir, [spec])

            bars = load_bars(outdir, sym, tf, asof_utc=cfg.replay_utc)
            if bars.empty:
                bars = load_bars(outdir, sym, None, asof_utc=cfg.replay_utc)
            lifecycle = update_lifecycle(outdir, bars, [spec], ttl_hours=cfg.ttl_hours)
            update_chart_metrics(outdir, specs_created=[spec], lifecycle_state=lifecycle, run_label="fib_time_v2")

            if cfg.emit_spec_only:
                print(f"[V2][FTIME] Spec only: {sym} {tf} id={spec.object_id}")
                continue

            apply_path, cleanup_path = write_scripts(
                sym,
                tf,
                [spec],
                tool_label="FibTime",
                mt5_data_folder=cfg.mt5_data_folder,
                max_objects=cfg.max_objects,
            )
            print(f"[V2][FTIME] Wrote {apply_path.name} + {cleanup_path.name} for {sym} {tf}")


def main() -> None:
    p = build_parser(description="Plots V2 Tool 5 — Fibonacci Time Zones (OBJ_FIBOTIMES)")
    p.add_argument("--time-levels", default=None, help="Comma-separated time zone levels (e.g. 1,2,3,5,8,13,21)")
    args = p.parse_args()
    cfg = parse_cfg(args)
    def parse_time_levels(val):
        if not val:
            return list(DEFAULT_TIME_LEVELS)
        out = []
        for part in str(val).split(","):
            part = part.strip()
            if not part:
                continue
            try:
                out.append(float(part))
            except Exception:
                continue
        return out or list(DEFAULT_TIME_LEVELS)
    def run_once_with_levels(cfg):
        outdir = cfg.outputs_dir
        time_levels = parse_time_levels(getattr(cfg, "time_levels", None))
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
                    print(f"[V2][FTIME] No anchors for {sym} {tf}")
                    continue
                levels = [ObjectLevel(value=float(x), text=str(x)) for x in time_levels]
                spec = MT5ObjectSpec(
                    object_id="",
                    symbol=sym,
                    timeframe=tf,
                    object_type="OBJ_FIBOTIMES",
                    engine_metadata={"anchor_version": "2.1", "fib_time_version": "2.0"},
                    priority="LOW",
                    source_tf=tf,
                    anchor_1=sel.a,
                    anchor_2=sel.b,
                    levels=levels,
                    strength=0.55,
                    context=ObjectContext(label="fib_time", sources=[f"anchor:{sel.kind}"]),
                    metadata={
                        **build_description_metadata(
                            "fib_time",
                            score=0.55,
                            anchor_source=sel.kind,
                            components=["swing_time", "fib_time_ratios"],
                        ),
                        "time_levels": time_levels,
                        "atr": sel.atr,
                        "point": sel.point,
                    },
                )
                spec.object_id = MT5ObjectSpec.compute_object_id(
                    symbol=spec.symbol,
                    timeframe=spec.timeframe,
                    object_type=spec.object_type,
                    anchors=[spec.anchor_1, spec.anchor_2],
                    levels=levels,
                    engine_version=spec.engine_version,
                    engine_metadata=spec.engine_metadata,
                    priority=spec.priority,
                    parent_object_id=spec.parent_object_id,
                    related_object_ids=spec.related_object_ids,
                    source_tf=spec.source_tf,
                    parent_tf=spec.parent_tf,
                )
                append_specs(outdir, [spec])
                bars = load_bars(outdir, sym, tf, asof_utc=cfg.replay_utc)
                if bars.empty:
                    bars = load_bars(outdir, sym, None, asof_utc=cfg.replay_utc)
                lifecycle = update_lifecycle(outdir, bars, [spec], ttl_hours=cfg.ttl_hours)
                update_chart_metrics(outdir, specs_created=[spec], lifecycle_state=lifecycle, run_label="fib_time_v2")
                if cfg.emit_spec_only:
                    print(f"[V2][FTIME] Spec only: {sym} {tf} id={spec.object_id}")
                    continue
                apply_path, cleanup_path = write_scripts(
                    sym,
                    tf,
                    [spec],
                    tool_label="FibTime",
                    mt5_data_folder=cfg.mt5_data_folder,
                    max_objects=cfg.max_objects,
                )
                print(f"[V2][FTIME] Wrote {apply_path.name} + {cleanup_path.name} for {sym} {tf}")
    run_loop(run_once_with_levels, cfg)


if __name__ == "__main__":
    main()
