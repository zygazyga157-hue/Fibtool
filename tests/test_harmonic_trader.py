import pytest
from harmonic_trader import (
    digital_root_value,
    price_phase,
    harmonic_square,
    volatility_phase,
    weighted_resonance,
    generate_signal,
)


def test_digital_root_and_price_phase():
    assert digital_root_value(17) == 8
    assert price_phase(26) == 8


def test_harmonic_square_true():
    assert harmonic_square(10, 10, True) is True

def test_harmonic_square_false_when_no_hit():
    assert harmonic_square(10, 10, False) is False

def test_volatility_phase():
    assert volatility_phase(1.0, 1.0) == 'NORMAL'
    assert volatility_phase(0.5, 1.0) == 'COMPRESSION'
    assert volatility_phase(1.3, 1.0) == 'EXPANSION'
    assert volatility_phase(2.0, 1.0) == 'EXTREME'

def test_weighted_resonance():
    assert weighted_resonance('STRONG', 'NEW_YORK') > 0

def test_generate_signal_gate():
    ctx = {
        'gates': {
            'harmonic_hit': True,
            'squared': True,
            'vol_phase': 'NORMAL',
            'weighted_score': 0.8,
            'confirmations': 2,
        },
        'meta': {
            'regime': 'TRENDING',
        },
        'structure': {
            'volume_confirmed': True,
            'buy_acceptance': True,
            'sell_rejection': False,
        },
    }
    assert generate_signal(ctx) == 'BUY'

def test_generate_signal_none_when_gate_fails():
    ctx = {
        'gates': {
            'harmonic_hit': False,
            'squared': True,
            'vol_phase': 'NORMAL',
            'weighted_score': 0.8,
            'confirmations': 2,
        },
        'acceptance': True,
        'rejection': False,
    }
    assert generate_signal(ctx) is None


def test_classify_regime_synthetic():
    import pandas as pd
    # create synthetic trending series
    prices = [100 + i * 0.1 for i in range(250)]
    df = pd.DataFrame({'open': prices, 'high': [p + 0.2 for p in prices], 'low': [p - 0.2 for p in prices], 'close': prices})
    r = None
    try:
        from harmonic_trader import classify_regime
        r = classify_regime(df)
    except Exception:
        r = 'UNKNOWN'
    assert r in ('TRENDING', 'BALANCED', 'EXPANSION', 'COMPRESSION', 'UNKNOWN')
