"""V4 training entry point for Asia Sweep + candlestick features.

This wraps the hardened V3 training defaults while stamping artifacts as
`v4_{YYYYMMDD_HHMMSS}` and using the expanded FEATURE_COLS contract from
`ml.asia_sweep_london_mss.features`.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from ml.asia_sweep_london_mss import train_v3


_DEFAULT_DATA = "ml/asia_sweep_london_mss/data/dataset_v4_both.csv"
_DEFAULT_ROOT = "outputs/models/asia_sweep_mss"


def _has_arg(args: list[str], name: str) -> bool:
    return any(a == name or a.startswith(name + "=") for a in args)


def _arg_value(args: list[str], name: str, default: str) -> str:
    for i, a in enumerate(args):
        if a == name and i + 1 < len(args):
            return args[i + 1]
        if a.startswith(name + "="):
            return a.split("=", 1)[1]
    return default


def main() -> None:
    args = list(sys.argv[1:])
    if "--help" in args or "-h" in args:
        sys.argv = [sys.argv[0]] + args
        train_v3.main()
        return

    if not _has_arg(args, "--data"):
        args.extend(["--data", _DEFAULT_DATA])
    if not _has_arg(args, "--activate-root"):
        args.extend(["--activate-root", _DEFAULT_ROOT])
    if not _has_arg(args, "--out"):
        root = _arg_value(args, "--activate-root", _DEFAULT_ROOT)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        args.extend(["--out", str(Path(root) / f"v4_{stamp}")])

    sys.argv = [sys.argv[0]] + args
    train_v3.main()


if __name__ == "__main__":
    main()
