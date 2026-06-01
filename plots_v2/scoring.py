from __future__ import annotations


INSTRUMENT_WEIGHTS = {
    "BTC": 0.85,
    "BTCUSD": 0.85,
    "US30": 0.96,
    "XAU": 0.93,
    "XAUUSD": 0.93,
    "EURUSD": 0.98,
}


def instrument_weight(symbol: str) -> float:
    sym = str(symbol or "").upper().replace(".", "").replace("_", "")
    if sym in INSTRUMENT_WEIGHTS:
        return INSTRUMENT_WEIGHTS[sym]
    for key, weight in INSTRUMENT_WEIGHTS.items():
        if sym.startswith(key):
            return weight
    return 1.0


def confidence_label(score_0_to_100: float) -> str:
    score = float(score_0_to_100 or 0.0)
    if score >= 90:
        return "EXTREME"
    if score >= 80:
        return "HIGH"
    if score >= 60:
        return "STRONG"
    if score >= 40:
        return "MODERATE"
    return "WEAK"


def reaction_bias(anchor_a_price: float, anchor_b_price: float, level_price: float) -> str:
    try:
        direction_up = float(anchor_b_price) >= float(anchor_a_price)
        if direction_up:
            return "Moderate bearish reaction" if float(level_price) >= float(anchor_b_price) else "Bullish continuation decision"
        return "Moderate bullish reaction" if float(level_price) <= float(anchor_b_price) else "Bearish continuation decision"
    except Exception:
        return "Neutral reaction"
