import pytest
import sys
from pathlib import Path

try:
    import pandas as pd
    import numpy as np
except Exception:
    pd = None
    np = None

if pd is None:  # pragma: no cover
    pytest.skip("pandas not installed", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.asia_sweep_london_mss.features import (
    FEATURE_COLS,
    STRUCTURAL_FEATURE_COLS,
    build_asia_sweep_feature_bundle,
    evaluate_candlestick_hard_block,
)
from ml.asia_sweep_london_mss.inference import vectorize_features
from ml.asia_sweep_london_mss.torch_dataset import StandardScalerStats


def _m5_df(periods=30):
    idx = pd.date_range("2026-02-07 06:00", periods=periods, freq="5min", tz="UTC")
    rows = []
    price = 100.0
    for i, _ in enumerate(idx):
        open_ = price
        close = price + (0.2 if i % 2 == 0 else -0.1)
        high = max(open_, close) + 0.5
        low = min(open_, close) - 0.5
        rows.append({"open": open_, "high": high, "low": low, "close": close})
        price = close
    return pd.DataFrame(rows, index=idx)


def test_feature_builder_returns_stable_expanded_columns_with_missing_m15_neutral():
    m5 = _m5_df()
    t0 = m5.index[20]
    bundle = build_asia_sweep_feature_bundle(
        symbol="EURUSD",
        side="Long",
        t0=t0,
        m5_session=m5,
        asia_high=105.0,
        asia_low=99.0,
        eqh_count=1,
        eql_count=2,
        sweep_time=m5.index[18],
        entry=101.0,
        stop=100.0,
        tp=105.0,
        confirm_window_bars=12,
        london_start="08:00",
        london_end="14:00",
        m15_utc=None,
    )

    assert list(bundle.features.keys()) == FEATURE_COLS
    assert set(STRUCTURAL_FEATURE_COLS).issubset(bundle.features)
    assert bundle.diagnostics["features_version"] == "v4_candles_m5_m15"
    assert bundle.diagnostics["m15"]["missing"] is True
    assert bundle.features["m15_candle_score"] == 0.0


def test_feature_builder_uses_no_bars_after_t0():
    m5 = _m5_df(periods=32)
    t0 = m5.index[20]
    before = m5.loc[:t0].copy()
    with_future = m5.copy()
    # Make future bars extreme; features at t0 must not change.
    with_future.loc[with_future.index > t0, ["open", "high", "low", "close"]] = [200.0, 220.0, 180.0, 181.0]

    kwargs = dict(
        symbol="EURUSD",
        side="Short",
        t0=t0,
        asia_high=105.0,
        asia_low=99.0,
        eqh_count=1,
        eql_count=1,
        sweep_time=m5.index[18],
        entry=101.0,
        stop=102.0,
        tp=99.0,
        confirm_window_bars=12,
        london_start="08:00",
        london_end="14:00",
    )
    a = build_asia_sweep_feature_bundle(m5_session=before, m15_utc=before.resample("15min").last(), **kwargs)
    b = build_asia_sweep_feature_bundle(m5_session=with_future, m15_utc=with_future.resample("15min").last(), **kwargs)

    for col in FEATURE_COLS:
        assert b.features[col] == pytest.approx(a.features[col])


def test_hard_block_disabled_and_enabled_paths():
    diag = {"m5": {"enabled": True, "missing": False, "alignment": -1, "score": -2.0}}
    disabled = evaluate_candlestick_hard_block(diag, enabled=False, min_score=1.0, allow_neutral=True)
    assert disabled["blocked"] is False

    enabled = evaluate_candlestick_hard_block(diag, enabled=True, min_score=1.0, allow_neutral=True)
    assert enabled["blocked"] is True
    assert enabled["reason"] == "contradictory_candlestick"


def test_hard_block_neutral_respects_allow_neutral():
    diag = {"m5": {"enabled": True, "missing": False, "alignment": 0, "score": 0.0}}
    allowed = evaluate_candlestick_hard_block(diag, enabled=True, min_score=1.0, allow_neutral=True)
    blocked = evaluate_candlestick_hard_block(diag, enabled=True, min_score=1.0, allow_neutral=False)
    assert allowed["blocked"] is False
    assert blocked["blocked"] is True
    assert blocked["reason"] == "neutral_candlestick"


def test_old_feature_cols_vectorize_compatibility():
    old_cols = ["asia_range", "atr14", "rr"]
    scaler = StandardScalerStats(mean=np.zeros(3, dtype=np.float32), std=np.ones(3, dtype=np.float32))
    x = vectorize_features({"asia_range": 5.0, "atr14": 0.5, "rr": 2.0, "m5_candle_score": 9.0}, scaler=scaler, feature_cols=old_cols)
    assert x.shape == (1, 3)
    assert x.tolist()[0] == [5.0, 0.5, 2.0]
