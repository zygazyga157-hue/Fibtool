## Asia Sweep MT5 Overlay: Capability Audit + Visual Upgrade Plan

### Summary
- Current capability: `plots/asia_sweep_plot.py` generates an MT5 `.mq5` overlay from `outputs/asia_mss_signals.csv` (Asia range zone, Asia high/low with EQH/EQL styling, fib zones, and entry/SL/TP *only if* `trade_setup.valid`).
- Why it’s not suitable right now: your current dataset has `valid_trade=0` (28 signals, 0 qualified), so the overlay never draws the live-execution-critical objects (entry/SL/TP/alert). It also doesn’t surface the “why” (sweep + MSS alignment) in a way you can read at a glance.

### Key Implementation Changes (MT5 Only, Rich Annotated, Clean Redraw)
- **Data source upgrade (use the depth you already output)**
  - Change `load_asia_signals()` to prefer `outputs/asia_mss_signals.jsonl` (native booleans + nested dicts: `mss`, `m5`, `trade_setup`, `pretrade`) and fall back to CSV if JSONL is missing.
  - Parse timestamps as datetimes (not string max) to pick the latest record per symbol deterministically.
- **“Live Read” Status Panel (always drawn)**
  - Add an MT5 on-chart panel (`OBJ_RECTANGLE_LABEL` + `OBJ_LABEL`) summarizing:
  - `timestamp_session` + `session_tz`, `in_london`, `in_asia`
  - `asia_high/asia_low`, `eqh/eql` pool + touch counts
  - `sweep_high/sweep_low`
  - `bullMSS/bearMSS` and computed MSS thresholds (see next bullet)
  - `trade_setup.valid` + reason (if invalid), and `pretrade.passed` + reason, `lots`, `rr` when present
  - Color-code panel background: green (trade valid + pretrade passed), amber (trade valid but pretrade blocked), red (not qualified).
- **Make the chart explain qualification (without needing a trade)**
  - From `mss.prev3`, compute and plot two dashed “MSS threshold” lines:
  - `prev3_high_max` (bull MSS trigger) and `prev3_low_min` (bear MSS trigger), each labeled.
  - Plot current M5 `high/low` lines (thin) and show the last M5 close marker, so you can visually see why MSS is/ isn’t triggered.
  - Add sweep markers:
  - If `sweep_high`, annotate AsiaHigh with a “SWEEP HIGH” tag; if `sweep_low`, tag AsiaLow similarly.
- **Fix sizing/formatting issues that hurt live clarity**
  - Remove the hard-coded `0.0001` offsets; compute offsets inside MQL5 using `SYMBOL_POINT` and `SYMBOL_DIGITS`.
  - Stop formatting everything as `%.5f`; format using `DoubleToString(price, digits)` so BTC/XAU/JPY display correctly.
  - Replace the current “2% entry alert zone” with a signal-based buffer:
  - Default: `buffer = max((m5_high - m5_low) * 0.15, point * 10)` (computed in Python and embedded), so FX doesn’t get a chart-filling rectangle.
  - Use ARGB transparency for filled rectangles via `ColorToARGB()` so zones don’t bury candles.
- **Robust object naming + safe cleanup**
  - Use `symbol_slug(symbol)` consistently for object names and script file names.
  - Replace `ObjectsDeleteAll(chartId, prefix)` with a prefix-based delete helper in MQL5 (iterate objects and delete those starting with prefix) to avoid overload/version issues.
- **MT5 scripts folder portability**
  - Allow overriding MT5 data folder via env var (e.g., `FIBTOOL_MT5_DATA_FOLDER`), falling back to the current hardcoded terminal folder.

### Test Plan
- Add a small unit test that feeds a synthetic signal dict to `generate_mql5_script()` and asserts the script includes:
  - Status panel objects
  - Asia high/low objects
  - MSS threshold objects
  - A trade-setup case (when `trade_setup.valid=true`) produces entry/SL/TP objects and uses the new non-% alert buffer logic.
- Add a loader test that verifies JSONL is preferred over CSV and that timestamp ordering is datetime-based.

### Assumptions / Defaults
- Run target is an MT5 **M5** chart; visuals prioritize fast “take/skip” readability.
- Overlay behavior is **clean redraw** per run (no historical snapshots left behind).
- If no trade qualifies, the overlay still fully renders the state (sweep/MSS/thresholds + reasons) so you can diagnose alignment in real time.
