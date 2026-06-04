"""Tests for harmonic signals + autotrade pipeline."""
import json
import os
import types
import pytest

from harmonic_trader import compute_multiples_tp_sl


# ---------------------------------------------------------------------------
# Case-study math validation (from docs/harmonic_multiples_tp_sl_case_studies.md)
# ---------------------------------------------------------------------------

class TestComputeMultiplesTPSL:
    """Verify TP/SL math against documented case studies."""

    def test_sp500_case_study(self):
        """US SP 500: base=[110,170], multiples=[270,350,540], entry=5400, ATR=30, point=1.0"""
        ts = compute_multiples_tp_sl(
            symbol="US SP 500",
            side="BUY",
            entry=5400,
            atr=30,
            point=1.0,
            base_harmonics=[110, 170],
            common_multiples=[270, 350, 540],
        )
        assert ts, "compute_multiples_tp_sl returned empty"
        # structural_risk = 170*1 = 170,  atr_floor = 0.25*30 = 7.5  => risk = 170
        assert ts["risk"] == 170
        # scale = ceil(170 / (270*1)) = ceil(0.629) = 1
        assert ts["scale"] == 1
        # SL = 5400 - 170 = 5230
        assert ts["sl"] == 5230
        # TP1 = 5400 + 270*1*1 = 5670,  RR = 270/170 ≈ 1.5882
        assert abs(ts["tp_levels"][0] - 5670) < 0.01
        assert ts["rr_levels"][0] >= 1.5

    def test_xauusd_case_study(self):
        """XAUUSD: base=[11,17], multiples=[22,34,44,55,68], entry=2050, ATR=18, point=0.01"""
        ts = compute_multiples_tp_sl(
            symbol="XAUUSD",
            side="BUY",
            entry=2050,
            atr=18,
            point=0.01,
            base_harmonics=[11, 17],
            common_multiples=[22, 34, 44, 55, 68],
            k_atr=0.25,
        )
        assert ts
        # structural_risk = 17*0.01 = 0.17,  atr_floor = 0.25*18 = 4.5
        # risk = max(0.17, 4.5) = 4.5
        assert abs(ts["risk"] - 4.5) < 0.001
        # raw_step = 22*0.01 = 0.22
        # scale = ceil(4.5 / 0.22) = ceil(20.45) = 21
        assert ts["scale"] == 21
        # SL = 2050 - 4.5 = 2045.5
        assert abs(ts["sl"] - 2045.5) < 0.001
        # TP1 = 2050 + 22*21*0.01 = 2050 + 4.62 = 2054.62
        assert abs(ts["tp_levels"][0] - 2054.62) < 0.01
        # RR1 = 4.62 / 4.5 ≈ 1.0267
        assert ts["rr_levels"][0] >= 1.0

    def test_sell_direction(self):
        """Verify SL is above entry and TP below entry for SELL."""
        ts = compute_multiples_tp_sl(
            symbol="EURUSD",
            side="SELL",
            entry=1.10,
            atr=0.005,
            point=0.0001,
            base_harmonics=[27, 54],
            common_multiples=[81, 108, 162],
        )
        assert ts
        assert ts["sl"] > ts["entry"], "SL should be above entry for SELL"
        for tp in ts["tp_levels"]:
            assert tp < ts["entry"], "TP should be below entry for SELL"

    def test_be_trigger(self):
        """Breakeven trigger at 0.618R from entry."""
        ts = compute_multiples_tp_sl(
            symbol="TEST",
            side="BUY",
            entry=100,
            atr=2,
            point=0.01,
            base_harmonics=[10],
            common_multiples=[20, 40],
        )
        assert ts
        expected_be = 100 + 0.618 * ts["risk"]
        assert abs(ts["be_trigger_0618"] - expected_be) < 0.0001

    def test_swing_hybrid_uses_anchor_invalidation_stop(self):
        """Swing method should place SL beyond anchor/zone instead of using a wide multiples-only stop."""
        from harmonic_trader import compute_swing_hybrid_tp_sl

        ts = compute_swing_hybrid_tp_sl(
            symbol="USDCHF",
            side="BUY",
            entry=0.79063,
            atr=0.000792857,
            point=0.00001,
            base_harmonics=[27, 54],
            common_multiples=[81, 108],
            anchor_price=0.78842,
            zone_low=0.789635,
            zone_high=0.790445,
            vol_phase="COMPRESSION",
        )

        assert ts["method"] == "SWING_HYBRID"
        assert ts["sl_basis"] == "anchor_invalidation_atr_buffer"
        assert ts["sl"] < 0.78842
        assert ts["risk"] < 0.01
        assert ts["be_trigger_r"] == 1.0
        assert ts["tp_levels"][0] > ts["entry"]
        assert ts["rr_levels"][0] >= 1.0


# ---------------------------------------------------------------------------
# Harmonic signals HTML builder
# ---------------------------------------------------------------------------

class TestHarmonicSignalHTML:
    def _rich_context(self):
        return {
            "meta": {
                "symbol": "USDCHF",
                "timeframe": "H1",
                "regime": "TRENDING",
                "close": 0.79063,
                "atr": 0.000792857,
                "stress": "LOW",
                "resonance_strength": "STRONG",
                "price_move_points": 221,
                "price_move_last_bar": 0.00044,
                "anchor_price": 0.78842,
                "anchor_time": "2026-06-03 11:00:00",
                "anchor_kind": "swing_low",
                "bars_elapsed": 3,
                "harmonic_hit_level": 0.79004,
                "harmonic_hit_harmonic": "54x3",
                "harmonic_hit_distance": 0.00059,
                "harmonic_hit_method": "ANCHOR",
                "volume": 1501,
                "avg_volume": 1003.5,
                "harmonic_levels": [
                    {"level": 0.79004, "harmonic": "54x3"},
                    {"level": 0.7895, "harmonic": "54x2"},
                    {"level": 0.78923, "harmonic": "27x3"},
                ],
            },
            "gates": {
                "harmonic_hit": True,
                "squared": False,
                "vol_phase": "COMPRESSION",
                "weighted_score": 1.2,
                "confirmations": 2,
            },
            "structure": {
                "zone_low": 0.789635,
                "zone_mid": 0.79004,
                "zone_high": 0.790445,
                "buy_acceptance": True,
                "sell_rejection": False,
                "volume_confirmed": True,
            },
        }

    def test_build_html_contains_key_sections(self):
        from harmonic_signals import _build_html_harmonic_signal

        trade_setup = compute_multiples_tp_sl(
            "XAUUSD", "BUY", 2050, 18, 0.01,
            [11, 17], [22, 34, 44, 55, 68],
        )
        html = _build_html_harmonic_signal(
            symbol="XAUUSD",
            signal="BUY",
            context={
                "meta": {
                    "regime": "TRENDING",
                    "close": 2050,
                    "atr": 18,
                    "stress": "LOW",
                    "resonance_strength": "STRONG",
                },
                "gates": {
                    "squared": True,
                    "vol_phase": "NORMAL",
                },
            },
            trade_setup=trade_setup,
        )
        assert "XAUUSD" in html
        assert "BUY" in html
        assert "SL" in html
        assert "TP" in html
        assert "Scale" in html or "scale" in html.lower()

    def test_signal_grade_thresholds(self):
        from harmonic_signals import _signal_grade

        assert _signal_grade(1.5) == "A+"
        assert _signal_grade(1.2) == "A"
        assert _signal_grade(0.9) == "B"
        assert _signal_grade(0.1) == "C"

    def test_rich_html_contains_professional_sections_and_hit_ladder(self):
        from harmonic_signals import _build_html_harmonic_signal

        trade_setup = compute_multiples_tp_sl(
            "USDCHF", "BUY", 0.79063, 0.000792857, 0.000405,
            [27, 54], [81, 108],
        )
        html = _build_html_harmonic_signal(
            symbol="USDCHF",
            signal="BUY",
            context=self._rich_context(),
            trade_setup=trade_setup,
        )

        for section in (
            "Signal Quality",
            "Harmonic Structure",
            "Acceptance Structure",
            "Trade Plan",
            "Harmonic Framework",
            "Active Harmonics",
            "Gate Status",
        ):
            assert section in html
        assert "Signal Grade: <b>A</b>" in html
        assert "54x3" in html
        assert "HIT ✅" in html
        assert "❌ Market Not Squared" in html

    def test_market_evolution_for_previous_buy_signal(self):
        from harmonic_signals import _build_html_harmonic_signal, _build_market_evolution

        context = self._rich_context()
        current_meta = context["meta"]
        current_meta["anchor_price"] = 0.78958
        current_meta["price_move_points"] = 257
        current_meta["harmonic_hit_level"] = 0.7912
        previous = {
            "symbol": "USDCHF",
            "signal": "BUY",
            "context_meta": {
                "anchor_price": 0.78842,
                "price_move_points": 221,
                "harmonic_hit_level": 0.79004,
            },
        }
        evo = _build_market_evolution(previous, current_meta, "BUY")
        assert evo["structure"] == "Higher Low Formed ✅"
        assert evo["status"] == "Trend Continuation"

        trade_setup = compute_multiples_tp_sl(
            "USDCHF", "BUY", 0.79215, 0.000927143, 0.000405,
            [27, 54], [81, 108],
        )
        html = _build_html_harmonic_signal("USDCHF", "BUY", context, trade_setup, previous_signal=previous)
        assert "Market Evolution" in html
        assert "Higher Low Formed" in html
        assert "221 pts" in html
        assert "257 pts" in html

    def test_formatter_handles_missing_optional_fields(self):
        from harmonic_signals import _build_html_harmonic_signal

        html = _build_html_harmonic_signal(
            symbol="TEST",
            signal="BUY",
            context={"meta": {"close": 100}, "gates": {}, "structure": {}},
            trade_setup={"entry": 100, "sl": 99, "tp_levels": [102], "rr_levels": [2]},
        )
        assert "HARMONIC SIGNAL" in html
        assert "N/A" in html

    def test_signal_dispatcher_uses_swing_hybrid_method(self, tmp_path):
        from harmonic_signals import run_harmonic_signal_for_symbol

        context = self._rich_context()
        context["meta"]["point"] = 0.00001
        cfg = types.SimpleNamespace(
            HARMONIC_K_ATR=0.25,
            HARMONIC_TP_SL_METHOD="SWING_HYBRID",
            HARMONIC_SWING_SL_ATR_BUFFER=0.55,
            HARMONIC_SWING_MIN_RISK_ATR=1.0,
            HARMONIC_SWING_BE_TRIGGER_R=1.0,
            HARMONIC_SWING_TRAIL_ATR_MULT=2.0,
            HARMONIC_TP_LEVEL=1,
            HARMONIC_RR_MIN=1.0,
            HARMONIC_AUTOTRADE_COOLDOWN_SECONDS=0,
            HARMONIC_AUTOTRADE_STATE_PATH=str(tmp_path / "harmonic_state.json"),
            HARMONIC_SIGNALS_TELEGRAM=False,
        )

        out = run_harmonic_signal_for_symbol(
            "USDCHF",
            {"signal": "BUY", "context": context},
            cfg=cfg,
            outputs_dir=str(tmp_path),
        )

        assert out["reason"] == "telegram_disabled"
        assert out["trade_setup"]["method"] == "SWING_HYBRID"
        assert out["trade_setup"]["sl"] < context["meta"]["anchor_price"]
        row = json.loads((tmp_path / "harmonic_signals.jsonl").read_text(encoding="utf-8").splitlines()[0])
        assert row["trade_setup"]["method"] == "SWING_HYBRID"


# ---------------------------------------------------------------------------
# Autotrade candidate evaluation
# ---------------------------------------------------------------------------

class TestHarmonicAutotrade:
    def _make_result(self, signal="BUY", regime="TRENDING", vol_phase="NORMAL",
                     stress="LOW", volume_confirmed=True, weighted_score=0.8,
                     close=2050, atr=18):
        return {
            "signal": signal,
            "context": {
                "meta": {
                    "regime": regime,
                    "close": close,
                    "atr": atr,
                    "stress": stress,
                    "resonance_strength": "STRONG",
                    "harmonic_levels": [{"tolerance": 0.01}],
                },
                "gates": {
                    "harmonic_hit": True,
                    "squared": True,
                    "vol_phase": vol_phase,
                    "weighted_score": weighted_score,
                    "confirmations": 3,
                },
                "structure": {
                    "volume_confirmed": volume_confirmed,
                    "buy_acceptance": True,
                },
            },
        }

    def _make_cfg(self, **overrides):
        d = {
            "HARMONIC_AUTOTRADE_ENABLED": True,
            "HARMONIC_AUTOTRADE_DRY_RUN": True,
            "HARMONIC_AUTOTRADE_COOLDOWN_SECONDS": 0,
            "HARMONIC_AUTOTRADE_STATE_PATH": "tmp_pytest/harmonic_at_state.json",
            "HARMONIC_BLOCK_UNKNOWN_REGIME": True,
            "HARMONIC_ALLOW_EXTREME": False,
            "HARMONIC_K_ATR": 0.25,
            "HARMONIC_TP_LEVEL": 1,
            "HARMONIC_RR_MIN": 1.0,
        }
        d.update(overrides)
        return types.SimpleNamespace(**d)

    def test_eligible_candidate(self):
        from harmonic_autotrade import evaluate_harmonic_autotrade_candidate
        c = evaluate_harmonic_autotrade_candidate(
            "XAUUSD", self._make_result(), 2050, 2050.10, cfg=self._make_cfg(),
        )
        assert c.eligible, f"Expected eligible, got reason={c.reason}"
        assert c.rr >= 1.0

    def test_blocked_regime_unknown(self):
        from harmonic_autotrade import evaluate_harmonic_autotrade_candidate
        c = evaluate_harmonic_autotrade_candidate(
            "XAUUSD", self._make_result(regime="UNKNOWN"), 2050, 2050.10,
            cfg=self._make_cfg(),
        )
        assert not c.eligible
        assert c.reason == "regime_unknown"

    def test_blocked_vol_extreme(self):
        from harmonic_autotrade import evaluate_harmonic_autotrade_candidate
        c = evaluate_harmonic_autotrade_candidate(
            "XAUUSD", self._make_result(vol_phase="EXTREME"), 2050, 2050.10,
            cfg=self._make_cfg(),
        )
        assert not c.eligible
        assert c.reason == "vol_extreme"

    def test_blocked_volume_not_confirmed(self):
        from harmonic_autotrade import evaluate_harmonic_autotrade_candidate
        c = evaluate_harmonic_autotrade_candidate(
            "XAUUSD", self._make_result(volume_confirmed=False), 2050, 2050.10,
            cfg=self._make_cfg(),
        )
        assert not c.eligible
        assert c.reason == "volume_not_confirmed"

    def test_blocked_low_rr(self):
        from harmonic_autotrade import evaluate_harmonic_autotrade_candidate
        c = evaluate_harmonic_autotrade_candidate(
            "XAUUSD", self._make_result(), 2050, 2050.10,
            cfg=self._make_cfg(HARMONIC_RR_MIN=99.0),
        )
        assert not c.eligible
        assert "rr_too_low" in c.reason

    def test_blocked_stress_high(self):
        from harmonic_autotrade import evaluate_harmonic_autotrade_candidate
        c = evaluate_harmonic_autotrade_candidate(
            "XAUUSD", self._make_result(stress="HIGH"), 2050, 2050.10,
            cfg=self._make_cfg(),
        )
        assert not c.eligible
        assert c.reason == "stress_high"
