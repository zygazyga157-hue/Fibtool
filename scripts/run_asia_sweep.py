import sys
import os
from pathlib import Path
import json
import threading
import subprocess
import csv
from datetime import datetime, timezone, timedelta
import time

# ensure repo root on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from asia_sweep_london_mss import AsiaSweepStrategy


def _append_jsonl(path: Path, record: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception:
        pass


def _atomic_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    with src.open("rb") as r, tmp.open("wb") as w:
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            w.write(chunk)
    os.replace(tmp, dst)


def _dataset_label_stats(csv_path: Path) -> dict:
    """Return cheap stats without pandas: rows, pos, neg, pos_rate.

    Assumes a header with a `label` column (as produced by prepare_dataset.py).
    """
    rows = 0
    pos = 0
    neg = 0
    try:
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, [])
            if not header:
                return {"rows": 0, "pos": 0, "neg": 0, "pos_rate": None}
            try:
                label_idx = header.index("label")
            except ValueError:
                label_idx = -1
            for r in reader:
                if not r:
                    continue
                rows += 1
                if label_idx < 0 or label_idx >= len(r):
                    continue
                v = str(r[label_idx]).strip()
                if v == "1":
                    pos += 1
                else:
                    neg += 1
    except Exception:
        return {"rows": None, "pos": None, "neg": None, "pos_rate": None}

    pos_rate = float(pos) / float(rows) if rows else None
    return {"rows": int(rows), "pos": int(pos), "neg": int(neg), "pos_rate": pos_rate}


def _parse_hhmm(value: str, default: str = "14:15") -> tuple[int, int]:
    raw = (value or "").strip()
    if not raw:
        raw = default
    try:
        hh, mm = raw.split(":", 1)
        h = int(hh)
        m = int(mm)
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m
    except Exception:
        pass
    # fallback
    hh, mm = default.split(":", 1)
    return int(hh), int(mm)


def _compute_next_run(now_tz: datetime, hh: int, mm: int) -> datetime:
    target = now_tz.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if target <= now_tz:
        target = target + timedelta(days=1)
    return target


def _acquire_lockfile(lock_path: Path, *, stale_after_seconds: int = 6 * 3600) -> bool:
    """Best-effort cross-process lock via exclusive file create.

    If the lock exists and is older than stale_after_seconds, treat it as stale and replace it.
    """
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    try:
        # Stale check
        if lock_path.exists():
            try:
                age = datetime.now(timezone.utc).timestamp() - lock_path.stat().st_mtime
                if age > float(stale_after_seconds):
                    lock_path.unlink(missing_ok=True)  # py311+; safe on 3.14
            except Exception:
                pass
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            payload = {"pid": os.getpid(), "ts": datetime.now(timezone.utc).isoformat()}
            os.write(fd, json.dumps(payload).encode("utf-8"))
        finally:
            os.close(fd)
        return True
    except Exception:
        return False


def _release_lockfile(lock_path: Path) -> None:
    try:
        lock_path.unlink(missing_ok=True)
    except Exception:
        try:
            if lock_path.exists():
                lock_path.unlink()
        except Exception:
            pass


def _resolve_model_ok(model_root: Path) -> bool:
    try:
        from ml.asia_sweep_london_mss.model_registry import resolve_active_model_dir

        _ = resolve_active_model_dir(model_root)
        return True
    except Exception:
        return False


def _start_ml_retrain_threads(
    *,
    enabled: bool,
    model_root: Path,
    retrain_at_hhmm: str,
    retrain_tz: str,
    train_symbols: list[str],
) -> None:
    if not enabled:
        return

    audit_path = ROOT / "outputs" / "asia_sweep_ml_retrain.jsonl"
    model_root.mkdir(parents=True, exist_ok=True)
    lockfile = model_root / "retrain.lock"
    inproc_lock = threading.Lock()

    def run_retrain_once(*, reason: str) -> None:
        if not inproc_lock.acquire(blocking=False):
            _append_jsonl(
                audit_path,
                {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "event": "retrain_skip",
                    "reason": "inproc_locked",
                },
            )
            return
        if not _acquire_lockfile(lockfile):
            inproc_lock.release()
            _append_jsonl(
                audit_path,
                {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "event": "retrain_skip",
                    "reason": "lockfile_locked",
                    "lockfile": str(lockfile),
                },
            )
            return

        started = datetime.now(timezone.utc)
        _append_jsonl(
            audit_path,
            {
                "time": started.isoformat(),
                "event": "retrain_start",
                "reason": reason,
                "model_root": str(model_root),
                "symbols": train_symbols,
            },
        )

        try:
            ts = started.strftime("%Y%m%d_%H%M%S")
            versioned_dir = model_root / f"v1_{ts}"
            tmp_dir = model_root / "_tmp"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            dataset_path = tmp_dir / f"dataset_{ts}.csv"

            # 1) prepare dataset
            cmd_prepare = [
                sys.executable,
                "-m",
                "ml.asia_sweep_london_mss.prepare_dataset",
                "--symbols",
                ",".join(train_symbols),
                "--outputs-dir",
                "outputs",
                "--out",
                str(dataset_path),
            ]
            p1 = subprocess.run(cmd_prepare, capture_output=True, text=True, cwd=str(ROOT))
            if p1.returncode != 0:
                raise RuntimeError(f"prepare_dataset failed rc={p1.returncode}: {p1.stderr[-800:]}")

            # Guardrail: don't attempt training on an empty dataset (it will fail / produce NaNs).
            try:
                with dataset_path.open("r", encoding="utf-8") as f:
                    line_count = 0
                    for _ in f:
                        line_count += 1
                        if line_count > 2:
                            break
                if line_count <= 1:
                    raise RuntimeError("prepare_dataset produced 0 rows (empty CSV)")
            except Exception as e:
                raise RuntimeError(f"prepare_dataset produced unusable dataset: {e}")

            # Refresh the "current dataset" pointer on every retrain so operators can inspect the exact
            # dataset used for training without hunting the timestamped tmp file.
            dataset_current = model_root / "current_dataset.csv"
            try:
                _atomic_copy(dataset_path, dataset_current)
            except Exception:
                # keep retrain running even if the convenience copy fails
                pass
            ds_stats = _dataset_label_stats(dataset_path)

            # 2) train
            cmd_train = [
                sys.executable,
                "-m",
                "ml.asia_sweep_london_mss.train",
                "--data",
                str(dataset_path),
                "--out",
                str(versioned_dir),
            ]
            p2 = subprocess.run(cmd_train, capture_output=True, text=True, cwd=str(ROOT))
            if p2.returncode != 0:
                raise RuntimeError(f"train failed rc={p2.returncode}: {p2.stderr[-800:]}")

            # 3) write current.json pointer last (atomic)
            metrics = None
            try:
                mp = versioned_dir / "metrics.json"
                if mp.exists():
                    metrics = json.loads(mp.read_text(encoding="utf-8"))
            except Exception:
                metrics = None

            from ml.asia_sweep_london_mss.model_registry import write_current_pointer

            pointer_path = write_current_pointer(
                model_root,
                active_dir=versioned_dir,
                metrics=metrics if isinstance(metrics, dict) else None,
                trained_at=started.isoformat(),
            )

            finished = datetime.now(timezone.utc)
            _append_jsonl(
                audit_path,
                {
                    "time": finished.isoformat(),
                    "event": "retrain_success",
                    "reason": reason,
                    "versioned_dir": str(versioned_dir),
                    "current_json": str(pointer_path),
                    "dataset_path": str(dataset_path),
                    "dataset_current": str(dataset_current),
                    "dataset_stats": ds_stats,
                    "prepare_rc": p1.returncode,
                    "train_rc": p2.returncode,
                    "prepare_stdout_tail": (p1.stdout or "")[-800:],
                    "train_stdout_tail": (p2.stdout or "")[-800:],
                    "metrics": metrics if isinstance(metrics, dict) else None,
                },
            )
        except Exception as e:
            _append_jsonl(
                audit_path,
                {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "event": "retrain_fail",
                    "reason": reason,
                    "error": str(e),
                },
            )
        finally:
            _release_lockfile(lockfile)
            try:
                inproc_lock.release()
            except Exception:
                pass

    # Bootstrap retrain if no model exists yet (non-blocking).
    if not _resolve_model_ok(model_root):
        t = threading.Thread(target=run_retrain_once, kwargs={"reason": "bootstrap_missing_model"}, daemon=True)
        t.start()

    # Daily scheduler thread (DST-safe via zoneinfo when available).
    def scheduler_loop() -> None:
        try:
            from zoneinfo import ZoneInfo

            tz = ZoneInfo(retrain_tz)
        except Exception:
            tz = None

        hh, mm = _parse_hhmm(retrain_at_hhmm, "14:15")
        while True:
            try:
                now = datetime.now(tz) if tz is not None else datetime.now(timezone.utc)
                next_run = _compute_next_run(now, hh, mm)
                sleep_s = max(1.0, (next_run - now).total_seconds())
                time_to = next_run.isoformat()
                _append_jsonl(
                    audit_path,
                    {
                        "time": datetime.now(timezone.utc).isoformat(),
                        "event": "retrain_scheduled",
                        "next_run": time_to,
                        "tz": retrain_tz,
                    },
                )
                # Sleep in chunks to remain responsive to process exit.
                remaining = sleep_s
                while remaining > 0:
                    chunk = min(60.0, remaining)
                    time.sleep(chunk)
                    remaining -= chunk

                run_retrain_once(reason="scheduled")
            except Exception:
                # never crash the main process because of scheduler errors
                time.sleep(60.0)

    t2 = threading.Thread(target=scheduler_loop, daemon=True)
    t2.start()


def main():
    import argparse, json
    parser = argparse.ArgumentParser(description='Asia Sweep London MSS 0.71')
    parser.add_argument('--symbols', nargs='*', help='Symbols to process (e.g. EURUSD USDJPY)')
    dry_group = parser.add_mutually_exclusive_group()
    dry_group.add_argument('--dry-run', dest='dry_run', action='store_true', help='Run in dry-run mode (no live orders)')
    dry_group.add_argument('--no-dry-run', dest='dry_run', action='store_false', help='Disable dry-run and allow live order placement')
    parser.set_defaults(dry_run=None)
    parser.add_argument('--live', action='store_true', help='Run continuously (loop mode). Without this, runner does a single pass.')
    parser.add_argument('--time-zone', type=str, help='Display/local timezone for timestamp_local (example: Africa/Harare)')
    parser.add_argument('--session-time-zone', type=str, help='Timezone used for Asia/London session windows (example: Europe/London)')
    parser.add_argument('--risk-pct', type=float, help='Risk percent per trade (overrides admin settings)')
    parser.add_argument('--order-size', type=float, help='Default order size (lots) to use if sizing helper not available')
    parser.add_argument('--log-orders', type=str, help='Path to order log CSV (default outputs/asia_mss_orders.csv)')
    parser.add_argument('--interval', type=int, default=60, help='Interval seconds between live loop iterations')
    parser.add_argument('--once', action='store_true', help='Run a single live iteration and exit')

    # ML filter + retrain (plan-aligned)
    ml_group = parser.add_mutually_exclusive_group()
    ml_group.add_argument('--ml', dest='ml', action='store_true', help='Enable ML filter + background retrain')
    ml_group.add_argument('--no-ml', dest='ml', action='store_false', help='Disable ML filter')
    parser.set_defaults(ml=None)
    parser.add_argument('--ml-min-prob', type=float, help='Minimum probability required to allow a trade')
    parser.add_argument('--ml-model-root', type=str, default=None, help='Model root (contains current.json and versioned dirs)')
    parser.add_argument('--ml-retrain-at', type=str, default='14:15', help='Daily retrain time HH:MM (default 14:15)')
    parser.add_argument('--ml-retrain-tz', type=str, default=None, help='Timezone for retrain schedule (default session-time-zone)')
    parser.add_argument('--ml-train-symbols', type=str, default=None, help='Comma-separated symbols to train on (default: same as --symbols)')
    args = parser.parse_args()

    if args.once and not args.live:
        parser.error('--once requires --live')

    # Default symbols: try to read symbols_timeframes.json if present
    symbols = args.symbols
    try:
        st_path = ROOT / 'symbols_timeframes.json'
        if not symbols and st_path.exists():
            with open(st_path, 'r') as f:
                data = json.load(f)
            if isinstance(data, dict):
                if 'symbols' in data and isinstance(data['symbols'], list):
                    symbols = [s for s in data['symbols'] if isinstance(s, str)]
                else:
                    symbols = list(data.keys())
            elif isinstance(data, list):
                symbols = [s if isinstance(s, str) else s.get('symbol') for s in data]
    except Exception:
        symbols = symbols or None

    if not symbols:
        symbols = ['EURUSD', 'GBPUSD', 'USDJPY']

    # Load strategy-level defaults from config if available
    try:
        from config import (
            ASIA_SWEEP_ORDER_SIZE,
            ASIA_SWEEP_LOG_ORDERS,
            ASIA_SWEEP_RISK_PCT,
            ASIA_SWEEP_DRY_RUN,
            ASIA_SWEEP_TIME_ZONE,
            ASIA_SWEEP_SESSION_TIME_ZONE,
            ASIA_SWEEP_ML_ENABLED as _CFG_ML_ENABLED,
            ASIA_SWEEP_ML_MODEL_DIR as _CFG_ML_MODEL_DIR,
            ASIA_SWEEP_ML_MIN_PROB as _CFG_ML_MIN_PROB,
        )
    except Exception:
        ASIA_SWEEP_ORDER_SIZE = None
        ASIA_SWEEP_LOG_ORDERS = None
        ASIA_SWEEP_RISK_PCT = None
        ASIA_SWEEP_DRY_RUN = None
        ASIA_SWEEP_TIME_ZONE = None
        ASIA_SWEEP_SESSION_TIME_ZONE = None
        _CFG_ML_ENABLED = False
        _CFG_ML_MODEL_DIR = "outputs/models/asia_sweep_mss"
        _CFG_ML_MIN_PROB = 0.55

    strategy = AsiaSweepStrategy(symbols=symbols)
    # precedence: CLI args > config env vars > strategy defaults
    cfg_order_size = args.order_size if args.order_size is not None else ASIA_SWEEP_ORDER_SIZE
    cfg_log_orders = args.log_orders if args.log_orders is not None else ASIA_SWEEP_LOG_ORDERS
    cfg_risk_pct = args.risk_pct if args.risk_pct is not None else (ASIA_SWEEP_RISK_PCT or strategy.risk_pct)
    cfg_time_zone = args.time_zone if args.time_zone else (ASIA_SWEEP_TIME_ZONE or strategy.time_zone)
    cfg_session_time_zone = (
        args.session_time_zone
        if args.session_time_zone
        else (ASIA_SWEEP_SESSION_TIME_ZONE or 'Europe/London')
    )
    # dry-run controls order submission; --live controls loop mode only.
    if args.dry_run is not None:
        cfg_dry_run = bool(args.dry_run)
    elif ASIA_SWEEP_DRY_RUN is not None:
        cfg_dry_run = bool(ASIA_SWEEP_DRY_RUN)
    else:
        cfg_dry_run = True

    # ML enablement: CLI overrides config/env.
    if args.ml is not None:
        ml_enabled = bool(args.ml)
    else:
        ml_enabled = bool(_CFG_ML_ENABLED)
    ml_min_prob = float(args.ml_min_prob) if args.ml_min_prob is not None else float(_CFG_ML_MIN_PROB or 0.55)
    ml_model_root = Path(args.ml_model_root) if args.ml_model_root else Path(str(_CFG_ML_MODEL_DIR or "outputs/models/asia_sweep_mss"))
    if not ml_model_root.is_absolute():
        ml_model_root = (ROOT / ml_model_root).resolve()

    ml_retrain_tz = args.ml_retrain_tz or cfg_session_time_zone or "Europe/London"
    # By default train on the same symbols we trade.
    if args.ml_train_symbols:
        train_symbols = [s.strip().upper() for s in str(args.ml_train_symbols).replace(";", ",").split(",") if s.strip()]
    else:
        train_symbols = [str(s).strip().upper() for s in symbols]

    # Pass ML knobs to the strategy via config module mutation (single-process truth).
    try:
        import config as _config_mod

        _config_mod.ASIA_SWEEP_ML_ENABLED = bool(ml_enabled)
        _config_mod.ASIA_SWEEP_ML_MIN_PROB = float(ml_min_prob)
        _config_mod.ASIA_SWEEP_ML_MODEL_DIR = str(ml_model_root)
    except Exception:
        pass

    strategy.configure(dry_run=cfg_dry_run,
                       risk_pct=cfg_risk_pct,
                       time_zone=cfg_time_zone,
                       session_time_zone=cfg_session_time_zone,
                       order_size=cfg_order_size,
                       log_orders=cfg_log_orders)
    print(
        f"Asia Sweep mode={'live-loop' if args.live else 'single-pass'} "
        f"dry_run={cfg_dry_run} session_tz={cfg_session_time_zone} local_tz={cfg_time_zone}"
    )
    if ml_enabled:
        print(f"[ML] enabled=True min_prob={ml_min_prob} model_root={ml_model_root} retrain_at={args.ml_retrain_at} tz={ml_retrain_tz}")
        _start_ml_retrain_threads(
            enabled=True,
            model_root=ml_model_root,
            retrain_at_hhmm=str(args.ml_retrain_at or "14:15"),
            retrain_tz=str(ml_retrain_tz),
            train_symbols=train_symbols,
        )
    if getattr(args, 'live', False):
        # enter live loop (or single pass if --once)
        out = strategy.run_live(interval_seconds=args.interval, once=args.once, symbols=symbols)
        if args.once and isinstance(out, list):
            print(f"Asia Sweep live-once processed {len(out)} symbols (dry_run={cfg_dry_run})")
    else:
        results = strategy.run()
        print(f"Asia Sweep processed {len(results)} symbols")

if __name__ == '__main__':
    main()
