from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from plots_v2.anchor_engine import select_anchors
from plots_v2.cli import build_parser, parse_cfg, run_loop, RunConfig
from plots_v2.common import calc_atr, clamp, infer_point, load_bars
from plots_v2.object_lifecycle import update_lifecycle
from plots_v2.object_specs import AnchorPoint, MT5ObjectSpec, ObjectContext, append_specs
from plots_v2.mt5_script_generator import write_scripts
from plots_v2.telemetry import update_chart_metrics
from plots_v2.descriptions import build_description_metadata, level_trade_bias


CANONICAL_DEGREES = {45.0, 90.0, 180.0, 270.0, 360.0}


def _compute_s9_levels(pivot_price: float) -> list[tuple[float, float]]:
    try:
        from fib_square_strategy import FibonacciSquareOfNine
    except Exception:
        return []
    fs9 = FibonacciSquareOfNine()
    try:
        lv = fs9.calculate_s9_levels(float(pivot_price))
    except Exception:
        return []
    out: list[tuple[float, float]] = []
    for deg, price in lv.items():
        try:
            out.append((float(deg), float(price)))
        except Exception:
            continue
    return out


def _strength_for(deg: float, price: float, close: float, atr: float | None) -> float:
    dist = abs(price - close)
    atr_norm = (dist / atr) if atr and atr > 0 else dist / max(1.0, abs(close) * 0.001)
    deg_w = 1.0 if abs(deg) in CANONICAL_DEGREES else 0.75
    return float(clamp((deg_w / (1.0 + atr_norm)), 0.0, 1.0))


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
                print(f"[V2][S9] No anchors for {sym} {tf}")
                continue

            bars = load_bars(outdir, sym, tf, asof_utc=cfg.replay_utc)
            if bars.empty:
                bars = load_bars(outdir, sym, None, asof_utc=cfg.replay_utc)
            if bars.empty:
                print(f"[V2][S9] No bars for {sym} {tf}")
                continue

            close = float(bars["close"].iloc[-1])
            atr = calc_atr(bars, period=14)

            pivot = sel.b
            s9 = _compute_s9_levels(float(pivot.price))
            if not s9:
                print(f"[V2][S9] Could not compute S9 for {sym} {tf}")
                continue

            # Select K nearest levels around current price to avoid chart spam
            k = int(cfg.max_levels or 20)
            ranked = sorted(s9, key=lambda kv: abs(kv[1] - close))[:k]
            ts = pd.to_datetime(bars["time"].iloc[-1], utc=True, errors="coerce")
            if pd.isna(ts):
                ts = pd.Timestamp(datetime.now(timezone.utc))
            ts_iso = ts.to_pydatetime().isoformat()

            specs: list[MT5ObjectSpec] = []
            for deg, price in ranked:
                s = _strength_for(deg, price, close, atr)
                side = "above" if price >= close else "below"
                color = "clrRed" if side == "above" else "clrDodgerBlue"
                line = MT5ObjectSpec(
                    object_id="",
                    symbol=sym,
                    timeframe=tf,
                    object_type="OBJ_HLINE",
                    engine_metadata={"anchor_version": "2.1", "s9_version": "1.0"},
                    priority="LOW",
                    source_tf=tf,
                    anchor_1=AnchorPoint(time_utc=ts_iso, price=float(price), kind=f"s9_{deg}"),
                    strength=s,
                    context=ObjectContext(label=f"s9_{deg}", sources=[f"anchor:{sel.kind}"]),
                    metadata={
                        **build_description_metadata(
                            "square9_level",
                            score=s,
                            trade_bias=level_trade_bias(price, close),
                            anchor_source=sel.kind,
                            components=[f"S9 {deg:g}deg", "pivot_rotation"],
                        ),
                        "color": color,
                        "width": 2 if s > 0.8 else 1,
                        "degree": float(deg),
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
                specs.append(line)

            append_specs(outdir, specs)
            lifecycle = update_lifecycle(outdir, bars, specs, ttl_hours=cfg.ttl_hours)
            update_chart_metrics(outdir, specs_created=specs, lifecycle_state=lifecycle, run_label="square9_v2")

            if cfg.emit_spec_only:
                print(f"[V2][S9] Spec only: {sym} {tf} count={len(specs)}")
                continue

            apply_path, cleanup_path = write_scripts(
                sym,
                tf,
                specs,
                tool_label="Square9",
                mt5_data_folder=cfg.mt5_data_folder,
                max_objects=cfg.max_objects,
            )
            print(f"[V2][S9] Wrote {apply_path.name} + {cleanup_path.name} for {sym} {tf} (K={k})")


def main() -> None:
    p = build_parser(description="Plots V2 Tool 6 — Square of Nine levels (OBJ_HLINE + OBJ_TEXT)")
    p.add_argument("--max-levels", type=int, default=20, help="Max S9 levels to render (nearest to current price)")
    args = p.parse_args()
    cfg = parse_cfg(args)
    run_loop(run_once, cfg)


if __name__ == "__main__":
    main()
