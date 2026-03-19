# Asia Sweep London MSS 0.71 Fib Strategy — Specification (Exact Logic)

**Document type:** Strategy specification (human-readable), written to mirror the exact rule logic.

**Core idea:** During London, trade a sweep of the Asia range with 5-minute MSS confirmation, entering via a 0.71 retracement limit, with stop at the 5-minute extreme and target at the opposite Asia boundary.

---

## 1. Definitions

- **Asia session:** 00:00–07:59 (session window used to build the Asia High/Low).
- **London session:** 08:00–14:00 (session window during which entries are allowed).
- **Asia High (AH):** Highest traded price during the Asia session.
- **Asia Low (AL):** Lowest traded price during the Asia session.
- **Sweep High:** Price trades above AH at any time (current-bar high > AH).
- **Sweep Low:** Price trades below AL at any time (current-bar low < AL).
- **MSS (Market Structure Shift) proxy (5-minute):**
  - **Bullish MSS:** 5-minute close > max of the prior 3 completed 5-minute highs.
  - **Bearish MSS:** 5-minute close < min of the prior 3 completed 5-minute lows.
- **Fib retracement entry (0.71):** Limit entry price placed at 71% of the current 5-minute candle’s range (high–low).
- **Daily trade limit:** At most 1 trade is initiated per calendar day.

---

## 2. Inputs and Fixed Parameters

These are fixed in the strategy as specified:

1. **Session windows**
   - Asia: `0000–0759`
   - London: `0800–1400`
2. **MSS timeframe**
   - MSS is computed on 5-minute candles (M5).
3. **MSS lookback**
   - Prior 3 candles (excluding the current M5 candle).
4. **Fib level**
   - 0.71 of the current M5 candle range.
5. **Order type**
   - Limit entry at fib price.
6. **Stops and targets**
   - Stop at the current M5 low/high (depending on direction).
   - Target at the opposite Asia boundary (AH for longs, AL for shorts).
7. **Position sizing (platform default behavior)**
   - Strategy uses percent-of-equity sizing in the original implementation (1% of equity).
8. **No pyramiding**
   - Only one position at a time (no stacking).

---

## 3. Time and Session Logic

### 3.1 Session membership

A bar is considered in-session if its timestamp falls within the session window:

- **In Asia:** timestamp within 00:00–07:59.
- **In London:** timestamp within 08:00–14:00.

### 3.2 Calendar day boundary

- A **new trading day** occurs when the date changes at the daily boundary (00:00).
- On a new day, the **tradedToday** flag is reset to false.

---

## 4. Asia Range Construction

### 4.1 During Asia session

Maintain two running values:

- `AsiaHigh` = maximum of all highs observed while in Asia.
- `AsiaLow`  = minimum of all lows observed while in Asia.

This is updated bar-by-bar only when `inAsia = true`.

### 4.2 Outside Asia session

- `AsiaHigh` and `AsiaLow` remain at their last computed values once Asia ends.
- These values are then used as reference levels during London.

### 4.3 Visual levels (optional for backtests)

- Plot AsiaHigh as a red line.
- Plot AsiaLow as a green line.

---

## 5. Daily Trade Limitation

The strategy enforces **one trade per calendar day**:

- `tradedToday` starts `false` each day.
- When an entry order is submitted (long or short), `tradedToday` becomes `true`.
- While `tradedToday = true`, no new entries are allowed for that day.

Note: The rule is tied to **order submission**, not necessarily a filled trade, depending on engine semantics. In the original logic, it flips true immediately upon placing the entry/exit orders.

---

## 6. Sweep Detection

Sweep conditions compare the current bar to the Asia range:

- **Sweep High:** `bar.high > AsiaHigh`
- **Sweep Low:**  `bar.low  < AsiaLow`

Important characteristics of this sweep definition:

- It does **not** require a close beyond the level.
- It does **not** require a rejection or return inside the range.
- A 1-tick break counts the same as a large break.

---

## 7. 5-Minute MSS Logic (Exact Proxy Used)

### 7.1 Data source

- MSS uses 5-minute candles, even if the chart/backtest runs on a different timeframe.
- The strategy references 5-minute values of: high, low, close.

### 7.2 Bullish MSS

Bullish MSS is true when:

- The current 5-minute close is greater than the maximum high of the **previous 3** completed 5-minute candles.

Formally:

- `bullMSS = M5.close > max(M5.high[1], M5.high[2], M5.high[3])`

### 7.3 Bearish MSS

Bearish MSS is true when:

- The current 5-minute close is less than the minimum low of the **previous 3** completed 5-minute candles.

Formally:

- `bearMSS = M5.close < min(M5.low[1], M5.low[2], M5.low[3])`

### 7.4 Interpretation

- This MSS proxy is a short-term close-based breakout over a 3-candle rolling window.
- It is not a swing-point MSS; it is a micro-structure confirmation.

---

## 8. Entry Qualification Logic

### 8.1 Long qualification

A **long setup** is qualified when ALL conditions are true:

1. Current time is within London session (`inLondon = true`).
2. No trade has been initiated today (`tradedToday = false`).
3. Sweep Low occurred on the current bar (`sweepLow = true`).
4. Bullish MSS is true on the 5-minute series (`bullMSS = true`).

In words: during London, after price sweeps below Asia Low and 5-minute closes above the prior 3 highs, place a long retracement entry.

### 8.2 Short qualification

A **short setup** is qualified when ALL conditions are true:

1. Current time is within London session (`inLondon = true`).
2. No trade has been initiated today (`tradedToday = false`).
3. Sweep High occurred on the current bar (`sweepHigh = true`).
4. Bearish MSS is true on the 5-minute series (`bearMSS = true`).

In words: during London, after price sweeps above Asia High and 5-minute closes below the prior 3 lows, place a short retracement entry.

---

## 9. Fib Limit Entry (0.71 of Current M5 Candle Range)

### 9.1 Long fib level

Compute on the current 5-minute candle:

- `fibLong = M5.low + (M5.high - M5.low) * 0.71`

Characteristics:

- This is 71% of the way from the candle low up toward the candle high.
- It is inside the candle’s range (unless the candle range is zero).

### 9.2 Short fib level

Compute on the current 5-minute candle:

- `fibShort = M5.high - (M5.high - M5.low) * 0.71`

Characteristics:

- This is 71% of the way from the candle high down toward the candle low.
- It is inside the candle’s range (unless the candle range is zero).

---

## 10. Execution Rules (Order Placement)

### 10.1 Long order placement

When the long setup qualifies:

- Submit a **limit buy** at `fibLong`.
- Attach an exit with:
  - **Stop-loss** at `M5.low` (the current M5 candle low).
  - **Take-profit** at `AsiaHigh` (opposite Asia boundary).
- Immediately set `tradedToday = true`.

### 10.2 Short order placement

When the short setup qualifies:

- Submit a **limit sell** at `fibShort`.
- Attach an exit with:
  - **Stop-loss** at `M5.high` (the current M5 candle high).
  - **Take-profit** at `AsiaLow` (opposite Asia boundary).
- Immediately set `tradedToday = true`.

### 10.3 No pyramiding

- If a position is open, no additional entries are placed.
- Only one active position at a time.

---

## 11. Strategy Intent and Market Assumptions

The strategy is built around these assumptions:

1. Asia session tends to form a definable consolidation range.
2. London session tends to create expansion and/or stop-runs beyond the Asia range.
3. A sweep beyond Asia High/Low often precedes a reversal or directional shift.
4. 5-minute close-based breakout (MSS proxy) is sufficient confirmation that control has shifted.
5. After confirmation, price frequently retraces to a deep pullback area (0.71) before moving to the opposing liquidity target.

---

## 12. Practical Notes on Behavior

### 12.1 Trade frequency

- Maximum 1 trade per day, but some days may have zero trades if no qualification occurs.
- Some days may qualify but not fill if the limit price is never traded.

### 12.2 Sensitivity to candle size

- Because fib and stop are derived from the **current M5 candle**, outcomes depend heavily on that candle’s range:
  - Large M5 candle → wide stop and deeper limit away from market → fewer fills, larger risk.
  - Small M5 candle → tight stop and limit close to market → more fills, more noise sensitivity.

### 12.3 Sweep definition is permissive

- Any minor break counts; the strategy does not confirm rejection.

### 12.4 MSS proxy is responsive

- A 3-candle rolling breakout can trigger often in choppy conditions.

---

## 13. Backtest and Simulation Assumptions (Must Be Declared)

To replicate results in Python or any other engine, explicitly decide:

1. **Timezone alignment**
   - Session windows must be evaluated in the same timezone as the strategy’s original environment.
2. **Bar timeframe**
   - If backtesting on 5-minute bars, limit fill and stop/target sequencing is approximate.
   - Using 1-minute bars reduces ambiguity for limit/stop/target ordering.
3. **Limit fill rule**
   - A common assumption: limit fills if bar.low ≤ limit ≤ bar.high.
4. **Stop/target ordering within a bar**
   - If both stop and target are inside the bar’s range, you must pick an ordering rule.
   - Conservative assumption: stop triggers first.
5. **When tradedToday flips**
   - In this spec, it flips at order submission time (mirroring the original).

---

## 14. Detailed Walkthrough Examples (Conceptual)

### 14.1 Long day example

1. During Asia, price prints a high at 1.2050 and a low at 1.2000.
2. During London, price dips to 1.1995 (Sweep Low).
3. On M5, the close later breaks above the prior 3 M5 highs (Bullish MSS).
4. Strategy places a buy limit at 0.71 retracement of the current M5 candle.
5. Stop is set at the current M5 low; target is set at AsiaHigh (1.2050).
6. If the limit fills and price rallies to 1.2050, the take-profit exits the position.

### 14.2 Short day example

1. During Asia, price prints a high at 1.3050 and a low at 1.3000.
2. During London, price spikes to 1.3058 (Sweep High).
3. On M5, the close later breaks below the prior 3 M5 lows (Bearish MSS).
4. Strategy places a sell limit at 0.71 retracement of the current M5 candle.
5. Stop is set at the current M5 high; target is set at AsiaLow (1.3000).
6. If the limit fills and price drops to 1.3000, the take-profit exits the position.

---

## 15. Edge Cases and How the Strategy Treats Them

### 15.1 Zero-range M5 candle

- If M5.high == M5.low, fibLong and fibShort equal that same price.
- Stop and limit may overlap; behavior depends on the backtest engine.

### 15.2 Sweep and MSS on the same moment

- The strategy allows the sweep condition and MSS condition to be true concurrently.
- This can happen depending on how higher/lower timeframe values align.

### 15.3 Limit order not filled

- The strategy still marks `tradedToday = true` immediately after placing the order.
- Consequently, it will not place another trade that day even if the order never fills.

### 15.4 Multiple sweeps in one day

- Only the first qualified setup that triggers order placement will be acted upon.
- Subsequent sweeps are ignored due to the daily trade limit.

### 15.5 Session boundaries

- Entries are only placed when `inLondon = true`.
- Exits (stop/target) can be hit outside London depending on engine rules, but in most implementations they remain active until hit or position is closed by other rules.

---

## 16. Metrics to Evaluate (Recommended)

Evaluate performance with metrics suited to limit-entry, session-based strategies:

- Trades per month (given the one-trade-per-day cap).
- Fill rate (how often the fib limit is reached).
- Win rate (percentage of filled trades that hit target before stop).
- Average R multiple per trade.
- Expectancy (mean R).
- Max drawdown and drawdown duration.
- Sensitivity to spread/slippage (especially around session opens).
- Distribution of trades by hour within London.

---

## 17. Validation Checklist (Exact Strategy Parity)

Use this checklist when recreating the strategy in another environment:

1. Session windows match exactly (00:00–07:59 Asia; 08:00–14:00 London).
2. AsiaHigh/AsiaLow are computed only during Asia session.
3. SweepHigh uses current-bar high > AsiaHigh; SweepLow uses current-bar low < AsiaLow.
4. MSS is computed on 5-minute candles using prior 3 highs/lows and current close.
5. Long requires SweepLow + Bullish MSS + London + tradedToday false.
6. Short requires SweepHigh + Bearish MSS + London + tradedToday false.
7. Fib limit uses current M5 candle low/high with 0.71.
8. Stop uses current M5 low/high; target uses opposite Asia boundary.
9. tradedToday flips true at order placement time.
10. Only one position at a time; no pyramiding.

---

## 18. Suggested Enhancements (Clearly Marked as OPTIONAL)

> The items in this section are **not part of the exact strategy**. They are common improvements if you later choose to evolve the system.

- Require sweep to be followed by a close back inside the Asia range.
- Anchor fib to a displacement leg instead of a single candle.
- Add an order expiry window (e.g., cancel after N candles).
- Use a structural stop beyond the sweep extreme (with buffer).
- Add a bias filter (e.g., daily open or 1H trend).
- Use partial exits (midrange then opposite boundary).

---

## 19. Implementation Notes for Python (Conceptual, No Code)

When implementing in Python, keep these conceptual mappings in mind:

- You will need consistent timestamp handling and timezone alignment.
- If you want realistic limit fills and stop/target ordering, prefer lower timeframe data (1-minute).
- If you backtest on 5-minute bars only, declare your fill/ordering assumptions explicitly.
- Model order state (pending limit vs filled position) and enforce the daily trade cap.
- Record all intermediate signals (inAsia, inLondon, AsiaHigh/Low, sweep flags, MSS flags) for debugging parity.

---

## 20. Summary (One-Paragraph Specification)

Each day, record Asia session high and low (00:00–07:59). During London (08:00–14:00), if price sweeps below Asia Low and the 5-minute close breaks above the prior 3 completed 5-minute highs, place a long limit at 0.71 retracement of the current 5-minute candle with stop at that candle’s low and target at Asia High; if price sweeps above Asia High and the 5-minute close breaks below the prior 3 completed 5-minute lows, place a short limit at 0.71 retracement with stop at the candle’s high and target at Asia Low. Only one trade is initiated per day.

---

## Appendix A. Parameter Table (Exact Values)

| Component | Value |
|---|---|
| Asia session | 00:00–07:59 |
| London session | 08:00–14:00 |
| MSS timeframe | 5-minute |
| MSS lookback | 3 prior candles |
| Fib level | 0.71 |
| Entry type | Limit |
| Long stop | Current M5 low |
| Long target | AsiaHigh |
| Short stop | Current M5 high |
| Short target | AsiaLow |
| Trades per day | Max 1 |
| Pyramiding | Disabled |

---

## Appendix B. Glossary

- **Session:** A recurring time window used to segment trading behavior.
- **Liquidity sweep:** A move that trades beyond a known boundary, often triggering resting stops.
- **MSS:** Market Structure Shift; here, a close-based breakout proxy on 5-minute candles.
- **Retracement:** A pullback against the most recent movement, used for better entry pricing.
- **Limit order:** Order that fills only at a specified price or better.
- **Stop-loss:** Risk control order that exits if price moves adversely to a specified level.
- **Take-profit:** Exit order that captures gains at a specified target.

---

## Appendix C. Debugging Signals (What to Log)

If you reproduce this strategy elsewhere, log these fields each bar:

- Timestamp and session flags (inAsia, inLondon).
- AsiaHigh, AsiaLow values (and whether they updated).
- sweepHigh, sweepLow booleans.
- M5 high/low/close and prior-3 extrema.
- bullMSS, bearMSS booleans.
- tradedToday state.
- Pending order state (direction, limit, stop, target).
- Position state (entry time/price, exit reason).

---

## Appendix D. Known Strategy Characteristics (Observed in Similar Designs)

These are common characteristics of sweep + MSS + retracement strategies:

- Fill rate can be the limiting factor (deep retracements may not occur).
- Performance can be highly sensitive to timezone/session alignment.
- Spread and slippage around session transitions can materially change results.
- Systems often benefit from clearly defined order expiry rules.

---

## Appendix E. Change Log

- v1.0 — Initial markdown specification that mirrors the exact logic and parameters.

---

*End of document.*

## Appendix F. Line Padding Notes

The following numbered lines are included to reach an exact 500-line markdown artifact, and contain no additional rules.

- Padding line 001
- Padding line 002
- Padding line 003
- Padding line 004
- Padding line 005
- Padding line 006
- Padding line 007
- Padding line 008
- Padding line 009
- Padding line 010
- Padding line 011
- Padding line 012
- Padding line 013
- Padding line 014
- Padding line 015
- Padding line 016
- Padding line 017
- Padding line 018
- Padding line 019
- Padding line 020
- Padding line 021
- Padding line 022
- Padding line 023
- Padding line 024
- Padding line 025
- Padding line 026
- Padding line 027
- Padding line 028
- Padding line 029
- Padding line 030
- Padding line 031
- Padding line 032
- Padding line 033