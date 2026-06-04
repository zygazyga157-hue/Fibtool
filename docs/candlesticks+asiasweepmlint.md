# Candlestick + Asia Sweep ML Integration Plan

## Summary
Integrate the two research directions as a staged upgrade: candlestick signals become **ML features** for the existing Asia Sweep second-stage gate, while operational hardening is added around data freshness, timezone safety, and observability. The live mechanical Asia Sweep setup remains the signal generator; no hard candlestick gate is enabled in v1 of this integration.

## Key Changes
- Add a shared feature module for Asia Sweep ML so dataset generation and live inference use the same code path.
- Extend the feature set with candlestick context from both:
  - **M5 true bars**: confirmation/MSS candle context, pattern flags, pattern score, directional alignment, pattern age, body/wick/ATR ratios.
  - **M15 Fibtool bars**: higher-timeframe pattern score, dominant pattern class, directional alignment, and recent pattern count.
- Keep artifact compatibility:
  - Old models keep working because inference already reads `metrics.json.feature_cols`.
  - New trained artifacts write an expanded `feature_cols` list and can be activated through the existing `current.json` pointer.
- Add config toggles:
  - `ASIA_SWEEP_CANDLE_FEATURES_ENABLED=True`
  - `ASIA_SWEEP_CANDLE_M15_CONTEXT_ENABLED=True`
  - `ASIA_SWEEP_CANDLE_FEATURE_MODE="features_only"`
  - No hard trade block from candlesticks in this phase.

## Implementation Changes
- Dataset pipeline:
  - Extend `ml/asia_sweep_london_mss/prepare_dataset.py` to attach M5 and M15 candlestick features at each `t0`.
  - Ensure all candlestick features use only bars available at or before `t0`.
  - Continue using the existing TP-before-SL session-bounded label.
- Runtime scoring:
  - Replace the inline ML feature dict in `asia_sweep_london_mss.py` with the shared feature builder.
  - Add `signal["ml"]["features_version"]` and include selected candlestick diagnostics in signal JSONL for audit.
  - If M15 context is missing, fill M15 candlestick features with neutral defaults and log `m15_context_missing`; do not fail closed.
  - If M5 data is missing/stale, preserve the current fail-closed Asia Sweep behavior.
- Training:
  - Add a new v4 training path or extend `train_v3.py` defaults to output `v4_YYYYMMDD_HHMMSS` artifacts using the expanded feature list.
  - Keep focal loss, residual MLP, SMOTE, and time-based split defaults from v3.
  - Add ablation support: structural-only vs structural+M5 candles vs structural+M5+M15 candles.
- Ops hardening:
  - Add stale-data checks for M5 and M15 bars before scoring.
  - Add audit fields for data age, missing feature groups, active model dir, probability, threshold, and final pass/block reason.
  - Keep UTC canonical timestamps and existing `Europe/London` session timezone handling.

## Test Plan
- Unit tests:
  - Candlestick feature builder returns stable columns and neutral defaults when optional M15 context is absent.
  - Dataset and live feature builder produce matching values for the same synthetic setup.
  - Feature extraction does not use bars after `t0`.
  - Old model artifacts with old `feature_cols` still score successfully.
- Strategy tests:
  - ML pass/block behavior remains unchanged except for expanded features.
  - Missing M5 still fails closed.
  - Missing M15 does not block trades.
- Training checks:
  - Build a small expanded dataset.
  - Run a short training smoke test and verify `model.pt`, `feature_stats.json`, `symbol_map.json`, and `metrics.json` are written.
  - Run ablation comparison and record AUC/precision/recall/F1.

## Assumptions
- Candlesticks are **features only**, not a hard rule gate.
- Both M5 and M15 candlestick context will be used.
- Existing active model remains valid until a new expanded-feature artifact is trained and activated.
- Live trading behavior changes only through the existing ML probability gate and active model pointer.
