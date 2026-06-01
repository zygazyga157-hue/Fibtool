from __future__ import annotations

import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

# Allow running as a script: `python plots_v2/fib_retracement_plot.py ...`
sys.path.insert(0, str(Path(__file__).parent.parent))

from plots_v2.anchor_engine import select_anchors
from plots_v2.cli import build_parser, parse_cfg, run_loop, RunConfig
from plots_v2.common import clamp, load_bars, parse_iso_dt
from plots_v2.object_lifecycle import update_lifecycle
from plots_v2.object_specs import (
    MT5ObjectSpec,
    ObjectContext,
    ObjectLevel,
    append_specs,
)
from plots_v2.mt5_script_generator import write_scripts
from plots_v2.telemetry import update_chart_metrics
from plots_v2.multitf import pick_available_parent_tf, compute_alignment_score
from plots_v2.descriptions import build_description_metadata, swing_trade_bias


DEFAULT_RATIOS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618]


def _level_text(r: float) -> str:
    try:
        return f"{r*100:.1f}%"
    except Exception:
        return str(r)


def _strength(sel) -> float:
    try:
        a = sel.a
        b = sel.b
        atr = sel.atr or 0.0
        swing = abs(float(b.price) - float(a.price))
        swing_score = min(1.0, (swing / atr) / 5.0) if atr and atr > 0 else 0.5
        pivot_quality = 1.0 if a.kind != b.kind else 0.85
        last_dt = max(parse_iso_dt(a.time_utc) or datetime.min.replace(tzinfo=timezone.utc), parse_iso_dt(b.time_utc) or datetime.min.replace(tzinfo=timezone.utc))
        hours = max(0.0, (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600.0)
        recency = pow(0.5, hours / 48.0)  # half-life 48h
        s = 0.35 * swing_score + 0.25 * pivot_quality + 0.40 * recency
        return float(clamp(s, 0.0, 1.0))
    except Exception:
        return 0.5


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
                print(f"[V2][FIBO] No anchors for {sym} {tf}")
                continue

            # Visual styling: highlight key fibs, keep others subtle.
            levels = []
            for r in DEFAULT_RATIOS:
                key = abs(r - 0.5) < 1e-9 or abs(r - 0.618) < 1e-9 or abs(r - 0.786) < 1e-9 or abs(r - 1.0) < 1e-9
                if abs(r - 0.618) < 1e-9:
                    color = "clrDeepSkyBlue"
                elif abs(r - 0.5) < 1e-9:
                    color = "clrGold"
                elif abs(r - 0.786) < 1e-9:
                    color = "clrDodgerBlue"
                elif abs(r - 1.618) < 1e-9:
                    color = "clrOrange"
                else:
                    color = "clrSilver"
                levels.append(
                    ObjectLevel(
                        value=float(r),
                        text=_level_text(r),
                        color=color,
                        style="STYLE_SOLID" if key else "STYLE_DOT",
                        width=2 if key else 1,
                    )
                )
            engine_md = {
                "anchor_version": "2.1",
                "lifecycle_version": "2.1",
                "fibo_version": "2.0",
            }
            parent_tf = pick_available_parent_tf(outdir, sym, cfg.timeframes, tf, asof_utc=cfg.replay_utc)
            alignment = 0.0
            if parent_tf:
                parent_sel = select_anchors(
                    outdir,
                    sym,
                    parent_tf,
                    pivot_left=cfg.pivot_left,
                    pivot_right=cfg.pivot_right,
                    asof_utc=cfg.replay_utc,
                )
                if parent_sel:
                    alignment = compute_alignment_score(sel, parent_sel)
            spec = MT5ObjectSpec(
                object_id="",
                symbol=sym,
                timeframe=tf,
                object_type="OBJ_FIBO",
                engine_metadata=engine_md,
                priority="HIGH",
                parent_object_id=None,
                related_object_ids=[],
                source_tf=tf,
                parent_tf=parent_tf,
                alignment_score=float(alignment),
                anchor_1=sel.a,
                anchor_2=sel.b,
                levels=levels,
                strength=_strength(sel),
                context=ObjectContext(label="fib_retracement", sources=[f"anchor:{sel.kind}"]),
                metadata={
                    **build_description_metadata(
                        "fib_retracement",
                        score=_strength(sel),
                        trade_bias=swing_trade_bias(sel.a.price, sel.b.price),
                        anchor_source=sel.kind,
                        components=["pivot_pair", "fib_ratios", "atr", "timeframe_alignment"],
                    ),
                    "ratios": DEFAULT_RATIOS,
                    "atr": sel.atr,
                    "point": sel.point,
                    "anchor_confidence": float(sel.confidence or 0.0),
                    "anchor_components": sel.confidence_components or {},
                    "parent_tf_alignment": float(alignment),
                },
            )
            spec.object_id = MT5ObjectSpec.compute_object_id(
                symbol=spec.symbol,
                timeframe=spec.timeframe,
                object_type=spec.object_type,
                anchors=[sel.a, sel.b],
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
            update_chart_metrics(outdir, specs_created=[spec], lifecycle_state=lifecycle, run_label="fib_retracement_v2")

            if cfg.emit_spec_only:
                print(f"[V2][FIBO] Spec only: {sym} {tf} id={spec.object_id}")
                continue

            apply_path, cleanup_path = write_scripts(
                sym,
                tf,
                [spec],
                tool_label="FibRetracement",
                mt5_data_folder=cfg.mt5_data_folder,
                max_objects=cfg.max_objects,
            )
            print(f"[V2][FIBO] Wrote {apply_path.name} + {cleanup_path.name} for {sym} {tf}")


def main() -> None:
    p = build_parser(description="Plots V2 Tool 1  Native Fibonacci Retracement (OBJ_FIBO)")
    p.add_argument("--fib-ratios", default=None, help="Comma-separated fib ratios (e.g. 0,0.236,0.382,0.5,0.618,0.786,1,1.272,1.618)")
    args = p.parse_args()
    cfg = parse_cfg(args)
    def parse_fib_ratios(val):
        if not val:
            return list(DEFAULT_RATIOS)
        out = []
        for part in str(val).split(","):
            part = part.strip()
            if not part:
                continue
            try:
                out.append(float(part))
            except Exception:
                continue
        return out or list(DEFAULT_RATIOS)
    def run_once_with_ratios(cfg):
        outdir = cfg.outputs_dir
        fib_ratios = parse_fib_ratios(getattr(cfg, "fib_ratios", None))
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
                    print(f"[V2][FIBO] No anchors for {sym} {tf}")
                    continue
                levels = []
                for r in fib_ratios:
                    key = abs(r - 0.5) < 1e-9 or abs(r - 0.618) < 1e-9 or abs(r - 0.786) < 1e-9 or abs(r - 1.0) < 1e-9
                    if abs(r - 0.618) < 1e-9:
                        color = "clrDeepSkyBlue"
                    elif abs(r - 0.5) < 1e-9:
                        color = "clrGold"
                    elif abs(r - 0.786) < 1e-9:
                        color = "clrDodgerBlue"
                    elif abs(r - 1.618) < 1e-9:
                        color = "clrOrange"
                    else:
                        color = "clrSilver"
                    levels.append(
                        ObjectLevel(
                            value=float(r),
                            text=_level_text(r),
                            color=color,
                            style="STYLE_SOLID" if key else "STYLE_DOT",
                            width=2 if key else 1,
                        )
                    )
                engine_md = {
                    "anchor_version": "2.1",
                    "lifecycle_version": "2.1",
                    "fibo_version": "2.0",
                }
                parent_tf = pick_available_parent_tf(outdir, sym, cfg.timeframes, tf, asof_utc=cfg.replay_utc)
                alignment = 0.0
                if parent_tf:
                    parent_sel = select_anchors(
                        outdir,
                        sym,
                        parent_tf,
                        pivot_left=cfg.pivot_left,
                        pivot_right=cfg.pivot_right,
                        asof_utc=cfg.replay_utc,
                    )
                    if parent_sel:
                        alignment = compute_alignment_score(sel, parent_sel)
                spec = MT5ObjectSpec(
                    object_id="",
                    symbol=sym,
                    timeframe=tf,
                    object_type="OBJ_FIBO",
                    engine_metadata=engine_md,
                    priority="HIGH",
                    parent_object_id=None,
                    related_object_ids=[],
                    source_tf=tf,
                    parent_tf=parent_tf,
                    alignment_score=float(alignment),
                    anchor_1=sel.a,
                    anchor_2=sel.b,
                    levels=levels,
                    strength=_strength(sel),
                    context=ObjectContext(label="fib_retracement", sources=[f"anchor:{sel.kind}"]),
                    metadata={
                        **build_description_metadata(
                            "fib_retracement",
                            score=_strength(sel),
                            trade_bias=swing_trade_bias(sel.a.price, sel.b.price),
                            anchor_source=sel.kind,
                            components=["pivot_pair", "fib_ratios", "atr", "timeframe_alignment"],
                        ),
                        "ratios": fib_ratios,
                        "atr": sel.atr,
                        "point": sel.point,
                        "anchor_confidence": float(sel.confidence or 0.0),
                        "anchor_components": sel.confidence_components or {},
                        "parent_tf_alignment": float(alignment),
                    },
                )
                spec.object_id = MT5ObjectSpec.compute_object_id(
                    symbol=spec.symbol,
                    timeframe=spec.timeframe,
                    object_type=spec.object_type,
                    anchors=[sel.a, sel.b],
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
                update_chart_metrics(outdir, specs_created=[spec], lifecycle_state=lifecycle, run_label="fib_retracement_v2")
                if cfg.emit_spec_only:
                    print(f"[V2][FIBO] Spec only: {sym} {tf} id={spec.object_id}")
                    continue
                apply_path, cleanup_path = write_scripts(
                    sym,
                    tf,
                    [spec],
                    tool_label="FibRetracement",
                    mt5_data_folder=cfg.mt5_data_folder,
                    max_objects=cfg.max_objects,
                )
                print(f"[V2][FIBO] Wrote {apply_path.name} + {cleanup_path.name} for {sym} {tf}")
    run_loop(run_once_with_ratios, cfg)


if __name__ == "__main__":
    main()
