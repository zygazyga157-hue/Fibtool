# Candlestick Trading System — Entry Models Documentation

## Overview
This document defines **Model A (Close Entry)** and **Model C (Retrace Entry)** for integration into the candlestick signal system.

---

# Model A — Close Entry

## Concept
Enter immediately at the close of the signal candle.

## Rules

### BUY
- Entry = Close price of signal candle
- Stop Loss = Low of signal candle - buffer
- Take Profit = Entry + (Risk × RR)

### SELL
- Entry = Close price of signal candle
- Stop Loss = High of signal candle + buffer
- Take Profit = Entry - (Risk × RR)

## Characteristics
- High fill rate (100%)
- Captures fast momentum
- Lower reward-to-risk ratio
- Higher drawdown risk

## Best Use Case
- Strong signals (high score)
- Momentum markets
- Breakout conditions

---

# Model C — Retrace Entry

## Concept
Enter on a pullback into the signal candle.

## Rules

### BUY
- Entry = Low + 0.5 × (High − Low)
- Stop Loss = Low - buffer
- Take Profit = Entry + (Risk × RR)

### SELL
- Entry = High − 0.5 × (High − Low)
- Stop Loss = High + buffer
- Take Profit = Entry - (Risk × RR)

## Optional Enhancement
- Use 0.618 instead of 0.5 for deeper retracement

## Characteristics
- Lower fill rate
- Higher reward-to-risk ratio
- Better entry precision
- Lower drawdown

## Best Use Case
- Reversal signals
- Exhaustion patterns
- Ranging markets

---

# Comparison Summary

| Feature | Model A | Model C |
|--------|--------|--------|
| Entry Type | Immediate | Retrace |
| Fill Rate | High | Medium-Low |
| R:R | Medium | High |
| Risk | Higher | Lower |
| Best For | Momentum | Reversals |

---

# Integration Strategy

## Suggested Logic

```
if score >= 3.5:
    use Model A
elif score >= 2.0:
    use Model B
else:
    use Model C
```

## Advanced Strategy
- Run Model A and Model C simultaneously
- Cancel one order when the other triggers

---

# Notes
- Always apply spread and safety margin
- Use ATR filters to avoid large candles
- Combine with breakout score for validation
