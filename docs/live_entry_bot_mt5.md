# live_entry_bot_mt5.py

Purpose
-------
Live trader that monitors a symbol/timeframe and places market orders on MetaTrader 5 when SuperTrend and UTBot align and S9 offers valid TP/SL. Includes optional AI-enhanced signal summaries.

Quick CLI
---------
PowerShell examples:

```powershell
python live_entry_bot_mt5.py --symbol XAUUSD --timeframe H1 --interval 60 --dry-run
python live_entry_bot_mt5.py --symbol EURUSD --timeframe H1 --interval 30
```

Multi-symbol / multi-timeframe examples:

```powershell
# Run two symbols across two timeframes continuously (poll each pair every 120s)
python live_entry_bot_mt5.py --symbols "XAUUSD,BTCUSD" --timeframes "H1,H4" --interval 120

# Run each symbol/timeframe pair once and exit
python live_entry_bot_mt5.py --symbols "XAUUSD,BTCUSD" --timeframes "H1,H4" --once --dry-run
```

Important configuration
-----------------------
- `config.py` must supply MT5 credentials: `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`, and `MT5_PATH` for terminal initialization.
- Telegram and Gemini keys: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_GROUP_ID`, `TELEGRAM_ADMIN_ID`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_BASE_URL`. These can be provided via `config.py` or environment variables as the script gracefully falls back.

Safety features
---------------
- Dry-run mode (`--dry-run`) logs the would-be order to `outputs/orders.csv` with `result_retcode`=`DRY-RUN`.
- TP/SL validation ensures TP is on the correct side relative to entry.
- Rejects orders with RR outside configured bounds or distance > ATR thresholds.
- Deduplication per bar+side is persisted via an index in `outputs/trade_setup_index.json`.
- Optional `--start-admin-poller` to enable admin command polling (the orchestrator uses this to avoid duplicates).

Multi-run mode and admin poller
-------------------------------
- You can run the bot in a single process that sequentially iterates symbol × timeframe pairs using the `--symbols` and `--timeframes` flags. This is useful for small setups or a single-host deployment.
- Deduplication is file-based (`outputs/live_signals_index.json` and sent ids) and reused by multi-run, so you should not get duplicate Telegram messages when running multi-run in a single process.
- Important: do NOT start the admin poller (`--start-admin-poller`) in more than one process. If you use `launcher.py` (recommended for production) let the launcher start the admin poller in only one child or start a single dedicated process for admin commands.

Best practice
-------------
- For multi-symbol production operation prefer using `launcher.py` to spawn supervised child processes (one per symbol/timeframe). The launcher manages restarts, backoff, and heartbeats.
- Use the single-process `--symbols`/`--timeframes` multi-run mode for lightweight setups or local testing.

AI notes
--------
- If `GEMINI_API_KEY` is set, the script may call the Gemini API to generate textual summaries or follow-ups. Ensure your API keys and model names are up to date and you respect rate limits.

Outputs
-------
- `outputs/orders.csv` — logs each attempted order (dry or real) with timestamp and result code.
- Optionally sends Telegram messages when signals are executed.

Best-run strategies
-------------------
- Run under the `launcher.py` orchestrator for multi-symbol setups.
- Always start with `--dry-run` to validate behavior; monitor `outputs/orders.csv`.
- Keep `config.py` out of VCS; use environment variables in production.
- Use `--confirm-window` to require multi-bar confirmation on noisy instruments.

Edge cases & troubleshooting
---------------------------
- If MT5 Python package not installed, the script tries to import and may run in reduced mode — install `MetaTrader5` to enable live trading.
- If MT5 initialization fails, check `MT5_PATH` and that the terminal is accessible.
- Be mindful of floating point rounding and `point`/`digits` for symbols — the script rounds SL/TP to tick size.
