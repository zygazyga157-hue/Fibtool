# Asia Sweep — Trading Hours & Use Cases

This document summarizes the exact session windows the Asia Sweep strategy uses and the recommended uses for each window.

## Key Windows (exact hours)

- **Asia (range build)**: 00:00–07:59 (local calendar day)
  - Purpose: Build the AsiaHigh / AsiaLow reference range for the day.
  - Notes: Use these bars only to compute the Asia range; do not execute entries during this window.

- **London (primary execution window)**: 08:00–14:00 (local)
  - Purpose: Primary time for evaluating sweep detection and placing entries.
  - System behavior: The strategy only issues entries when `in_london == True`.

## Recommended Subwindows (higher-probability execution)

- **London Open Momentum**: 08:00–10:00 (local)
  - Use case: Strong early volatility and price discovery after Asia range — good for sweep follow‑through and MSS confirmation.

- **Late London / Follow‑through**: 12:00–14:00 (local)
  - Use case: Continuation trades and late confirmation after London market activity.

## Avoid / Lower Priority

- Outside the London window (after 14:00 local until next day Asia build) — do not trigger entries. Asia window remains for range-building only.
- If `auto_state` disables trading, pre‑trade gating (RR, margin, tradedToday) blocks entries — respect these checks.

## Operational & Data Requirements

- MSS requirement: at least 4 completed 5‑minute (M5) candles (previous 3 + current M5). Do not rely on MSS without sufficient M5 history.
- Evaluate signals on M5 closes during the London window for consistent behavior.
- Timezone separation:
  - `session_time_zone` drives session logic (`in_asia`, `in_london`, Asia range day boundaries).
  - `time_zone` is for reporting/audit fields (`timestamp_local`, `in_*_local`).
- DST: use IANA timezone names (for example `Europe/London`) for `session_time_zone` to keep London window aligned through DST transitions.

## Quick Reference (UTC examples)

- Asia build (UTC example): 22:00 (previous day) – 05:59 UTC
- London execution (UTC example): 06:00 – 12:00 UTC

---

File: `docs/asia_sweep_trading_hours.md`
