from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class RunConfig:
    symbols: list[str]
    timeframes: list[str]
    outputs_dir: Path
    mt5_data_folder: str | None
    emit_spec_only: bool
    interval: int | None
    once: bool
    replay_utc: str | None
    max_objects: int
    max_levels: int
    top_n: int
    fib_ratios: str | None

    pivot_left: int
    pivot_right: int
    ttl_hours: int


def build_parser(*, description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--symbols", default="XAUUSD", help="Comma-separated symbols (e.g. XAUUSD,EURUSD)")
    p.add_argument("--timeframes", default="H1", help="Comma-separated timeframes (e.g. H1,H4,D1)")
    p.add_argument("--outputs-dir", default="outputs", help="Outputs directory (default: outputs)")
    p.add_argument("--mt5-data-folder", default=None, help="Override MT5 data folder (else uses env FIBTOOL_MT5_DATA_FOLDER)")
    p.add_argument("--emit-spec-only", action="store_true", help="Persist spec JSONL/CSV only; do not write .mq5 scripts")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--once", action="store_true", help="Run once and exit (default if neither once/interval provided)")
    g.add_argument("--interval", type=int, default=None, help="Run continuously every N seconds")
    p.add_argument(
        "--replay",
        default=None,
        help="Replay/as-of mode: ISO timestamp; engine behaves as if future candles do not exist (e.g. 2026-04-18T12:00:00Z).",
    )
    p.add_argument("--pivot-left", type=int, default=5, help="Pivot detection left bars")
    p.add_argument("--pivot-right", type=int, default=5, help="Pivot detection right bars")
    p.add_argument("--ttl-hours", type=int, default=72, help="Object lifecycle TTL in hours")
    p.add_argument(
        "--max-objects",
        type=int,
        default=50,
        help="Max objects to emit into MT5 apply script for a symbol/timeframe batch (priority-based filtering).",
    )
    return p


def parse_cfg(args: argparse.Namespace) -> RunConfig:
    syms = [s.strip().upper() for s in str(args.symbols).split(",") if s.strip()]
    tfs = [t.strip().upper() for t in str(args.timeframes).split(",") if t.strip()]
    if not syms:
        syms = ["XAUUSD"]
    if not tfs:
        tfs = ["H1"]
    once = bool(args.once) or (args.interval is None)
    return RunConfig(
        symbols=syms,
        timeframes=tfs,
        outputs_dir=Path(str(args.outputs_dir)),
        mt5_data_folder=(str(args.mt5_data_folder) if args.mt5_data_folder else None),
        emit_spec_only=bool(args.emit_spec_only),
        interval=(int(args.interval) if args.interval is not None else None),
        once=once,
        replay_utc=(str(args.replay).strip() if args.replay else None),
        max_objects=int(args.max_objects),
        max_levels=int(getattr(args, "max_levels", 20) or 20),
        top_n=int(getattr(args, "top_n", 10) or 10),
        fib_ratios=(str(getattr(args, "fib_ratios", "")).strip() or None),
        pivot_left=int(args.pivot_left),
        pivot_right=int(args.pivot_right),
        ttl_hours=int(args.ttl_hours),
    )


def run_loop(fn, cfg: RunConfig) -> None:
    if cfg.once:
        fn(cfg)
        return
    assert cfg.interval is not None
    while True:
        fn(cfg)
        time.sleep(int(cfg.interval))
