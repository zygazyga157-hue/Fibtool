import json
import sys
from pathlib import Path


# Ensure repo root on path for imports (mirrors other tests in this repo)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


from plots.asia_sweep_plot import (
    load_asia_signals,
    generate_mql5_script,
    generate_mql5_script_rich,
)


def test_loader_prefers_jsonl_and_datetime_ordering(tmp_path):
    out = tmp_path / "outputs"
    out.mkdir()

    # JSONL contains two EURUSD records; latest should win.
    jsonl = out / "asia_mss_signals.jsonl"
    rec1 = {
        "timestamp": "2026-03-16T13:15:00+00:00",
        "timestamp_session": "2026-03-16T13:15:00+00:00",
        "session_tz": "Europe/London",
        "symbol": "EURUSD",
        "current_price": 1.101,
        "asia_high": 1.2000,
        "asia_low": 1.1000,
        "eqh_liquidity_pool": False,
        "eql_liquidity_pool": False,
        "eqh_touch_count": 1,
        "eql_touch_count": 1,
        "in_london": True,
        "in_asia": False,
        "sweep_high": False,
        "sweep_low": False,
        "mss": {"bullMSS": False, "bearMSS": False, "current_m5": {"high": 1.11, "low": 1.10, "close": 1.101}, "prev3": {"high": {"t": 1.12}, "low": {"t": 1.09}}},
        "fib_ratio": 0.71,
        "fib_long": 1.105,
        "fib_short": 1.106,
        "trade_setup": {"valid": False, "reason": "Not qualified"},
        "pretrade": {"passed": False, "reason": "Not qualified"},
    }
    rec2 = dict(rec1)
    rec2["timestamp"] = "2026-03-16T13:30:00+00:00"
    rec2["asia_high"] = 1.3000

    jsonl.write_text(json.dumps(rec1) + "\n" + json.dumps(rec2) + "\n", encoding="utf-8")

    # CSV exists and is "later", but loader should still prefer JSONL when present.
    csvp = out / "asia_mss_signals.csv"
    csvp.write_text(
        "timestamp,session_tz,symbol,current_price,asia_high,asia_low,eqh_liquidity_pool,eql_liquidity_pool,eqh_touch_count,eql_touch_count,in_london,in_asia,sweep_high,sweep_low,m5,mss,fib_ratio,fib_long,fib_short,trade_setup,pretrade\n"
        + '2026-03-16T14:00:00+00:00,Europe/London,EURUSD,1.101,9.9,1.1,False,False,1,1,True,False,False,False,"{}","{}",0.71,1.105,1.106,"{\\"valid\\": false}","{\\"passed\\": false}"\n',
        encoding="utf-8",
    )

    latest = load_asia_signals("EURUSD", output_dir=out)
    assert latest is not None
    assert latest.get("asia_high") == 1.3000
    assert latest.get("timestamp") == "2026-03-16T13:30:00+00:00"


def test_generate_mql5_script_clean_is_minimal():
    signal = {
        "timestamp": "2026-03-16T13:30:00+00:00",
        "timestamp_session": "2026-03-16T13:30:00+00:00",
        "session_tz": "Europe/London",
        "symbol": "EURUSD",
        "current_price": 1.1479,
        "asia_high": 1.1500,
        "asia_low": 1.1400,
        "eqh_liquidity_pool": True,
        "eql_liquidity_pool": False,
        "eqh_touch_count": 3,
        "eql_touch_count": 1,
        "in_london": True,
        "in_asia": False,
        "sweep_high": True,
        "sweep_low": False,
        "mss": {
            "bullMSS": False,
            "bearMSS": False,
            "current_m5": {"open": 1.145, "high": 1.148, "low": 1.144, "close": 1.1479},
            "prev3": {"high": {"t1": 1.1470, "t2": 1.1465}, "low": {"t1": 1.1432, "t2": 1.1428}},
        },
        "fib_ratio": 0.71,
        "fib_long": 1.1460,
        "fib_short": 1.1468,
        "trade_setup": {"valid": False, "reason": "Not qualified"},
        "pretrade": {"passed": False, "reason": "Not qualified", "lots": None, "rr": None},
    }

    script = generate_mql5_script("EURUSD", signal)  # default style is clean
    assert script is not None
    assert "OBJ_RECTANGLE_LABEL" not in script
    assert "_entry_alert_zone" not in script
    assert "OBJ_LABEL" in script
    assert "DeleteByPrefix" in script


def test_generate_mql5_script_rich_includes_panel_and_thresholds():
    signal = {
        "timestamp": "2026-03-16T13:30:00+00:00",
        "timestamp_session": "2026-03-16T13:30:00+00:00",
        "session_tz": "Europe/London",
        "symbol": "EURUSD",
        "current_price": 1.1479,
        "asia_high": 1.1500,
        "asia_low": 1.1400,
        "eqh_liquidity_pool": True,
        "eql_liquidity_pool": False,
        "eqh_touch_count": 3,
        "eql_touch_count": 1,
        "in_london": True,
        "in_asia": False,
        "sweep_high": True,
        "sweep_low": False,
        "mss": {
            "bullMSS": False,
            "bearMSS": False,
            "current_m5": {"open": 1.145, "high": 1.148, "low": 1.144, "close": 1.1479},
            "prev3": {"high": {"t1": 1.1470, "t2": 1.1465}, "low": {"t1": 1.1432, "t2": 1.1428}},
        },
        "fib_ratio": 0.71,
        "fib_long": 1.1460,
        "fib_short": 1.1468,
        "trade_setup": {"valid": False, "reason": "Not qualified"},
        "pretrade": {"passed": False, "reason": "Not qualified", "lots": None, "rr": None},
    }

    script = generate_mql5_script_rich("EURUSD", signal)
    assert script is not None
    assert "OBJ_RECTANGLE_LABEL" in script
    assert "_panel_text" in script
    assert "_mss_bull_threshold" in script
    assert "_mss_bear_threshold" in script
    assert "DeleteByPrefix" in script
    assert "SYMBOL_POINT" in script
    assert "SYMBOL_DIGITS" in script
    assert "0.0001" not in script


def test_generate_mql5_script_rich_trade_alert_buffer_math():
    signal = {
        "timestamp": "2026-03-16T13:30:00+00:00",
        "timestamp_session": "2026-03-16T13:30:00+00:00",
        "session_tz": "Europe/London",
        "symbol": "EURUSD",
        "current_price": 1.1479,
        "asia_high": 1.1500,
        "asia_low": 1.1400,
        "eqh_liquidity_pool": False,
        "eql_liquidity_pool": False,
        "eqh_touch_count": 1,
        "eql_touch_count": 1,
        "in_london": True,
        "in_asia": False,
        "sweep_high": False,
        "sweep_low": True,
        "mss": {
            "bullMSS": True,
            "bearMSS": False,
            "current_m5": {"open": 1.145, "high": 1.148, "low": 1.144, "close": 1.1479},
            "prev3": {"high": {"t1": 1.1470}, "low": {"t1": 1.1432}},
        },
        "fib_ratio": 0.71,
        "fib_long": 1.1460,
        "fib_short": 1.1468,
        "trade_setup": {
            "valid": True,
            "type": "Long",
            "entry": 1.1460,
            "stop_loss": 1.1440,
            "take_profit": 1.1500,
            "method": "unit-test",
        },
        "pretrade": {"passed": True, "reason": "", "lots": 0.01, "rr": 2.0},
    }

    script = generate_mql5_script_rich("EURUSD", signal)
    assert script is not None
    assert "_entry_alert_zone" in script
    assert "MathMax(" in script
    assert "pt * 10" in script
    assert "buffer_pct" not in script
