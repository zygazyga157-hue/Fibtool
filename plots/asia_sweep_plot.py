"""
Production Tool: Asia Sweep Plot
==================================

Draws Asia range lines, Fib levels, and liquidity pools on MT5 charts from Asia Sweep signals.

Features:
- Plots horizontal lines at Asia high/low with liquidity pool highlighting
- Shows Fibonacci retracement levels for valid trade setups
- Color-coded: red for resistance (Asia high), blue for support (Asia low)
- Thicker lines for EQH/EQL liquidity pools
- Entry levels for qualified trades
- Clean labels with signal details

Usage:
    python plots/asia_sweep_plot.py --symbols EURUSD,GBPUSD --once
    python plots/asia_sweep_plot.py --symbols XAUUSD --cleanup
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

def symbol_slug(symbol: str) -> str:
    """Filesystem-safe slug for a symbol (lowercase, non-alnum -> _)."""
    try:
        return ''.join(ch if ch.isalnum() else '_' for ch in str(symbol)).replace('/', '_').replace(' ', '_').lower()
    except Exception:
        return str(symbol).replace('/', '_').replace(' ', '_').lower()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False

try:
    from config import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, MT5_PATH
except ImportError:
    MT5_LOGIN = None
    MT5_PASSWORD = None
    MT5_SERVER = None
    MT5_PATH = None

# Configuration
OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
OBJECT_PREFIX = "fibtool_asia"
_DEFAULT_MT5_DATA_FOLDER = Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "D0E8209F77C8CF37AD8BF550E51FF075"
# Optional override for portability across MT5 installs/profiles.
# Example: set FIBTOOL_MT5_DATA_FOLDER="C:\\Users\\<you>\\AppData\\Roaming\\MetaQuotes\\Terminal\\<terminal_id>"
MT5_DATA_FOLDER = Path(os.environ.get("FIBTOOL_MT5_DATA_FOLDER", str(_DEFAULT_MT5_DATA_FOLDER)))
MQL5_SCRIPTS_DIR = MT5_DATA_FOLDER / "MQL5" / "Scripts"


def _parse_iso_dt(value: Any) -> Optional[datetime]:
    """Best-effort parse for ISO timestamps with timezone offsets (or 'Z')."""
    if not value:
        return None
    try:
        s = str(value).strip()
        if not s:
            return None
        # datetime.fromisoformat doesn't accept "Z" suffix.
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in ("1", "true", "t", "yes", "y", "on")


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _maybe_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return default
    s = value.strip()
    if not s:
        return default
    try:
        return json.loads(s)
    except Exception:
        return default


def _mql5_escape(value: Any) -> str:
    """Escape a value for inclusion in a MQL5 double-quoted string literal."""
    s = "" if value is None else str(value)
    return s.replace("\\", "\\\\").replace('"', '\\"')

def connect_mt5():
    """Initialize and connect to MT5."""
    if not MT5_AVAILABLE:
        raise RuntimeError("MetaTrader5 not installed. Run: pip install MetaTrader5")

    if not mt5.initialize(MT5_PATH):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")

    try:
        mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
    except:
        pass  # Continue even if login fails

    print(f"[MT5] Connected to {MT5_SERVER}")


def load_asia_signals(symbol: str, *, output_dir: Path = OUTPUT_DIR) -> Optional[dict]:
    """Load the latest Asia sweep signal for a symbol.

    Prefers JSONL (native types, nested mss/m5/trade_setup/pretrade) and falls back to CSV.
    Timestamp ordering uses datetime parsing (not lexicographic string max).
    """
    symbol_u = str(symbol).upper()

    jsonl_path = output_dir / "asia_mss_signals.jsonl"
    if jsonl_path.exists():
        latest: Optional[dict] = None
        latest_dt: Optional[datetime] = None

        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if str(rec.get("symbol", "")).upper() != symbol_u:
                    continue
                ts = rec.get("timestamp") or rec.get("timestamp_session") or rec.get("timestamp_local")
                dt = _parse_iso_dt(ts)
                if dt is None:
                    dt = datetime.min.replace(tzinfo=timezone.utc)

                if latest is None or latest_dt is None or dt > latest_dt:
                    latest = rec
                    latest_dt = dt

        if latest:
            print(f"[JSONL] Loaded latest signal for {symbol_u} from {latest.get('timestamp')}")
            return latest

    csv_path = output_dir / "asia_mss_signals.csv"
    if not csv_path.exists():
        print("[DATA] No asia_mss_signals.jsonl or asia_mss_signals.csv found")
        return None

    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    symbol_rows = [r for r in rows if str(r.get("symbol", "")).upper() == symbol_u]
    if not symbol_rows:
        print(f"[CSV] No signals found for {symbol_u}")
        return None

    def _row_dt(r: dict) -> datetime:
        dt = _parse_iso_dt(r.get("timestamp") or r.get("timestamp_session") or r.get("timestamp_local"))
        return dt or datetime.min.replace(tzinfo=timezone.utc)

    latest_row = max(symbol_rows, key=_row_dt)

    # Normalize CSV row into JSONL-like structure for plotting.
    out: dict[str, Any] = dict(latest_row)
    out["symbol"] = symbol_u
    out["current_price"] = _coerce_float(out.get("current_price"), 0.0)
    out["asia_high"] = _coerce_float(out.get("asia_high"), 0.0)
    out["asia_low"] = _coerce_float(out.get("asia_low"), 0.0)
    out["eqh_liquidity_pool"] = _coerce_bool(out.get("eqh_liquidity_pool"))
    out["eql_liquidity_pool"] = _coerce_bool(out.get("eql_liquidity_pool"))
    try:
        out["eqh_touch_count"] = int(float(out.get("eqh_touch_count") or 0))
    except Exception:
        out["eqh_touch_count"] = 0
    try:
        out["eql_touch_count"] = int(float(out.get("eql_touch_count") or 0))
    except Exception:
        out["eql_touch_count"] = 0

    out["in_london"] = _coerce_bool(out.get("in_london"))
    out["in_asia"] = _coerce_bool(out.get("in_asia"))
    out["sweep_high"] = _coerce_bool(out.get("sweep_high"))
    out["sweep_low"] = _coerce_bool(out.get("sweep_low"))

    out["fib_ratio"] = _coerce_float(out.get("fib_ratio"), 0.71)
    out["fib_long"] = _coerce_float(out.get("fib_long"), 0.0)
    out["fib_short"] = _coerce_float(out.get("fib_short"), 0.0)

    out["m5"] = _maybe_json(out.get("m5"), {})
    out["mss"] = _maybe_json(out.get("mss"), {})
    out["trade_setup"] = _maybe_json(out.get("trade_setup"), {"valid": False, "reason": "Not qualified"})
    out["pretrade"] = _maybe_json(out.get("pretrade"), {"passed": False, "reason": "Not qualified"})

    print(f"[CSV] Loaded latest signal for {symbol_u} from {out.get('timestamp')}")
    return out


def _generate_mql5_script_legacy(symbol: str, signal: dict) -> str:
    """Generate advanced MQL5 script to draw Asia sweep elements with detailed styling."""
    if not signal:
        return None

    draw_commands = []
    idx = 0

    # Get current price for reference
    current_price = float(signal.get('current_price', 0) or 0)
    asia_high = float(signal.get('asia_high', 0) or 0)
    asia_low = float(signal.get('asia_low', 0) or 0)

    if asia_high <= 0 or asia_low <= 0 or current_price <= 0:
        return None

    # Calculate range and mid-point
    asia_range = asia_high - asia_low
    asia_mid = (asia_high + asia_low) / 2

    # ═══════════════════════════════════════════════════════════════
    # 1. ASIA RANGE BACKGROUND ZONE
    # ═══════════════════════════════════════════════════════════════
    zone_name = f"{OBJECT_PREFIX}_{symbol}_asia_zone"
    zone_color = "clrLightGray"  # Subtle background
    zone_alpha = 30  # 30% opacity

    draw_commands.append(f"""
   // Asia Range Background Zone
   if(!ObjectCreate(chartId, "{zone_name}", OBJ_RECTANGLE, 0, TimeCurrent()-PeriodSeconds(PERIOD_CURRENT)*200, {asia_high}, TimeCurrent()+PeriodSeconds(PERIOD_CURRENT)*50, {asia_low}))
   {{
      Print("✗ Error creating Asia zone: ", GetLastError());
   }}
   else
   {{
      ObjectSetInteger(chartId, "{zone_name}", OBJPROP_COLOR, {zone_color});
      ObjectSetInteger(chartId, "{zone_name}", OBJPROP_BACK, true);
      ObjectSetInteger(chartId, "{zone_name}", OBJPROP_FILL, true);
      ObjectSetInteger(chartId, "{zone_name}", OBJPROP_WIDTH, 1);
      ObjectSetInteger(chartId, "{zone_name}", OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetString(chartId, "{zone_name}", OBJPROP_TOOLTIP, "Asia Session Range: {asia_low:.5f} - {asia_high:.5f}");
      Print("✓ Asia range zone created");
   }}
""")
    # ═══════════════════════════════════════════════════════════════
    # 2. ASIA HIGH LINE WITH ADVANCED STYLING
    # ═══════════════════════════════════════════════════════════════
    eqh_pool = signal.get('eqh_liquidity_pool', 'False').lower() == 'true'
    eqh_count = int(signal.get('eqh_touch_count', 1) or 1)

    if eqh_pool:
        # Liquidity pool - thicker, gradient effect with multiple lines
        high_color = "clrOrangeRed"
        high_width = 3
        high_style = "STYLE_SOLID"
        # Add secondary line slightly offset for depth effect
        draw_commands.append(f"""
   // EQH Pool Secondary Line (depth effect)
   if(!ObjectCreate(chartId, "{OBJECT_PREFIX}_{symbol}_asia_high_bg", OBJ_HLINE, 0, 0, {asia_high + 0.0001}))
   {{
      Print("✗ Error creating Asia High BG: ", GetLastError());
   }}
   else
   {{
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_asia_high_bg", OBJPROP_COLOR, clrDarkOrange);
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_asia_high_bg", OBJPROP_WIDTH, 5);
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_asia_high_bg", OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_asia_high_bg", OBJPROP_BACK, true);
      Print("✓ EQH pool background line");
   }}
""")
    else:
        high_color = "clrRed"
        high_width = 2
        high_style = "STYLE_SOLID"

    line_name = f"{OBJECT_PREFIX}_{symbol}_asia_high"
    label_name = f"{OBJECT_PREFIX}_{symbol}_asia_high_label"

    label_text = f"Asia High: {asia_high:.5f}"
    if eqh_pool:
        label_text += f" ⚡ EQH Pool ({eqh_count} touches)"

    draw_commands.append(f"""
   // Asia High Main Line
   if(!ObjectCreate(chartId, "{line_name}", OBJ_HLINE, 0, 0, {asia_high}))
   {{
      Print("✗ Error creating Asia High line: ", GetLastError());
   }}
   else
   {{
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_COLOR, {high_color});
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_WIDTH, {high_width});
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_STYLE, {high_style});
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_BACK, false);
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_SELECTABLE, true);
      ObjectSetString(chartId, "{line_name}", OBJPROP_TOOLTIP, "{label_text} | Resistance Level");
      Print("✓ Asia High at {asia_high}");
   }}

   // Asia High Enhanced Label
   datetime labelTime_high = TimeCurrent() + PeriodSeconds(PERIOD_CURRENT) * 5;
   if(!ObjectCreate(chartId, "{label_name}", OBJ_TEXT, 0, labelTime_high, {asia_high}))
   {{
      Print("✗ Error creating Asia High label: ", GetLastError());
   }}
   else
   {{
      ObjectSetString(chartId, "{label_name}", OBJPROP_TEXT, "{label_text}");
      ObjectSetString(chartId, "{label_name}", OBJPROP_FONT, "Arial Black");
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_COLOR, {high_color});
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_FONTSIZE, 10);
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_ANCHOR, ANCHOR_LEFT);
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_BACK, false);
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_SELECTABLE, true);
      Print("✓ Asia High label: {label_text}");
   }}
""")

    # ═══════════════════════════════════════════════════════════════
    # 3. ASIA LOW LINE WITH ADVANCED STYLING
    # ═══════════════════════════════════════════════════════════════
    eql_pool = signal.get('eql_liquidity_pool', 'False').lower() == 'true'
    eql_count = int(signal.get('eql_touch_count', 1) or 1)

    if eql_pool:
        low_color = "clrDodgerBlue"
        low_width = 3
        low_style = "STYLE_SOLID"
        # Add secondary line for depth
        draw_commands.append(f"""
   // EQL Pool Secondary Line (depth effect)
   if(!ObjectCreate(chartId, "{OBJECT_PREFIX}_{symbol}_asia_low_bg", OBJ_HLINE, 0, 0, {asia_low - 0.0001}))
   {{
      Print("✗ Error creating Asia Low BG: ", GetLastError());
   }}
   else
   {{
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_asia_low_bg", OBJPROP_COLOR, clrDarkBlue);
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_asia_low_bg", OBJPROP_WIDTH, 5);
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_asia_low_bg", OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_asia_low_bg", OBJPROP_BACK, true);
      Print("✓ EQL pool background line");
   }}
""")
    else:
        low_color = "clrBlue"
        low_width = 2
        low_style = "STYLE_SOLID"

    line_name = f"{OBJECT_PREFIX}_{symbol}_asia_low"
    label_name = f"{OBJECT_PREFIX}_{symbol}_asia_low_label"

    label_text = f"Asia Low: {asia_low:.5f}"
    if eql_pool:
        label_text += f" ⚡ EQL Pool ({eql_count} touches)"

    draw_commands.append(f"""
   // Asia Low Main Line
   if(!ObjectCreate(chartId, "{line_name}", OBJ_HLINE, 0, 0, {asia_low}))
   {{
      Print("✗ Error creating Asia Low line: ", GetLastError());
   }}
   else
   {{
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_COLOR, {low_color});
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_WIDTH, {low_width});
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_STYLE, {low_style});
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_BACK, false);
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_SELECTABLE, true);
      ObjectSetString(chartId, "{line_name}", OBJPROP_TOOLTIP, "{label_text} | Support Level");
      Print("✓ Asia Low at {asia_low}");
   }}

   // Asia Low Enhanced Label
   datetime labelTime_low = TimeCurrent() + PeriodSeconds(PERIOD_CURRENT) * 10;
   if(!ObjectCreate(chartId, "{label_name}", OBJ_TEXT, 0, labelTime_low, {asia_low}))
   {{
      Print("✗ Error creating Asia Low label: ", GetLastError());
   }}
   else
   {{
      ObjectSetString(chartId, "{label_name}", OBJPROP_TEXT, "{label_text}");
      ObjectSetString(chartId, "{label_name}", OBJPROP_FONT, "Arial Black");
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_COLOR, {low_color});
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_FONTSIZE, 10);
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_ANCHOR, ANCHOR_LEFT);
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_BACK, false);
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_SELECTABLE, true);
      Print("✓ Asia Low label: {label_text}");
   }}
""")

    # ═══════════════════════════════════════════════════════════════
    # 4. FIBONACCI RETRACEMENT ZONES
    # ═══════════════════════════════════════════════════════════════
    fib_ratio = float(signal.get('fib_ratio', 0.71) or 0.71)
    fib_long = float(signal.get('fib_long', 0) or 0)
    fib_short = float(signal.get('fib_short', 0) or 0)

    if fib_long > 0 and fib_short > 0:
        # Create Fib zone rectangles
        fib_zone_color = "clrLightGreen"
        fib_zone_alpha = 20

        # Long zone (below fib_long)
        draw_commands.append(f"""
   // Fibonacci Long Zone
   if(!ObjectCreate(chartId, "{OBJECT_PREFIX}_{symbol}_fib_long_zone", OBJ_RECTANGLE, 0, TimeCurrent()-PeriodSeconds(PERIOD_CURRENT)*150, {fib_long}, TimeCurrent()+PeriodSeconds(PERIOD_CURRENT)*25, {asia_low}))
   {{
      Print("✗ Error creating Fib Long zone: ", GetLastError());
   }}
   else
   {{
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_fib_long_zone", OBJPROP_COLOR, {fib_zone_color});
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_fib_long_zone", OBJPROP_BACK, true);
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_fib_long_zone", OBJPROP_FILL, true);
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_fib_long_zone", OBJPROP_WIDTH, 1);
      ObjectSetString(chartId, "{OBJECT_PREFIX}_{symbol}_fib_long_zone", OBJPROP_TOOLTIP, "Fib {fib_ratio} Long Zone: {fib_long:.5f}");
      Print("✓ Fib Long zone created");
   }}
""")

        # Short zone (above fib_short)
        draw_commands.append(f"""
   // Fibonacci Short Zone
   if(!ObjectCreate(chartId, "{OBJECT_PREFIX}_{symbol}_fib_short_zone", OBJ_RECTANGLE, 0, TimeCurrent()-PeriodSeconds(PERIOD_CURRENT)*150, {asia_high}, TimeCurrent()+PeriodSeconds(PERIOD_CURRENT)*25, {fib_short}))
   {{
      Print("✗ Error creating Fib Short zone: ", GetLastError());
   }}
   else
   {{
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_fib_short_zone", OBJPROP_COLOR, clrLightPink);
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_fib_short_zone", OBJPROP_BACK, true);
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_fib_short_zone", OBJPROP_FILL, true);
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_fib_short_zone", OBJPROP_WIDTH, 1);
      ObjectSetString(chartId, "{OBJECT_PREFIX}_{symbol}_fib_short_zone", OBJPROP_TOOLTIP, "Fib {fib_ratio} Short Zone: {fib_short:.5f}");
      Print("✓ Fib Short zone created");
   }}
""")

    # ═══════════════════════════════════════════════════════════════
    # 5. TRADE ENTRY LEVELS WITH ALERT ZONES
    # ═══════════════════════════════════════════════════════════════
    trade_setup = json.loads(signal.get('trade_setup', '{}') or '{}')
    if trade_setup.get('valid'):
        entry_price = float(trade_setup.get('entry', 0) or 0)
        stop_loss = float(trade_setup.get('stop_loss', 0) or 0)
        take_profit = float(trade_setup.get('take_profit', 0) or 0)
        trade_type = trade_setup.get('type', 'Unknown')
        method = trade_setup.get('method', 'Unknown')

        if entry_price > 0:
            # Entry line
            entry_color = "clrGreen" if trade_type == 'Long' else "clrMagenta"
            entry_line_name = f"{OBJECT_PREFIX}_{symbol}_entry"
            entry_label_name = f"{OBJECT_PREFIX}_{symbol}_entry_label"

            draw_commands.append(f"""
   // Entry Level Line
   if(!ObjectCreate(chartId, "{entry_line_name}", OBJ_HLINE, 0, 0, {entry_price}))
   {{
      Print("✗ Error creating Entry line: ", GetLastError());
   }}
   else
   {{
      ObjectSetInteger(chartId, "{entry_line_name}", OBJPROP_COLOR, {entry_color});
      ObjectSetInteger(chartId, "{entry_line_name}", OBJPROP_WIDTH, 2);
      ObjectSetInteger(chartId, "{entry_line_name}", OBJPROP_STYLE, STYLE_DASH);
      ObjectSetInteger(chartId, "{entry_line_name}", OBJPROP_BACK, false);
      ObjectSetInteger(chartId, "{entry_line_name}", OBJPROP_SELECTABLE, true);
      ObjectSetString(chartId, "{entry_line_name}", OBJPROP_TOOLTIP, "{trade_type} Entry: {entry_price:.5f} | {method}");
      Print("✓ Entry at {entry_price}");
   }}

   // Entry Label with Arrow
   datetime labelTime_entry = TimeCurrent() + PeriodSeconds(PERIOD_CURRENT) * 15;
   string entry_arrow = "{trade_type}" == "Long" ? "▲" : "▼";
   string entry_label_text = StringFormat("%s %s Entry: %.5f", entry_arrow, "{trade_type}", {entry_price});
   if(!ObjectCreate(chartId, "{entry_label_name}", OBJ_TEXT, 0, labelTime_entry, {entry_price}))
   {{
      Print("✗ Error creating Entry label: ", GetLastError());
   }}
   else
   {{
      ObjectSetString(chartId, "{entry_label_name}", OBJPROP_TEXT, entry_label_text);
      ObjectSetString(chartId, "{entry_label_name}", OBJPROP_FONT, "Wingdings");
      ObjectSetInteger(chartId, "{entry_label_name}", OBJPROP_COLOR, {entry_color});
      ObjectSetInteger(chartId, "{entry_label_name}", OBJPROP_FONTSIZE, 12);
      ObjectSetInteger(chartId, "{entry_label_name}", OBJPROP_ANCHOR, ANCHOR_LEFT);
      ObjectSetInteger(chartId, "{entry_label_name}", OBJPROP_BACK, false);
      Print("✓ Entry label: ", entry_label_text);
   }}
""")

            # Alert zone around entry (2% buffer)
            buffer_pct = 0.02
            buffer_amount = entry_price * buffer_pct
            alert_zone_top = entry_price + buffer_amount
            alert_zone_bottom = entry_price - buffer_amount

            draw_commands.append(f"""
   // Entry Alert Zone
   if(!ObjectCreate(chartId, "{OBJECT_PREFIX}_{symbol}_entry_alert_zone", OBJ_RECTANGLE, 0, TimeCurrent()-PeriodSeconds(PERIOD_CURRENT)*100, {alert_zone_top}, TimeCurrent()+PeriodSeconds(PERIOD_CURRENT)*10, {alert_zone_bottom}))
   {{
      Print("✗ Error creating Entry alert zone: ", GetLastError());
   }}
   else
   {{
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_entry_alert_zone", OBJPROP_COLOR, clrYellow);
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_entry_alert_zone", OBJPROP_BACK, true);
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_entry_alert_zone", OBJPROP_FILL, true);
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_entry_alert_zone", OBJPROP_WIDTH, 1);
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_entry_alert_zone", OBJPROP_STYLE, STYLE_DOT);
      ObjectSetString(chartId, "{OBJECT_PREFIX}_{symbol}_entry_alert_zone", OBJPROP_TOOLTIP, "Entry Alert Zone: {alert_zone_bottom:.5f} - {alert_zone_top:.5f}");
      Print("✓ Entry alert zone created");
   }}
""")

    # ═══════════════════════════════════════════════════════════════
    # 6. CURRENT PRICE MARKER
    # ═══════════════════════════════════════════════════════════════
    draw_commands.append(f"""
   // Current Price Marker
   if(!ObjectCreate(chartId, "{OBJECT_PREFIX}_{symbol}_current_price", OBJ_HLINE, 0, 0, {current_price}))
   {{
      Print("✗ Error creating Current Price line: ", GetLastError());
   }}
   else
   {{
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_current_price", OBJPROP_COLOR, clrWhite);
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_current_price", OBJPROP_WIDTH, 1);
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_current_price", OBJPROP_STYLE, STYLE_DOT);
      ObjectSetInteger(chartId, "{OBJECT_PREFIX}_{symbol}_current_price", OBJPROP_BACK, false);
      ObjectSetString(chartId, "{OBJECT_PREFIX}_{symbol}_current_price", OBJPROP_TOOLTIP, "Current Price: {current_price:.5f}");
      Print("✓ Current price marker at {current_price}");
   }}
""")

    if not draw_commands:
        return None

    # Complete MQL5 script with enhanced header
    script = f"""//+------------------------------------------------------------------+
//|                     FibtoolAsiaSweep_{symbol}.mq5               |
//|                  Advanced Asia Sweep Strategy Plot                |
//|              Draws ranges, Fib zones, and entry levels            |
//+------------------------------------------------------------------+
#property copyright "Fibtool"
#property version   "2.00"
#property description "Advanced Asia Sweep plotting with liquidity pools, Fib zones, and alert areas"

void OnStart()
{{
   long chartId = ChartID();
   Print("Starting Advanced Asia Sweep plot for {symbol}...");
   Print("Features: Asia zones, EQH/EQL pools, Fib retracements, entry alerts");
   
   // Remove existing objects
   ObjectsDeleteAll(chartId, "{OBJECT_PREFIX}_{symbol}");
   
   // Draw advanced objects
   {''.join(draw_commands)}
   
   Print("Advanced Asia Sweep plot completed for {symbol}");
   Print("Objects created: Asia ranges, liquidity pools, Fib zones, entry levels, alert areas");
   ChartRedraw(chartId);
}}
"""

    return script


def generate_mql5_script_rich(symbol: str, signal: dict) -> Optional[str]:
    """Generate the Asia Sweep MT5 overlay (rich).

    Adds:
    - JSONL-first parsing (callers should pass a JSONL-like dict)
    - Always-on live-read status panel
    - MSS thresholds + current M5 context lines
    - Digit/point-aware formatting (no hard-coded 0.0001 offsets or %.5f)
    - Prefix-based cleanup (safe redraw)
    """
    if not signal:
        return None

    symbol_u = str(symbol).upper()
    sym_slug = symbol_slug(symbol_u)
    prefix = f"{OBJECT_PREFIX}_{sym_slug}"

    current_price = _coerce_float(signal.get("current_price"), 0.0)
    asia_high = _coerce_float(signal.get("asia_high"), 0.0)
    asia_low = _coerce_float(signal.get("asia_low"), 0.0)
    if asia_high <= 0 or asia_low <= 0:
        return None

    eqh_pool = _coerce_bool(signal.get("eqh_liquidity_pool"))
    eql_pool = _coerce_bool(signal.get("eql_liquidity_pool"))
    try:
        eqh_count = int(float(signal.get("eqh_touch_count") or 0))
    except Exception:
        eqh_count = 0
    try:
        eql_count = int(float(signal.get("eql_touch_count") or 0))
    except Exception:
        eql_count = 0

    sweep_high = _coerce_bool(signal.get("sweep_high"))
    sweep_low = _coerce_bool(signal.get("sweep_low"))
    in_london = _coerce_bool(signal.get("in_london"))
    in_asia = _coerce_bool(signal.get("in_asia"))

    fib_ratio = _coerce_float(signal.get("fib_ratio"), 0.71)
    fib_long = _coerce_float(signal.get("fib_long"), 0.0)
    fib_short = _coerce_float(signal.get("fib_short"), 0.0)

    mss = _maybe_json(signal.get("mss"), {})
    if not isinstance(mss, dict):
        mss = {}
    bull_mss = _coerce_bool(mss.get("bullMSS"))
    bear_mss = _coerce_bool(mss.get("bearMSS"))

    curr_m5 = _maybe_json(mss.get("current_m5"), {})
    if not isinstance(curr_m5, dict):
        curr_m5 = {}
    m5_high = _coerce_float(curr_m5.get("high"), 0.0)
    m5_low = _coerce_float(curr_m5.get("low"), 0.0)
    m5_close = _coerce_float(curr_m5.get("close"), 0.0)

    prev3 = _maybe_json(mss.get("prev3"), {})
    if not isinstance(prev3, dict):
        prev3 = {}
    prev3_high_max = 0.0
    prev3_low_min = 0.0
    try:
        highs = prev3.get("high") or {}
        lows = prev3.get("low") or {}
        if isinstance(highs, dict) and highs:
            prev3_high_max = max(_coerce_float(v, 0.0) for v in highs.values())
        if isinstance(lows, dict) and lows:
            prev3_low_min = min(_coerce_float(v, 0.0) for v in lows.values())
    except Exception:
        prev3_high_max = 0.0
        prev3_low_min = 0.0

    trade_setup = _maybe_json(signal.get("trade_setup"), {"valid": False, "reason": "Not qualified"})
    pretrade = _maybe_json(signal.get("pretrade"), {"passed": False, "reason": ""})
    if not isinstance(trade_setup, dict):
        trade_setup = {"valid": False, "reason": "Not qualified"}
    if not isinstance(pretrade, dict):
        pretrade = {"passed": False, "reason": ""}

    trade_valid = _coerce_bool(trade_setup.get("valid"))
    trade_reason = str(trade_setup.get("reason") or "")
    trade_type = str(trade_setup.get("type") or "")
    trade_method = str(trade_setup.get("method") or "")

    pretrade_passed = _coerce_bool(pretrade.get("passed"))
    pretrade_reason = str(pretrade.get("reason") or "")
    lots_txt = "" if pretrade.get("lots") is None else str(pretrade.get("lots"))
    rr_txt = "" if pretrade.get("rr") is None else str(pretrade.get("rr"))

    entry_price = _coerce_float(trade_setup.get("entry"), 0.0)
    stop_loss = _coerce_float(trade_setup.get("stop_loss"), 0.0)
    take_profit = _coerce_float(trade_setup.get("take_profit"), 0.0)

    timestamp_session = _mql5_escape(signal.get("timestamp_session") or signal.get("timestamp") or "")
    session_tz = _mql5_escape(signal.get("session_tz") or "")

    if trade_valid and pretrade_passed:
        panel_color = "clrDarkGreen"
        panel_alpha = 40
        panel_state = "TRADE OK"
    elif trade_valid and not pretrade_passed:
        panel_color = "clrOrange"
        panel_alpha = 45
        panel_state = "TRADE BLOCKED"
    else:
        panel_color = "clrFireBrick"
        panel_alpha = 45
        panel_state = "NO TRADE"

    # Signal-based buffer term (price units). The point-based min is computed in MQL5.
    buffer_range_term = max((m5_high - m5_low) * 0.15, 0.0)

    draw: list[str] = []

    draw.append(f"""
   // Status panel (always drawn)
   string panelBg = prefix + "_panel_bg";
   string panelTx = prefix + "_panel_text";

   if(ObjectCreate(chartId, panelBg, OBJ_RECTANGLE_LABEL, 0, 0, 0))
   {{
      ObjectSetInteger(chartId, panelBg, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(chartId, panelBg, OBJPROP_XDISTANCE, 10);
      ObjectSetInteger(chartId, panelBg, OBJPROP_YDISTANCE, 20);
      ObjectSetInteger(chartId, panelBg, OBJPROP_XSIZE, 370);
      ObjectSetInteger(chartId, panelBg, OBJPROP_YSIZE, 190);
      ObjectSetInteger(chartId, panelBg, OBJPROP_COLOR, ColorToARGB({panel_color}, {panel_alpha}));
      ObjectSetInteger(chartId, panelBg, OBJPROP_BACK, true);
   }}

   if(ObjectCreate(chartId, panelTx, OBJ_LABEL, 0, 0, 0))
   {{
      ObjectSetInteger(chartId, panelTx, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(chartId, panelTx, OBJPROP_XDISTANCE, 18);
      ObjectSetInteger(chartId, panelTx, OBJPROP_YDISTANCE, 26);
      ObjectSetInteger(chartId, panelTx, OBJPROP_COLOR, clrWhite);
      ObjectSetInteger(chartId, panelTx, OBJPROP_FONTSIZE, 9);
      ObjectSetString(chartId, panelTx, OBJPROP_FONT, "Consolas");

      string bullTh = ({prev3_high_max} > 0.0 ? DoubleToString({prev3_high_max}, digits) : "n/a");
      string bearTh = ({prev3_low_min} > 0.0 ? DoubleToString({prev3_low_min}, digits) : "n/a");
      string fibL = ({fib_long} > 0.0 ? DoubleToString({fib_long}, digits) : "n/a");
      string fibS = ({fib_short} > 0.0 ? DoubleToString({fib_short}, digits) : "n/a");
      string entryTxt = ({entry_price} > 0.0 ? DoubleToString({entry_price}, digits) : "n/a");
      string slTxt = ({stop_loss} > 0.0 ? DoubleToString({stop_loss}, digits) : "n/a");
      string tpTxt = ({take_profit} > 0.0 ? DoubleToString({take_profit}, digits) : "n/a");

      string panel = "";
      panel += "ASIA SWEEP | {panel_state}\\n";
      panel += StringFormat("Symbol: %s\\n", _Symbol);
      panel += "Session: {timestamp_session} ({session_tz})\\n";
      panel += "in_london={str(in_london).lower()} in_asia={str(in_asia).lower()}\\n";
      panel += StringFormat("Asia: L=%s H=%s | EQH={str(eqh_pool).lower()}({eqh_count}) EQL={str(eql_pool).lower()}({eql_count})\\n", DoubleToString({asia_low}, digits), DoubleToString({asia_high}, digits));
      panel += "Sweep: high={str(sweep_high).lower()} low={str(sweep_low).lower()}\\n";
      panel += StringFormat("MSS: bull={str(bull_mss).lower()} bear={str(bear_mss).lower()} | th(bull)=%s th(bear)=%s\\n", bullTh, bearTh);
      panel += StringFormat("Fib: r={fib_ratio} L=%s S=%s\\n", fibL, fibS);
      panel += StringFormat("M5: H=%s L=%s C=%s\\n", DoubleToString({m5_high}, digits), DoubleToString({m5_low}, digits), DoubleToString({m5_close}, digits));
      panel += "Trade: valid={str(trade_valid).lower()} type={_mql5_escape(trade_type)} method={_mql5_escape(trade_method)}\\n";
      panel += StringFormat("Levels: entry=%s sl=%s tp=%s\\n", entryTxt, slTxt, tpTxt);
      panel += "Reason: {_mql5_escape(trade_reason) if trade_reason else 'n/a'}\\n";
      panel += "Pretrade: passed={str(pretrade_passed).lower()} lots={_mql5_escape(lots_txt) if lots_txt else 'n/a'} rr={_mql5_escape(rr_txt) if rr_txt else 'n/a'}\\n";
      panel += "Pretrade reason: {_mql5_escape(pretrade_reason) if pretrade_reason else 'n/a'}";
      ObjectSetString(chartId, panelTx, OBJPROP_TEXT, panel);
   }}
""")

    draw.append(f"""
   // Asia range zone
   string asiaZone = prefix + "_asia_zone";
   if(ObjectCreate(chartId, asiaZone, OBJ_RECTANGLE, 0, TimeCurrent()-PeriodSeconds(PERIOD_CURRENT)*200, {asia_high}, TimeCurrent()+PeriodSeconds(PERIOD_CURRENT)*50, {asia_low}))
   {{
      ObjectSetInteger(chartId, asiaZone, OBJPROP_COLOR, ColorToARGB(clrLightGray, 20));
      ObjectSetInteger(chartId, asiaZone, OBJPROP_BACK, true);
      ObjectSetInteger(chartId, asiaZone, OBJPROP_FILL, true);
   }}
""")

    draw.append(f"""
   // Asia High/Low with liquidity pool styling
   string asiaHighName = prefix + "_asia_high";
   string asiaLowName  = prefix + "_asia_low";

   if({str(eqh_pool).lower()})
   {{
      string asiaHighBg = prefix + "_asia_high_bg";
      ObjectCreate(chartId, asiaHighBg, OBJ_HLINE, 0, 0, {asia_high} + (pt * 2));
      ObjectSetInteger(chartId, asiaHighBg, OBJPROP_COLOR, clrDarkOrange);
      ObjectSetInteger(chartId, asiaHighBg, OBJPROP_WIDTH, 5);
      ObjectSetInteger(chartId, asiaHighBg, OBJPROP_BACK, true);
   }}
   ObjectCreate(chartId, asiaHighName, OBJ_HLINE, 0, 0, {asia_high});
   ObjectSetInteger(chartId, asiaHighName, OBJPROP_COLOR, { "clrOrangeRed" if eqh_pool else "clrRed" });
   ObjectSetInteger(chartId, asiaHighName, OBJPROP_WIDTH, { 3 if eqh_pool else 2 });
   ObjectSetString(chartId, asiaHighName, OBJPROP_TOOLTIP, StringFormat("Asia High: %s", DoubleToString({asia_high}, digits)));

   if({str(eql_pool).lower()})
   {{
      string asiaLowBg = prefix + "_asia_low_bg";
      ObjectCreate(chartId, asiaLowBg, OBJ_HLINE, 0, 0, {asia_low} - (pt * 2));
      ObjectSetInteger(chartId, asiaLowBg, OBJPROP_COLOR, clrDarkBlue);
      ObjectSetInteger(chartId, asiaLowBg, OBJPROP_WIDTH, 5);
      ObjectSetInteger(chartId, asiaLowBg, OBJPROP_BACK, true);
   }}
   ObjectCreate(chartId, asiaLowName, OBJ_HLINE, 0, 0, {asia_low});
   ObjectSetInteger(chartId, asiaLowName, OBJPROP_COLOR, { "clrDeepSkyBlue" if eql_pool else "clrBlue" });
   ObjectSetInteger(chartId, asiaLowName, OBJPROP_WIDTH, { 3 if eql_pool else 2 });
   ObjectSetString(chartId, asiaLowName, OBJPROP_TOOLTIP, StringFormat("Asia Low: %s", DoubleToString({asia_low}, digits)));

   // Labels
   datetime t1 = TimeCurrent() + PeriodSeconds(PERIOD_CURRENT) * 5;
   string asiaHighLbl = prefix + "_asia_high_label";
   ObjectCreate(chartId, asiaHighLbl, OBJ_TEXT, 0, t1, {asia_high});
   ObjectSetString(chartId, asiaHighLbl, OBJPROP_FONT, "Arial Black");
   ObjectSetInteger(chartId, asiaHighLbl, OBJPROP_COLOR, { "clrOrangeRed" if eqh_pool else "clrRed" });
   ObjectSetInteger(chartId, asiaHighLbl, OBJPROP_FONTSIZE, 9);
   ObjectSetString(chartId, asiaHighLbl, OBJPROP_TEXT, StringFormat("Asia High: %s", DoubleToString({asia_high}, digits)));

   datetime t2 = TimeCurrent() + PeriodSeconds(PERIOD_CURRENT) * 10;
   string asiaLowLbl = prefix + "_asia_low_label";
   ObjectCreate(chartId, asiaLowLbl, OBJ_TEXT, 0, t2, {asia_low});
   ObjectSetString(chartId, asiaLowLbl, OBJPROP_FONT, "Arial Black");
   ObjectSetInteger(chartId, asiaLowLbl, OBJPROP_COLOR, { "clrDeepSkyBlue" if eql_pool else "clrBlue" });
   ObjectSetInteger(chartId, asiaLowLbl, OBJPROP_FONTSIZE, 9);
   ObjectSetString(chartId, asiaLowLbl, OBJPROP_TEXT, StringFormat("Asia Low: %s", DoubleToString({asia_low}, digits)));
""")

    if sweep_high:
        draw.append(f"""
   // Sweep high marker
   datetime tSW = TimeCurrent() + PeriodSeconds(PERIOD_CURRENT) * 15;
   string sweepH = prefix + "_sweep_high";
   ObjectCreate(chartId, sweepH, OBJ_TEXT, 0, tSW, {asia_high} + (pt * 6));
   ObjectSetInteger(chartId, sweepH, OBJPROP_COLOR, clrYellow);
   ObjectSetInteger(chartId, sweepH, OBJPROP_FONTSIZE, 10);
   ObjectSetString(chartId, sweepH, OBJPROP_TEXT, "SWEEP HIGH");
""")
    if sweep_low:
        draw.append(f"""
   // Sweep low marker
   datetime tSW = TimeCurrent() + PeriodSeconds(PERIOD_CURRENT) * 15;
   string sweepL = prefix + "_sweep_low";
   ObjectCreate(chartId, sweepL, OBJ_TEXT, 0, tSW, {asia_low} - (pt * 6));
   ObjectSetInteger(chartId, sweepL, OBJPROP_COLOR, clrYellow);
   ObjectSetInteger(chartId, sweepL, OBJPROP_FONTSIZE, 10);
   ObjectSetString(chartId, sweepL, OBJPROP_TEXT, "SWEEP LOW");
""")

    if prev3_high_max > 0:
        draw.append(f"""
   // Bull MSS threshold
   string bullTh = prefix + "_mss_bull_threshold";
   ObjectCreate(chartId, bullTh, OBJ_HLINE, 0, 0, {prev3_high_max});
   ObjectSetInteger(chartId, bullTh, OBJPROP_COLOR, clrGold);
   ObjectSetInteger(chartId, bullTh, OBJPROP_STYLE, STYLE_DASH);
   ObjectSetInteger(chartId, bullTh, OBJPROP_WIDTH, 1);

   // Label
   datetime tBull = TimeCurrent() + PeriodSeconds(PERIOD_CURRENT) * 7;
   string bullLbl = prefix + "_mss_bull_threshold_label";
   ObjectCreate(chartId, bullLbl, OBJ_TEXT, 0, tBull, {prev3_high_max});
   ObjectSetInteger(chartId, bullLbl, OBJPROP_COLOR, clrGold);
   ObjectSetInteger(chartId, bullLbl, OBJPROP_FONTSIZE, 8);
   ObjectSetString(chartId, bullLbl, OBJPROP_TEXT, StringFormat("BULL MSS TH: %s", DoubleToString({prev3_high_max}, digits)));
""")
    if prev3_low_min > 0:
        draw.append(f"""
   // Bear MSS threshold
   string bearTh = prefix + "_mss_bear_threshold";
   ObjectCreate(chartId, bearTh, OBJ_HLINE, 0, 0, {prev3_low_min});
   ObjectSetInteger(chartId, bearTh, OBJPROP_COLOR, clrDeepSkyBlue);
   ObjectSetInteger(chartId, bearTh, OBJPROP_STYLE, STYLE_DASH);
   ObjectSetInteger(chartId, bearTh, OBJPROP_WIDTH, 1);

   // Label
   datetime tBear = TimeCurrent() + PeriodSeconds(PERIOD_CURRENT) * 8;
   string bearLbl = prefix + "_mss_bear_threshold_label";
   ObjectCreate(chartId, bearLbl, OBJ_TEXT, 0, tBear, {prev3_low_min});
   ObjectSetInteger(chartId, bearLbl, OBJPROP_COLOR, clrDeepSkyBlue);
   ObjectSetInteger(chartId, bearLbl, OBJPROP_FONTSIZE, 8);
   ObjectSetString(chartId, bearLbl, OBJPROP_TEXT, StringFormat("BEAR MSS TH: %s", DoubleToString({prev3_low_min}, digits)));
""")

    if m5_high > 0 and m5_low > 0:
        draw.append(f"""
   // Current M5 H/L/C context
   string m5H = prefix + "_m5_high";
   string m5L = prefix + "_m5_low";
   string m5C = prefix + "_m5_close";
   ObjectCreate(chartId, m5H, OBJ_HLINE, 0, 0, {m5_high});
   ObjectSetInteger(chartId, m5H, OBJPROP_COLOR, clrSilver);
   ObjectSetInteger(chartId, m5H, OBJPROP_STYLE, STYLE_DOT);
   ObjectSetInteger(chartId, m5H, OBJPROP_WIDTH, 1);

   ObjectCreate(chartId, m5L, OBJ_HLINE, 0, 0, {m5_low});
   ObjectSetInteger(chartId, m5L, OBJPROP_COLOR, clrSilver);
   ObjectSetInteger(chartId, m5L, OBJPROP_STYLE, STYLE_DOT);
   ObjectSetInteger(chartId, m5L, OBJPROP_WIDTH, 1);

   if({m5_close} > 0.0)
   {{
      ObjectCreate(chartId, m5C, OBJ_HLINE, 0, 0, {m5_close});
      ObjectSetInteger(chartId, m5C, OBJPROP_COLOR, clrWhite);
      ObjectSetInteger(chartId, m5C, OBJPROP_STYLE, STYLE_DOT);
      ObjectSetInteger(chartId, m5C, OBJPROP_WIDTH, 1);
   }}
""")

    if fib_long > 0 and fib_short > 0:
        draw.append(f"""
   // Fib zones (0.71)
   string fibL = prefix + "_fib_long_zone";
   string fibS = prefix + "_fib_short_zone";
   ObjectCreate(chartId, fibL, OBJ_RECTANGLE, 0, TimeCurrent()-PeriodSeconds(PERIOD_CURRENT)*150, {fib_long}, TimeCurrent()+PeriodSeconds(PERIOD_CURRENT)*25, {asia_low});
   ObjectSetInteger(chartId, fibL, OBJPROP_COLOR, ColorToARGB(clrLimeGreen, 18));
   ObjectSetInteger(chartId, fibL, OBJPROP_BACK, true);
   ObjectSetInteger(chartId, fibL, OBJPROP_FILL, true);
   ObjectSetString(chartId, fibL, OBJPROP_TOOLTIP, StringFormat("Fib {fib_ratio} Long Zone: %s", DoubleToString({fib_long}, digits)));

   ObjectCreate(chartId, fibS, OBJ_RECTANGLE, 0, TimeCurrent()-PeriodSeconds(PERIOD_CURRENT)*150, {asia_high}, TimeCurrent()+PeriodSeconds(PERIOD_CURRENT)*25, {fib_short});
   ObjectSetInteger(chartId, fibS, OBJPROP_COLOR, ColorToARGB(clrHotPink, 18));
   ObjectSetInteger(chartId, fibS, OBJPROP_BACK, true);
   ObjectSetInteger(chartId, fibS, OBJPROP_FILL, true);
   ObjectSetString(chartId, fibS, OBJPROP_TOOLTIP, StringFormat("Fib {fib_ratio} Short Zone: %s", DoubleToString({fib_short}, digits)));
""")

    if trade_valid and entry_price > 0 and stop_loss > 0 and take_profit > 0:
        draw.append(f"""
   // Trade setup: Entry/SL/TP
   string entryLine = prefix + "_entry";
   string slLine    = prefix + "_sl";
   string tpLine    = prefix + "_tp";

   ObjectCreate(chartId, entryLine, OBJ_HLINE, 0, 0, {entry_price});
   ObjectSetInteger(chartId, entryLine, OBJPROP_COLOR, clrLimeGreen);
   ObjectSetInteger(chartId, entryLine, OBJPROP_WIDTH, 2);
   ObjectSetString(chartId, entryLine, OBJPROP_TOOLTIP, StringFormat("{_mql5_escape(trade_type)} Entry: %s", DoubleToString({entry_price}, digits)));

   ObjectCreate(chartId, slLine, OBJ_HLINE, 0, 0, {stop_loss});
   ObjectSetInteger(chartId, slLine, OBJPROP_COLOR, clrRed);
   ObjectSetInteger(chartId, slLine, OBJPROP_WIDTH, 2);
   ObjectSetInteger(chartId, slLine, OBJPROP_STYLE, STYLE_DASH);
   ObjectSetString(chartId, slLine, OBJPROP_TOOLTIP, StringFormat("SL: %s", DoubleToString({stop_loss}, digits)));

   ObjectCreate(chartId, tpLine, OBJ_HLINE, 0, 0, {take_profit});
   ObjectSetInteger(chartId, tpLine, OBJPROP_COLOR, clrDodgerBlue);
   ObjectSetInteger(chartId, tpLine, OBJPROP_WIDTH, 2);
   ObjectSetInteger(chartId, tpLine, OBJPROP_STYLE, STYLE_DASH);
   ObjectSetString(chartId, tpLine, OBJPROP_TOOLTIP, StringFormat("TP: %s", DoubleToString({take_profit}, digits)));

   // Entry alert zone: buffer = max(0.15*M5range, point*10)
   double buffer = MathMax({buffer_range_term}, pt * 10);
   string alertZone = prefix + "_entry_alert_zone";
   ObjectCreate(chartId, alertZone, OBJ_RECTANGLE, 0, TimeCurrent()-PeriodSeconds(PERIOD_CURRENT)*100, {entry_price} + buffer, TimeCurrent()+PeriodSeconds(PERIOD_CURRENT)*10, {entry_price} - buffer);
   ObjectSetInteger(chartId, alertZone, OBJPROP_COLOR, ColorToARGB(clrYellow, 25));
   ObjectSetInteger(chartId, alertZone, OBJPROP_BACK, true);
   ObjectSetInteger(chartId, alertZone, OBJPROP_FILL, true);
   ObjectSetInteger(chartId, alertZone, OBJPROP_STYLE, STYLE_DOT);
""")

    if current_price > 0:
        draw.append(f"""
   // Current price marker
   string curP = prefix + "_current_price";
   ObjectCreate(chartId, curP, OBJ_HLINE, 0, 0, {current_price});
   ObjectSetInteger(chartId, curP, OBJPROP_COLOR, clrWhite);
   ObjectSetInteger(chartId, curP, OBJPROP_WIDTH, 1);
   ObjectSetInteger(chartId, curP, OBJPROP_STYLE, STYLE_DOT);
""")

    script = f"""//+------------------------------------------------------------------+
//|                   FibtoolAsiaSweep_{symbol_u}.mq5                |
//|                  Asia Sweep MT5 Overlay (v3)                     |
//+------------------------------------------------------------------+
#property strict
#property version   "3.00"
#property description "Asia Sweep overlay with status panel, MSS thresholds, and trade levels"

void DeleteByPrefix(long chartId, string prefix)
{{
   int total = ObjectsTotal(chartId, 0, -1);
   for(int i = total - 1; i >= 0; i--)
   {{
      string name = ObjectName(chartId, i, 0, -1);
      if(StringFind(name, prefix) == 0)
         ObjectDelete(chartId, name);
   }}
}}

void OnStart()
{{
   long chartId = ChartID();
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   string prefix = "{prefix}";

   DeleteByPrefix(chartId, prefix);

{''.join(draw)}

   ChartRedraw(chartId);
}}
"""

    return script


def generate_mql5_script_clean(symbol: str, signal: dict) -> Optional[str]:
    """Generate the Asia Sweep MT5 overlay (clean).

    Clean overlay rules:
    - No rectangles (no session zone, no alert zone)
    - Always draw Asia high/low
    - Optional sweep text markers
    - Optional MSS thresholds (only when sweep or MSS)
    - Fib levels drawn only when relevant
    - Entry/SL/TP only when trade_setup.valid==true
    - One-line status label (top-left)
    """
    if not signal:
        return None

    symbol_u = str(symbol).upper()
    sym_slug = symbol_slug(symbol_u)
    prefix = f"{OBJECT_PREFIX}_{sym_slug}"

    current_price = _coerce_float(signal.get("current_price"), 0.0)
    asia_high = _coerce_float(signal.get("asia_high"), 0.0)
    asia_low = _coerce_float(signal.get("asia_low"), 0.0)
    if asia_high <= 0 or asia_low <= 0:
        return None

    eqh_pool = _coerce_bool(signal.get("eqh_liquidity_pool"))
    eql_pool = _coerce_bool(signal.get("eql_liquidity_pool"))
    try:
        eqh_count = int(float(signal.get("eqh_touch_count") or 0))
    except Exception:
        eqh_count = 0
    try:
        eql_count = int(float(signal.get("eql_touch_count") or 0))
    except Exception:
        eql_count = 0

    sweep_high = _coerce_bool(signal.get("sweep_high"))
    sweep_low = _coerce_bool(signal.get("sweep_low"))

    fib_long = _coerce_float(signal.get("fib_long"), 0.0)
    fib_short = _coerce_float(signal.get("fib_short"), 0.0)

    mss = _maybe_json(signal.get("mss"), {})
    if not isinstance(mss, dict):
        mss = {}
    bull_mss = _coerce_bool(mss.get("bullMSS"))
    bear_mss = _coerce_bool(mss.get("bearMSS"))

    prev3 = _maybe_json(mss.get("prev3"), {})
    if not isinstance(prev3, dict):
        prev3 = {}
    prev3_high_max = 0.0
    prev3_low_min = 0.0
    try:
        highs = prev3.get("high") or {}
        lows = prev3.get("low") or {}
        if isinstance(highs, dict) and highs:
            prev3_high_max = max(_coerce_float(v, 0.0) for v in highs.values())
        if isinstance(lows, dict) and lows:
            prev3_low_min = min(_coerce_float(v, 0.0) for v in lows.values())
    except Exception:
        prev3_high_max = 0.0
        prev3_low_min = 0.0

    trade_setup = _maybe_json(signal.get("trade_setup"), {"valid": False, "reason": "Not qualified"})
    pretrade = _maybe_json(signal.get("pretrade"), {"passed": False, "reason": ""})
    if not isinstance(trade_setup, dict):
        trade_setup = {"valid": False, "reason": "Not qualified"}
    if not isinstance(pretrade, dict):
        pretrade = {"passed": False, "reason": ""}

    trade_valid = _coerce_bool(trade_setup.get("valid"))
    trade_type = str(trade_setup.get("type") or "")

    pretrade_passed = _coerce_bool(pretrade.get("passed"))

    entry_price = _coerce_float(trade_setup.get("entry"), 0.0)
    stop_loss = _coerce_float(trade_setup.get("stop_loss"), 0.0)
    take_profit = _coerce_float(trade_setup.get("take_profit"), 0.0)

    # Status label coloring
    if trade_valid and pretrade_passed:
        status_color = "clrLimeGreen"
    elif trade_valid and not pretrade_passed:
        status_color = "clrOrange"
    else:
        status_color = "clrTomato"

    sh = 1 if sweep_high else 0
    sl = 1 if sweep_low else 0
    mb = 1 if bull_mss else 0
    ms = 1 if bear_mss else 0

    if trade_valid and entry_price > 0 and trade_type:
        status_text = f"TRADE {trade_type.upper()} @ {entry_price}"
    else:
        status_text = f"ASIA: SH={sh} SL={sl} | MSS B={mb} S={ms} | TRADE=NO"

    # Relevant fib rules
    want_fib_long = (sweep_low or bull_mss or (trade_valid and trade_type.lower() == "long"))
    want_fib_short = (sweep_high or bear_mss or (trade_valid and trade_type.lower() == "short"))

    # Draw thresholds only when sweep or MSS
    want_thresholds = sweep_high or sweep_low or bull_mss or bear_mss

    draw: list[str] = []

    # One-line status label (top-left)
    draw.append(f"""
   // Status label (one line)
   string statusName = prefix + "_status";
   if(ObjectCreate(chartId, statusName, OBJ_LABEL, 0, 0, 0))
   {{
      ObjectSetInteger(chartId, statusName, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(chartId, statusName, OBJPROP_XDISTANCE, 10);
      ObjectSetInteger(chartId, statusName, OBJPROP_YDISTANCE, 10);
      ObjectSetInteger(chartId, statusName, OBJPROP_COLOR, {status_color});
      ObjectSetInteger(chartId, statusName, OBJPROP_FONTSIZE, 9);
      ObjectSetString(chartId, statusName, OBJPROP_FONT, "Consolas");
      ObjectSetString(chartId, statusName, OBJPROP_TEXT, "{_mql5_escape(status_text)}");
   }}
""")

    # Asia high/low (always)
    high_width = 3 if eqh_pool else 2
    low_width = 3 if eql_pool else 2
    draw.append(f"""
   // Asia High/Low
   string asiaHigh = prefix + "_asia_high";
   string asiaLow  = prefix + "_asia_low";

   ObjectCreate(chartId, asiaHigh, OBJ_HLINE, 0, 0, {asia_high});
   ObjectSetInteger(chartId, asiaHigh, OBJPROP_COLOR, clrRed);
   ObjectSetInteger(chartId, asiaHigh, OBJPROP_WIDTH, {high_width});
   ObjectSetInteger(chartId, asiaHigh, OBJPROP_STYLE, STYLE_SOLID);
   ObjectSetString(chartId, asiaHigh, OBJPROP_TOOLTIP, StringFormat("Asia High: %s | EQH={str(eqh_pool).lower()}({eqh_count}) | sweep_high={str(sweep_high).lower()}", DoubleToString({asia_high}, digits)));

   ObjectCreate(chartId, asiaLow, OBJ_HLINE, 0, 0, {asia_low});
   ObjectSetInteger(chartId, asiaLow, OBJPROP_COLOR, clrBlue);
   ObjectSetInteger(chartId, asiaLow, OBJPROP_WIDTH, {low_width});
   ObjectSetInteger(chartId, asiaLow, OBJPROP_STYLE, STYLE_SOLID);
   ObjectSetString(chartId, asiaLow, OBJPROP_TOOLTIP, StringFormat("Asia Low: %s | EQL={str(eql_pool).lower()}({eql_count}) | sweep_low={str(sweep_low).lower()}", DoubleToString({asia_low}, digits)));
""")

    # Sweep markers
    if sweep_high:
        draw.append(f"""
   // Sweep high marker
   datetime tSH = TimeCurrent() + PeriodSeconds(PERIOD_CURRENT) * 5;
   string shName = prefix + "_sweep_h";
   ObjectCreate(chartId, shName, OBJ_TEXT, 0, tSH, {asia_high} + (pt * 3));
   ObjectSetInteger(chartId, shName, OBJPROP_COLOR, clrGold);
   ObjectSetInteger(chartId, shName, OBJPROP_FONTSIZE, 8);
   ObjectSetString(chartId, shName, OBJPROP_TEXT, "SWEEP H");
""")
    if sweep_low:
        draw.append(f"""
   // Sweep low marker
   datetime tSL = TimeCurrent() + PeriodSeconds(PERIOD_CURRENT) * 5;
   string slName = prefix + "_sweep_l";
   ObjectCreate(chartId, slName, OBJ_TEXT, 0, tSL, {asia_low} - (pt * 3));
   ObjectSetInteger(chartId, slName, OBJPROP_COLOR, clrGold);
   ObjectSetInteger(chartId, slName, OBJPROP_FONTSIZE, 8);
   ObjectSetString(chartId, slName, OBJPROP_TEXT, "SWEEP L");
""")

    # MSS thresholds (conditional)
    if want_thresholds and prev3_high_max > 0:
        draw.append(f"""
   // Bull MSS threshold
   string bullTh = prefix + "_mss_bull_threshold";
   ObjectCreate(chartId, bullTh, OBJ_HLINE, 0, 0, {prev3_high_max});
   ObjectSetInteger(chartId, bullTh, OBJPROP_COLOR, clrGold);
   ObjectSetInteger(chartId, bullTh, OBJPROP_WIDTH, 1);
   ObjectSetInteger(chartId, bullTh, OBJPROP_STYLE, STYLE_DASH);
   ObjectSetString(chartId, bullTh, OBJPROP_TOOLTIP, StringFormat("Bull MSS trigger: close > %s", DoubleToString({prev3_high_max}, digits)));
""")

    if want_thresholds and prev3_low_min > 0:
        draw.append(f"""
   // Bear MSS threshold
   string bearTh = prefix + "_mss_bear_threshold";
   ObjectCreate(chartId, bearTh, OBJ_HLINE, 0, 0, {prev3_low_min});
   ObjectSetInteger(chartId, bearTh, OBJPROP_COLOR, clrDeepSkyBlue);
   ObjectSetInteger(chartId, bearTh, OBJPROP_WIDTH, 1);
   ObjectSetInteger(chartId, bearTh, OBJPROP_STYLE, STYLE_DASH);
   ObjectSetString(chartId, bearTh, OBJPROP_TOOLTIP, StringFormat("Bear MSS trigger: close < %s", DoubleToString({prev3_low_min}, digits)));
""")

    # Fib (relevant only)
    if want_fib_long and fib_long > 0:
        draw.append(f"""
   // Fib long (relevant only)
   string fibL = prefix + "_fib_long";
   ObjectCreate(chartId, fibL, OBJ_HLINE, 0, 0, {fib_long});
   ObjectSetInteger(chartId, fibL, OBJPROP_COLOR, clrLimeGreen);
   ObjectSetInteger(chartId, fibL, OBJPROP_WIDTH, 1);
   ObjectSetInteger(chartId, fibL, OBJPROP_STYLE, STYLE_DASH);
   ObjectSetString(chartId, fibL, OBJPROP_TOOLTIP, StringFormat("Fib Long (0.71): %s", DoubleToString({fib_long}, digits)));
""")

    if want_fib_short and fib_short > 0:
        draw.append(f"""
   // Fib short (relevant only)
   string fibS = prefix + "_fib_short";
   ObjectCreate(chartId, fibS, OBJ_HLINE, 0, 0, {fib_short});
   ObjectSetInteger(chartId, fibS, OBJPROP_COLOR, clrHotPink);
   ObjectSetInteger(chartId, fibS, OBJPROP_WIDTH, 1);
   ObjectSetInteger(chartId, fibS, OBJPROP_STYLE, STYLE_DASH);
   ObjectSetString(chartId, fibS, OBJPROP_TOOLTIP, StringFormat("Fib Short (0.71): %s", DoubleToString({fib_short}, digits)));
""")

    # Trade levels (only when valid)
    if trade_valid and entry_price > 0 and stop_loss > 0 and take_profit > 0:
        draw.append(f"""
   // Trade levels
   string entryLine = prefix + "_entry";
   string slLine    = prefix + "_sl";
   string tpLine    = prefix + "_tp";

   ObjectCreate(chartId, entryLine, OBJ_HLINE, 0, 0, {entry_price});
   ObjectSetInteger(chartId, entryLine, OBJPROP_COLOR, clrLimeGreen);
   ObjectSetInteger(chartId, entryLine, OBJPROP_WIDTH, 2);
   ObjectSetInteger(chartId, entryLine, OBJPROP_STYLE, STYLE_SOLID);
   ObjectSetString(chartId, entryLine, OBJPROP_TOOLTIP, StringFormat("Entry: %s", DoubleToString({entry_price}, digits)));

   ObjectCreate(chartId, slLine, OBJ_HLINE, 0, 0, {stop_loss});
   ObjectSetInteger(chartId, slLine, OBJPROP_COLOR, clrRed);
   ObjectSetInteger(chartId, slLine, OBJPROP_WIDTH, 2);
   ObjectSetInteger(chartId, slLine, OBJPROP_STYLE, STYLE_DASH);
   ObjectSetString(chartId, slLine, OBJPROP_TOOLTIP, StringFormat("SL: %s", DoubleToString({stop_loss}, digits)));

   ObjectCreate(chartId, tpLine, OBJ_HLINE, 0, 0, {take_profit});
   ObjectSetInteger(chartId, tpLine, OBJPROP_COLOR, clrDodgerBlue);
   ObjectSetInteger(chartId, tpLine, OBJPROP_WIDTH, 2);
   ObjectSetInteger(chartId, tpLine, OBJPROP_STYLE, STYLE_DASH);
   ObjectSetString(chartId, tpLine, OBJPROP_TOOLTIP, StringFormat("TP: %s", DoubleToString({take_profit}, digits)));

   // Small labels near right side
   datetime tR = TimeCurrent() + PeriodSeconds(PERIOD_CURRENT) * 8;
   string entryLbl = prefix + "_entry_lbl";
   string slLbl = prefix + "_sl_lbl";
   string tpLbl = prefix + "_tp_lbl";

   ObjectCreate(chartId, entryLbl, OBJ_TEXT, 0, tR, {entry_price});
   ObjectSetInteger(chartId, entryLbl, OBJPROP_COLOR, clrLimeGreen);
   ObjectSetInteger(chartId, entryLbl, OBJPROP_FONTSIZE, 8);
   ObjectSetString(chartId, entryLbl, OBJPROP_TEXT, "ENTRY");

   ObjectCreate(chartId, slLbl, OBJ_TEXT, 0, tR, {stop_loss});
   ObjectSetInteger(chartId, slLbl, OBJPROP_COLOR, clrRed);
   ObjectSetInteger(chartId, slLbl, OBJPROP_FONTSIZE, 8);
   ObjectSetString(chartId, slLbl, OBJPROP_TEXT, "SL");

   ObjectCreate(chartId, tpLbl, OBJ_TEXT, 0, tR, {take_profit});
   ObjectSetInteger(chartId, tpLbl, OBJPROP_COLOR, clrDodgerBlue);
   ObjectSetInteger(chartId, tpLbl, OBJPROP_FONTSIZE, 8);
   ObjectSetString(chartId, tpLbl, OBJPROP_TEXT, "TP");
""")

    # Current price marker is intentionally omitted in clean mode.

    script = f"""//+------------------------------------------------------------------+
//|                   FibtoolAsiaSweep_{symbol_u}.mq5                |
//|                  Asia Sweep MT5 Overlay (clean)                  |
//+------------------------------------------------------------------+
#property strict
#property version   "3.10"
#property description "Asia Sweep clean overlay (minimal lines + tooltips)"

void DeleteByPrefix(long chartId, string prefix)
{{
   int total = ObjectsTotal(chartId, 0, -1);
   for(int i = total - 1; i >= 0; i--)
   {{
      string name = ObjectName(chartId, i, 0, -1);
      if(StringFind(name, prefix) == 0)
         ObjectDelete(chartId, name);
   }}
}}

void OnStart()
{{
   long chartId = ChartID();
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   string prefix = "{prefix}";

   DeleteByPrefix(chartId, prefix);

{''.join(draw)}

   ChartRedraw(chartId);
}}
"""

    return script


def generate_mql5_script(symbol: str, signal: dict, *, style: str = "clean") -> Optional[str]:
    """Public entrypoint that dispatches to the chosen style (default: clean)."""
    s = (style or "clean").strip().lower()
    if s == "rich":
        return generate_mql5_script_rich(symbol, signal)
    return generate_mql5_script_clean(symbol, signal)


def cleanup_mt5_objects(symbol: str):
    """Remove all Asia sweep objects for a symbol."""
    symbol_u = str(symbol).upper()
    sym_slug = symbol_slug(symbol_u)
    prefix = f"{OBJECT_PREFIX}_{sym_slug}"

    script = f"""//+------------------------------------------------------------------+
//|               FibtoolAsiaSweepCleanup_{symbol_u}.mq5             |
//|              Asia Sweep MT5 Overlay Cleanup (v3)                 |
//+------------------------------------------------------------------+
#property strict
#property version   "3.00"
#property description "Deletes Asia Sweep overlay objects by prefix"

void DeleteByPrefix(long chartId, string prefix)
{{
   int total = ObjectsTotal(chartId, 0, -1);
   for(int i = total - 1; i >= 0; i--)
   {{
      string name = ObjectName(chartId, i, 0, -1);
      if(StringFind(name, prefix) == 0)
         ObjectDelete(chartId, name);
   }}
}}

void OnStart()
{{
   long chartId = ChartID();
   string prefix = "{prefix}";
   DeleteByPrefix(chartId, prefix);
   ChartRedraw(chartId);
}}
"""

    script_path = MQL5_SCRIPTS_DIR / f"FibtoolAsiaSweepCleanup_{sym_slug}.mq5"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)

    print(f"[MQL5] Cleanup script saved: {script_path}")
    print(f"[{symbol_u}] Run in MT5: Navigator -> Scripts -> FibtoolAsiaSweepCleanup_{sym_slug}")


def plot_symbol(symbol: str, *, style: str = "clean"):
    """Plot Asia sweep elements for a symbol."""
    symbol_u = str(symbol).upper()
    sym_slug = symbol_slug(symbol_u)

    signal = load_asia_signals(symbol_u)
    if not signal:
        print(f"[SKIP] No signals for {symbol_u}")
        return

    script = generate_mql5_script(symbol_u, signal, style=style)
    if not script:
        print(f"[SKIP] No drawable elements for {symbol_u}")
        return

    # Save script to MQL5 Scripts directory
    script_path = MQL5_SCRIPTS_DIR / f"FibtoolAsiaSweep_{sym_slug}.mq5"
    script_path.parent.mkdir(parents=True, exist_ok=True)

    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script)

    print(f"[MQL5] Script saved: {script_path}")

    print(f"\n[{symbol_u}] Ready to execute")
    print(f"[{symbol_u}] To run:")
    print(f"  1. Open MT5")
    print(f"  2. Open {symbol_u} chart (M5 timeframe)")
    print(f"  3. Navigator -> Scripts -> FibtoolAsiaSweep_{sym_slug}")
    print(f"  4. Drag to chart or double-click")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Plot Asia Sweep elements on MT5 charts")
    parser.add_argument('--symbols', required=True, help='Comma-separated list of symbols')
    parser.add_argument('--cleanup', action='store_true', help='Remove existing plots instead of drawing new ones')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--style', default='clean', choices=['clean', 'rich'], help='Overlay style (clean/rich)')

    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(',')]

    if args.cleanup:
        print("Cleaning up existing plots...")
        for symbol in symbols:
            cleanup_mt5_objects(symbol)
        return

    print(f"Plotting Asia Sweep for symbols: {symbols}")
    for symbol in symbols:
        plot_symbol(symbol, style=args.style)

    if args.once:
        print("Completed one-time plot")
    else:
        print("Plot completed - scripts saved to MT5 Scripts folder")


if __name__ == "__main__":
    main()
