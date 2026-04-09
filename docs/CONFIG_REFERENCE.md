# Fibtool Config Reference

`config.py` is the single source of truth for all runtime behaviour. This document covers every tuneable parameter, its current live value, what it controls, and how to adjust it safely.

---

## MT5 Connection

| Key | Value | Purpose |
|-----|-------|---------|
| `MT5_LOGIN` | `81616483` | Account number |
| `MT5_PASSWORD` | `'Zyga_157'` | Account password |
| `MT5_SERVER` | `'Exness-MT5Trial10'` | Broker server name |
| `MT5_PATH` | `'C:/Program Files/MetaTrader 5/terminal64.exe'` | Terminal executable |

> Change `MT5_SERVER` when switching between demo and live — wrong server silently fails to connect.

---

## Telegram

| Key | Value | Purpose |
|-----|-------|---------|
| `TELEGRAM_BOT_TOKEN` | `"8303..."` | Bot token from BotFather |
| `TELEGRAM_GROUP_ID` | `""` | Primary chat/group ID (signals + reports) |
| `TELEGRAM_ADMIN_ID` | `"7254..."` | Admin user ID for admin-only alerts |
| `TELEGRAM_EXTRA_CHAT_IDS` | `""` | Comma-separated extra recipients for signals |
| `TELEGRAM_HEARTBEAT_EXTRA_IDS` | `""` | Comma-separated extra recipients for heartbeats |

**To add extra signal recipients:** set `TELEGRAM_EXTRA_CHAT_IDS = "123456789,987654321"`.  
Both candlestick and harmonic signals use the same destination.

---

## Candlestick Reports

| Key | Current | Purpose |
|-----|---------|---------|
| `CANDLE_REPORTS_ENABLED` | `True` | Master switch for candlestick Telegram reports |
| `CANDLES_DEDUPE_PERSIST` | `"outputs/telegram_sent.json"` | State file for signal deduplication |
| `CANDLES_DEDUPE_MIN_SECONDS` | `3600` | Minimum seconds between repeat reports for same symbol |
| `CANDLES_DEDUPE_MIN_SCORE_DELTA` | `0.5` | Minimum score change to force a resend before cooldown |

**To silence reports:** set `CANDLE_REPORTS_ENABLED = False`.  
**To tighten duplication:** raise `CANDLES_DEDUPE_MIN_SECONDS` (e.g. `7200` for 2-hour cooldown).

---

## Candlestick Autotrade

All gates must pass before an order is placed.

| Key | Current | Purpose |
|-----|---------|---------|
| `CANDLE_AUTOTRADE_ENABLED` | `True` | Master switch — enables evaluation and order placement |
| `CANDLE_AUTOTRADE_DRY_RUN` | `False` | **Live.** Set `True` to log orders without sending to MT5 |
| `CANDLE_AUTOTRADE_MIN_ABS_SCORE` | `2.0` | Minimum absolute pattern score to qualify |
| `CANDLE_SIGNAL_WINDOW_BARS` | `3` | Bars back to scan for qualifying patterns |
| `CANDLE_AUTOTRADE_FRESH_BARS` | `1` | Pattern must have fired within this many bars |
| `CANDLE_AUTOTRADE_MIN_BARS` | `60` | Minimum historical bars required to compute ATR/patterns |
| `CANDLE_AUTOTRADE_MIN_RANGE_ATR` | `0.5` | Bar range must be ≥ 0.5 × ATR (filters low-energy bars) |
| `CANDLE_AUTOTRADE_MAX_SPREAD_PIPS_FX` | `2.5` | Max spread in pips for FX pairs |
| `CANDLE_AUTOTRADE_MAX_SPREAD_ATR_FRAC` | `0.04` | Max spread as fraction of ATR (non-FX) |
| `CANDLE_AUTOTRADE_MAX_ENTRY_DISTANCE_ATR` | `1.5` | Max distance from close to pending entry in ATR multiples |
| `CANDLE_AUTOTRADE_LATE_ENTRY_MAX_BUFFER_MULT` | `1.0` | Market-order buffer when breakout already happened |
| `CANDLE_AUTOTRADE_COOLDOWN_SECONDS` | `3600` | Per-symbol cooldown after a trade (seconds) |
| `CANDLE_AUTOTRADE_STATE_PATH` | `"outputs/candlestick_autotrade_state.json"` | Cooldown state file |
| `CANDLE_AUTOTRADE_CLASSIFICATION_HOLD` | `True` | Block trade when indecision patterns dominate |

**Required patterns** (`CANDLE_AUTOTRADE_REQUIRED_PATTERNS`): at least one of the listed strong patterns must be present and fresh. The full list covers 3-line strikes, morning/evening stars, engulfing, hammers, and 20 other high-reliability patterns. Remove patterns from this list to loosen entry, add to tighten.

**Liquidity windows** (London 07:00–17:00, NY 08:00–12:00 local time): trades are blocked outside these windows for FX/metals/indices. Crypto is always open.

### Tuning the Model Selection Engine (MSE)

| Key | Current | Effect |
|-----|---------|--------|
| `MSE_SCORE_A_THRESHOLD` | `3.5` | ≥ this + momentum dominates → Model A (close entry) |
| `MSE_BREAKOUT_SCORE_THRESHOLD` | `0.6` | ≥ this → Model B (pending stop above/below bar) |
| `MSE_ATR_RATIO_HIGH` | `0.02` | ATR ratio above this = high volatility (favours B) |
| `MSE_ATR_RATIO_LOW` | `0.005` | ATR ratio below this = compression (favours C retrace) |
| `MSE_RR_BASE` | `2.0` | Starting RR before reflexive multipliers |
| `MSE_RR_FLOOR` | `1.2` | Minimum RR after reflexive adjustment |
| `MSE_RR_CEILING` | `4.5` | Maximum RR after reflexive adjustment |
| `MODEL_C_RETRACE_RATIO` | `0.618` | Fibonacci retrace depth for Model C entries |

---

## Harmonic Signals

| Key | Current | Purpose |
|-----|---------|---------|
| `HARMONIC_SIGNALS_ENABLED` | `True` | Run harmonic analysis in the collector |
| `HARMONIC_SIGNALS_TELEGRAM` | `True` | Send rich HTML harmonic signals to Telegram |
| `HARMONIC_SPEC_V2_ENABLED` | `True` | V2 signal path (regime + volume structure gates) |
| `HARMONIC_BLOCK_UNKNOWN_REGIME` | `True` | Block signals when market regime is UNKNOWN |
| `HARMONIC_REQUIRE_SQUARED` | `True` | Require price–time squaring for confirmation |
| `HARMONIC_ALLOW_EXTREME` | `False` | Allow signals during EXTREME volatility (dangerous) |
| `HARMONIC_MIN_CONFIRMATIONS` | `2` | Minimum gate confirmations before signal fires |
| `HARMONIC_WEIGHTED_SCORE_MIN` | `0.7` | Minimum weighted resonance score |
| `HARMONIC_SESSION` | `'auto'` | Session context (`auto`, `ASIA`, `LONDON`, `NEW_YORK`, `DEAD_ZONE`) |

**Resonance tuning:**

| Key | Current | Notes |
|-----|---------|-------|
| `HARMONIC_VOLUME_STRONG_RATIO` | `1.2` | Volume ≥ mean × 1.2 → STRONG |
| `HARMONIC_VOLUME_MODERATE_RATIO` | `0.8` | Volume ≥ mean × 0.8 → MODERATE |
| `HARMONIC_RESONANCE_STRONG` | `1.0` | Score weight for STRONG resonance |
| `HARMONIC_RESONANCE_MODERATE` | `0.6` | Score weight for MODERATE resonance |
| `HARMONIC_RESONANCE_WEAK` | `0.2` | Score weight for WEAK resonance |
| `HARMONIC_VOLUME_WINDOW` | `50` | Bars used for volume average (median) |
| `HARMONIC_REGIME_DAMPEN_UNKNOWN` | `0.5` | Score multiplier when regime is UNKNOWN |
| `HARMONIC_SQUARED_DAMPING` | `0.8` | Score multiplier when squaring absent (only when `REQUIRE_SQUARED=False`) |
| `HARMONIC_BARS_ELAPSED_WINDOW` | `20` | Lookback for time/price squaring anchor |

### V2 Structure Gates

These keys feed `analyze_symbol_live()` when `HARMONIC_SPEC_V2_ENABLED = True`. They control zone width, rejection candle shape, and the minimum volume class needed to confirm entry.

| Key | Current | Purpose |
|-----|---------|---------|
| `HARMONIC_ZONE_ATR_MULT` | `0.25` | Harmonic zone half-width = ATR × this. Wider = more price accepted inside zone |
| `HARMONIC_REJECTION_WICK_BODY_RATIO` | `1.2` | Sell rejection: wick must be ≥ body × this (pin-bar filter). Raise to require sharper rejections |
| `HARMONIC_VOLUME_CONFIRM_MIN` | `"MODERATE"` | Minimum volume class for `volume_confirmed`. Options: `"WEAK"`, `"MODERATE"`, `"STRONG"` |

**How zone acceptance/rejection works:**

- **Buy**: close must be inside the harmonic zone (`zone_low` … `zone_high`) → `buy_acceptance = True`
- **Sell rejection**: upper wick ≥ body × `HARMONIC_REJECTION_WICK_BODY_RATIO` while price touches the zone  
- **Sell bearish acceptance**: full bearish close through zone in a downtrend (`is_downtrend()`)
- **Volume confirmation**: resonance strength (`WEAK`/`MODERATE`/`STRONG`) must be ≥ `HARMONIC_VOLUME_CONFIRM_MIN`

The `structure` dict from `analyze_symbol_live()` exposes all these booleans for inspection in the JSONL audit.

**Harmonic price levels** are loaded automatically from `docs/data/market_harmonics.json` — 28 instruments with `base_harmonics` and `common_multiples`. No config needed for levels.

---

## Harmonic TP/SL Computation

Harmonic SL/TP uses a multiples-ladder derived from `market_harmonics.json`:

```
structural_risk = max(base_harmonics) × point
atr_floor       = HARMONIC_K_ATR × ATR
risk            = max(structural_risk, atr_floor)
scale           = ceil(risk / (min(common_multiples) × point))
TP_i            = entry ± common_multiples[i] × scale × point
breakeven       = entry ± 0.618 × risk
```

| Key | Current | Purpose |
|-----|---------|---------|
| `HARMONIC_K_ATR` | `0.25` | ATR floor fraction — raise for wider stops in choppy markets |
| `HARMONIC_TP_LEVEL` | `1` | TP ladder index used for MT5 order (1 = first/conservative TP) |
| `HARMONIC_RR_MIN` | `1.0` | Minimum RR; signals and autotrade are blocked below this |

**To use a more aggressive TP:** set `HARMONIC_TP_LEVEL = 2` or `3`.  
**To require better setups:** raise `HARMONIC_RR_MIN` to `1.5` or `2.0`.

---

## Harmonic Autotrade

| Key | Current | Purpose |
|-----|---------|---------|
| `HARMONIC_AUTOTRADE_ENABLED` | `True` | Evaluate and place harmonic trades |
| `HARMONIC_AUTOTRADE_DRY_RUN` | `False` | **Live.** Set `True` to audit without placing real orders |
| `HARMONIC_AUTOTRADE_COOLDOWN_SECONDS` | `3600` | Per-symbol cooldown after a trade |
| `HARMONIC_AUTOTRADE_STATE_PATH` | `"outputs/harmonic_autotrade_state.json"` | Cooldown state + last trade metadata |

**Gate order** (first failure blocks the trade):

1. Signal is BUY or SELL
2. `HARMONIC_AUTOTRADE_ENABLED = True`
3. Regime is not UNKNOWN (when `HARMONIC_BLOCK_UNKNOWN_REGIME = True`)
4. Vol phase is not EXTREME (when `HARMONIC_ALLOW_EXTREME = False`)
5. `volume_confirmed = True`
6. Computed RR ≥ `HARMONIC_RR_MIN`
7. Stress is not HIGH
8. Per-symbol cooldown has elapsed

**Audit trail:** all candidates (eligible and blocked) are logged to `outputs/harmonic_autotrade_audit.jsonl`. Each line contains the full `HarmonicCandidate` fields + order result.

**To revert to simulation mode:** set `HARMONIC_AUTOTRADE_DRY_RUN = True`. Orders will be logged to `outputs/harmonic_autotrade_audit.jsonl` without hitting MT5.

---

## Asia Sweep (London MSS)

Asia Sweep parameters support both `config.py` defaults and **environment variable overrides** — the env var always wins, making this safe to run in containers or cron without editing the file.

| Key | Default | Env var | Purpose |
|-----|---------|---------|---------|
| `ASIA_SWEEP_DRY_RUN` | `False` | `ASIA_SWEEP_DRY_RUN` | **Live.** Set `1` in env or `True` in config for simulation |
| `ASIA_SWEEP_ORDER_SIZE` | `0.1` | `ASIA_SWEEP_ORDER_SIZE` | Lot size per trade |
| `ASIA_SWEEP_RISK_PCT` | `1.0` | `ASIA_SWEEP_RISK_PCT` | Risk percent per trade |
| `ASIA_SWEEP_ML_ENABLED` | `True` | `ASIA_SWEEP_ML_ENABLED` | ML V3 gate (blocks low-probability setups) |
| `ASIA_SWEEP_ML_MODEL_DIR` | `"outputs/models/asia_sweep_mss"` | `ASIA_SWEEP_ML_MODEL_DIR` | Model artifacts or root with `current.json` |
| `ASIA_SWEEP_ML_MIN_PROB` | `0.60` | `ASIA_SWEEP_ML_MIN_PROB` | Minimum ML probability to pass gate |
| `ASIA_SWEEP_M5_ENABLED` | `True` | `ASIA_SWEEP_M5_ENABLED` | True M5 bar collection for MSS confirmation |
| `ASIA_SWEEP_TIME_ZONE` | `"UTC"` | `ASIA_SWEEP_TIME_ZONE` | Timezone for order timestamps |
| `ASIA_SWEEP_SESSION_TIME_ZONE` | `"Europe/London"` | `ASIA_SWEEP_SESSION_TIME_ZONE` | DST-aware session window timezone |

**Session windows** (in `ASIA_SWEEP_SESSION_TIME_ZONE`):

| Window | Start | End |
|--------|-------|-----|
| Asia | `00:00` | `07:59` |
| London | `08:00` | `14:00` |
| Sweep detection | mirrors London window | — |

**MSS tuning:**

| Key | Current | Notes |
|-----|---------|-------|
| `ASIA_SWEEP_MSS_LOOKBACK` | `3` | Bars of structure to confirm MSS |
| `ASIA_SWEEP_CONFIRM_WINDOW_BARS` | `12` | M5 bars to wait for MSS confirmation after sweep |
| `ASIA_SWEEP_MSS_MODE` | `'close'` | Confirmation on close (spec-aligned) |

**To run Asia Sweep in dry-run from the shell:**
```
ASIA_SWEEP_DRY_RUN=1 python asia_sweep_london_mss.py
```

---

## ML Gate (Asia Sweep)

Model: `v3_20260330` — test AUC 0.742 (vs V1 0.524).  
The active model is resolved from `outputs/models/asia_sweep_mss/current.json`.

| Key | Current | Notes |
|-----|---------|-------|
| `ASIA_SWEEP_ML_ENABLED` | `True` | Activates the gate; any import failure auto-disables |
| `ASIA_SWEEP_ML_MIN_PROB` | `0.60` | Raise to `0.70`+ for tighter filtering, lower to `0.50` for recall |

**To retrain:** `python -m ml.asia_sweep_london_mss.train_v3` — updates `current.json` automatically.

---

## TEST_MODE (legacy simulation)

| Key | Current | Purpose |
|-----|---------|---------|
| `TEST_MODE` | `False` | When `True`, writes simulated trades to `outputs/harmonic_test_trades.jsonl` instead of placing orders |
| `TEST_MODE_CONSERVATIVE_RR` | `3.0` | Target RR for simulated trades |

`TEST_MODE` is superseded by `HARMONIC_AUTOTRADE_DRY_RUN` and `CANDLE_AUTOTRADE_DRY_RUN` for production use. Keep `False` in live.

---

## Model B (Breakout Predicted Entry)

| Key | Current | Notes |
|-----|---------|-------|
| `MODEL_B_PREDICT_ENABLED` | `True` | Attaches a predicted pending entry price to signals |
| `MODEL_B_CANCEL_AFTER_BARS` | `6` | Informational: order lifecycle in bars |

Spread/safety/buffer overrides are set per asset class (FX, metals, crypto, indices). The shared defaults apply when a profile-specific key is absent.

---

## Common Tuning Recipes

### Back to simulation (all strategies)
```python
CANDLE_AUTOTRADE_DRY_RUN = True
HARMONIC_AUTOTRADE_DRY_RUN = True
ASIA_SWEEP_DRY_RUN = os.environ.get('ASIA_SWEEP_DRY_RUN', '1') in ('1', 'true', 'True', 'yes')
```

### Tighten harmonic quality
```python
HARMONIC_RR_MIN = 1.5
HARMONIC_WEIGHTED_SCORE_MIN = 0.75
HARMONIC_MIN_CONFIRMATIONS = 3
HARMONIC_TP_LEVEL = 2           # target second TP (better RR)
```

### Widen harmonic capture
```python
HARMONIC_ALLOW_EXTREME = True   # allow EXTREME volatility windows
HARMONIC_BLOCK_UNKNOWN_REGIME = False
HARMONIC_RR_MIN = 0.8
HARMONIC_WEIGHTED_SCORE_MIN = 0.5
```

### Tighten candlestick autotrade
```python
CANDLE_AUTOTRADE_MIN_ABS_SCORE = 3.0
MSE_RR_BASE = 2.5
MSE_RR_FLOOR = 1.5
```

### Disable harmonic signals only (keep autotrade analysis)
```python
HARMONIC_SIGNALS_TELEGRAM = False
```

### Disable harmonic autotrade only (keep Telegram signals)
```python
HARMONIC_AUTOTRADE_ENABLED = False
```

---

## Output Files Quick Reference

| File | Written by | Contents |
|------|-----------|---------|
| `outputs/harmonic_autotrade_audit.jsonl` | `harmonic_autotrade.py` | Every candidate evaluation + order result |
| `outputs/harmonic_autotrade_state.json` | `harmonic_autotrade.py` | Per-symbol last trade timestamp/side |
| `outputs/harmonic_signals.jsonl` | `harmonic_signals.py` | All fired harmonic signals with HTML payload |
| `outputs/candlestick_autotrade_state.json` | `candlestick_autotrade.py` | Per-symbol candlestick cooldown state |
| `outputs/telegram_sent.json` | `candlestick_signals.py` | Candlestick signal deduplication state |
| `outputs/asia_mss_signals.jsonl` | `asia_sweep_london_mss.py` | Asia Sweep signal events |
| `outputs/asia_mss_orders.csv` | `asia_sweep_london_mss.py` | Asia Sweep order log |
| `outputs/admin_settings.json` | Admin UI / manual edit | Default lot size, RR overrides |
