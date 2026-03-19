Asia Sweep — London MSS 0.71 Fib Strategy (dry-run)

Quick start

- Generate dry-run signals using saved bars from `outputs/<symbol>_bars.csv`.
- Runner (single pass, dry-run): `python scripts/run_asia_sweep.py --dry-run --time-zone Africa/Harare --session-time-zone Europe/London` from repository root.
- Outputs:
  - `outputs/asia_mss_signals.jsonl` (append-only trace of runs)
  - `outputs/asia_mss_signals.csv` (CSV view)
  - `outputs/asia_mss_state.json` (tracks `tradedToday` per symbol)

Notes
- `--live` enables loop mode only.
- `--dry-run` / `--no-dry-run` controls whether orders can be submitted.
- For live monitoring without orders: `python scripts/run_asia_sweep.py --live --dry-run`.
- For live execution: `python scripts/run_asia_sweep.py --live --no-dry-run`.
- `--once` is only valid with `--live`.
- `--time-zone` controls `timestamp_local` display/audit timezone.
- `--session-time-zone` controls Asia/London session windows (use IANA names like `Europe/London` for DST-aware behavior).
- Config fallbacks: `ASIA_SWEEP_TIME_ZONE` and `ASIA_SWEEP_SESSION_TIME_ZONE` in `config.py`.
- Ensure `outputs/<symbol>_bars.csv` files exist (the collector writes them).
