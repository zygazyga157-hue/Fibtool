import json
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

from plots_v2.anchor_engine import select_anchors
from plots_v2.descriptions import build_confluence_chart_text
from plots_v2.object_specs import AnchorPoint, MT5ObjectSpec, ObjectContext, ObjectLevel
from plots_v2.mt5_object_factory import to_mql_create_lines


def _write_bars_csv(path: Path) -> pd.DataFrame:
    times = pd.date_range("2026-05-19 00:00:00+00:00", periods=30, freq="h")
    base = 100.0
    close = []
    high = []
    low = []
    open_ = []
    for i in range(len(times)):
        # Simple wave with explicit pivot low at i=10 and pivot high at i=20
        if i == 10:
            c = base - 15
        elif i == 20:
            c = base + 15
        else:
            c = base + (i % 5) - 2
        o = c - 0.5
        h = c + 1.0
        l = c - 1.0
        close.append(c)
        open_.append(o)
        high.append(h)
        low.append(l)

    df = pd.DataFrame(
        {
            "time": times,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": [100] * len(times),
            "point": [0.01] * len(times),
        }
    )
    df.to_csv(path, index=False)
    return df


def test_anchor_engine_selects_alternating_pair(tmp_path: Path):
    outdir = tmp_path
    bars_path = outdir / "xauusd_h1_bars.csv"
    _write_bars_csv(bars_path)

    sel = select_anchors(
        outdir,
        "XAUUSD",
        "H1",
        pivot_left=2,
        pivot_right=2,
        swing_min_atr_mult=0.0,
        prefer_asia_sweep=False,
    )
    assert sel is not None
    assert sel.a.kind != sel.b.kind


def test_object_id_deterministic():
    a1 = AnchorPoint(time_utc="2026-05-19T00:00:00+00:00", price=100.0, kind="pivot_low")
    a2 = AnchorPoint(time_utc="2026-05-19T10:00:00+00:00", price=110.0, kind="pivot_high")
    levels = [ObjectLevel(value=0.618, text="61.8%")]
    oid1 = MT5ObjectSpec.compute_object_id(
        symbol="XAUUSD",
        timeframe="H1",
        object_type="OBJ_FIBO",
        anchors=[a1, a2],
        levels=levels,
    )
    oid2 = MT5ObjectSpec.compute_object_id(
        symbol="XAUUSD",
        timeframe="H1",
        object_type="OBJ_FIBO",
        anchors=[a1, a2],
        levels=levels,
    )
    assert oid1 == oid2


def test_mql_generator_contains_objectcreate():
    a1 = AnchorPoint(time_utc="2026-05-19T00:00:00+00:00", price=100.0, kind="pivot_low")
    a2 = AnchorPoint(time_utc="2026-05-19T10:00:00+00:00", price=110.0, kind="pivot_high")
    spec = MT5ObjectSpec(
        object_id="abc123",
        symbol="XAUUSD",
        timeframe="H1",
        object_type="OBJ_FIBO",
        anchor_1=a1,
        anchor_2=a2,
        levels=[ObjectLevel(value=0.5, text="50.0%")],
    )
    lines = to_mql_create_lines("fibtool_v2_xauusd_h1", spec)
    joined = "\n".join(lines)
    assert "ObjectCreate" in joined
    assert "OBJ_FIBO" in joined


def test_mql_generator_sets_description_and_compact_tooltip():
    a1 = AnchorPoint(time_utc="2026-05-19T00:00:00+00:00", price=100.0, kind="pivot_low")
    a2 = AnchorPoint(time_utc="2026-05-19T10:00:00+00:00", price=110.0, kind="pivot_high")
    spec = MT5ObjectSpec(
        object_id="abc123",
        symbol="XAUUSD",
        timeframe="H1",
        object_type="OBJ_FIBO",
        anchor_1=a1,
        anchor_2=a2,
        levels=[ObjectLevel(value=0.5, text="50.0%")],
        metadata={
            "description": "FIBONACCI RETRACEMENT DECISION REGION",
            "confidence": "HIGH",
            "confidence_score": 84.5,
            "trade_bias": "Bullish continuation",
            "expected_reaction": "Decision region reaction.",
            "risk_note": "Close beyond pivot origin invalidates setup.",
            "generated_by": "FibRetracementEngine V2",
        },
    )
    lines = to_mql_create_lines("fibtool_v2_xauusd_h1", spec)
    joined = "\n".join(lines)
    tooltip_line = next(line for line in lines if "OBJPROP_TOOLTIP" in line)
    tooltip_body = tooltip_line.split("OBJPROP_TOOLTIP, ", 1)[1]

    assert 'OBJPROP_TEXT, "FIBONACCI RETRACEMENT DECISION REGION"' in joined
    assert "Confidence: 84.5 (HIGH)" in tooltip_body
    assert "Bias: Bullish continuation" in tooltip_body
    assert "Risk: Close beyond pivot origin invalidates setup." in tooltip_body
    assert "abc123" not in tooltip_body
    assert "fibtool_v2_xauusd_h1" not in tooltip_body


def test_mql_generator_preserves_obj_text_visible_label_and_sets_tooltip():
    a1 = AnchorPoint(time_utc="2026-05-19T00:00:00+00:00", price=100.0, kind="label")
    spec = MT5ObjectSpec(
        object_id="label123",
        symbol="XAUUSD",
        timeframe="H1",
        object_type="OBJ_TEXT",
        anchor_1=a1,
        context=ObjectContext(label="confluence_label"),
        metadata={
            "text": "HIGH CONFLUENCE RESISTANCE",
            "description": "CONFLUENCE REACTION ZONE",
            "confidence": "HIGH",
            "confidence_score": 86,
            "trade_bias": "Moderate bearish reaction",
            "expected_reaction": "Pause or rejection.",
            "risk_note": "Zone close-through invalidates reaction.",
            "generated_by": "ConfluenceEngine V2",
        },
    )
    lines = to_mql_create_lines("fibtool_v2_xauusd_h1", spec)
    joined = "\n".join(lines)
    tooltip_line = next(line for line in lines if "OBJPROP_TOOLTIP" in line)
    tooltip_body = tooltip_line.split("OBJPROP_TOOLTIP, ", 1)[1]

    assert 'OBJPROP_TEXT, "HIGH CONFLUENCE RESISTANCE"' in joined
    assert 'OBJPROP_TEXT, "CONFLUENCE REACTION ZONE"' not in joined
    assert "CONFLUENCE REACTION ZONE" in tooltip_body
    assert "Confidence: 86 (HIGH)" in tooltip_body
    assert "label123" not in tooltip_body


def test_confluence_chart_text_is_compact():
    text = build_confluence_chart_text(score=78.4, fib_ratio=0.382, s9_degree=-45)
    assert text == "78 | Fib 0.382 | S9 -45deg"
    assert "Reaction" not in text
    assert "Risk" not in text
    assert "\n" not in text
