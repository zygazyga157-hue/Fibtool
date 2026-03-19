# Session-Based Execution & Capital Plan

## Objective
Deploy the harmonic–square–confluence trading system with **maximum structural edge**, **minimal noise**, and **strict capital discipline**, starting **February 1**. The system will only execute **non-null signals** and will remain inactive otherwise.

This document defines:
- When the server should be ON / OFF
- Which sessions provide the highest-quality signals
- Capital deployment assumptions
- Position limits and consistency rules

---

## Core Philosophy

> *We trade anticipation, not recognition.*

The system performs best when:
- Liquidity is present but not chaotic
- Volatility is emerging, not extreme
- Institutions are positioning, not distributing

Therefore, session selection is critical.

---

## Session Selection (MOST IMPORTANT)

### 1. Primary Execution Window (HIGH PRIORITY)

**London Session (08:00–11:00 UTC)**

This is the *core execution window*.

Why:
- Institutional positioning begins
- Metals and FX respect structure
- Volatility transitions from compression → expansion
- Harmonics and Square-of-Nine align cleanly

**Server State:**
- ✅ ON
- Full signal evaluation
- All symbols enabled

---

### 2. Secondary Execution Window (CONDITIONAL)

**London–New York Overlap (12:00–15:00 UTC)**

Used primarily for:
- Campaign continuation
- Confirmation of earlier signals
- Management of open positions

Why:
- Peak liquidity
- Strong continuation moves
- Risk transfer often occurs here

Rules:
- New positions ONLY if:
  - Signal is non-null
  - Not EXTREME volatility OR is early EXTREME with clear asymmetry

**Server State:**
- ✅ ON
- Slightly stricter filters

---

### 3. New York Late Session (LOW PRIORITY)

**15:00–17:00 UTC**

Purpose:
- Monitoring only
- No new trades unless exceptional

Why:
- Late participation
- Increased chance of distribution
- Reduced structural clarity

**Server State:**
- ⚠️ ON (monitoring mode)
- ❌ No new entries by default

---

### 4. Asian Session (OFF)

**00:00–06:00 UTC**

Why OFF:
- Thin liquidity for metals
- Crypto noise dominates
- Harmonic distortions common
- Poor risk asymmetry

**Server State:**
- ❌ OFF

---

## Symbol-Specific Session Bias

| Symbol Group | Preferred Session |
|------------|------------------|
| XAUUSD / XAGUSD | London → Early NY |
| FX Majors | London |
| Crypto (ETH/BTC) | London overlap only |
| Crosses | London only |

---

## Capital & Position Framework (BASELINE)

### Assumptions
- Average: **6 positions per month**
- All positions sized to **0.01 XAUUSD-equivalent risk**
- No compounding
- No pyramiding

### Exposure Rules
- Max positions per symbol: **2**
- Max total open positions: **4**
- No correlated stacking (e.g., Gold + Silver + BTC all at once)

---

## Position Sizing

- Reference unit: **0.01 lot XAUUSD**
- Less volatile symbols are sized UP to match gold volatility
- More volatile symbols (crypto) are sized DOWN accordingly

Sizing is always:

```
Risk-based, stop-defined, structure-invalidated
```

If broker minimum lot > required lot → **trade is skipped**.

---

## Monthly Expectation (Conservative)

- Avg trades: 6
- Avg return per trade: $300–400

**Expected monthly range:**
- $1,800 – $2,400

**Annual (Feb–Dec):**
- $20,000 – $30,000 (no scaling)

---

## Consistency Rules (MANDATORY)

1. Null signal = No trade (no exceptions)
2. Only trade during defined sessions
3. One signal = one decision (no re-interpretation)
4. No size increase mid-year
5. No emotional overrides after wins
6. First loss changes nothing

---

## What This Plan Protects

- Structural edge
- Psychological stability
- Capital survival
- Scalability potential

---

## Review Cadence

- Weekly: behavioral review (not PnL)
- Monthly: signal quality review
- Quarterly: drawdown & expectancy check

No parameter changes during the year.

---

## Final Statement

> *Silence is a position.*

The system is allowed to do nothing most days.
That inactivity is what funds the rare moments of precision.

---

**Start Date:** February 1
**Duration:** 12 months
**Rule:** Execute exactly as written

---

# Appendix A — Daily Execution Checklist (One Page)

## Pre-Session Checklist (Before London Open)

- [ ] Server OFF until session window
- [ ] Review overnight volatility (no action taken)
- [ ] Confirm today’s active session window
- [ ] Confirm capital limits unchanged
- [ ] Confirm no emotional bias from prior day
- [ ] Confirm: *Only non-null signals are actionable*

If any box cannot be checked → **Do not trade today**.

---

## In-Session Checklist (Server ON)

- [ ] Is the session within allowed window?
- [ ] Is the signal **non-null**?
- [ ] Is volatility phase acceptable?
- [ ] Is this the first position on the symbol?
- [ ] Does position size respect gold-equivalent 0.01 risk?
- [ ] Is stop defined by structure (not discretion)?

If any answer is NO → **No trade**.

---

## Post-Session Checklist (Server OFF)

- [ ] Server switched OFF outside window
- [ ] Trades logged (if any)
- [ ] No review of PnL beyond logging
- [ ] Emotional state neutral
- [ ] No strategy changes considered

---

# Appendix B — Trade Log Template

Each executed trade must be logged exactly as follows:

```
Date:
Symbol:
Session:
Signal Type (BUY/SELL):
Volatility Phase:
Regime:
Resonance Strength:
Lot Size:
Stop Distance:
Risk ($):
Outcome (R-multiple):
Notes (objective only):
```

Rules:
- No subjective language
- No hindsight commentary
- No changes after entry

---

# Appendix C — Loss Protocol (MANDATORY)

## Definition of a Loss
A loss is defined as:
- Full structural stop hit
- Or forced exit due to invalidation

## Protocol After First Loss

- No parameter changes
- No lot size changes
- No reduction in confidence
- No increase in selectivity
- No revenge trading

Action steps:
1. Log the loss
2. Confirm rules were followed
3. Resume trading normally

If rules were followed → **Loss is accepted as valid**.

---

# Appendix D — Year 2 Scaling Appendix (INACTIVE)

> *This section is informational only. It is not to be executed during Year 1.*

## Eligibility Criteria for Scaling

Scaling may be considered only if:
- Minimum 12 months completed
- At least one full loss cycle experienced
- Rules followed with zero deviations
- Drawdown remained within tolerance

## Allowed Scaling Methods (Choose One Only)

### Option 1: Lot Increment
- Increase base size from 0.01 → 0.02
- Hold for minimum 90 days before further change

### Option 2: Parallel Accounts
- Duplicate strategy across multiple accounts
- Identical rules, identical sizing

## Prohibited Actions

- No pyramiding
- No increased frequency
- No loosening of signal requirements
- No trading null signals

---

## Final Reminder

> *Consistency is the strategy.*

Scaling is a reward for discipline, not performance.

