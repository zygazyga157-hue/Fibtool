# live_trade_setup_bot_mt5.py

Purpose
-------
Per-symbol helper that analyzes the latest bars using Fibonacci Square of Nine and attempts to place a single market order (or dry-run) on MetaTrader 5 with risk-based position sizing.

Quick CLI
---------
PowerShell examples:

```powershell
python live_trade_setup_bot_mt5.py --symbol XAUUSD --timeframe H1 --once --dry-run
python live_trade_setup_bot_mt5.py --symbol EURUSD --timeframe H1 --min-rr 1.5 --min-confs 3
```

Key options
-----------
- `--symbol` Symbol (default: XAUUSD)
- `--timeframe` Timeframe (default: H1)
- `--min-rr` Minimum R:R to accept (default: 1.5)
- `--min-confs` Minimum strong confluence zones required (default: 3)
- `--max-entry-slippage-points` Max allowed distance from suggested entry (points)
- `--risk-pct` Percent of account balance risked per trade (default: 1.0)
- `--require-wyckoff` Require Wyckoff pattern detection
- `--wyckoff-bias` Bias enforcement: `auto`, `accumulation`, `distribution`, `any`
- `--dry-run` Log but do not send order
- `--once` Run just once and exit
- `--allow-multiple` Allow multiple entries per bar

Technical flow
--------------
1. Fetch bars via MetaTrader5 API (uses `mt5.copy_rates_from`).
2. Build strategy dataframe and run `FibonacciSquareOfNine.analyze_market()`.
3. Validate setup, require Wyckoff if requested, apply filters (RR, confluence count).
4. Pick nearest confluence within `K * ATR` as TP if available; otherwise use provided TP.
5. Round SL/TP to symbol tick and ensure correct ordering relative to entry.
6. Risk sizing uses symbol tick value and tick size; computes lots such that risk = balance * risk_pct.
7. Submit `mt5.order_send()` with `ORDER_FILLING_FOK` and `ORDER_TIME_GTC` defaults.

Safety and validation
---------------------
- Validates TP/SL ordering and RR bounds (rejects too-wide or too-narrow setups).
- Rejects if entry deviates too far from current price (slippage filter).
- Dedupes per bar+side using `outputs/trade_setup_index.json`.
- If `dry_run`, logs a row in `outputs/orders.csv` with `result_retcode` set to `DRY-RUN`.

Best-run strategies
-------------------
- Use `--dry-run` and `--once` during testing.
- Prefer running from `launcher.py` for supervised, multi-symbol operation.
- Keep `MT5_PATH` configured in `config.py` and ensure terminal is logged-in.

Edge cases & debugging
----------------------
- If `mt5` is unavailable the script will raise; install the `MetaTrader5` Python package.
- Rounding and symbol info rely on `mt5.symbol_info()`; missing attributes will be handled with defaults but validate on your broker's symbol definitions.
- Watch for `INVALID-TP-SL-RR` and `INVALID-TP-SL` entries in `outputs/orders.csv` for rejected orders.
