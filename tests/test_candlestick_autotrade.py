import types


def test_choose_order_kind_long_pending_stop_ok():
    from candlesticks.candlestick_autotrade import choose_order_kind_for_breakout

    kind, reason = choose_order_kind_for_breakout(
        "long",
        entry=1.1050,
        bid=1.1040,
        ask=1.1042,
        buffer=0.0002,
        late_mult=1.0,
    )
    assert kind == "stop"
    assert reason == "pending_stop_ok"


def test_choose_order_kind_short_pending_stop_ok():
    from candlesticks.candlestick_autotrade import choose_order_kind_for_breakout

    kind, reason = choose_order_kind_for_breakout(
        "short",
        entry=1.0950,
        bid=1.0960,
        ask=1.0962,
        buffer=0.0002,
        late_mult=1.0,
    )
    assert kind == "stop"
    assert reason == "pending_stop_ok"


def test_choose_order_kind_late_market_allowed_within_buffer():
    from candlesticks.candlestick_autotrade import choose_order_kind_for_breakout

    kind, reason = choose_order_kind_for_breakout(
        "long",
        entry=1.1000,
        bid=1.1001,
        ask=1.1002,
        buffer=0.0003,
        late_mult=1.0,
    )
    assert kind == "market"
    assert reason == "late_market_ok"


def test_choose_order_kind_late_entry_skips_when_too_far():
    from candlesticks.candlestick_autotrade import choose_order_kind_for_breakout

    kind, reason = choose_order_kind_for_breakout(
        "long",
        entry=1.1000,
        bid=1.1010,
        ask=1.1012,
        buffer=0.0001,
        late_mult=1.0,
    )
    assert kind is None
    assert reason == "late_entry"


def test_pick_last_closed_bar_drops_forming_last_bar():
    import pandas as pd
    from datetime import datetime, timezone, timedelta
    from candlesticks.candlestick_autotrade import pick_last_closed_bar

    now = datetime.now(timezone.utc)
    # Pretend M15 bars, last bar started 2 minutes ago (forming).
    times = [
        (now - timedelta(minutes=30)).replace(tzinfo=None),
        (now - timedelta(minutes=15)).replace(tzinfo=None),
        (now - timedelta(minutes=2)).replace(tzinfo=None),
    ]
    df = pd.DataFrame(
        {
            "time": times,
            "open": [1.0, 1.0, 1.0],
            "high": [1.1, 1.1, 1.1],
            "low": [0.9, 0.9, 0.9],
            "close": [1.0, 1.0, 1.0],
        }
    )
    df_closed, sig_idx, dropped = pick_last_closed_bar(df, grace_seconds=5)
    assert len(df_closed) == 2
    assert sig_idx == 1
    assert dropped == 2

