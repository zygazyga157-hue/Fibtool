from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from plots_v2.anchor_engine import select_anchors
from plots_v2.cli import build_parser, parse_cfg, run_loop, RunConfig
from plots_v2.common import calc_atr, infer_point, load_bars
from plots_v2.confluence_engine import fib_prices, find_confluences, s9_levels_from_pivot_price
from plots_v2.object_lifecycle import update_lifecycle
from plots_v2.object_specs import AnchorPoint, MT5ObjectSpec, ObjectContext, append_specs
from plots_v2.mt5_script_generator import write_scripts
from plots_v2.telemetry import update_chart_metrics
from plots_v2.multitf import pick_available_parent_tf, compute_alignment_score
from plots_v2.scoring import confidence_label, instrument_weight, reaction_bias
from plots_v2.descriptions import build_confluence_chart_text, build_description_metadata


FIB_RATIOS_DEFAULT = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618]


def _parse_fib_ratios(value: str | None) -> list[float]:
    if not value:
        return list(FIB_RATIOS_DEFAULT)
    out: list[float] = []
    for part in str(value).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(float(part))
        except Exception:
            continue
    return out or list(FIB_RATIOS_DEFAULT)


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
                print(f"[V2][CONF] No anchors for {sym} {tf}")
                continue

            bars = load_bars(outdir, sym, tf, asof_utc=cfg.replay_utc)
            if bars.empty:
                bars = load_bars(outdir, sym, None, asof_utc=cfg.replay_utc)
            if bars.empty:
                print(f"[V2][CONF] No bars for {sym} {tf}")
                continue

            close = float(bars["close"].iloc[-1])
            atr = calc_atr(bars, period=14)
            point = infer_point(bars)
            tolerance = max(point * 5.0, (atr * 0.15) if atr else 0.0)
            if tolerance <= 0:
                tolerance = point * 5.0

            fib_ratios = _parse_fib_ratios(cfg.fib_ratios)
            fib_lv = fib_prices(sel.a.price, sel.b.price, fib_ratios)
            s9_lv = s9_levels_from_pivot_price(sel.b.price)
            weight = instrument_weight(sym)
            confs = find_confluences(
                fib_levels=fib_lv,
                s9_levels=s9_lv,
                tolerance=tolerance,
                atr=atr,
                score_weight=weight,
            )
            if not confs:
                print(f"[V2][CONF] No confluences within tolerance for {sym} {tf}")
                continue

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

            # Use last bar timestamp as "now" anchor for labels
            ts = pd.to_datetime(bars["time"].iloc[-1], utc=True, errors="coerce")
            if pd.isna(ts):
                ts = pd.Timestamp(datetime.now(timezone.utc))
            t_mid = ts.to_pydatetime().replace(tzinfo=timezone.utc)
            t1 = (t_mid - timedelta(hours=12)).isoformat()
            t2 = (t_mid + timedelta(hours=12)).isoformat()

            # Only render strongest regions (top N)
            top_n = int(cfg.top_n or 10)
            confs = confs[:top_n]

            specs: list[MT5ObjectSpec] = []
            for i, c in enumerate(confs):
                strength_ratio = float(c.strength / 100.0)
                if atr and atr > 0:
                    half_width = max(point * 5.0, atr * max(0.05, 1.0 - strength_ratio))
                else:
                    half_width = tolerance
                zone_top = float(c.fib_price + half_width)
                zone_bot = float(c.fib_price - half_width)
                conf_label = confidence_label(c.strength)
                bias = reaction_bias(sel.a.price, sel.b.price, c.fib_price)
                zone_role = "RESISTANCE" if c.fib_price >= close else "SUPPORT"
                title = f"{conf_label} CONFLUENCE {zone_role}"
                rect = MT5ObjectSpec(
                    object_id="",
                    symbol=sym,
                    timeframe=tf,
                    object_type="OBJ_RECTANGLE",
                    engine_metadata={"anchor_version": "2.1", "confluence_version": "1.1", "s9_version": "1.0"},
                    priority="HIGH",
                    source_tf=tf,
                    parent_tf=parent_tf,
                    alignment_score=float(alignment),
                    anchor_1=AnchorPoint(time_utc=t1, price=zone_top, kind="conf_zone_top"),
                    anchor_2=AnchorPoint(time_utc=t2, price=zone_bot, kind="conf_zone_bot"),
                    strength=float(c.strength / 100.0),
                    context=ObjectContext(label="confluence_zone", sources=[f"anchor:{sel.kind}", "engine:confluence_v2"]),
                    metadata={
                        **build_description_metadata(
                            "confluence_zone",
                            score=c.strength,
                            trade_bias=bias,
                            anchor_source=sel.kind,
                            components=[f"Fib {c.fib_ratio:g}", f"S9 {c.s9_degree:g}deg", "timeframe_alignment"],
                            extra={"summary": f"Fib {c.fib_ratio:g} overlaps S9 {c.s9_degree:g}deg within {c.distance:.5g}."},
                        ),
                        "color": "clrLightSteelBlue",
                        "back": True,
                        "parent_tf_alignment": float(alignment),
                        "instrument_weight": float(weight),
                        "zone_half_width": float(half_width),
                        "zone_title": title,
                    },
                )
                rect.object_id = MT5ObjectSpec.compute_object_id(
                    symbol=rect.symbol,
                    timeframe=rect.timeframe,
                    object_type=rect.object_type,
                    anchors=[rect.anchor_1, rect.anchor_2],
                    levels=[],
                    engine_version=rect.engine_version,
                    engine_metadata=rect.engine_metadata,
                    priority=rect.priority,
                    parent_object_id=rect.parent_object_id,
                    related_object_ids=rect.related_object_ids,
                    source_tf=rect.source_tf,
                    parent_tf=rect.parent_tf,
                )
                specs.append(rect)

                label = MT5ObjectSpec(
                    object_id="",
                    symbol=sym,
                    timeframe=tf,
                    object_type="OBJ_TEXT",
                    engine_metadata={"anchor_version": "2.1", "confluence_version": "1.1", "s9_version": "1.0"},
                    priority="HIGH",
                    source_tf=tf,
                    parent_object_id=rect.object_id,
                    parent_tf=parent_tf,
                    alignment_score=float(alignment),
                    anchor_1=AnchorPoint(time_utc=t_mid.isoformat(), price=float(c.fib_price), kind="conf_label"),
                    strength=float(c.strength / 100.0),
                    context=ObjectContext(label="confluence_label", sources=[f"anchor:{sel.kind}", "engine:confluence_v2"]),
                    metadata={
                        **build_description_metadata(
                            "confluence_zone",
                            score=c.strength,
                            trade_bias=bias,
                            anchor_source=sel.kind,
                            components=[f"Fib {c.fib_ratio:g}", f"S9 {c.s9_degree:g}deg", "timeframe_alignment"],
                            extra={"summary": f"Fib {c.fib_ratio:g} overlaps S9 {c.s9_degree:g}deg within {c.distance:.5g}."},
                        ),
                        "text": build_confluence_chart_text(score=c.strength, fib_ratio=c.fib_ratio, s9_degree=c.s9_degree),
                        "color": "clrWhite",
                        "font_size": 8,
                        "zone_title": title,
                    },
                )
                label.object_id = MT5ObjectSpec.compute_object_id(
                    symbol=label.symbol,
                    timeframe=label.timeframe,
                    object_type=label.object_type,
                    anchors=[label.anchor_1],
                    levels=[],
                    engine_version=label.engine_version,
                    engine_metadata=label.engine_metadata,
                    priority=label.priority,
                    parent_object_id=label.parent_object_id,
                    related_object_ids=label.related_object_ids,
                    source_tf=label.source_tf,
                    parent_tf=label.parent_tf,
                )
                rect.related_object_ids = [label.object_id]
                specs.append(label)

            append_specs(outdir, specs)
            lifecycle = update_lifecycle(outdir, bars, specs, ttl_hours=cfg.ttl_hours)
            update_chart_metrics(outdir, specs_created=specs, lifecycle_state=lifecycle, run_label="confluence_v2")

            if cfg.emit_spec_only:
                print(f"[V2][CONF] Spec only: {sym} {tf} count={len(specs)} tol={tolerance:.5g}")
                continue

            apply_path, cleanup_path = write_scripts(
                sym,
                tf,
                specs,
                tool_label="Confluence",
                mt5_data_folder=cfg.mt5_data_folder,
                max_objects=cfg.max_objects,
            )
            print(f"[V2][CONF] Wrote {apply_path.name} + {cleanup_path.name} for {sym} {tf} (N={len(confs)} tol={tolerance:.5g})")


def main() -> None:
    p = build_parser(description="Plots V2 Tool 7 — Smart Confluence Layer (OBJ_RECTANGLE + OBJ_TEXT)")
    p.add_argument("--top-n", type=int, default=10, help="Render only the strongest N confluences")
    p.add_argument("--fib-ratios", default="", help="Comma-separated fib ratios (e.g. 0,0.236,0.382,0.5,0.618,1,1.618)")
    args = p.parse_args()
    cfg = parse_cfg(args)
    run_loop(run_once, cfg)


if __name__ == "__main__":
    main()
