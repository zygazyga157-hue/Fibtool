**Candlestick Reporter**
- **Purpose**: Analyze saved OHLC bars and send candlestick pattern reports to Telegram. Uses TA-Lib when available and falls back to simple detectors otherwise.

- **Files**:
  - `candlesticks/candlestick_signals.py`: detector, scorer, reporter, and Telegram sender.
  - `outputs/<symbol>_bars.csv`: per-symbol OHLC CSV saved by the collector.
  - `outputs/telegram_sent.json`: deduplication index used to avoid repeated sends.

- **Message Format (HTML)**
  - Header: `🔥 <b>SIGNAL ALERT</b>`
  - Symbol: `📉 <b>Symbol:</b> <code>SYMBOL</code>`
  - Action: `📊 <b>Action:</b> <b><code>BUY|SELL|NEUTRAL</code></b>`
  - Score: `🏆 <b>Score:</b> <code>SCORE</code>` (rounded to 2 decimal places)
  - Time: `🕒 <b>Time:</b> <code>UTC_TIMESTAMP</code>`
  - Top Patterns: numbered list with `NAME → <code>+N · W.WW</code>` entries
  - Reason Summary: compact checklist like `<code>PatternA ✔ | PatternB ✖ | ...</code>`
  - Coverage line: `<code>X patterns scanned · Y rows</code>`
  - Footer: `⚠️ <i>Signals are suggestions only. Use your risk management.</i>`

- **Behavioral Details**:
  - BUY/SELL signals are sent as HTML to the main chat ID and any extras configured via `TELEGRAM_EXTRA_CHAT_IDS`.
  - Neutral/summary reports are sent as Markdown/plain text to the main chat only.
  - Messages retry without `parse_mode` if Telegram returns a parse error.
  - Deduplication is governed by `outputs/telegram_sent.json`. The reporter uses a time threshold and a minimum score delta to decide when to re-send.

- **Configuration** (via `config.py` or environment overrides):
  - `CANDLE_REPORTS_ENABLED` (bool): whether the collector auto-runs the reporter after saving bars.
  - `CANDLES_DEDUPE_PERSIST` (str): path to dedupe file (default `outputs/telegram_sent.json`).
  - `CANDLES_DEDUPE_MIN_SECONDS` (int): minimum seconds between similar reports for same symbol.
  - `CANDLES_DEDUPE_MIN_SCORE_DELTA` (float): minimum absolute change in score to force resend.
  - `TELEGRAM_EXTRA_CHAT_IDS` (str): optional comma-separated extra chat ids to CC.

- **Run / Test**:
  - Dry-run (no Telegram send):

```powershell
python -m candlesticks.candlestick_signals --bars outputs/xauusd_bars.csv --dry-run
```

  - Programmatic call (from Python):

```python
from candlesticks.candlestick_signals import run_report_for_bars
res = run_report_for_bars('outputs/xauusd_bars.csv', chat_id, bot_token, dry_run=True)
print(res)
```

  - Collector once (may call reporter if enabled):

```powershell
python mt5_bg_collector.py --once --symbols XAUUSD
```

- **Safety & Security**:
  - Do not commit Telegram bot tokens or API keys to the repo. Prefer environment variables or a local untracked `secrets.py`.
  - If a token was committed, rotate it immediately.

- **Troubleshooting**:
  - If messages appear with literal HTML/escape characters, ensure `send_telegram` is called with `parse_mode='HTML'` and dynamic values are escaped via `_escape_html`.
  - If Telegram returns 400 or 404, check bot token and chat permissions. The reporter logs response bodies on failure.
  - If TA-Lib is not installed, the reporter will still run using fallback detectors but with fewer patterns.

- **Extensibility**:
  - Attaching annotated charts as photos is supported as a future enhancement (requires matplotlib/Pillow and sending via `sendPhoto`).
  - CLI flags for `persist_path`, `min_seconds`, `min_score_delta`, and `--force` are available programmatically and can be added to the CLI on request.
