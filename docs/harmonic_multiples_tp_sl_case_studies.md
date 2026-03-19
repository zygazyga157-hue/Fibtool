  # Harmonic Multiples TP/SL Draft (Heatmap Case Studies)

Date: 2026-02-10

## Objective
Define a practical TP/SL function that uses symbol-specific harmonic multiples from `docs/data/market_harmonics.json`, validated against live resonance context in `outputs/harmonic_heatmap.json`.

## Data Snapshot Used
- `outputs/harmonic_heatmap.json`
- `outputs/harmonic_signals.jsonl`
- `docs/data/market_harmonics.json`

Heatmap at time of draft:
- `US SP 500`: 1 resonance event at `6961.17` (`2026-02-10T19:45:58Z`)
- `XAUUSD`: 2 resonance events at `4738.40` and `4929.79` (latest `2026-01-23T13:44:00Z`)

## Function Hypothesis (v0)
Use a risk floor so TP spacing remains meaningful across instruments:

1. Inputs:
- `symbol`, `side`, `entry`, `atr`, `point`
- `base_harmonics` and `common_multiples` from `market_harmonics.json`
- risk floor coefficient `k_atr = 0.25`

2. Risk:
- `structural_risk = max(base_harmonics) * point`
- `risk = max(structural_risk, k_atr * atr)`

3. Stop loss:
- Buy: `sl = entry - risk`
- Sell: `sl = entry + risk`

4. Harmonic scaling:
- `raw_step = min(common_multiples) * point`
- `scale = max(1, ceil(risk / raw_step))`

5. TP ladder (buy):
- `tp_i = entry + (common_multiples[i] * scale * point)`
- Sell mirrors with subtraction.

6. Management trigger:
- Breakeven trigger at `+0.618R` in trade direction.

## Case Study A: US SP 500 (BUY)
Context:
- Latest signal had `close=6961.17`, `atr=14.3043`, `regime=TRENDING`, `stress=LOW`.
- Harmonics:
- `base_harmonics=[110,170]`
- `common_multiples=[270,350,540]`
- inferred `point=0.01`

Risk build:
- `structural_risk = 170 * 0.01 = 1.70`
- `atr_floor = 0.25 * 14.3043 = 3.5761`
- `risk = 3.5761`
- Buy `SL = 6961.17 - 3.5761 = 6957.5939`

Scaling:
- `raw_step = 270 * 0.01 = 2.70`
- `scale = ceil(3.5761 / 2.70) = 2`

TPs:
- `TP1 = 6966.57` (RR `1.51`)
- `TP2 = 6968.17` (RR `1.96`)
- `TP3 = 6971.97` (RR `3.02`)

Management:
- Breakeven trigger at `entry + 0.618R = 6963.38`

## Case Study B: XAUUSD (No active BUY/SELL, structural test)
Context:
- Latest row had `close=5025.30`, `atr=27.5971`, `regime=TRENDING`, `stress=LOW`.
- Harmonics:
- `base_harmonics=[11,17]`
- `common_multiples=[22,34,44,55,68]`
- inferred `point=0.01`

Risk build:
- `structural_risk = 17 * 0.01 = 0.17`
- `atr_floor = 0.25 * 27.5971 = 6.8993`
- `risk = 6.8993`
- Buy `SL = 5025.30 - 6.8993 = 5018.4007`

Scaling:
- `raw_step = 22 * 0.01 = 0.22`
- `scale = ceil(6.8993 / 0.22) = 32`

TPs:
- `TP1 = 5032.34` (RR `1.02`)
- `TP2 = 5036.18` (RR `1.58`)
- `TP3 = 5039.38` (RR `2.04`)

Observation:
- Without scaling, XAU multiples produce very tight TP steps versus ATR.
- Scaled multiples fix this and restore usable RR.

## Key Findings
- Raw harmonic multiples are too compressed on some instruments when `point` is small.
- ATR floor plus harmonic scaling keeps the model cross-instrument consistent.
- `0.618R` breakeven rule from pattern literature integrates cleanly.

## Suggested Implementation Target
Implement a pure helper in `harmonic_trader.py`:
- `compute_multiples_tp_sl(symbol, side, entry, atr, point, base_harmonics, common_multiples, k_atr=0.25)`
- Return:
- `entry`, `sl`, `risk`, `scale`, `tp_levels`, `rr_levels`, `be_trigger_0618`

