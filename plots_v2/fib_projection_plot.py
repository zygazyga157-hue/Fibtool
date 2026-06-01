from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from plots_v2.anchor_engine import select_abc
from plots_v2.cli import build_parser, parse_cfg, run_loop, RunConfig
from plots_v2.common import clamp, load_bars, parse_iso_dt
from plots_v2.object_lifecycle import update_lifecycle
from plots_v2.object_specs import AnchorPoint, MT5ObjectSpec, ObjectContext, ObjectLevel, append_specs
from plots_v2.mt5_script_generator import write_scripts
from plots_v2.telemetry import update_chart_metrics
from plots_v2.multitf import pick_available_parent_tf, compute_alignment_score
from plots_v2.scoring import confidence_label, instrument_weight
from plots_v2.descriptions import build_description_metadata, swing_trade_bias


DEFAULT_LEVELS = [1.272, 1.618, 2.618, 4.236]


def _strength(sel) -> float:
    try:
        a = sel.a
        b = sel.b
        atr = sel.atr or 0.0
        swing = abs(float(b.price) - float(a.price))
        swing_score = min(1.0, (swing / atr) / 6.0) if atr and atr > 0 else 0.4
        last_dt = max(parse_iso_dt(a.time_utc) or datetime.min.replace(tzinfo=timezone.utc), parse_iso_dt(b.time_utc) or datetime.min.replace(tzinfo=timezone.utc))
        hours = max(0.0, (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600.0)
        recency = pow(0.5, hours / 72.0)
        return float(clamp(0.55 * swing_score + 0.45 * recency, 0.0, 1.0))
    except Exception:
        return 0.4


def _projection_confidence(sel, c, *, alignment: float, weight: float) -> tuple[float, dict]:
    try:
        a_price = float(sel.a.price)
        b_price = float(sel.b.price)
        c_price = float(c.price)
        ab = abs(b_price - a_price)
        bc = abs(c_price - b_price)
        atr = float(sel.atr or 0.0)
        anchor_score = float(sel.confidence or _strength(sel))
        structure_score = 0.5
        if ab > 0:
            retrace = bc / ab
            structure_score = clamp(1.0 - min(1.0, abs(retrace - 0.618) / 0.618), 0.0, 1.0)
        volatility_score = clamp((ab / atr) / 6.0, 0.0, 1.0) if atr > 0 else 0.5
        timeframe_alignment = clamp(float(alignment or 0.0), 0.0, 1.0)
        base = (
            0.35 * anchor_score
            + 0.25 * structure_score
            + 0.20 * volatility_score
            + 0.20 * timeframe_alignment
        )
        adjusted = clamp(base * float(weight or 1.0), 0.0, 1.0)
        return adjusted, {
            "anchor_score": anchor_score,
            "structure_score": structure_score,
            "volatility_score": volatility_score,
            "timeframe_alignment": timeframe_alignment,
            "instrument_weight": float(weight or 1.0),
            "base_score": base,
            "adjusted_score": adjusted,
            "confidence": confidence_label(adjusted * 100.0),
        }
    except Exception:
        adjusted = clamp(0.4 * float(weight or 1.0), 0.0, 1.0)
        return adjusted, {"instrument_weight": float(weight or 1.0), "adjusted_score": adjusted, "confidence": confidence_label(adjusted * 100.0)}


def _future_label_time(bars, fallback_iso: str, projection_forward: int) -> str:
    fallback_dt = parse_iso_dt(fallback_iso) or datetime.now(timezone.utc)
    try:
        if bars.empty or "time" not in bars.columns or len(bars) < 2:
            return (fallback_dt + timedelta(hours=max(1, int(projection_forward)))).isoformat()
        deltas = bars["time"].diff().dropna().dt.total_seconds()
        seconds = float(deltas.median()) if not deltas.empty else 3600.0
        if seconds <= 0:
            seconds = 3600.0
        last_dt = bars["time"].iloc[-1].to_pydatetime().replace(tzinfo=timezone.utc)
        return (last_dt + timedelta(seconds=seconds * max(1, int(projection_forward)))).isoformat()
    except Exception:
        return (fallback_dt + timedelta(hours=max(1, int(projection_forward)))).isoformat()


def _parse_levels(value: str | None, default: list[float]) -> list[float]:
    if not value:
        return list(default)
    out: list[float] = []
    for part in str(value).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(float(part))
        except Exception:
            continue
    return out or list(default)


def run_once(cfg: RunConfig, *, predict_d: bool, d_levels: list[float], projection_forward: int) -> None:
    outdir = cfg.outputs_dir
    for sym in cfg.symbols:
        for tf in cfg.timeframes:
            res = select_abc(
                outdir,
                sym,
                tf,
                pivot_left=cfg.pivot_left,
                pivot_right=cfg.pivot_right,
                asof_utc=cfg.replay_utc,
            )
            if not res:
                print(f"[V2][EXP] No ABC anchors for {sym} {tf} (need 3 alternating pivots)")
                continue
            sel, c = res
            # Visual styling: highlight 1.618 and keep others thinner/dotted.
            try:
                ab = float(sel.b.price) - float(sel.a.price)
            except Exception:
                ab = 0.0
            base_color = "clrDeepSkyBlue" if ab >= 0 else "clrOrangeRed"
            levels = []
            for r in d_levels:
                is_key = abs(float(r) - 1.618) < 1e-9
                levels.append(
                    ObjectLevel(
                        value=float(r),
                        text=f"{r*100:.1f}%",
                        color=base_color,
                        style="STYLE_SOLID" if is_key else "STYLE_DOT",
                        width=2 if is_key else 1,
                    )
                )
            engine_md = {
                "anchor_version": "2.1",
                "lifecycle_version": "2.1",
                "expansion_version": "2.0",
            }
            parent_tf = pick_available_parent_tf(outdir, sym, cfg.timeframes, tf, asof_utc=cfg.replay_utc)
            alignment = 0.0
            if parent_tf:
                parent_sel = select_abc(
                    outdir,
                    sym,
                    parent_tf,
                    pivot_left=cfg.pivot_left,
                    pivot_right=cfg.pivot_right,
                    asof_utc=cfg.replay_utc,
                )
                if parent_sel:
                    # compare AB to AB
                    alignment = compute_alignment_score(sel, parent_sel[0])
            weight = instrument_weight(sym)
            projection_strength, confidence_components = _projection_confidence(sel, c, alignment=alignment, weight=weight)
            spec = MT5ObjectSpec(
                object_id="",
                symbol=sym,
                timeframe=tf,
                object_type="OBJ_EXPANSION",
                engine_metadata=engine_md,
                priority="HIGH",
                source_tf=tf,
                parent_tf=parent_tf,
                alignment_score=float(alignment),
                anchor_1=sel.a,
                anchor_2=sel.b,
                anchor_3=c,
                levels=levels,
                strength=projection_strength,
                context=ObjectContext(label="fib_expansion", sources=[f"anchor:{sel.kind}"]),
                metadata={
                    **build_description_metadata(
                        "fib_projection",
                        score=projection_strength,
                        trade_bias=swing_trade_bias(sel.a.price, sel.b.price),
                        anchor_source=sel.kind,
                        components=["abc_structure", "fib_expansion", "atr", "timeframe_alignment"],
                    ),
                    "levels": d_levels,
                    "atr": sel.atr,
                    "point": sel.point,
                    "parent_tf_alignment": float(alignment),
                    "projection_confidence": confidence_components,
                    "projection_forward_bars": int(projection_forward),
                },
            )
            spec.object_id = MT5ObjectSpec.compute_object_id(
                symbol=spec.symbol,
                timeframe=spec.timeframe,
                object_type=spec.object_type,
                anchors=[spec.anchor_1, spec.anchor_2, spec.anchor_3],
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
            # --- D prediction markers (project AB from point C) ---
            # D_price = C + (B-A) * ratio
            d_specs: list[MT5ObjectSpec] = []
            bars = load_bars(outdir, sym, tf, asof_utc=cfg.replay_utc)
            if bars.empty:
                bars = load_bars(outdir, sym, None, asof_utc=cfg.replay_utc)
            try:
                if predict_d:
                    ab = float(sel.b.price) - float(sel.a.price)
                    c_price = float(c.price)
                    t_c = _future_label_time(bars, str(c.time_utc), projection_forward)
                    for r in d_levels:
                        d_price = c_price + ab * float(r)
                        # highlight the most used projection ratio
                        pri = "MEDIUM" if abs(float(r) - 1.618) < 1e-9 else "LOW"
                        color = "clrDeepSkyBlue" if ab >= 0 else "clrOrangeRed"
                        line = MT5ObjectSpec(
                            object_id="",
                            symbol=sym,
                            timeframe=tf,
                            object_type="OBJ_HLINE",
                            engine_metadata={"projection_d_version": "1.0", "anchor_version": "2.1"},
                            priority=pri,
                            source_tf=tf,
                            parent_tf=parent_tf,
                            alignment_score=float(alignment),
                            parent_object_id=spec.object_id,
                            anchor_1=AnchorPoint(time_utc=t_c, price=float(d_price), kind=f"D_{r:g}"),
                            strength=float(spec.strength),
                            context=ObjectContext(label="projection_D", sources=[f"parent:{spec.object_id}"]),
                            metadata={
                                **build_description_metadata(
                                    "projection_D",
                                    score=spec.strength,
                                    trade_bias=swing_trade_bias(sel.a.price, sel.b.price),
                                    anchor_source=sel.kind,
                                    components=["parent_projection", f"D_{r:g}", "abc_structure"],
                                ),
                                "color": color,
                                "width": 2 if pri != "LOW" else 1,
                                "projection_ratio": float(r),
                            },
                        )
                        line.object_id = MT5ObjectSpec.compute_object_id(
                            symbol=line.symbol,
                            timeframe=line.timeframe,
                            object_type=line.object_type,
                            anchors=[line.anchor_1],
                            levels=[],
                            engine_version=line.engine_version,
                            engine_metadata=line.engine_metadata,
                            priority=line.priority,
                            parent_object_id=line.parent_object_id,
                            related_object_ids=line.related_object_ids,
                            source_tf=line.source_tf,
                            parent_tf=line.parent_tf,
                        )
                        d_specs.append(line)
            except Exception:
                d_specs = []

            if d_specs:
                append_specs(outdir, d_specs)
            all_specs = [spec] + d_specs
            lifecycle = update_lifecycle(outdir, bars, all_specs, ttl_hours=cfg.ttl_hours)
            update_chart_metrics(outdir, specs_created=all_specs, lifecycle_state=lifecycle, run_label="fib_projection_v2")

            if cfg.emit_spec_only:
                print(f"[V2][EXP] Spec only: {sym} {tf} id={spec.object_id}")
                continue

            apply_path, cleanup_path = write_scripts(
                sym,
                tf,
                all_specs,
                tool_label="FibProjection",
                mt5_data_folder=cfg.mt5_data_folder,
                max_objects=cfg.max_objects,
            )
            print(f"[V2][EXP] Wrote {apply_path.name} + {cleanup_path.name} for {sym} {tf}")


def main() -> None:
    p = build_parser(description="Plots V2 Tool 2 — Fibonacci Expansion / Projection (OBJ_EXPANSION)")
    p.add_argument("--no-predict-d", action="store_true", help="Disable D prediction markers")
    p.add_argument("--d-levels", default=None, help="Comma-separated D projection ratios (default: expansion levels)")
    p.add_argument("--projection-forward", type=int, default=50, help="Place projection labels this many bars ahead")
    args = p.parse_args()
    cfg = parse_cfg(args)
    def parse_d_levels(val):
        if not val:
            return list(DEFAULT_LEVELS)
        out = []
        for part in str(val).split(","):
            part = part.strip()
            if not part:
                continue
            try:
                out.append(float(part))
            except Exception:
                continue
        return out or list(DEFAULT_LEVELS)
    predict_d = not bool(getattr(args, "no_predict_d", False))
    d_levels = parse_d_levels(getattr(args, "d_levels", None))
    projection_forward = int(getattr(args, "projection_forward", 50) or 50)
    run_loop(lambda c: run_once(c, predict_d=predict_d, d_levels=d_levels, projection_forward=projection_forward), cfg)


if __name__ == "__main__":
    main()
