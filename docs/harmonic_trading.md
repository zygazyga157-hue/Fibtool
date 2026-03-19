# Instrument Harmonic–Temporal Resonance Trading Strategy  
## (Final Signal-Generating System)

---

## 1. Strategy Overview

This strategy is a **quantitative, state-based trading system** designed to generate **BUY and SELL signals** using:

- Instrument-specific **price harmonics** (instrument DNA)
- **Digital root normalization** of price and time
- **Time–price squaring** to detect stress points
- **Volatility regime filtering**
- **Session-based behavioral weighting**
- **Resonance heatmap memory**
- Strict **risk governance**

The system does **not predict price direction**.  
It detects **decision zones** where probability of continuation or rejection is statistically elevated.

Signals are generated **only when multiple independent dimensions align**.

---

## 2. Instrument Harmonics (Price DNA)

Each instrument has recurring price expansion units (“harmonics”) that define its behavior.

| Instrument | Harmonics |
|----------|-----------|
| Gold | 11, 17 |
| Crude Oil | 44, 88 |
| S&P 500 | 110, 170, 270, 350, 540 |
| Dow Jones | 35, 70, 105 |
| Treasury Bonds | 20 (multiples) |
| Silver | 12, 18, 36 |
| Wheat | 11, 17 |
| Soybeans | 18, 36 |
| Swiss Franc | 27, 54, 81 |

Harmonics are used to:
- Project price expansion
- Define decision zones
- Anchor time–price analysis

They are **never used alone as entry signals**.

---

## 3. Market Regime Classification

Before any signal logic is evaluated, the market is classified into one regime:

### 3.1 Balanced (Rotational)
- Overlapping swings
- Mean reversion dominant
- Expect **single harmonic reactions**

### 3.2 Trending
- Clean impulse legs
- Structure alignment
- Expect **harmonic multiples**

### 3.3 Volatility Expansion
- News-driven
- Range breaks
- Expect **overshoots**

If regime is unclear → **no signals allowed**.

---

## 4. Digital Root Normalization (Core Innovation)

Digital root compresses price and time into a shared 1–9 phase space.

Example:
- 17 → 1 + 7 = 8
- 26 → 2 + 6 = 8

This allows **price and time to be compared directly**, regardless of instrument or timeframe.

---

## 5. Time–Price Squaring Logic

A **Time–Price Square** occurs when:

- Price reaches a harmonic level
- Time elapsed from impulse origin
- Digital root of price movement == digital root of elapsed time

This indicates **market stress / decision pressure**, not direction.

---

## 6. Volatility Phase Normalization

Volatility is classified using ATR:

- Compression
- Normal
- Expansion
- Extreme

Digital-root squaring is:
- **Disabled during Extreme volatility**
- **Weighted down during Expansion**
- **Most effective during Normal & Compression**

This prevents false signals during chaos.

---

## 7. Session-Based Weighting

Market behavior changes by session:

| Session | Weight |
|-------|--------|
| Asia | 0.7 |
| London | 1.0 |
| New York | 1.2 |
| Dead Zone | 0.5 |

Digital-root resonance is **amplified or dampened** depending on session context.

---

## 8. Resonance Heatmap (Market Memory)

The system tracks repeated resonance events at similar prices.

- LOW stress → normal execution
- MODERATE stress → reduce size
- HIGH stress → disable counter-trend signals

This prevents overtrading clustered zones.

---

## 9. Signal Generation Logic

Signals are generated **only if all gates pass**:

- Harmonic level reached
- Time–price digital root squared
- Volatility phase acceptable
- Session-weighted resonance ≥ threshold
- Confirmation score ≥ 2
- Risk limits not breached

### 9.1 BUY Signal

Generated when:
- Price **accepts higher value** at harmonic
- Closes beyond zone
- Volume confirms
- Regime = Trending or Expansion

Interpretation:
> Market effort is rewarded → continuation likely

---

### 9.2 SELL Signal

Generated when:
- Price **rejects value** at harmonic
- Wick rejection + failure
- Regime = Balanced  
  OR bearish acceptance in downtrend

Interpretation:
> Market effort fails → rotation or reversal likely

---

## 10. Risk Management Principles

- Max risk per trade: 0.5–1%
- Daily instrument risk cap: 2%
- Total exposure cap: 4%
- Stops always placed beyond harmonic invalidation
- No averaging, no stop widening

Risk rules override all signals.

---

## 11. What the Strategy Actually Does

This strategy identifies:
- When price has moved **far enough**
- When time has passed **long enough**
- When volatility and session behavior align
- When market stress reaches decision levels

It trades **reaction**, not prediction.

---

## 12. Strengths & Limitations

### Strengths
- Instrument-specific (non-generic)
- Regime-aware
- Low-frequency, high-quality signals
- Capital preservation focused

### Limitations
- Will miss fast, random moves
- Not designed for scalping
- Requires discipline and patience

---

## 13. Deployment Use-Cases

- Manual discretionary trading
- MT5 Expert Advisor
- TradingView signal indicator
- Telegram auto-signal bot
- Portfolio-level risk engine

---

## 14. Code Rule Mapping (V2)

This section documents the implemented V2 BUY/SELL structure path.

- Feature flag:
  - `HARMONIC_SPEC_V2_ENABLED = True`
- Unknown-regime block:
  - if `HARMONIC_BLOCK_UNKNOWN_REGIME` and regime is `UNKNOWN` -> no signal
- Harmonic zone:
  - nearest harmonic level is selected
  - `zone_half_width = max(level_tolerance, ATR * HARMONIC_ZONE_ATR_MULT)`
  - `zone_low = level - zone_half_width`
  - `zone_mid = level`
  - `zone_high = level + zone_half_width`
- Volume confirmation:
  - `volume_confirmed = resonance_strength >= HARMONIC_VOLUME_CONFIRM_MIN`
  - order: `WEAK < MODERATE < STRONG`
- BUY structure (`buy_acceptance`):
  - bullish candle (`close > open`)
  - `close > zone_high`
  - `open <= zone_high`
- SELL rejection structure (`sell_rejection`):
  - upper wick/body ratio `>= HARMONIC_REJECTION_WICK_BODY_RATIO`
  - `high >= zone_high`
  - bearish close below zone midline (`close < zone_mid` and `close < open`)
- SELL downtrend acceptance (`sell_bearish_acceptance_downtrend`):
  - downtrend is `SMA50 < SMA200` (fallback: negative SMA50 slope)
  - bearish candle
  - `close < zone_low`
- Regime matrix:
  - BUY allowed only in `TRENDING` or `EXPANSION`
  - SELL allowed when:
    - regime is `BALANCED` and `sell_rejection` is true, or
    - `sell_bearish_acceptance_downtrend` is true

All existing global gates remain active before direction selection:
- harmonic hit
- harmonic square policy
- volatility gate
- weighted score threshold
- confirmations threshold

---

## 15. Functionality Notes & Reference Code

Below is **reference pseudocode** showing how the system generates BUY / SELL signals.

```python
# --- Digital Root ---
def digital_root(n):
    if n == 0:
        return 0
    return 1 + (abs(n) - 1) % 9


# --- Phase Encoding ---
def price_phase(price_move):
    return digital_root(round(price_move))

def time_phase(bars_elapsed):
    return digital_root(bars_elapsed)


# --- Harmonic Squaring ---
def harmonic_square(price_move, bars_elapsed, harmonic_hit):
    if not harmonic_hit:
        return False
    return price_phase(price_move) == time_phase(bars_elapsed)


# --- Volatility Phase ---
def volatility_phase(current_atr, atr_mean):
    ratio = current_atr / atr_mean
    if ratio < 0.85:
        return "COMPRESSION"
    elif ratio <= 1.15:
        return "NORMAL"
    elif ratio <= 1.45:
        return "EXPANSION"
    else:
        return "EXTREME"


# --- Session Weighting ---
SESSION_WEIGHTS = {
    "ASIA": 0.7,
    "LONDON": 1.0,
    "NEW_YORK": 1.2,
    "DEAD_ZONE": 0.5
}

def weighted_resonance(resonance_strength, session):
    base = {"STRONG": 1.0, "MODERATE": 0.6, "WEAK": 0.0}[resonance_strength]
    return base * SESSION_WEIGHTS[session]


# --- Signal Gate ---
def signal_gate(harmonic_hit, squared, vol_phase, weighted_score, confirmations):
    return (
        harmonic_hit
        and squared
        and vol_phase != "EXTREME"
        and weighted_score >= 0.7
        and confirmations >= 2
    )


# --- BUY / SELL Logic ---
def generate_signal(context):
    if not signal_gate(**context["gates"]):
        return None

    if context["acceptance"]:
        return "BUY"

    if context["rejection"]:
        return "SELL"

    return None

