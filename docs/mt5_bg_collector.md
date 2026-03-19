# mt5_bg_collector.py

Purpose
-------
Background collector that fetches bars from MetaTrader5, runs `DegreeFactor` and `FibonacciSquareOfNine` analyses, and writes:

- `outputs/xauusd_analysis.csv` — per-run summary
- `outputs/xauusd_bars.csv` — raw OHLCV bars (written once)
- `outputs/xauusd_confluences.csv` — detailed confluence zones

Quick CLI
---------
PowerShell examples:

```powershell
python mt5_bg_collector.py --once
python mt5_bg_collector.py --interval 900 --symbols XAUUSD,EURUSD
```

Requirements and setup
----------------------
- MetaTrader5 terminal must be installed and accessible via `MT5_PATH` in `config.py`.
- Python package `MetaTrader5` required to fetch bars; plotting (`matplotlib`) and image annotation (`Pillow`) are optional.

Resilience and fallbacks
------------------------
- Script handles missing plotting libraries by skipping images and still recording CSV rows.
- Confluence CSV header reconciliation attempts to preserve existing rows and migrate columns safely.
- Maintains an index JSON to deduplicate confluences within a TTL (default 60 minutes).

Outputs and artifacts
---------------------
- Analysis CSV has fields like timestamp, pivot_low/high, trade validity, RR, and strong confluence count.
- Confluence CSV includes severity, strength score, distance normalized to ATR, and conf_id for deduplication.
- Optionally generates annotated confluence PNGs (Pillow) and matplotlib plots.

Best-run strategies
-------------------
- Run as a scheduled background job (every 10–30 minutes) to keep `outputs/xauusd_bars.csv` fresh for offline analysis.
- Use `--once` during testing; enable `--interval` for continuous operation.
- If running headless, avoid enabling screenshot attempts (they may fail depending on MT5 build). The script already falls back gracefully.

Edge cases
----------
- If MT5 returns no bars, the script raises an error; ensure symbol names match the MT5 symbol list.
- If `BARS_CSV` already exists, raw bars are not overwritten — to refresh, delete the CSV or run collector with a different path.
