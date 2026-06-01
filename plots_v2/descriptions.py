from __future__ import annotations

from copy import deepcopy
from typing import Any

from .scoring import confidence_label


DESCRIPTION_VERSION = "2.2"


DESCRIPTION_REGISTRY: dict[str, dict[str, Any]] = {
    "fib_retracement": {
        "title": "FIBONACCI RETRACEMENT DECISION REGION",
        "purpose": "Identify pullback zones inside an active impulse leg.",
        "market_context": "Generated after a significant pivot-to-pivot move where price may retrace before continuation.",
        "interpretation": "Retracement levels measure wave proportion after an impulse; the zone is useful only when price, ratio, and structure agree.",
        "expected_reaction": "Treat the level as a possible pattern-completion area: shallow reactions favor momentum, 0.500-0.618 is the main decision band, and 0.786 is a deep square-root retracement where continuation must prove itself.",
        "default_trade_bias": "Continuation while the pivot origin remains valid.",
        "risk_note": "A close beyond the pivot origin invalidates the retracement setup.",
        "generated_by": "FibRetracementEngine V2",
        "operator_note": "Do not treat the ratio alone as a signal; confirm pattern quality and define risk before execution.",
    },
    "fib_projection": {
        "title": "FIBONACCI PROJECTION REACTION PATH",
        "purpose": "Forecast expansion and reaction zones after an A-B-C structure.",
        "market_context": "Generated after an impulse, pullback, and continuation structure.",
        "interpretation": "Projection levels extend the A-B impulse from Pivot C to estimate where the next wave may complete in ratio and proportion.",
        "expected_reaction": "1.272, the square root of 1.618, is the first expansion checkpoint; 1.618 is the golden-mean expansion; 2.618 and 4.236 mark stretched continuation where reaction or acceleration risk increases.",
        "default_trade_bias": "Continuation until Pivot C or the active structure fails.",
        "risk_note": "A close beyond Pivot C invalidates the active projection path.",
        "generated_by": "FibProjectionEngine V2",
        "operator_note": "Use the projection to compare profit potential against the defined failure point; it is not a standalone prediction.",
    },
    "projection_D": {
        "title": "PROJECTED D REACTION LEVEL",
        "purpose": "Mark a projected expansion price derived from C plus the A-B impulse.",
        "market_context": "Generated from the same A-B-C structure as the parent projection object.",
        "interpretation": "The level is a projected completion point for the next wave, derived from C plus an A-B ratio.",
        "expected_reaction": "Expect a decision rather than a guaranteed target: price may pause, reject, or accelerate if the pattern remains valid into the D area.",
        "default_trade_bias": "Continuation checkpoint.",
        "risk_note": "Invalid when the parent projection structure fails.",
        "generated_by": "FibProjectionEngine V2",
        "operator_note": "Use the parent ABC quality and risk/reward before acting on an individual D marker.",
    },
    "confluence_zone": {
        "title": "CONFLUENCE REACTION ZONE",
        "purpose": "Merge independent geometry systems into a single reaction region.",
        "market_context": "Generated when Fibonacci, Square of Nine, and optional structure/timeframe signals overlap.",
        "interpretation": "Multiple independent measurements point to the same price region, creating a stronger pattern-completion candidate than any single level.",
        "expected_reaction": "Expect a behavioral change at the zone: hesitation, rejection, consolidation, or a continuation break. A clean failure through the zone often supports continuation.",
        "default_trade_bias": "Derived from the zone position and dominant geometry.",
        "risk_note": "A decisive close beyond the zone invalidates the immediate reaction expectation.",
        "generated_by": "ConfluenceEngine V2",
        "operator_note": "Highest value when ratio, pattern, and risk all line up; do not force the setup if the structure is not obvious.",
    },
    "square9_level": {
        "title": "SQUARE OF NINE ROTATIONAL LEVEL",
        "purpose": "Convert price into rotational geometry around a pivot.",
        "market_context": "Generated from the selected pivot price and ranked by distance to current price.",
        "interpretation": "The level acts like a vibratory price measurement around the pivot; repeated swings near the same rotation increase its usefulness.",
        "expected_reaction": "Use the level as a possible profit-projection or stop-placement reference; reaction quality improves when it aligns with Fibonacci or structure.",
        "default_trade_bias": "Support below price, resistance above price.",
        "risk_note": "A clean close through the level weakens the immediate reaction case.",
        "generated_by": "Square9Engine V2",
        "operator_note": "Use S9 levels as geometry context; confluence zones are preferred for action.",
    },
    "gann_fan": {
        "title": "GANN FAN PRICE/TIME EQUILIBRIUM",
        "purpose": "Map directional price/time balance from a selected pivot.",
        "market_context": "Generated from the latest qualified pivot using ATR or point-based scale.",
        "interpretation": "Fan angles compare price movement with time, helping judge whether the swing is maintaining proportion or losing momentum.",
        "expected_reaction": "The 1x1 area is a balance line: holding it supports the active swing; losing it warns that momentum and proportion are changing.",
        "default_trade_bias": "Bullish above equilibrium, bearish below equilibrium.",
        "risk_note": "Invalid when the selected pivot is replaced by a stronger structure.",
        "generated_by": "GannFanEngine V2",
        "operator_note": "Use with retracement and confluence layers; fan geometry alone is context.",
    },
    "gann_grid": {
        "title": "GANN GRID PRICE/TIME MAP",
        "purpose": "Project repeated price/time intervals from a selected pivot.",
        "market_context": "Generated from the latest qualified pivot using ATR or point-based scale.",
        "interpretation": "Grid intersections map repeated price/time vibration from the selected pivot.",
        "expected_reaction": "Price may pause or rebalance near intersections, especially when the grid agrees with a Fibonacci or S9 reaction level.",
        "default_trade_bias": "Directional context depends on which side of equilibrium price holds.",
        "risk_note": "Invalid when the selected pivot is replaced by a stronger structure.",
        "generated_by": "GannGridEngine V2",
        "operator_note": "Use the grid to frame reactions, not as a standalone entry signal.",
    },
    "fib_time": {
        "title": "FIBONACCI TIME WINDOW",
        "purpose": "Project future timing windows from the selected swing.",
        "market_context": "Generated from the same A-B swing used by price geometry.",
        "interpretation": "Time ratios estimate when a wave may complete or change behavior, complementing price-ratio analysis.",
        "expected_reaction": "Watch for acceleration, consolidation, or reversal only when the timing window coincides with price structure or confluence.",
        "default_trade_bias": "Neutral timing context.",
        "risk_note": "Timing windows lose value when price structure changes before the window is reached.",
        "generated_by": "FibTimeEngine V2",
        "operator_note": "Time windows require price confirmation from structure or confluence.",
    },
    "asia_range": {
        "title": "ASIA STRUCTURE RANGE",
        "purpose": "Show the session range that may define liquidity and breakout behavior.",
        "market_context": "Generated from the latest Asia/MSS signal record.",
        "interpretation": "The range frames sweep, breakout, and mean-reversion behavior after Asia.",
        "expected_reaction": "Sweeps beyond the range can trigger rejection, continuation, or MSS confirmation.",
        "default_trade_bias": "Neutral until sweep or break direction is confirmed.",
        "risk_note": "Invalid when the session range is stale or a newer structure replaces it.",
        "generated_by": "StructureOverlayEngine V2",
        "operator_note": "Use sweeps as anchor context for retracement and confluence generation.",
    },
    "sweep_high": {
        "title": "ASIA HIGH LIQUIDITY SWEEP",
        "purpose": "Mark a sweep above the Asia range high.",
        "market_context": "Generated when the Asia signal reports sweep_high.",
        "interpretation": "Buy-side liquidity was taken; reaction risk increases if price fails to hold above the range.",
        "expected_reaction": "Rejection, consolidation, or continuation after acceptance above the high.",
        "default_trade_bias": "Bearish reaction unless price accepts above the swept high.",
        "risk_note": "Invalid when price accepts and closes above the sweep region.",
        "generated_by": "StructureOverlayEngine V2",
        "operator_note": "Check MSS or displacement before treating the sweep as reversal evidence.",
    },
    "sweep_low": {
        "title": "ASIA LOW LIQUIDITY SWEEP",
        "purpose": "Mark a sweep below the Asia range low.",
        "market_context": "Generated when the Asia signal reports sweep_low.",
        "interpretation": "Sell-side liquidity was taken; reaction risk increases if price fails to hold below the range.",
        "expected_reaction": "Rejection, consolidation, or continuation after acceptance below the low.",
        "default_trade_bias": "Bullish reaction unless price accepts below the swept low.",
        "risk_note": "Invalid when price accepts and closes below the sweep region.",
        "generated_by": "StructureOverlayEngine V2",
        "operator_note": "Check MSS or displacement before treating the sweep as reversal evidence.",
    },
}


def score_to_100(score: float | None) -> float:
    if score is None:
        return 0.0
    val = float(score)
    if val <= 1.0:
        val *= 100.0
    return max(0.0, min(100.0, val))


def build_description_metadata(
    key: str,
    *,
    score: float | None = None,
    trade_bias: str | None = None,
    anchor_source: str | None = None,
    components: list[str] | None = None,
    risk_note: str | None = None,
    operator_note: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = deepcopy(DESCRIPTION_REGISTRY.get(key, {}))
    score_100 = score_to_100(score)
    title = str(base.get("title", key.replace("_", " ").upper()))
    out = {
        "description_version": DESCRIPTION_VERSION,
        "description": title,
        "summary": base.get("interpretation", ""),
        "purpose": base.get("purpose", ""),
        "market_context": base.get("market_context", ""),
        "interpretation": base.get("interpretation", ""),
        "expected_reaction": base.get("expected_reaction", ""),
        "trade_bias": trade_bias or base.get("default_trade_bias", "Neutral"),
        "confidence": confidence_label(score_100),
        "confidence_score": round(score_100, 2),
        "risk_note": risk_note or base.get("risk_note", ""),
        "operator_note": operator_note or base.get("operator_note", ""),
        "generated_by": base.get("generated_by", ""),
        "anchor_source": anchor_source or "",
        "components": list(components or []),
    }
    if extra:
        out.update(extra)
    return out


def build_confluence_chart_text(*, score: float, fib_ratio: float, s9_degree: float) -> str:
    """Minimal on-chart confluence label; full narrative belongs in tooltip metadata."""
    return f"{float(score):.0f} | Fib {float(fib_ratio):g} | S9 {float(s9_degree):g}deg"


def swing_trade_bias(a_price: float, b_price: float) -> str:
    try:
        return "Bullish continuation" if float(b_price) >= float(a_price) else "Bearish continuation"
    except Exception:
        return "Neutral"


def level_trade_bias(level_price: float, reference_price: float) -> str:
    try:
        return "Resistance reaction" if float(level_price) >= float(reference_price) else "Support reaction"
    except Exception:
        return "Neutral reaction"
