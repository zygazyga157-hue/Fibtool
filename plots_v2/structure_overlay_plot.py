from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from plots_v2.cli import build_parser, parse_cfg, run_loop, RunConfig
from plots_v2.common import load_bars
from plots_v2.object_lifecycle import update_lifecycle
from plots_v2.object_specs import append_specs
from plots_v2.structure_overlay import build_structure_overlay_specs
from plots_v2.mt5_script_generator import write_scripts
from plots_v2.telemetry import update_chart_metrics


def run_once(cfg: RunConfig) -> None:
    outdir = cfg.outputs_dir
    for sym in cfg.symbols:
        for tf in cfg.timeframes:
            specs = build_structure_overlay_specs(outdir, sym, tf, asof_utc=cfg.replay_utc)
            if not specs:
                print(f"[V2][STRUCT] No asia sweep overlay data for {sym} {tf}")
                continue
            append_specs(outdir, specs)
            bars = load_bars(outdir, sym, tf)
            if bars.empty:
                bars = load_bars(outdir, sym, None)
            lifecycle = update_lifecycle(outdir, bars, specs, ttl_hours=cfg.ttl_hours)
            update_chart_metrics(outdir, specs_created=specs, lifecycle_state=lifecycle, run_label="structure_overlay_v2")

            if cfg.emit_spec_only:
                print(f"[V2][STRUCT] Spec only: {sym} {tf} count={len(specs)}")
                continue
            apply_path, cleanup_path = write_scripts(
                sym,
                tf,
                specs,
                tool_label="StructureOverlay",
                mt5_data_folder=cfg.mt5_data_folder,
                max_objects=cfg.max_objects,
            )
            print(f"[V2][STRUCT] Wrote {apply_path.name} + {cleanup_path.name} for {sym} {tf}")


def main() -> None:
    p = build_parser(description="Plots V2 Tool 8 — Structure Overlay (Asia sweep objects)")
    args = p.parse_args()
    cfg = parse_cfg(args)
    run_loop(run_once, cfg)


if __name__ == "__main__":
    main()
