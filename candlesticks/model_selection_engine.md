# Model Selection Engine (MSE) — Candlestick Trading System

## Overview
The Model Selection Engine (MSE) dynamically selects the best execution model:
- Model A (Close Entry)
- Model B (Breakout Entry)
- Model C (Retrace Entry)

It maps **market conditions → optimal entry strategy**.

---

# Inputs

## 1. Candlestick Score
```
abs_score = abs(score)
```

| Score | Interpretation |
|------|---------------|
| ≥ 3.5 | Strong |
| 2.0 – 3.5 | Moderate |
| < 2.0 | Weak |

---

## 2. Pattern Classification

### Momentum Patterns
- Marubozu
- Longline
- 3 White Soldiers

### Reversal Patterns
- Doji
- Hammer
- Harami
- Takuri

### Indecision Patterns
- SpinningTop
- HighWave
- Rickshawman

---

## 3. Volatility (ATR)
```
atr_ratio = ATR(14) / close_price
```

| State | Threshold | Meaning |
|------|-----------|--------|
| High | atr_ratio ≥ 0.02 (`MSE_ATR_RATIO_HIGH`) | Breakouts likely → boost Model B |
| Low | atr_ratio ≤ 0.005 (`MSE_ATR_RATIO_LOW`) | Compression → favor Model C |
| Medium | between thresholds | Normal — no adjustment |

### Volatility Effects
1. **Confidence modifier** (±0.05): When volatility aligns with the selected model (e.g., High + B, Low + C), confidence is boosted by +0.05. When misaligned (e.g., High + C, Low + B), it is penalized by −0.05.
2. **Default tie-breaker**: When no pattern, breakout, or Wyckoff signal is decisive, volatility determines the default model — High → B, Low → C, Medium → B.

---

## 4. Breakout Score

| Score | Meaning |
|------|--------|
| ≥ 0.75 | Strong |
| 0.5 – 0.74 | Valid |
| < 0.5 | Weak |

---

## 5. Wyckoff Phase

| Phase | Bias |
|------|------|
| Accumulation | Bullish |
| Distribution | Bearish |
| Phase 1 (ST) | Uncertain |

---

# Core Model Selection Logic

```python
def select_model(score, patterns, breakout_score, wyckoff, atr_ratio):
    abs_score = abs(score)
    volatility = classify_volatility(atr_ratio)  # high / medium / low

    momentum = count_momentum(patterns)
    reversal = count_reversal(patterns)

    if abs_score >= 3.5 and momentum > reversal:
        return "A", vol_adjust(0.85, "A", volatility)

    if breakout_score >= 0.6:
        return "B", vol_adjust(0.75, "B", volatility)

    if reversal >= momentum:
        return "C", vol_adjust(0.70, "C", volatility)

    if wyckoff in ["Accumulation", "Distribution"]:
        return "C", vol_adjust(0.65, "C", volatility)

    # Default: volatility breaks the tie
    if volatility == "high":
        return "B", vol_adjust(0.60, "B", volatility)
    if volatility == "low":
        return "C", vol_adjust(0.60, "C", volatility)

    return "B", 0.60
```

---

# Simplified Decision Model

```python
if abs_score >= 4:
    model = "A"
elif breakout_score >= 0.6:
    model = "B"
elif wyckoff in ["Accumulation", "Distribution"]:
    model = "C"
elif volatility == "high":
    model = "B"
elif volatility == "low":
    model = "C"
else:
    model = "B"
```

---

# Hybrid Execution Strategy

Primary Model + Secondary Model

Example:
Primary: B
Secondary: C

Execution:
- Place both orders
- Cancel the other when one triggers

---

# Telegram Output Format

🧠 Model Selected: B (Breakout)  
📊 Confidence: 0.78  
🔁 Backup Model: C (Retrace)  
🔴 Volatility: High

---

# System Architecture Integration

1. Data Collector  
2. Pattern Engine  
3. Score Generator  
4. Model Selection Engine (MSE)  
5. Entry Model (A/B/C)  
6. Execution Layer  

---

# Key Insights

- Model A = Momentum  
- Model B = Breakout  
- Model C = Retrace  

---

# Final Note

Signal Generator → Intelligent Trading System
