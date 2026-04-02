## Asia Sweep London MSS: PyTorch ML Filter (True M5, Session-Labeled)

### Summary
Build a **PyTorch trade-quality filter** for the existing Asia Sweep → London MSS strategy. The mechanical sweep→MSS logic remains the *signal generator*; the ML model is a *second-stage gate* that scores **qualified** setups and decides **take/skip** based on predicted “TP before SL (within the same London session day)”.

You chose:
- **Goal:** Trade filter (not a full signal model)
- **Label:** TP-before-SL within the same session day (London end)
- **Data:** Use **true M5** (not M15-resampled)

---

### Implementation Changes

#### 1) Data: Save True M5 Bars (Collector)
- Add a dedicated collector script `asia_sweep_m5_collector.py` to fetch + persist **TRUE M5** bars for a configurable list of symbols.
- File naming (decision-complete):
  - Keep existing M15 file: `outputs/<symbol_slug>_bars.csv`
  - Add M5 file: `outputs/<symbol_slug>_m5.csv`
- History length:
  - Reuse the collector’s history months logic (currently ~3 months). For M5, fetch enough bars for ~3 months (`days*24*12`), capped by `MAX_BATCH_BARS`.
- Update cadence:
  - On each collector cycle, fetch a smaller recent M5 window (e.g., last 1–3 days) and **merge/dedupe** into the existing `*_m5.csv`, keeping the most recent ~3 months.
- Add config knobs (in `config.py`):
  - `ASIA_SWEEP_M5_ENABLED` (default `True` once implemented)
  - `ASIA_SWEEP_M5_SYMBOLS` (list or CSV string; default empty means “same symbols collector is already processing”)
  - `ASIA_SWEEP_M5_HISTORY_MONTHS` (default `3`)
  - `ASIA_SWEEP_M5_FETCH_BARS_PER_CYCLE` (default `~1000–3000`, to avoid heavy re-fetch)

#### 2) Strategy: Use True M5 for Sweep + MSS + Levels
- Update `asia_sweep_london_mss.py` to load:
  - `df_m15` from `outputs/<slug>_bars.csv` (optional, only if still needed)
  - `df_m5` from `outputs/<slug>_m5.csv` (required)
- Compute with **session-TZ correctness** (keep existing DST-safe session logic):
  - Asia range (00:00–07:59 session time): compute from `df_m5` (preferred for consistency)
  - Sweep events: compute on `df_m5` during sweep window
  - MSS events: compute on `df_m5` with `ASIA_SWEEP_MSS_LOOKBACK`
  - Trade levels: compute from the **MSS confirmation candle** (as already implemented)
- If M5 file is missing/stale:
  - Emit a signal row with `trade_setup.valid=false` and deterministic reason `Missing M5 bars` (fail-closed so you don’t trade on wrong-resolution data).

#### 3) Labels: Deterministic Backtest Outcome (No-Leak)
Create a dataset builder that replays historical M5 bars and produces labeled examples.

- Example time (`t0`): the **MSS confirmation candle close time** (the moment the strategy would qualify).
- Entry simulation (pending kind inferred from price at `t0`):
  - Long:
    - if `entry <= close[t0]` -> Buy Limit fill when `low <= entry`
    - else -> Buy Stop fill when `high >= entry`
  - Short:
    - if `entry >= close[t0]` -> Sell Limit fill when `high >= entry`
    - else -> Sell Stop fill when `low <= entry`
- Horizon end: **London end** of the same session day (`ASIA_SWEEP_LONDON_END` in `ASIA_SWEEP_SESSION_TIME_ZONE`), converted to UTC for indexing.
- Outcome label (binary, decision-complete):
  - `y=1` if order **fills** and then **TP hits before SL** before horizon end
  - `y=0` otherwise (includes SL-first, no-fill, or neither hit)
- Same-bar TP/SL ambiguity rule: **worst-case** (count as SL-first) to avoid optimistic bias.

#### 4) Features: Mechanical + Normalized (v1 locked)
At `t0`, compute features using only data `<= t0`:
- `asia_range` = `asia_high - asia_low`
- `atr14` on M5 at `t0`
- `asia_range_atr` = `asia_range / atr14`
- `eqh_touch_count`, `eql_touch_count`
- `sweep_dir` encoded: `+1` (sweep_low → long setup path), `-1` (sweep_high → short path), `0` (shouldn’t happen for qualified trades but keep for robustness)
- `sweep_depth_atr`:
  - long path: `(asia_low - sweep_low_bar_low) / atr14`
  - short path: `(sweep_high_bar_high - asia_high) / atr14`
- `minutes_from_london_open` at `t0` (normalized to `[0,1]` using the configured window length)
- `bars_from_sweep_to_mss` (integer, also provide normalized by `confirm_window_bars`)
- `confirm_range_atr` = `(confirm_high-confirm_low)/atr14`
- `entry_dist_atr` = `abs(entry - close[t0]) / atr14`
- `rr` (using strategy TP/SL)
- `symbol_id` categorical (global model with embedding)

#### 5) Model: Simple, Calibratable PyTorch Classifier
- Architecture (v1):
  - `symbol_embedding( num_symbols, 8 )`
  - numeric features → `MLP( [in] -> 64 -> 32 -> 1 )` with ReLU + dropout(0.1) + LayerNorm
  - output is logit; train with `BCEWithLogitsLoss` and `pos_weight` from train split
- Train/val/test split:
  - **time-based split** by `t0` (no random shuffle across time)
- Early stopping:
  - patience 5 on validation AUC (or logloss if you prefer)
- Artifacts written to:
  - `outputs/models/asia_sweep_mss/v1/model.pt`
  - `outputs/models/asia_sweep_mss/v1/feature_stats.json` (mean/std)
  - `outputs/models/asia_sweep_mss/v1/symbol_map.json`
  - `outputs/models/asia_sweep_mss/v1/metrics.json`

Add dependency:
- `torch` to `requirements.txt` (CPU build is fine; allow CUDA optionally)

#### 6) Runtime Integration: ML Gate in Asia Strategy (Optional, Safe)
- Add config knobs:
  - `ASIA_SWEEP_ML_ENABLED` (default `False`)
  - `ASIA_SWEEP_ML_MODEL_DIR` (default `outputs/models/asia_sweep_mss/v1`)
  - `ASIA_SWEEP_ML_MIN_PROB` (default `0.55`)
- Decision point:
  - Apply ML only when `trade_setup.valid==true` and pretrade RR checks passed.
  - If ML enabled and model load fails: block trade with reason `ML model unavailable` (fail-closed).
- Persist into signal JSONL:
  - add `ml: {enabled, model_version, prob, passed}` and reflect in `pretrade.reason` when blocked.

---

### Test Plan
- Unit tests for dataset builder:
  - fills correctly for each order-kind case (limit/stop long/short)
  - labels TP-before-SL correctly, including same-bar ambiguity rule
  - enforces time-based split (no leakage)
- Unit test for feature builder:
  - stable feature list ordering
  - normalization uses train stats only
- Smoke test:
  - train script runs on a tiny slice (1–2 symbols, 5–10 days) and writes artifacts
  - inference loads artifacts and returns a float prob in `[0,1]`

---

### Assumptions / Defaults
- We keep the mechanical strategy unchanged; ML is a **filter**, not a signal generator.
- Label is **session-bounded TP-before-SL** and treats **no-fill as not-success** (`y=0`).
- Use **true M5 bars** from the collector; strategy fails closed if M5 data is missing.
- Global multi-symbol model with a **symbol embedding** (no per-symbol models in v1).
