import pytest

try:
    import pandas as pd
except Exception:
    pd = None

if pd is None:  # pragma: no cover
    pytest.skip("pandas not installed; skipping Asia Sweep ML dataset tests", allow_module_level=True)

from ml.asia_sweep_london_mss.prepare_dataset import simulate_label
from ml.asia_sweep_london_mss.torch_dataset import time_based_split


def _mk_df(index, rows):
    df = pd.DataFrame(rows, index=index)
    for c in ("open", "high", "low", "close"):
        if c not in df.columns:
            df[c] = 0.0
    return df


def test_simulate_label_long_buy_limit_tp_win():
    tz = "UTC"
    t0 = pd.Timestamp("2026-03-01 08:00:00", tz=tz)
    t1 = pd.Timestamp("2026-03-01 08:05:00", tz=tz)
    t2 = pd.Timestamp("2026-03-01 08:10:00", tz=tz)

    df = _mk_df(
        index=[t0, t1, t2],
        rows=[
            {"open": 100, "high": 101, "low": 99, "close": 100},
            {"open": 100, "high": 105, "low": 98, "close": 104},  # fill + TP
            {"open": 104, "high": 106, "low": 103, "close": 105},
        ],
    )

    label, fill_time = simulate_label(
        df,
        side="Long",
        t0=t0,
        entry=99.0,  # <= close[t0] => buy limit
        stop=96.0,
        tp=104.0,
        london_end="14:00",
    )
    assert label == 1
    assert fill_time == t1


def test_simulate_label_long_same_bar_tp_sl_tie_is_loss():
    tz = "UTC"
    t0 = pd.Timestamp("2026-03-01 08:00:00", tz=tz)
    t1 = pd.Timestamp("2026-03-01 08:05:00", tz=tz)

    df = _mk_df(
        index=[t0, t1],
        rows=[
            {"open": 100, "high": 101, "low": 99, "close": 100},
            {"open": 100, "high": 110, "low": 90, "close": 105},  # both TP and SL reachable
        ],
    )

    label, fill_time = simulate_label(
        df,
        side="Long",
        t0=t0,
        entry=99.0,
        stop=95.0,  # SL hit (low=90)
        tp=109.0,  # TP hit (high=110)
        london_end="14:00",
    )
    assert label == 0
    assert fill_time == t1


def test_simulate_label_short_sell_stop_tp_win():
    tz = "UTC"
    t0 = pd.Timestamp("2026-03-01 08:00:00", tz=tz)
    t1 = pd.Timestamp("2026-03-01 08:05:00", tz=tz)
    t2 = pd.Timestamp("2026-03-01 08:10:00", tz=tz)

    df = _mk_df(
        index=[t0, t1, t2],
        rows=[
            {"open": 100, "high": 101, "low": 99, "close": 100},
            {"open": 100, "high": 101, "low": 98, "close": 99},  # fill for sell stop (low<=entry)
            {"open": 99, "high": 100, "low": 96, "close": 97},  # TP hit
        ],
    )

    label, fill_time = simulate_label(
        df,
        side="Short",
        t0=t0,
        entry=99.0,  # < close[t0] => sell stop
        stop=103.0,
        tp=97.0,
        london_end="14:00",
    )
    assert label == 1
    assert fill_time == t1


def test_time_based_split_is_monotonic():
    df = pd.DataFrame(
        {
            "t0": pd.date_range("2026-01-01", periods=100, freq="H", tz="UTC"),
            "symbol": ["EURUSD"] * 100,
            "label": [0] * 100,
        }
    )
    train, val, test = time_based_split(df, val_frac=0.2, test_frac=0.2)
    assert len(train) > 0
    if len(val) > 0:
        assert train["t0"].max() <= val["t0"].min()
    if len(test) > 0:
        if len(val) > 0:
            assert val["t0"].max() <= test["t0"].min()
        else:
            assert train["t0"].max() <= test["t0"].min()

