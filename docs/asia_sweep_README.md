Asia Sweep — London MSS 0.71 Fib Strategy (dry-run)

Quick start

- Generate dry-run/live signals using saved **TRUE M5** bars from `outputs/<symbol>_m5.csv`.
- Collect/refresh M5 bars (one-off): `python asia_sweep_m5_collector.py --once --symbols EURUSD,GBPUSD,BTCUSD`.
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
- ML filter (trade-quality gate + daily retrain + hot reload):
  - Enable: `python scripts/run_asia_sweep.py --live --dry-run --ml`
  - Model root: `outputs/models/asia_sweep_mss/`
  - Active model pointer: `outputs/models/asia_sweep_mss/current.json` (written after successful retrain)
  - Latest retrain dataset snapshot: `outputs/models/asia_sweep_mss/current_dataset.csv` (refreshed on each retrain)
  - If ML is enabled but no model is available, the strategy **fails closed** (no live orders) with reason `ML model unavailable`.
- `--once` is only valid with `--live`.
- `--time-zone` controls `timestamp_local` display/audit timezone.
- `--session-time-zone` controls Asia/London session windows (use IANA names like `Europe/London` for DST-aware behavior).
- Config fallbacks: `ASIA_SWEEP_TIME_ZONE` and `ASIA_SWEEP_SESSION_TIME_ZONE` in `config.py`.
- Ensure `outputs/<symbol>_m5.csv` files exist (written by `asia_sweep_m5_collector.py`). If missing, the strategy fails closed with reason `Missing M5 bars`.
