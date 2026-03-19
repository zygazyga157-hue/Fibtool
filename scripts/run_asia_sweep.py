import sys
import os
from pathlib import Path

# ensure repo root on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from asia_sweep_london_mss import AsiaSweepStrategy

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
        )
    except Exception:
        ASIA_SWEEP_ORDER_SIZE = None
        ASIA_SWEEP_LOG_ORDERS = None
        ASIA_SWEEP_RISK_PCT = None
        ASIA_SWEEP_DRY_RUN = None
        ASIA_SWEEP_TIME_ZONE = None
        ASIA_SWEEP_SESSION_TIME_ZONE = None

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
