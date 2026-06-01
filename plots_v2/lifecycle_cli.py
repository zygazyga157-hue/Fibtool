from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from plots_v2.object_lifecycle import mark_broken


def main() -> None:
    p = argparse.ArgumentParser(description="Plots V2 — Object lifecycle utilities")
    p.add_argument("--outputs-dir", default="outputs")
    p.add_argument("--mark-broken", default=None, help="Mark an object_id as BROKEN")
    args = p.parse_args()
    outdir = Path(str(args.outputs_dir))
    if args.mark_broken:
        ok = mark_broken(outdir, str(args.mark_broken))
        if ok:
            print(f"[V2][LIFE] Marked BROKEN: {args.mark_broken}")
        else:
            print(f"[V2][LIFE] Not found: {args.mark_broken}")
    else:
        p.print_help()


if __name__ == "__main__":
    main()

