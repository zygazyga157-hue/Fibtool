MT5_LOGIN=81616483
MT5_PASSWORD='Zyga_157' 
MT5_SERVER='Exness-MT5Trial10'
MT5_PATH='C:/Program Files/MetaTrader 5/terminal64.exe'
TELEGRAM_BOT_TOKEN = "8303147443:AAGFOHdLS5KFeRCrQEMkHQb7go3uFH4yssQ"
TELEGRAM_GROUP_ID = ""
TELEGRAM_ADMIN_ID = "7254999897"
# Google Gemini AI API Key
GEMINI_API_KEY="AIzaSyAOC0v0C_2bonuoynmlNCwtbwDvf2SVyIo"

# Gemini Model Configuration
GEMINI_MODEL="gemini-1.5-flash"
GEMINI_BASE_URL="https://generativelanguage.googleapis.com"

# Optional: Comma-separated chat IDs for extra recipients
# - TELEGRAM_EXTRA_CHAT_IDS: additional recipients for signals (live_entry_bot_mt5 also reads from env var of same name)
# - TELEGRAM_HEARTBEAT_EXTRA_IDS: additional recipients for heartbeats (launcher imports this and can be overridden by env)
# Example value: "6077071417"
TELEGRAM_EXTRA_CHAT_IDS = ""
TELEGRAM_HEARTBEAT_EXTRA_IDS = ""

# Candlestick reporting orchestration - off by default to avoid unexpected Telegram posts
CANDLE_REPORTS_ENABLED = True
# Default dedupe settings used by `candlesticks.candlestick_signals.run_report_for_bars`
CANDLES_DEDUPE_PERSIST = "outputs/telegram_sent.json"
CANDLES_DEDUPE_MIN_SECONDS = 60 * 60  # minimum seconds between similar reports for same symbol (1 hour)
CANDLES_DEDUPE_MIN_SCORE_DELTA = 0.5  # minimum absolute change in score to force resend

# Candlestick auto-trade gates (mechanical, balanced capture)
# When enabled, mt5_bg_collector will evaluate the last CLOSED bar and (optionally) place an order
# using live_entry_bot_mt5.send_order(). Keep disabled by default.
CANDLE_AUTOTRADE_ENABLED = True
# Safety default: keep dry-run True until you've verified audit output + MT5 behavior.
CANDLE_AUTOTRADE_DRY_RUN = False
# Pattern scoring window and thresholds
CANDLE_SIGNAL_WINDOW_BARS = 3
CANDLE_AUTOTRADE_MIN_ABS_SCORE = 2.0
# Strong-only patterns (directional) that must be present + fresh to qualify for auto-trade
CANDLE_AUTOTRADE_REQUIRED_PATTERNS = [
    # Top-ranked / strong set from the notebook ranking table
    "CDL3LINESTRIKE",
    "CDL3BLACKCROWS",
    "CDL3WHITESOLDIERS",
    "CDLEVENINGSTAR",
    "CDLEVENINGDOJISTAR",
    "CDLMORNINGSTAR",
    "CDLMORNINGDOJISTAR",
    "CDLABANDONEDBABY",
    "CDLBREAKAWAY",
    "CDLPIERCING",
    "CDLDARKCLOUDCOVER",
    "CDLINVERTEDHAMMER",
    "CDLMATCHINGLOW",
    "CDLHOMINGPIGEON",
    "CDLIDENTICAL3CROWS",
    "CDL3INSIDE",
    "CDL3OUTSIDE",
    # Common, reliable staples (even if lower-ranked in the table)
    "CDLENGULFING",
    "CDLHAMMER",
    "CDLSHOOTINGSTAR",
    "CDLHANGINGMAN",
    "CDLHARAMI",
    "CDLHARAMICROSS",
    "CDLKICKING",
]
CANDLE_AUTOTRADE_FRESH_BARS = 1
# Minimum bars required to compute ATR/patterns safely
CANDLE_AUTOTRADE_MIN_BARS = 60
# Market-condition filters
CANDLE_AUTOTRADE_MIN_RANGE_ATR = 0.5
CANDLE_AUTOTRADE_MAX_SPREAD_PIPS_FX = 2.5
CANDLE_AUTOTRADE_MAX_SPREAD_ATR_FRAC = 0.04
# Pending entry sanity
CANDLE_AUTOTRADE_MAX_ENTRY_DISTANCE_ATR = 1.5
# If breakout already happened, allow market entry only if close enough to the planned entry.
CANDLE_AUTOTRADE_LATE_ENTRY_MAX_BUFFER_MULT = 1.0
# Cooldown to avoid repeat exposure
CANDLE_AUTOTRADE_COOLDOWN_SECONDS = 3600
# State file used for per-symbol dedupe/cooldown
CANDLE_AUTOTRADE_STATE_PATH = "outputs/candlestick_autotrade_state.json"
# When True, suppress trades when indecision patterns dominate (no directional edge)
CANDLE_AUTOTRADE_CLASSIFICATION_HOLD = True
# Liquidity windows (DST-safe via zoneinfo). Applied to fx/metals/indices; crypto remains 24/7.
CANDLE_AUTOTRADE_LONDON_TZ = "Europe/London"
CANDLE_AUTOTRADE_LONDON_START = "07:00"
CANDLE_AUTOTRADE_LONDON_END = "17:00"
CANDLE_AUTOTRADE_NY_TZ = "America/New_York"
CANDLE_AUTOTRADE_NY_START = "08:00"
CANDLE_AUTOTRADE_NY_END = "12:00"

# Harmonic signals orchestration
# When True the collector will run harmonic analysis and persist signals
HARMONIC_SIGNALS_ENABLED = True
# When True send harmonic signals to Telegram chat configured in TELEGRAM_GROUP_ID
HARMONIC_SIGNALS_TELEGRAM = False
# Optional mapping of symbol -> comma-separated harmonic price levels (string) e.g. {'XAUUSD':'1800,1850'}
# harmonics are loaded from docs/data/market_harmonics.json; no need to configure here
#HARMONIC_HARMONICS = {}
HARMONIC_MIN_CONFIRMATIONS = 2
# Harmonic resonance tuning
HARMONIC_VOLUME_STRONG_RATIO = 1.2      # vol must be >= mean * this to be STRONG
HARMONIC_VOLUME_MODERATE_RATIO = 0.8    # vol must be >= mean * this to be MODERATE
HARMONIC_RESONANCE_STRONG = 1.0         # base weight for STRONG resonance
HARMONIC_RESONANCE_MODERATE = 0.6       # base weight for MODERATE resonance
HARMONIC_RESONANCE_WEAK = 0.2           # base weight for WEAK resonance (instead of 0.0)
HARMONIC_VOLUME_WINDOW = 50             # bars to use for volume average (use median)
HARMONIC_REGIME_DAMPEN_UNKNOWN = 0.5   # multiply weighted_score by this if regime==UNKNOWN
HARMONIC_REQUIRE_SQUARED = True        # if True, require harmonic_square; if False, use as optional damping (0.8x)
HARMONIC_SQUARED_DAMPING = 0.8          # damping factor if harmonic_square is False but REQUIRE_SQUARED==False
HARMONIC_BARS_ELAPSED_WINDOW = 20       # lookback window for elapsed-bar anchor used in time/price squaring
HARMONIC_MIN_CONFIRMATIONS = 2          # minimum confirmations to allow signal (harmonic_hit counts as 1, sma50 as +1)
HARMONIC_WEIGHTED_SCORE_MIN = 0.7      # minimum weighted_score to generate signal (WEAK=0.2, so threshold allows weak signals)
# Whether to allow signals during EXTREME volatility. Default False (blocks EXTREME).
HARMONIC_ALLOW_EXTREME = False
# Session override: set to 'ASIA', 'LONDON', 'NEW_YORK', 'DEAD_ZONE' or 'auto' for auto-detect
# Can also set via env var HARMONIC_SESSION
HARMONIC_SESSION = 'auto'
# Spec-aligned structure/regime path (V2)
HARMONIC_SPEC_V2_ENABLED = True
HARMONIC_ZONE_ATR_MULT = 0.25
HARMONIC_REJECTION_WICK_BODY_RATIO = 1.2
HARMONIC_VOLUME_CONFIRM_MIN = "MODERATE"
HARMONIC_BLOCK_UNKNOWN_REGIME = True
# Test mode: when True, the collector will NOT place real orders but will
# write conservative simulated trade proposals to `outputs/harmonic_test_trades.jsonl`.
# Use this to validate end-to-end signal -> trade setup logic without risking live orders.
TEST_MODE = False
TEST_MODE_CONSERVATIVE_RR = 3.0  # target RR ratio for simulated trades
# Model B (breakout) predicted-entry configuration (non-invasive)
# Keep this section lean: define shared defaults once, then only profile-specific overrides.
MODEL_B_PREDICT_ENABLED = True          # attach Model B predicted entry to generated signals
MODEL_B_CANCEL_AFTER_BARS = 6           # informational for pending-order lifecycle

# Shared defaults used when a profile-specific value is not declared.
MODEL_B_ESTIMATED_SPREAD = 0.05         # fallback spread (price units)
MODEL_B_SAFETY_MARGIN = 0.02            # fallback safety buffer (price units)
MODEL_B_ATR_BUFFER_MULT_DEFAULT = 0.10
MODEL_B_MIN_BUFFER_TICKS_DEFAULT = 2
MODEL_B_MIN_RISK_ATR_MULT_DEFAULT = 0.30
MODEL_B_MIN_RISK_TICKS_DEFAULT = 10

# FX-specific pip-based buffers (fiat pairs only, e.g., EURUSD/USDJPY)
MODEL_B_SPREAD_PIPS_FX = 2.0
MODEL_B_SAFETY_PIPS_FX = 1.0

# Profile-specific spread/safety overrides (non-FX, price units)
MODEL_B_ESTIMATED_SPREAD_METALS = 0.06
MODEL_B_SAFETY_MARGIN_METALS = 0.03
MODEL_B_ESTIMATED_SPREAD_CRYPTO = 0.60
MODEL_B_SAFETY_MARGIN_CRYPTO = 0.25
MODEL_B_ESTIMATED_SPREAD_INDICES = 0.30
MODEL_B_SAFETY_MARGIN_INDICES = 0.12

# Buffer/risk overrides (only where they differ from shared defaults)
MODEL_B_ATR_BUFFER_MULT_FX = 0.08
MODEL_B_ATR_BUFFER_MULT_CRYPTO = 0.12

MODEL_B_MIN_BUFFER_TICKS_FX = 1

MODEL_B_MIN_RISK_ATR_MULT_FX = 0.25
MODEL_B_MIN_RISK_ATR_MULT_CRYPTO = 0.35
MODEL_B_MIN_RISK_ATR_MULT_INDICES = 0.32

MODEL_B_MIN_RISK_TICKS_FX = 6
MODEL_B_MIN_RISK_TICKS_CRYPTO = 20
MODEL_B_MIN_RISK_TICKS_INDICES = 14

# Model C (retrace) configuration
MODEL_C_RETRACE_RATIO = 0.618  # 0.5 = midpoint, 0.618 = deeper Fibonacci retracement

# Model Selection Engine (MSE) thresholds
MSE_SCORE_A_THRESHOLD = 3.5       # abs(score) >= this + momentum > reversal → Model A
MSE_SCORE_B_THRESHOLD = 2.0       # unused by cascade but reserved for future gating
MSE_BREAKOUT_SCORE_THRESHOLD = 0.6  # breakout_score >= this → Model B

# ATR / Volatility thresholds for MSE
MSE_ATR_RATIO_HIGH = 0.02         # atr_ratio >= this → High volatility (breakouts likely)
MSE_ATR_RATIO_LOW = 0.005         # atr_ratio <= this → Low volatility (compression, retrace)

# Reflexive RR — single base and bounds
MSE_RR_BASE = 2.0                 # starting RR before reflexive multipliers
MSE_RR_FLOOR = 1.2                # minimum reflexive RR (conservative)
MSE_RR_CEILING = 4.5              # maximum reflexive RR (aggressive)

# Asia Sweep strategy runtime environment variables (can be overridden via env)
import os

# Default order size (lots) for Asia Sweep when sizing helper isn't available
ASIA_SWEEP_ORDER_SIZE = float(os.environ.get('ASIA_SWEEP_ORDER_SIZE', os.environ.get('ASIA_SWEEP_ORDER_LOTS', '0.1')))
# Path to order log CSV for Asia Sweep
ASIA_SWEEP_LOG_ORDERS = os.environ.get('ASIA_SWEEP_LOG_ORDERS', 'outputs/asia_mss_orders.csv')
# Default risk percent (overrides CLI when provided)
ASIA_SWEEP_RISK_PCT = float(os.environ.get('ASIA_SWEEP_RISK_PCT', '1.0'))
# Default dry-run behaviour (True/False)
ASIA_SWEEP_DRY_RUN = os.environ.get('ASIA_SWEEP_DRY_RUN', '1') in ('1', 'true', 'True', 'yes')
# Time zone used for session boundaries
ASIA_SWEEP_TIME_ZONE = os.environ.get('ASIA_SWEEP_TIME_ZONE', 'UTC')
# Time zone used for Asia/London session window evaluation (DST-aware if IANA, e.g. Europe/London)
ASIA_SWEEP_SESSION_TIME_ZONE = os.environ.get('ASIA_SWEEP_SESSION_TIME_ZONE', 'Europe/London')

# Asia Sweep gate tuning (signal capture knobs)
# Times are interpreted in `ASIA_SWEEP_SESSION_TIME_ZONE`.
# Format: "HH:MM" (24-hour).
ASIA_SWEEP_ASIA_START = os.environ.get('ASIA_SWEEP_ASIA_START', '00:00')
ASIA_SWEEP_ASIA_END = os.environ.get('ASIA_SWEEP_ASIA_END', '07:59')
ASIA_SWEEP_LONDON_START = os.environ.get('ASIA_SWEEP_LONDON_START', '08:00')
ASIA_SWEEP_LONDON_END = os.environ.get('ASIA_SWEEP_LONDON_END', '14:00')
# Sweep detection window. Default equals the London window, but can be widened to capture
# "late Asia sweep -> London MSS confirmation" without changing mechanical logic.
ASIA_SWEEP_SWEEP_START = os.environ.get('ASIA_SWEEP_SWEEP_START', ASIA_SWEEP_LONDON_START)
ASIA_SWEEP_SWEEP_END = os.environ.get('ASIA_SWEEP_SWEEP_END', ASIA_SWEEP_LONDON_END)

# MSS confirmation tuning
ASIA_SWEEP_MSS_LOOKBACK = int(os.environ.get('ASIA_SWEEP_MSS_LOOKBACK', '3'))
ASIA_SWEEP_CONFIRM_WINDOW_BARS = int(os.environ.get('ASIA_SWEEP_CONFIRM_WINDOW_BARS', '12'))  # M5 bars
# MSS mode: keep "close" for spec-aligned confirmation (optional future extension).
ASIA_SWEEP_MSS_MODE = os.environ.get('ASIA_SWEEP_MSS_MODE', 'close').strip().lower()

# True M5 persistence for Asia sweep (keeps the rest of Fibtool on M15 while MSS stays mechanically correct).
ASIA_SWEEP_M5_ENABLED = os.environ.get('ASIA_SWEEP_M5_ENABLED', '1') in ('1', 'true', 'True', 'yes')
# Optional: limit M5 fetching to a subset of symbols. Empty => all symbols processed by the collector.
ASIA_SWEEP_M5_SYMBOLS = os.environ.get('ASIA_SWEEP_M5_SYMBOLS', '')
ASIA_SWEEP_M5_HISTORY_MONTHS = int(os.environ.get('ASIA_SWEEP_M5_HISTORY_MONTHS', '12'))
# Fetch a smaller recent M5 window each cycle and merge/dedupe into *_m5.csv
ASIA_SWEEP_M5_FETCH_BARS_PER_CYCLE = int(os.environ.get('ASIA_SWEEP_M5_FETCH_BARS_PER_CYCLE', '2000'))

# ML gate (optional, fail-closed when enabled)
ASIA_SWEEP_ML_ENABLED = os.environ.get('ASIA_SWEEP_ML_ENABLED', '0') in ('1', 'true', 'True', 'yes')
# Can point either to:
# - a model artifacts dir that contains model.pt, OR
# - a model root that contains current.json -> active_dir (hot-reload friendly)
ASIA_SWEEP_ML_MODEL_DIR = os.environ.get('ASIA_SWEEP_ML_MODEL_DIR', 'outputs/models/asia_sweep_mss')
ASIA_SWEEP_ML_MIN_PROB = float(os.environ.get('ASIA_SWEEP_ML_MIN_PROB', '0.60'))

# Optional pretrade RR override (normally read from outputs/admin_settings.json).
# Leave empty/unset to use admin settings.
_rr_min = os.environ.get('ASIA_SWEEP_RR_MIN', '').strip()
_rr_max = os.environ.get('ASIA_SWEEP_RR_MAX', '').strip()
ASIA_SWEEP_RR_MIN = float(_rr_min) if _rr_min else None
ASIA_SWEEP_RR_MAX = float(_rr_max) if _rr_max else None
