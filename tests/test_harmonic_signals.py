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


# ---------------------------------------------------------------------------
# Harmonic signals HTML builder
# ---------------------------------------------------------------------------

class TestHarmonicSignalHTML:
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
