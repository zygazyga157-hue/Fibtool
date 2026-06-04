# Executive Summary

This report analyzes the sample candlestick and harmonic signals and proposes improvements for Telegram alerts and stop/take-profit (TP/SL) rules. We extract and compare key fields from the provided records, design a comprehensive Telegram message template (including confirmations, confluence, ATR multiples, expected fill probability, position sizing suggestions, etc.), and survey four TP/SL methods suited to a hybrid harmonic–candlestick system. We recommend evaluation metrics and a backtest plan for these methods, present an implementation roadmap (with pseudocode), and suggest logging enhancements. The goal is to create a data-driven, “institutional-quality” signaling framework that combines price structure and volatility. 

Key findings:

- **Signal Confluence Matters:** When the candlestick (Hammer) and harmonic signals both triggered a USDCHF long, this “confluence” (two independent systems agreeing) strongly supports a trade. We will highlight confluence in the alerts.  
- **Impulse/ATR Filters:** The candlestick engine’s 0.8 ATR “impulse” threshold successfully filtered out weak signals (e.g. the GBPJPY case) and should generally remain high to ensure meaningful moves.  
- **Entry/Stop Placement:** The harmonic signals use extremely wide stops (≈25–28 ATR) versus the candlestick signal’s ≈1–1.5 ATR. We will explore methods (e.g. pattern invalidation stops, ATR multiples, trailing stops) that yield tighter, volatility-adjusted exits.  
- **TP Strategy:** Harmonic patterns traditionally use Fibonacci points (A, B, C) for TPs, whereas a pure ATR-based system would target fixed multiples or use structure. We consider both.  
- **Telegram Format:** We introduce a rich alert format including “resonance,” regime, volume phase, squared flag, score, confirmation count, ATR-based entries/stops/TPs, and confidence/position-size guidance. Three example alerts (one candlestick Hammer, two harmonic) are provided.  

This report is structured as follows:

1. **Extracted Signal Data (Comparison Table).** Key fields from the sample candlestick and harmonic records are normalized and tabulated for easy comparison.  
2. **Telegram Message Template & Examples.** A proposed message layout is given, along with 3 examples drawn from the provided data.  
3. **TP/SL Methods.** We describe 4 candidate stop/profit schemes (ATR-based, harmonic-zone, volatility-adjusted, ladder/trailed) with rationale, formulas, pros/cons, and parameter guidance.  
4. **Evaluation Plan.** We outline metrics (win rate, expectancy, drawdown, time-in-trade, fill rate) and simulation steps to compare methods, including a comparison table and a Mermaid flowchart of the trade lifecycle.  
5. **Implementation Pseudocode.** We give code-level pseudocode for generating Telegram payloads, computing risk metrics, and selecting TP/SL rules.  
6. **Logging & Data Plan.** We recommend additional log fields (`filled`, `minutes_until_fill`, `retracement_ratio`, `sl_atr_multiple`, `signal_confluence`, etc.) and outline a sample-size collection strategy for robust evaluation.  

Throughout, we cite authoritative sources on ATR stops, harmonic pattern exits, and volatility-based stops to ground our recommendations. The tone is analytical and implementation-focused. 

## 1. Signal Data Comparison

The table below consolidates the key fields from the three sample signals:

- **USDCHF Candlestick (Hammer)** – long @2026-06-03 13:48 UTC.  
- **USDCHF Harmonic #1** – long signal @2026-06-03 14:43 UTC.  
- **USDCHF Harmonic #2** – long signal @2026-06-03 16:47 UTC.  

Each column corresponds to one of these signals, with rows for relevant attributes. (Fields not applicable to a signal are left blank.)

| Field                   | USDCHF Hammer (Candlestick) | USDCHF Harmonic #1           | USDCHF Harmonic #2          |
|-------------------------|-----------------------------|------------------------------|-----------------------------|
| **Time**                | 2026-06-03 13:48 UTC        | 2026-06-03 14:43 UTC         | 2026-06-03 16:47 UTC        |
| **Symbol**              | USDCHF                      | USDCHF                       | USDCHF                      |
| **Side**                | Long                        | Buy                          | Buy                         |
| **Pattern / Harmonic**  | CDLHAMMER (Bullish Hammer)  | Harmonic: 54×3 (Bullish)     | Harmonic: 54×3 (Bullish)    |
| **Score**               | 4.40                        | 1.20                         | 1.20                        |
| **Confirmations**       | – (none)                    | 2                            | 2                           |
| **Regime**              | –                           | TRENDING                     | TRENDING                    |
| **Resonance**           | –                           | STRONG                       | STRONG                      |
| **Squared**             | –                           | ❌ (False)                   | ❌ (False)                  |
| **Volume Phase**        | –                           | COMPRESSION                  | COMPRESSION                 |
| **Gates Passed**        | Eligible (candles)          | Hit✅ Squared❌ VolOK ScoreOK  | Hit✅ Squared❌ VolOK ScoreOK |
| **ATR**                 | 0.0004529                   | 0.0007929                    | 0.0009271                   |
| **Range/Move**          | Range ATR = 0.839 (candlestick range ≈0.00038) | Price move = 221 pts (0.002210, ~2.79 ATR) | Price move = 257 pts (0.00257, ~2.77 ATR) |
| **Spread (pips)**       | 0.2 pips                    | n/a                          | n/a                         |
| **Entry**               | 0.78990 (limit order)       | 0.79063                      | 0.79215                     |
| **SL**                  | 0.78930                     | 0.76876                      | 0.77028                     |
| **TP1 / TP2**           | 0.79210 (TP only)           | 0.82344 / 0.83437            | 0.82496 / 0.83589           |
| **RR1 / RR2**           | 3.67                        | 1.5 / 2.0                    | 1.5 / 2.0                   |
| **Entry Δ (ATR)**       | 0.861                        | (Entry vs. Anchor) ~0.862 ATR¹| ~0.862 ATR (entry vs. anchor)¹ |
| **SL ATR Mult.**        | 1.325                       | 27.57                        | 23.57                       |
| **Entry->SL Δ**         | 0.00060                     | 0.02187                      | 0.02187                     |
| **Entry->TP Δ**         | 0.00220                     | 0.03280 / 0.04374            | 0.03281 / 0.04374           |
| **Entry Dist. ATR**     | 0.861 (deep retrace)        | n/a                          | n/a                         |
| **Spread (USDCHF)**     | 2e-05 (~0.2 pip)            | n/a                          | n/a                         |
| **Model**               | C (conf: 0.75)              | C (conf: 0.75)               | C (conf: 0.75)              |
| **Execution**           | Limit order, *sent*         | Signal generated (no order)  | Signal generated (no order) |
| **Filled/Active**       | Pending fill (limit not hit) | NA                           | NA                          |

¹ *For harmonics, entry vs. anchor ATR:* Using anchor price as reference (0.78842 for #1, 0.78958 for #2) and respective ATRs, entry-distances are ~0.86 ATR for each.

Some observations from the table:
- The **candlestick signal** has a much tighter stop (≈1.3 ATR) and uses a limit entry requiring ~0.86 ATR pullback, which may explain why it *has not been filled* yet. 
- The **harmonic signals** both propose extremely wide stops (~24–28 ATR) and much larger point moves (221–257 points, ~2.8 ATR). Both have identical risk of 0.02187 (~218 pips) despite different anchors. This suggests a fixed stop-distance logic. 
- Both harmonic setups share identical gates (score, confirmations, etc.), even though the market moved. The entry price shifted upward with price (0.79063 → 0.79215) but risk remained 0.02187, meaning the SL must have risen equally. This hints at a rigid stop placement (e.g. based on a fixed count of bars or an initial anchor rather than current market). We will revisit this in the TP/SL design.
- All signals show very high Reward/Risk (>3R for Hammer, 1.5–2R for harmonic). The candlestick mode favored larger RR, the harmonic used fixed Fibonacci targets (A, B levels).
- **Confluence:** Two independent systems agree on bullish USDCHF. We will highlight such confluence to add confidence. 

*Sources:* ATR-based stops often use fixed multiples; harmonic patterns traditionally stop at point X (pattern invalidation) and target points A/B/C.

## 2. Telegram Message Template & Examples

### 2.1 Message Template

We propose a structured Telegram signal format that encapsulates all key information in a readable layout. Each signal should include:

- **Header:** Signal type (e.g. “🔥 HARMONIC SIGNAL” or “🔥 CANDLE SIGNAL”), side and symbol, timestamp.  
- **Context Tags:** Regime, Volume phase, Resonance, Squared (if applicable), Confirmations, Score.  
- **Entry/Exit Details:** Entry price (with order type and ATR distance), Stop Loss price (with ATR multiple), Take-Profit levels (with ATR multiples and RR). Also show breakeven level if relevant (e.g. 0.618R).  
- **Additional Metrics:** Spread (pips), retracement ratio (entry pullback relative to ATR), expected fill probability (qualitative), model selected and confidence, implied position sizing or confidence level.  
- **Confluence & Notes:** Indicate if a concurrent candlestick pattern confirmed a harmonic signal (or vice versa), which adds weight. Possibly include friendly advice.  

All numeric values should be accompanied by ATR multiples or RR for clarity. We use emojis and markdown for readability. For example:

```
🔥 SIGNAL (type)   

🟢 BUY/🔴 SELL SYMBOL – HH:MM UTC (Time)  
📊 Regime: <TRENDING/CONSOLIDATION> | Vol: <PHASE> | Resonance: <STRONG/WK>  
🔲 Squared: ✔/❌ (bars, anchor) | ✔ Confirmations: N | Score: X.XX  

💎 Confluence: <CandlePattern + Harmonic?> (e.g. Hammer + Harmonic)  
🎯 Entry: `0.78990` (limit, 0.86 ATR retrace)  
🛑 Stop: `0.78930` (−0.60%) [1.33×ATR]  
🎯 TP1: `0.79210` (+0.00220, RR3.67)  
(➕ Breakeven @ +0.67×ATR)  
👤 Model: C (0.75) – Confidence: **High** (adjust risk ↑)  
⚡ Est. Fill Prob: **Low** (limit entry far)  
📉 RR: 3.67 : 1, Risk=0.06% of acct (↓ size if low conf)  
```

Each part is designed to be human-readable on Telegram. We place ATR multiples and RR next to prices (e.g. “[1.33×ATR]”, “RR3.67”) for clarity. The “Confluence” line highlights if both harmonic and candle signals agree. A sample template using markdown might look like:

```
🔥 *HARMONIC SIGNAL*  

🟢 *BUY USDCHF* – 2026-06-03 14:43 UTC  
📊 Regime: *TRENDING* | Vol: *COMPRESSION* | Resonance: *STRONG*  
🔲 Squared: ❌ (bars=3, swing_low) | ✔ Confirmations: 2 | Score: 1.20  

💡 *Confluence:* Hammer pattern on H1 reinforces this harmonic buy.  
🎯 *Entry:* 0.78990 (limit, needs 0.86×ATR retrace)  
🛑 *SL:* 0.78930 (−0.001†, ~1.33×ATR)  
💰 *TP:* 0.79210 (+0.0022, RR=3.67×)  

💬 *Notes:* Model C says bullish (conf=0.75). High ATR range but only moderate candlesize. Expect ~30% fill chance. Consider *increase* size slightly if filled, given strong confluence. 
```

*(Formatting uses bold, italics, emojis, and code-style to delineate values.)*

### 2.2 Example Messages

Using the above format, we fill in data from our sample signals. We also illustrate a pure candlestick alert. 

1. **Candlestick Signal (USDCHF Hammer)**

```
🔥 CANDLESTICK PATTERN

🟢 *BUY USDCHF* – 2026-06-03 13:48 UTC  
📊 Regime: *N/A* | Vol: *MODERATE* | Resonance: *N/A*  
🔲 Squared: N/A | ✔ Confirmations: N/A | Score: 4.40  

🎯 Entry: 0.78990 (limit @Hammer low, 0.86×ATR retrace)  
🛑 SL: 0.78930 (–0.00060, ~1.33×ATR)  
💰 TP: 0.79210 (+0.00220, RR=3.67×)  

📈 *Pattern:* Bullish **Hammer** confirmed by model C (conf=0.75).  
⚡ *Fill Prob:* **Low** (deep limit). Consider entry if retraced.  
💰 *RR:* 3.67. Volume is tight (only 0.2 pip spread). Position size = 0.6% for 1R risk.
```

2. **Harmonic Signal #1 (USDCHF)**

```
🔥 HARMONIC PATTERN

🟢 *BUY USDCHF* – 2026-06-03 14:43 UTC  
📊 Regime: *TRENDING* | Vol: *COMPRESSION* | Resonance: *STRONG*  
🔲 Squared: ❌ (bars=3, swing_low) | ✔ Confirmations: 2 | Score: 1.20  

💎 *Confluence:* High. Hammer pattern also formed on this swing low.  
🎯 Entry: 0.79063 (market/limit at zone)  
🛑 SL: 0.76876 (–0.02187, ~27.6×ATR)  
💰 TP1: 0.82344 (+0.03281, RR=1.50×)  
💰 TP2: 0.83437 (+0.04374, RR=2.00×)  

💬 *Notes:* Low stress, strong pattern. Model C (0.75) supports long. Very wide SL (28×ATR) means small size (0.2% risk for 1R). 
```

3. **Harmonic Signal #2 (USDCHF)**

```
🔥 HARMONIC PATTERN

🟢 *BUY USDCHF* – 2026-06-03 16:47 UTC  
📊 Regime: *TRENDING* | Vol: *COMPRESSION* | Resonance: *STRONG*  
🔲 Squared: ❌ (bars=2, swing_low) | ✔ Confirmations: 2 | Score: 1.20  

💎 *Confluence:* Still bullish. Follows previous harmonic entry.  
🎯 Entry: 0.79215 (market/limit at zone)  
🛑 SL: 0.77028 (–0.02187, ~23.6×ATR)  
💰 TP1: 0.82496 (+0.03281, RR=1.50×)  
💰 TP2: 0.83589 (+0.04374, RR=2.00×)  

📊 *Performance:* Volume OK, model C (0.75) says long. Wider SL than last entry (24×ATR). Consider light sizing.
```

In these examples, we highlight key metrics and use **bold text** for emphasis. We include qualitative assessments (e.g. “Fill Prob: Low/High”) to guide the trader. Position sizing advice (e.g. “0.6% for 1R risk”) ties risk to ATR-based stops.

## 3. TP/SL Methods

We consider four candidate TP/SL schemes suitable for a hybrid harmonic–candlestick system. Each method combines volatility (ATR) considerations with pattern structure. We evaluate formula, rationale, pros/cons, and parameter guidance.

1. **Fixed-ATR Stops & Targets:**  
   **Description:** Set stop-loss and take-profit at fixed multiples of ATR. For example, SL = *k*×ATR away from entry; TP = *m*×ATR. A common rule is SL = 1–3×ATR and TP = 2–4×ATR. Alternatively, use a fixed RR (e.g. 1:2 or 1:3).  
   **Formula:**  
   - SL = Entry – *k*·ATR (for long; reverse sign for short).  
   - TP = Entry + *m*·ATR.  
   - Suggested: *k*=1–2 for initial SL, *m*=2–3 for TP. Wilder originally used ~3×ATR for trailing stops.  
   **Pros:** Simple, volatility-adaptive stops. Easy to adjust risk by changing *k*. Uniform across symbols.  
   **Cons:** Ignores actual swing points or harmonic zones. If ATR is very low/high, may be too tight/wide. Might cut off winners on big moves or keep losing trades open. Needs tuning per instrument/timeframe.  
   **Use Case:** Acts as a baseline. Could be combined with trailing rules (see method 4).  

2. **Harmonic-Pattern Stops/Targets:**  
   **Description:** Use the harmonic pattern’s structure: place SL just beyond the invalidation point (swing point X), and set TP targets at preceding swing highs/lows (points A, B, C). This follows conventional harmonic rules.  
   **Formula:**  
   - SL = X ± offset (just beyond X, the last extreme before pattern).  
   - TP1 = point A, TP2 = point B (if exists). Optionally TP3 = point C.  
   - E.g., if pattern is bullish: Entry at D, Stop = X – ε, TP1=A, TP2=B, etc.  
   **Pros:** Directly tied to price action. The stop is the “pattern invalidation” (beyond X), providing conceptual justification. Targets are specific swing points (A/B/C) with high likelihood, often used by practitioners.  
   **Cons:** Requires identifying the pattern points (which we have). The stop can be very wide if swings are distant (as seen in our USDCHF example). The TP may be too conservative (only 1–2 R). Without trade management, profit is limited to pattern geometry.  
   **Use Case:** Best for pure harmonic signals. For our hybrid system, we can still compute “point X” from anchor to entry and use that as SL, then sell portions at Fib levels. For example, Method 2 for USDCHF #1 would put SL at ~0.787 (swing low) rather than 0.768.  

3. **Volatility-Adjusted Stops:**  
   **Description:** Adjust stops based on recent volatility or regime. E.g. multiply ATR by a factor dependent on volatility state. For instance, SL = Entry – (*k*·ATR·V) where *V* could be a function of ATR itself (e.g. current ATR/mean ATR) or a volatility index. The idea is to give more room in high volatility and tighten in calm conditions.  
   **Formula (example):**  
   - Compute mean ATR (e.g. 14-period) and current ATR. Let *V* = current_ATR / mean_ATR. Then SL = Entry – (*k*·ATR·*V*).  
   - Alternatively use an ATR-based trailing filter: if ATR spikes, increase SL proportionally.  
   **Pros:** Dynamically scales risk to market. In calm markets, stops can be tighter (higher win rate), while in choppy markets they automatically widen (fewer stop-outs). Aligns with volatility-based risk management.  
   **Cons:** More complex; requires choosing how to measure volatility. If ATR is unusually low then a too-tight stop may be used. Ratio *V* must be smoothed to avoid whipsaw. May be overkill for instruments with stable vol.  
   **Use Case:** Could override the fixed *k* in Method 1. For example, if USDCHF volatility doubles, *V*=2 and SL=2·k·ATR. Could also combine with ATR trailing (see Method 4).  

4. **Dynamic Trailing / Laddered Targets:**  
   **Description:** Combine partial profit-taking with moving stops. For example, scale out at multiple TP levels, then move SL to breakeven or trail by ATR. This is common in institutional trading: take some profit early and let the rest run.  
   **Formula:**  
   - E.g. SL initially at *k*·ATR. Once price reaches TP1 (or +1R), move SL to entry (breakeven). If price hits TP2, shift SL to TP1, etc. Or use an ATR trailing stop after TP1.  
   - An ATR trailing stop (like Welles Wilder’s ATR stop) can be used: on each new high (for long), set SL = current_price – *k*·ATR, for some *k* (often 3).  
   **Pros:** Locks in gains and adapts to trend continuation. Partial exit reduces risk. ATR trailing protects profits without a rigid target.  
   **Cons:** Requires active management or automation. May reduce overall RR if scaling out too early. Choosing when and how much to trail adds complexity.  
   **Use Case:** After a harmonic entry, take 50% at TP1=A, then trail the rest. If ATR=0.0009 and *k*=2, then after A is hit, set SL = high – 2·ATR.  

**Table: Comparing TP/SL Methods**

| Method                   | Stop (Long)                          | TP Targets                           | Pros                                 | Cons                                |
|--------------------------|--------------------------------------|--------------------------------------|--------------------------------------|-------------------------------------|
| **Fixed-ATR**            | Entry − *k*·ATR (e.g. *k*=1–2)       | Entry + *m*·ATR (e.g. *m*=2–3)       | Simple; adapts to volatility | Ignores structure; needs tuning     |
| **Harmonic-Zone**        | Below X (swing point)                | Points A, B, (C)      | Uses market geometry; “pattern invalidation” | SL often very wide; TP limited by pattern |
| **Volatility-Adj.**      | Entry − (*k*·ATR·*V*) (V = vol factor) | Could combine with any TP strategy    | Auto-adjusts to volatility | More complex; potential overfitting |
| **Trailing / Ladder**    | (Initial = *k*·ATR) then moved to BE or trailed by ATR | Multiple: exit at first RR (e.g. 1R), then trail remainder | Protects profits; scales position | Requires trade management logic     |

Parameter ranges should be tested via backtest. As a starting point:
- *k*=1.0–2.0 (SL =1–2×ATR) is common.  
- *m*=2.0–3.0 for TP.  
- ATR trailing *k*≈3 (Wilder’s default).  

The **harmonic-zone approach** uses the pattern’s own geometry, so it requires no extra parameter beyond the offsets. The disadvantage is that it can produce very high SL ATR multiples (as we see, >20×ATR). One compromise is to cap the max ATR multiple (e.g. “stop at either X or max 5×ATR, whichever is tighter”). 

**Sources:** ATR-based stop methods; harmonic stops at X, targets at A/B; volatility-based stop concept.

## 4. Evaluation Metrics & Backtest Plan

To choose the best TP/SL scheme, we recommend the following performance metrics and testing framework:

- **Win Rate:** Percentage of trades hitting TP vs SL.  
- **Profit Factor/Expectancy:** (Sum of all profits) / (sum of all losses) or expected return per trade in R.  
- **Reward-to-Risk (RR):** Average TP/SL ratio achieved.  
- **Max Drawdown:** Worst cumulative loss sequence.  
- **Average Time-in-Trade:** How long trades last (hours/days).  
- **Fill/Execution Rate:** Fraction of signals that actually enter a position (important if using limit entries).  

We will simulate each TP/SL rule on historical signals. Assuming access to price history and the recorded entries/sl points, run the signals forward:

1. **Data Preparation:** Use historical tick or bar data covering the same instruments/timeframes.  
2. **Signal Generation:** Replay the signal logic to identify entry and SL (or point X), then apply each TP/SL scheme.  
3. **Trade Simulation:** For each method, simulate order fill (market or limit) and track P/L to SL or TP, including partial fills if scaling.  
4. **Metrics Calculation:** Compute above metrics for each method.  
5. **Comparison Table:** Summarize results in a table (see example below).  

*Example Evaluation Table (hypothetical results):*

| Method            | Win% | Avg RR | Expectancy (R) | Max DD (R) | Avg. Dur (hrs) | Fill% |
|-------------------|------|--------|----------------|------------|---------------|-------|
| Fixed ATR (1×SL)  | 50%  | 2.5    | +1.0           | –3.2       | 4             | 90%   |
| Harmonic Zone     | 60%  | 1.8    | +0.9           | –2.8       | 10            | 100%  |
| Vol-Adj (k=1.5)   | 52%  | 2.2    | +1.1           | –2.9       | 6             | 90%   |
| Trailing/Ladder   | 55%  | 2.0    | +1.3           | –2.5       | 8             | 95%   |

*(Above numbers are illustrative.)*

Additionally, we can plot distribution charts (e.g. P/L distribution, ATR vs profit scatter) and equity curves.

### Mermaid Flowchart of Trade Lifecycle

Below is a Mermaid diagram illustrating the signal-to-trade process:

```mermaid
flowchart LR
    A[Signal Generated] --> B{Check Confluence}
    B -->|Yes| C[Build Trade Setup]
    B -->|No| Z[Discard Signal]
    C --> D[Select Entry (candlestick/harmonic)]
    C --> E[Compute Stop (ATR or Pattern X)]
    D --> F[Place Order (Limit/Market)]
    F -->|Filled| G[In Trade]
    F -->|No Fill/Expired| H[Missed Trade]
    G --> I{Price Hits TP/SL?}
    I -->|TP| J[Exit Profit]
    I -->|SL| K[Exit Loss]
    I -->|Time Expire| L[Exit at EndTime]
    J & K & L --> M[Record Outcome]
```

This flowchart clarifies that a signal must pass confluence checks, then an entry/stop/TP are determined, an order is placed, and the trade is managed to a conclusion.

## 5. Implementation Steps & Pseudocode

We outline the major implementation tasks, with pseudocode illustrating logic.

### 5.1 Telegram Payload Generation

Structure the JSON payload or message string according to the template. For example:

```python
def format_signal_message(signal):
    # signal: dict with fields from audit/context
    header = "🔥 HARMONIC SIGNAL\n\n" if signal['type']=="harmonic" else "🔥 CANDLESTICK SIGNAL\n\n"
    header += f"{'🟢 BUY' if signal['side']=='long' else '🔴 SELL'} {signal['symbol']} – {signal['time']} UTC\n"
    
    tags = f"📊 Regime: *{signal['regime']}* | Vol: *{signal['vol_phase']}* | Resonance: *{signal['resonance']}*\n"
    tags += f"🔲 Squared: {'✔' if signal['squared'] else '❌'}"
    if signal['squared'] == False:
        tags += f" (bars={signal['bars']}, {signal['anchor_kind']})"
    tags += f" | ✔ Confirmations: {signal['confirmations']} | Score: {signal['score']:.2f}\n\n"
    
    confluence = ""
    if signal.get('candle_pattern'):
        confluence = f"💎 *Confluence:* {signal['candle_pattern']} aligns with harmonic.\n"
    
    entry = signal['entry']
    entry_text = f"🎯 *Entry:* {entry:.5f}"
    if signal['order_kind']=='limit':
        entry_text += f" (limit, {signal['entry_dist_atr']:.2f}×ATR retrace)"
    entry_text += "\n"
    
    sl = signal['sl']
    sl_atr = (signal['entry'] - sl) / signal['atr']
    sl_text = f"🛑 *SL:* {sl:.5f} (–{signal['entry']-sl:.5f}, ~{sl_atr:.2f}×ATR)\n"
    
    # TP can have multiple levels
    tp_lines = ""
    for i,(tp,rr) in enumerate(zip(signal['tp_levels'], signal['rr_levels']), start=1):
        tp_lines += f"💰 *TP{i}:* {tp:.5f} (+{tp-entry:.5f}, RR={rr:.2f})\n"
    
    # Confidence/position sizing suggestion
    confidence = signal.get('model_confidence', signal.get('confidence', 0))
    conf_text = f"👤 Model {signal.get('model', 'N/A')} ({confidence:.2f}) – "
    if confidence > 0.8:
        conf_text += "Confidence: High. "
    elif confidence > 0.5:
        conf_text += "Confidence: Moderate. "
    else:
        conf_text += "Confidence: Low. "
    conf_text += "\n"
    
    # Expected fill probability (simple heuristic)
    fill_prob = "High" if signal['entry_dist_atr'] < 0.5 else "Medium" if signal['entry_dist_atr']<1 else "Low"
    conf_text += f"⚡ Est. Fill Prob: *{fill_prob}* (limit entry)\n"
    
    message = header + tags + confluence + entry_text + sl_text + tp_lines + conf_text
    return message
```

### 5.2 Computing Risk Metrics

```python
def compute_trade_metrics(signal):
    # ATR-based metrics
    atr = signal['atr']
    entry = signal['entry']
    sl = signal['sl']
    sl_atr = abs(entry - sl) / atr
    signal['sl_atr_multiple'] = sl_atr

    # For candlestick: retracement ratio = entry_dist_atr / range_atr
    if 'entry_dist_atr' in signal and 'range_atr' in signal:
        retrace_ratio = signal['entry_dist_atr'] / signal['range_atr']
        signal['retrace_ratio'] = retrace_ratio
    else:
        signal['retrace_ratio'] = None

    # Spread in pips (if needed)
    if 'spread' in signal:
        signal['spread_pips'] = signal['spread'] * 10000  # example conversion
    
    return signal
```

For the provided example, `sl_atr_multiple` for USDCHF Hammer = (0.7899–0.7893)/0.0004529 ≈ 1.33. For Harmonic #1: (0.79063–0.76876)/0.0007929 ≈ 27.6.

### 5.3 Selecting TP/SL Method & Sizing

A high-level routine to choose stops and TPs (pseudocode):

```python
def choose_tp_sl(signal, method):
    atr = signal['atr']
    entry = signal['entry']
    side = signal['side']
    # Example placeholder values for pattern points (needs actual values from pattern detection)
    X = signal.get('pattern_X')
    A = signal.get('pattern_A')
    B = signal.get('pattern_B')

    if method == "fixed_ATR":
        k = 1.5
        m = 3.0
        stop = entry - k*atr if side=='long' else entry + k*atr
        tp = entry + m*atr if side=='long' else entry - m*atr
        tps = [tp]
    elif method == "harmonic":
        stop = X - 0.0001 if side=='long' else X + 0.0001
        # Targets at A, then B (if exists)
        tps = []
        if side=='long':
            if A: tps.append(A)
            if B: tps.append(B)
        else:
            if A: tps.append(A)
            if B: tps.append(B)
    elif method == "volatility_adj":
        k = 1.2
        V = signal['atr'] / signal['atr_mean']  # volatility factor
        stop = entry - k*atr*V if side=='long' else entry + k*atr*V
        tp = entry + 2*m*atr*V if side=='long' else entry - 2*m*atr*V
        tps = [tp]
    elif method == "trailing_ladder":
        # Example: initial TP1 = entry + 1*ATR, TP2 = entry + 2*ATR
        tps = [entry + atr, entry + 2*atr] if side=='long' else [entry - atr, entry - 2*atr]
        # SL: initial ATR, will move later (handled by trade manager)
        stop = entry - atr if side=='long' else entry + atr

    return stop, tps
```

In practice, `pattern_X`, `pattern_A`, etc. would be computed from the harmonic detection. Position sizing can then be determined by risk: e.g. risk = |entry–stop| * position_size, set to some % of account.

## 6. Logging & Data Collection

To refine the system, we should log additional fields and collect ample data:

- **Filled Flag:** Mark whether a limit order was filled or not.  
- **Minutes_Until_Fill:** How long before the order filled or expired.  
- **Retracement_Ratio:** As defined, entry_pullback_ATR ÷ signal_candle_range_ATR.  
- **SL_ATR_Multiple:** Stop distance in ATR (as computed above).  
- **Signal_Confluence:** Boolean or descriptor (e.g. “none”, “candle+harmonic”) indicating if multiple systems agreed.  
- **Expected Fill Prob:** (optional) the heuristic we estimate.  
- **Trade Outcome:** Actual RR achieved, P/L, duration.  

A data plan might aim for **hundreds of signals** for initial analysis (e.g. 500–1000 signal attempts) to gather statistically meaningful metrics. Record every generated signal and its eventual fate. Over weeks of live data (or backtest if possible), compute the performance of each TP/SL method. 

**Logging Example (JSON schema):**  

```json
{
  "timestamp": "...",
  "symbol": "USDCHF",
  "signal_type": "harmonic",
  "side": "buy",
  "pattern": "54x3",
  "score": 1.20,
  "confirmations": 2,
  "confluence": "Hammer",
  "entry": 0.79063,
  "sl": 0.76876,
  "tp_levels": [0.82344, 0.83437],
  "spread_pips": null,
  "atr": 0.0007929,
  "range_atr": null,
  "entry_dist_atr": null,
  "sl_atr_multiple": 27.57,
  "retrace_ratio": 0.84/0.84=~1.0,
  "order_kind": "market",
  "filled": false,
  "minutes_until_fill": 0,
  "result": null
}
```

After collecting data, use analysis (Python/pandas) to compute the requested metrics by method.  

## Sources

We referenced authoritative materials on ATR and harmonic stops: ATR multiples for stops (Optimus Futures); Wilder’s ATR trailing default (Stockopedia); conventional harmonic stop/TP placement at pattern points; and volatility-based stop rationale (StockDisciplines). These inform our proposed formulas and guidelines. 

