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


# ----- Model A / C / MSE tests -----

def _make_test_df(n=100, close=1.1000, high=1.1050, low=1.0950, open_=1.0960):
    """Create a synthetic OHLC DataFrame for testing."""
    import pandas as pd
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    rows = []
    for i in range(n):
        rows.append({
            "time": (now - timedelta(minutes=15 * (n - i))).replace(tzinfo=None),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
        })
    return pd.DataFrame(rows)


def test_model_a_close_buy():
    from candlesticks.candlestick_signals import compute_model_a_close

    df = _make_test_df()
    result = compute_model_a_close(df, {"signal": "buy"}, symbol="EURUSD")
    assert result, "Model A returned empty"
    assert result["method"] == "model_a_close"
    assert result["entry"] == 1.1000  # close price
    assert result["stop"] < result["entry"]
    assert result["tp"] > result["entry"]


def test_model_a_close_sell():
    from candlesticks.candlestick_signals import compute_model_a_close

    df = _make_test_df()
    result = compute_model_a_close(df, {"signal": "sell"}, symbol="EURUSD")
    assert result, "Model A returned empty"
    assert result["method"] == "model_a_close"
    assert result["entry"] == 1.1000
    assert result["stop"] > result["entry"]
    assert result["tp"] < result["entry"]


def test_model_c_retrace_buy():
    from candlesticks.candlestick_signals import compute_model_c_retrace

    df = _make_test_df()
    result = compute_model_c_retrace(df, {"signal": "buy"}, symbol="EURUSD")
    assert result, "Model C returned empty"
    assert result["method"] == "model_c_retrace"
    # Entry should be between low and high (at 50% retrace)
    assert result["entry"] >= 1.0950
    assert result["entry"] <= 1.1050
    assert result["stop"] < result["entry"]
    assert result["tp"] > result["entry"]
    assert result["retrace_ratio"] == 0.618  # config.MODEL_C_RETRACE_RATIO default


def test_model_c_retrace_sell():
    from candlesticks.candlestick_signals import compute_model_c_retrace

    df = _make_test_df()
    result = compute_model_c_retrace(df, {"signal": "sell"}, symbol="EURUSD")
    assert result, "Model C returned empty"
    assert result["method"] == "model_c_retrace"
    assert result["entry"] >= 1.0950
    assert result["entry"] <= 1.1050
    assert result["stop"] > result["entry"]
    assert result["tp"] < result["entry"]


def test_model_c_custom_retrace_ratio():
    from candlesticks.candlestick_signals import compute_model_c_retrace

    df = _make_test_df()
    result = compute_model_c_retrace(df, {"signal": "buy"}, retrace_ratio=0.618, symbol="BTCUSD")
    assert result, "Model C returned empty"
    assert result["retrace_ratio"] == 0.618


def test_select_model_strong_momentum():
    from candlesticks.candlestick_signals import select_model

    result = select_model(
        score=4.0,
        strong_patterns_hit=["CDLMARUBOZU", "CDL3WHITESOLDIERS"],
    )
    assert result["model"] == "A"
    assert result["confidence"] == 0.85


def test_select_model_reversal_patterns():
    from candlesticks.candlestick_signals import select_model

    result = select_model(
        score=1.5,
        strong_patterns_hit=["CDLHAMMER", "CDLDOJI", "CDLMORNINGSTAR"],
    )
    assert result["model"] == "C"
    assert result["confidence"] == 0.70


def test_select_model_default_breakout():
    from candlesticks.candlestick_signals import select_model

    result = select_model(
        score=2.5,
        strong_patterns_hit=["CDL3INSIDE"],
    )
    assert result["model"] == "B"
    assert result["confidence"] == 0.60


def test_select_model_breakout_score():
    from candlesticks.candlestick_signals import select_model

    result = select_model(
        score=2.0,
        strong_patterns_hit=[],
        breakout_score=0.8,
    )
    assert result["model"] == "B"
    assert result["confidence"] == 0.75


def test_select_model_wyckoff_accumulation():
    from candlesticks.candlestick_signals import select_model

    result = select_model(
        score=1.0,
        strong_patterns_hit=[],
        wyckoff_phase="accumulation",
    )
    assert result["model"] == "C"
    assert result["confidence"] == 0.65


def test_select_model_high_volatility_default():
    """High ATR ratio should default to Model B (breakouts likely)."""
    from candlesticks.candlestick_signals import select_model

    result = select_model(
        score=1.0,
        strong_patterns_hit=[],
        atr_ratio=0.03,  # above default 0.02 threshold
    )
    assert result["model"] == "B"
    assert result["volatility"] == "high"
    assert result["reason"] == "default_high_vol_breakout"
    assert result["confidence"] == 0.65  # 0.60 + 0.05 high vol boost for B


def test_select_model_low_volatility_default():
    """Low ATR ratio should default to Model C (compression, retrace)."""
    from candlesticks.candlestick_signals import select_model

    result = select_model(
        score=1.0,
        strong_patterns_hit=[],
        atr_ratio=0.003,  # below default 0.005 threshold
    )
    assert result["model"] == "C"
    assert result["volatility"] == "low"
    assert result["reason"] == "default_low_vol_retrace"
    assert result["confidence"] == 0.65  # 0.60 + 0.05 low vol boost for C


def test_select_model_medium_volatility_default():
    """Medium ATR ratio should keep the default Model B."""
    from candlesticks.candlestick_signals import select_model

    result = select_model(
        score=1.0,
        strong_patterns_hit=[],
        atr_ratio=0.01,  # between 0.005 and 0.02
    )
    assert result["model"] == "B"
    assert result["volatility"] == "medium"
    assert result["reason"] == "default_breakout"
    assert result["confidence"] == 0.60


def test_select_model_volatility_confidence_boost():
    """High vol should boost Model B confidence when breakout_score triggers it."""
    from candlesticks.candlestick_signals import select_model

    result = select_model(
        score=2.0,
        strong_patterns_hit=[],
        breakout_score=0.8,
        atr_ratio=0.03,  # high vol
    )
    assert result["model"] == "B"
    assert result["confidence"] == 0.80  # 0.75 + 0.05 high vol boost


def test_select_model_volatility_confidence_penalty():
    """Low vol should reduce Model B confidence on breakout path."""
    from candlesticks.candlestick_signals import select_model

    result = select_model(
        score=2.0,
        strong_patterns_hit=[],
        breakout_score=0.8,
        atr_ratio=0.003,  # low vol
    )
    assert result["model"] == "B"
    assert result["confidence"] == 0.70  # 0.75 - 0.05 low vol penalty for B


def test_select_model_volatility_in_output():
    """Volatility state should always be present in output."""
    from candlesticks.candlestick_signals import select_model

    result = select_model(
        score=4.0,
        strong_patterns_hit=["CDLMARUBOZU", "CDL3WHITESOLDIERS"],
    )
    assert "volatility" in result
    assert result["volatility"] == "medium"  # None atr_ratio → medium


def test_compute_selected_model_integration():
    from candlesticks.candlestick_signals import compute_selected_model

    df = _make_test_df()
    signal = {"signal": "buy", "score": 4.0}
    result = compute_selected_model(
        df,
        signal,
        strong_patterns_hit=["CDLMARUBOZU", "CDL3WHITESOLDIERS"],
        symbol="EURUSD",
    )
    assert result["selection"]["model"] == "A"
    assert result["primary"]["method"] == "model_a_close"
    assert result["backup"] is not None
    assert result["backup"]["method"] == "model_b_breakout"


# ── Signal Recommendation tests ───────────────────────────────────────────────

def test_recommendation_reversal_confirms_buy():
    """Reversal-dominant pattern on a buy signal → confirms bullish."""
    from candlesticks.candlestick_signals import _build_signal_recommendation

    rec = _build_signal_recommendation(
        side="buy",
        pattern_hits=["CDLHAMMER", "CDLENGULFING", "CDLMORNINGSTAR"],
        momentum=0, reversal=3, indecision=0,
    )
    assert rec["alignment"] == "confirms"
    assert rec["suggested_side"] == "buy"
    assert "bullish" in rec["label"].lower()
    assert "exhaustion" in rec["because"].lower()


def test_recommendation_reversal_confirms_sell():
    """Reversal-dominant on sell → confirms bearish."""
    from candlesticks.candlestick_signals import _build_signal_recommendation

    rec = _build_signal_recommendation(
        side="sell",
        pattern_hits=["CDLEVENINGSTAR", "CDLSHOOTINGSTAR"],
        momentum=0, reversal=2, indecision=0,
    )
    assert rec["alignment"] == "confirms"
    assert rec["suggested_side"] == "sell"
    assert "bearish" in rec["label"].lower()


def test_recommendation_momentum_confirms():
    """Momentum-dominant patterns confirm the signal side."""
    from candlesticks.candlestick_signals import _build_signal_recommendation

    rec = _build_signal_recommendation(
        side="buy",
        pattern_hits=["CDLMARUBOZU", "CDL3WHITESOLDIERS"],
        momentum=2, reversal=0, indecision=0,
    )
    assert rec["alignment"] == "confirms"
    assert rec["suggested_side"] == "buy"
    assert "momentum" in rec["label"].lower()


def test_recommendation_indecision_suggests_wait():
    """Indecision-dominant patterns → suggested_side = wait."""
    from candlesticks.candlestick_signals import _build_signal_recommendation

    rec = _build_signal_recommendation(
        side="buy",
        pattern_hits=["CDLSPINNINGTOP", "CDLHIGHWAVE"],
        momentum=0, reversal=0, indecision=2,
    )
    assert rec["suggested_side"] == "wait"
    assert rec["alignment"] == "neutral"
    assert "indecision" in rec["label"].lower()


def test_recommendation_no_patterns():
    """No classified patterns → neutral, no directional edge."""
    from candlesticks.candlestick_signals import _build_signal_recommendation

    rec = _build_signal_recommendation(
        side="buy", pattern_hits=[],
        momentum=0, reversal=0, indecision=0,
    )
    assert rec["alignment"] == "neutral"
    assert "no pattern" in rec["label"].lower()


# ── Breakout Score tests ──────────────────────────────────────────────────────

def test_breakout_score_strong_bullish_candle():
    """Full-body bullish candle closing at high → high breakout score."""
    from candlesticks.candlestick_signals import _compute_breakout_score

    df = _make_test_df(close=1.1050, open_=1.0950, high=1.1050, low=1.0950)
    score = _compute_breakout_score(df, {"signal": "buy"})
    # body_ratio=1.0, close_pos=1.0, range_ratio depends on ATR
    assert score >= 0.6, f"Expected strong breakout score, got {score}"


def test_breakout_score_weak_doji():
    """Doji candle (open≈close) → low breakout score."""
    from candlesticks.candlestick_signals import _compute_breakout_score

    df = _make_test_df(close=1.1000, open_=1.1000, high=1.1050, low=1.0950)
    score = _compute_breakout_score(df, {"signal": "buy"})
    # body_ratio≈0, close_pos=0.5
    assert score < 0.5, f"Expected weak breakout score for doji, got {score}"


def test_breakout_score_sell_close_near_low():
    """Bearish candle closing near low → high breakout score for sell."""
    from candlesticks.candlestick_signals import _compute_breakout_score

    df = _make_test_df(close=1.0950, open_=1.1050, high=1.1050, low=1.0950)
    score = _compute_breakout_score(df, {"signal": "sell"})
    assert score >= 0.6, f"Expected strong sell breakout score, got {score}"


def test_breakout_score_empty_df():
    """Empty DataFrame → 0.0."""
    import pandas as pd
    from candlesticks.candlestick_signals import _compute_breakout_score

    score = _compute_breakout_score(pd.DataFrame(), {"signal": "buy"})
    assert score == 0.0


# ── Reflexive RR tests ────────────────────────────────────────────────────────

def test_reflexive_rr_default_medium():
    """Default conditions → RR near base (no extreme multipliers)."""
    from candlesticks.candlestick_signals import _compute_reflexive_rr

    rr = _compute_reflexive_rr(
        2.5, score=2.5, confidence=0.70, volatility="medium", model="B",
    )
    # score=2.5 → mult≈0.94, confidence=0.70 → mult≈1.03, vol=medium → 1.0, model B → 1.0
    assert 1.2 <= rr <= 4.5, f"RR out of bounds: {rr}"
    assert rr != 2.5, "Reflexive RR should differ from static base"


def test_reflexive_rr_strong_signal_high_conf():
    """Strong score + high confidence → RR above base."""
    from candlesticks.candlestick_signals import _compute_reflexive_rr

    rr = _compute_reflexive_rr(
        2.5, score=5.0, confidence=0.85, volatility="medium", model="A",
    )
    assert rr > 2.5, f"Expected RR above base 2.5, got {rr}"


def test_reflexive_rr_weak_signal_low_conf():
    """Weak score + low confidence → RR below base."""
    from candlesticks.candlestick_signals import _compute_reflexive_rr

    rr = _compute_reflexive_rr(
        2.5, score=1.5, confidence=0.55, volatility="high", model="B",
    )
    assert rr < 2.5, f"Expected RR below base 2.5, got {rr}"


def test_reflexive_rr_model_c_boost():
    """Model C gets a 1.10 boost for its deeper entry."""
    from candlesticks.candlestick_signals import _compute_reflexive_rr

    rr_b = _compute_reflexive_rr(
        2.5, score=3.0, confidence=0.70, volatility="medium", model="B",
    )
    rr_c = _compute_reflexive_rr(
        2.5, score=3.0, confidence=0.70, volatility="medium", model="C",
    )
    assert rr_c > rr_b, f"Model C RR ({rr_c}) should exceed Model B RR ({rr_b})"


def test_reflexive_rr_floor_ceiling():
    """RR is clamped between floor and ceiling."""
    from candlesticks.candlestick_signals import _compute_reflexive_rr
    import types

    cfg = types.SimpleNamespace(MSE_RR_FLOOR=1.5, MSE_RR_CEILING=3.0)

    # Very weak signal → should be clamped at floor
    rr_low = _compute_reflexive_rr(
        1.0, score=0.5, confidence=0.50, volatility="high", model="B", cfg=cfg,
    )
    assert rr_low >= 1.5, f"Expected floor 1.5, got {rr_low}"

    # Very strong signal → should be clamped at ceiling
    rr_high = _compute_reflexive_rr(
        5.0, score=6.0, confidence=0.95, volatility="low", model="C", cfg=cfg,
    )
    assert rr_high <= 3.0, f"Expected ceiling 3.0, got {rr_high}"


# ── MSE breakout_score integration ────────────────────────────────────────────

def test_select_model_auto_breakout_score_in_compute():
    """compute_selected_model auto-computes breakout_score and passes it to select_model."""
    from candlesticks.candlestick_signals import compute_selected_model

    # Full body bullish candle → high breakout score → should trigger Model B via breakout path
    df = _make_test_df(close=1.1050, open_=1.0950, high=1.1050, low=1.0950)
    signal = {"signal": "buy", "score": 2.0}
    result = compute_selected_model(df, signal, strong_patterns_hit=[], symbol="EURUSD")

    sel = result["selection"]
    assert "breakout_score" in sel, "breakout_score should be in selection output"
    assert sel["breakout_score"] > 0, "Auto-computed breakout_score should be > 0"


def test_compute_selected_model_reflexive_rr_in_output():
    """compute_selected_model should include reflexive_rr in its selection output."""
    from candlesticks.candlestick_signals import compute_selected_model

    df = _make_test_df()
    signal = {"signal": "buy", "score": 4.0}
    result = compute_selected_model(
        df, signal, strong_patterns_hit=["CDLMARUBOZU"], symbol="EURUSD",
    )
    sel = result["selection"]
    assert "reflexive_rr" in sel, "reflexive_rr should be in selection output"
    assert sel["reflexive_rr"] > 0, "reflexive_rr should be positive"

    # The primary model should use the reflexive RR, not the static config one
    primary = result["primary"]
    assert primary.get("rr") == sel["reflexive_rr"], \
        f"Primary model RR ({primary.get('rr')}) should match reflexive RR ({sel['reflexive_rr']})"

