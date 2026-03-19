# Candlesticks pattern detector

This folder contains a lightweight candlestick pattern detector and Telegram reporter.

Usage

From the repository root run (example):

```powershell
python -m candlesticks.candlestick_signals --bars outputs/xauusd_bars.csv --dry-run
```

To send to Telegram (ensure `TELEGRAM_BOT_TOKEN` and recipient/chat IDs are configured in `config.py` or via environment variables):

```powershell
python -m candlesticks.candlestick_signals --bars outputs/xauusd_bars.csv
```

Notes
- The module prefers `TA-Lib` when installed for broad pattern support. When `TA-Lib` is not available it falls back to a small set of builtin detectors (Doji, Engulfing, Hammer).
- Core dependencies: `pandas`, `numpy`, `requests`.

Message format
- BUY/SELL signals are sent as HTML to the main chat and any extras configured via `TELEGRAM_EXTRA_CHAT_IDS`.
- Neutral reports are sent as Markdown/plain text to the main chat only.
- The HTML signal layout includes symbol, action, rounded score, UTC time, a numbered top-patterns list, a compact reason summary (✔/✖), and a coverage line showing patterns scanned and rows.

Configuration
- `CANDLE_REPORTS_ENABLED`: (bool) whether the collector auto-runs the reporter after saving bars.
- `CANDLES_DEDUPE_PERSIST`: (path) default `outputs/telegram_sent.json` used for dedupe state.
- `CANDLES_DEDUPE_MIN_SECONDS`: (int) minimum seconds between similar reports for same symbol.
- `CANDLES_DEDUPE_MIN_SCORE_DELTA`: (float) minimum absolute change in score to force resend.

Safety
- Do not commit bot tokens or API keys to the repo. Use environment variables or a local untracked `secrets.py`. If a token is already committed, rotate it immediately.

Extensibility
- Adding annotated chart images as attachments is a recommended enhancement (requires `matplotlib` / `Pillow` and sending via Telegram `sendPhoto`).

Integration
- callers can use `run_report_for_bars(bars_path, chat_id, bot_token, ...)` to run programmatically and control dedupe and force behavior.


