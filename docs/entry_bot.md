# entry_bot.py

Purpose
-------
Offline entry detector that scans historical or live-saved bars CSV for trade setups where SuperTrend and UTBot align and chooses TP/SL from Square-of-Nine (S9) confluence zones.

Quick CLI
---------
PowerShell examples:

```powershell
python entry_bot.py --dry-run
python entry_bot.py --bars outputs/xauusd_bars.csv --symbol XAUUSD --timeframe H1
```

Options
-------
- `--bars` Path to OHLCV CSV (default: `outputs/xauusd_bars.csv`)
- `--symbol` Symbol label (default: `XAUUSD`)
- `--timeframe` Timeframe label (default: `H1`)
- `--st-period` SuperTrend period (default: 10)
- `--st-multiplier` SuperTrend multiplier (default: 3.0)
- `--ut-atr-coef` UTBot ATR coefficient (default: 2.0)
- `--ut-atr-len` UTBot ATR period (default: 1)
- `--confirm-window` Allow confirmation across N bars
- `--dry-run` Do not write CSV; print summary only

Outputs
-------
- Appends rows to `outputs/entries.csv` with columns including `entry_id`, `timestamp`, `symbol`, `timeframe`, `side`, `entry_price`, `tp`, `sl`, `atr`, and metadata such as `tp_source`/`sl_source`.

Technical notes
---------------
- Uses `SuperTrend` and `UTBot` to detect trend alignment. Both modules compute ATR internally; ensure input CSV contains at least `open,high,low,close` and optionally `volume`.
- TP/SL are selected from `FibonacciSquareOfNine.analyze_market()` confluence zones; if none are suitable, pivot highs/lows are used as fallback.
- Deduplication uses deterministic SHA1 of timestamp|symbol|timeframe|side|entry_price.

Best-run strategies
-------------------
- Dry-run on a recent snapshot before enabling actual writes.
- Provide a fresh `outputs/xauusd_bars.csv` produced by `mt5_bg_collector.py` for consistent pivot/confluence calculations.
- Use `--confirm-window` > 0 to avoid single-bar noise if running on lower timeframes.

Common edge cases
-----------------
- Missing columns in CSV will raise errors. Ensure timestamps and OHLC columns exist.
- Duplicate entries will be skipped based on `entry_id`.
- TP/SL ordering validated before writing; invalid combos are rejected.
