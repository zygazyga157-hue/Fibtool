"""
Production Tool 2: Vertical Lines Plot
========================================

Draws vertical lines at confluence timestamps on MT5 charts.

Features:
- Plots vertical lines at exact confluence detection times
- Marks key time events where confluences formed
- Color-coded by side (red=resistance, blue=support)
- Quality-based line width (1-3px)
- Shows timestamp labels
- Clean, minimal design for production use

Usage:
    python plots/vertical_lines_plot.py --symbols XAUUSD --once
    python plots/vertical_lines_plot.py --symbols XAUUSD,USDCAD --interval 60
    python plots/vertical_lines_plot.py --symbols XAUUSD --cleanup
"""

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

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
OBJECT_PREFIX = "fibtool_vline"
MT5_DATA_FOLDER = Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "D0E8209F77C8CF37AD8BF550E51FF075"
MQL5_SCRIPTS_DIR = MT5_DATA_FOLDER / "MQL5" / "Scripts"


def symbol_slug(symbol: str) -> str:
    """Filesystem-safe slug for a symbol (lowercase, non-alnum -> _)."""
    try:
        return ''.join(ch if ch.isalnum() else '_' for ch in str(symbol)).lower().strip('_')
    except Exception:
        return str(symbol).replace('/', '_').replace(' ', '_').lower()


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


def load_confluences(symbol: str) -> list[dict]:
    """Load latest confluences from CSV."""
    csv_path = OUTPUT_DIR / f"{symbol_slug(symbol)}_confluences.csv"
    
    if not csv_path.exists():
        print(f"[CSV] No data found for {symbol}")
        return []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    
    if not rows:
        return []
    
    # Get latest batch
    latest_ts = max(r.get('timestamp', '') for r in rows)
    latest = [r for r in rows if r.get('timestamp') == latest_ts]
    
    print(f"[CSV] Loaded {len(latest)} confluences from {latest_ts}")
    return latest


def parse_timestamp(ts_str: str) -> str:
    """
    Parse ISO timestamp to MQL5 datetime format.
    
    Args:
        ts_str: ISO format timestamp (e.g., '2025-10-21T07:53:29.693153+00:00')
    
    Returns:
        MQL5 datetime string format (e.g., '2025.10.21 07:53')
    """
    try:
        dt = datetime.fromisoformat(ts_str)
        return dt.strftime("%Y.%m.%d %H:%M")
    except:
        return "2025.01.01 00:00"  # Fallback


def get_line_style(conf: dict) -> dict:
    """
    Get visual style for a confluence line.
    
    Returns:
        dict with keys: color, width, style
    """
    strength_score = float(conf.get('strength_score', 0) or 0)
    severity = float(conf.get('severity', 0) or 0)
    side = conf.get('side', 'unknown').lower()
    
    # Quality score (0-3)
    quality = (strength_score + severity) / 2
    
    # Line width based on quality
    if quality >= 2.90:
        width = 3
        style = "STYLE_SOLID"
    elif quality >= 2.75:
        width = 2
        style = "STYLE_SOLID"
    else:
        width = 1
        style = "STYLE_DOT"
    
    # Color based on side
    if side == 'above':  # Resistance
        if quality >= 2.90:
            color = "clrRed"
        elif quality >= 2.80:
            color = "clrOrangeRed"
        elif quality >= 2.70:
            color = "clrOrange"
        else:
            color = "clrGold"
    elif side == 'below':  # Support
        if quality >= 2.90:
            color = "clrBlue"
        elif quality >= 2.80:
            color = "clrDodgerBlue"
        elif quality >= 2.70:
            color = "clrDeepSkyBlue"
        else:
            color = "clrCornflowerBlue"
    else:
        color = "clrSilver"
    
    return {
        'color': color,
        'width': width,
        'style': style
    }


def generate_mql5_script(symbol: str, confluences: list[dict]) -> str:
    """Generate MQL5 script for vertical lines."""
    
    timestamp = datetime.now(timezone.utc)
    ts_str = timestamp.strftime("%Y%m%dT%H%M%SZ")
    
    # Build drawing commands
    draw_commands = []
    
    for idx, conf in enumerate(confluences):
        try:
            price = float(conf.get('fib_price', 0))
            if price == 0:
                continue
            
            conf_id = conf.get('conf_id', f'conf{idx}')
            strength = conf.get('strength', 'moderate')
            fib_pct = conf.get('fib_pct', '?')
            timestamp_str = conf.get('timestamp', '')
            side = conf.get('side', 'unknown').lower()
            
            # Parse timestamp for MQL5
            mql_time = parse_timestamp(timestamp_str)
            
            # Object names
            line_name = f"{OBJECT_PREFIX}_{symbol}_{conf_id}_{ts_str}"
            label_name = f"{line_name}_label"
            
            # Get styling
            style = get_line_style(conf)
            color = style['color']
            width = style['width']
            line_style = style['style']
            
            # Quality score for label sizing
            quality = (float(conf.get('strength_score', 0) or 0) + float(conf.get('severity', 0) or 0)) / 2
            
            font_size = 9 if quality >= 2.90 else 8 if quality >= 2.75 else 7
            
            # Label text
            strength_symbol = "★★" if quality >= 2.90 else "★" if quality >= 2.80 else "●" if quality >= 2.70 else "○"
            side_arrow = "▼" if side == 'above' else "▲" if side == 'below' else "◆"
            time_label = mql_time.split()[1]  # Just the time part (HH:MM)
            label_text = f"{side_arrow}{strength_symbol} {time_label}"
            
            # Alert message mirrors the description
            alert_msg = f"{symbol} | {strength.upper()} confluence {side.upper()} @ {mql_time} | Price: {price} (Fib {fib_pct}%)"
            
            # MQL5 code for this line
            draw_cmd = f"""
   // ═══════════════════════════════════════════════════════════════
   // VLine #{idx + 1}: {strength.upper()} @ {mql_time}
   // Side: {side.upper()} | Quality: {quality:.2f} | Price: {price}
   // ═══════════════════════════════════════════════════════════════
   
   // Vertical line at confluence detection time
   datetime vlineTime_{idx} = StringToTime("{mql_time}");
   
   if(!ObjectCreate(chartId, "{line_name}", OBJ_VLINE, 0, vlineTime_{idx}, 0))
   {{
      Print("✗ Error creating vline #{idx + 1}: ", GetLastError());
   }}
   else
   {{
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_COLOR, {color});
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_WIDTH, {width});
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_STYLE, {line_style});
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_BACK, true);
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_SELECTABLE, true);
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_SELECTED, false);
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_HIDDEN, false);
    ObjectSetString(chartId, "{line_name}", OBJPROP_TOOLTIP, "{strength.upper()} confluence detected\\nTime: {mql_time}\\nPrice: {price} (Fib {fib_pct}%)");
    Print("✓ VLine #{idx + 1} at ", TimeToString(vlineTime_{idx}));
    // Alerts
    if(Enable_Alerts) Alert("{alert_msg}");
    if(Enable_Push)   SendNotification("{alert_msg}");
    if(Enable_Email)  SendMail(Email_Subject, "{alert_msg}");
   }}
   
   // Text label at top of chart
   double labelPrice_{idx} = ChartGetDouble(chartId, CHART_PRICE_MAX, 0);
   if(!ObjectCreate(chartId, "{label_name}", OBJ_TEXT, 0, vlineTime_{idx}, labelPrice_{idx}))
   {{
      Print("✗ Error creating label #{idx + 1}: ", GetLastError());
   }}
   else
   {{
      ObjectSetString(chartId, "{label_name}", OBJPROP_TEXT, "{label_text}");
      ObjectSetString(chartId, "{label_name}", OBJPROP_FONT, "Arial");
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_COLOR, {color});
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_FONTSIZE, {font_size});
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_BACK, false);
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_SELECTABLE, true);
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_HIDDEN, false);
      Print("✓ Label #{idx + 1}: {label_text}");
   }}
"""
            draw_commands.append(draw_cmd)
            
        except Exception as e:
            print(f"[ERROR] Skipping confluence {idx}: {e}")
            continue
    
    # Complete script
    script = f"""//+------------------------------------------------------------------+
//|                           FibtoolVerticalLines_{symbol}.mq5 |
//|                        Production Tool 2: Vertical Lines         |
//|                        Draws vertical confluence time markers     |
//+------------------------------------------------------------------+
#property copyright "Fibtool"
#property version   "1.00"
#property script_show_inputs

input string Symbol_Input = "{symbol}";  // Symbol to draw on
input bool   Enable_Alerts   = true;      // Pop-up alerts
input bool   Enable_Push     = true;      // Push notifications (requires MetaQuotes ID)
input bool   Enable_Email    = false;     // Email alerts (requires email configured)
input string Email_Subject   = "Fibtool Alert";  // Email subject

//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
void OnStart()
{{
   Print("═══════════════════════════════════════════════════");
   Print("  FIBTOOL - Vertical Lines Plot");
   Print("═══════════════════════════════════════════════════");
   Print("Symbol: ", Symbol_Input);
   Print("Drawing {len(draw_commands)} vertical time markers...");
   Print("═══════════════════════════════════════════════════");
   Print("");
   
   long chartId = ChartID();
   
   // Verify symbol
   if(Symbol() != Symbol_Input)
   {{
      Print("⚠ WARNING: Running on ", Symbol(), " but targeting ", Symbol_Input);
   }}
   
   Print("Drawing vertical lines on chart ", chartId, "...");
   Print("");
{''.join(draw_commands)}
   
   Print("");
   Print("═══════════════════════════════════════════════════");
   Print("✓ DRAWING COMPLETE!");
   Print("═══════════════════════════════════════════════════");
   Print("Vertical lines drawn: {len(draw_commands)}");
   Print("Use Ctrl+B to view all objects");
   Print("═══════════════════════════════════════════════════");
   
   ChartRedraw(chartId);
}}
//+------------------------------------------------------------------+
"""
    
    return script


def save_script(symbol: str, script_content: str) -> Path:
    """Save MQL5 script to MT5 Scripts folder."""
    MQL5_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    
    script_path = MQL5_SCRIPTS_DIR / f"FibtoolVerticalLines_{symbol}.mq5"
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    print(f"[MQL] ✓ Script saved: {script_path}")
    return script_path


def generate_cleanup_script(symbol: str) -> str:
    """Generate cleanup script for vertical lines."""
    script = f"""//+------------------------------------------------------------------+
//|                     FibtoolVerticalLines_{symbol}_Cleanup.mq5 |
//|                        Cleanup vertical lines objects             |
//+------------------------------------------------------------------+
#property copyright "Fibtool"
#property version   "1.00"

void OnStart()
{{
   Print("═══════════════════════════════════════════════════");
   Print("  Cleaning up vertical lines for {symbol}");
   Print("═══════════════════════════════════════════════════");
   
   long chartId = ChartID();
   int totalObjects = ObjectsTotal(chartId, 0, OBJ_ALL_PERIODS);
   int cleaned = 0;
   
   for(int i = totalObjects - 1; i >= 0; i--)
   {{
      string name = ObjectName(chartId, i, 0, OBJ_ALL_PERIODS);
      if(StringFind(name, "{OBJECT_PREFIX}_{symbol}_") == 0)
      {{
         if(ObjectDelete(chartId, name))
            cleaned++;
      }}
   }}
   
   ChartRedraw(chartId);
   
   Print("✓ Cleanup complete!");
   Print("Objects removed: ", cleaned);
   Print("═══════════════════════════════════════════════════");
}}
//+------------------------------------------------------------------+
"""
    return script


def save_cleanup_script(symbol: str):
    """Save cleanup script."""
    script_content = generate_cleanup_script(symbol)
    cleanup_path = MQL5_SCRIPTS_DIR / f"FibtoolVerticalLines_{symbol}_Cleanup.mq5"
    
    with open(cleanup_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    print(f"[MQL] ✓ Cleanup script saved: {cleanup_path}")


def plot_vertical_lines(symbol: str):
    """Main function to plot vertical lines for a symbol."""
    print(f"\n{'='*60}")
    print(f"[{symbol}] Generating vertical lines plot...")
    print(f"{'='*60}")
    
    # Load confluences
    confluences = load_confluences(symbol)
    
    if not confluences:
        print(f"[{symbol}] No confluences to plot")
        return
    
    # Generate script
    script_content = generate_mql5_script(symbol, confluences)
    
    # Save script
    script_path = save_script(symbol, script_content)
    
    print(f"\n[{symbol}] ✓ Ready to execute")
    print(f"[{symbol}] To run:")
    print(f"  1. Open MT5")
    print(f"  2. Open {symbol} chart")
    print(f"  3. Navigator → Scripts → FibtoolVerticalLines_{symbol}")
    print(f"  4. Drag to chart or double-click")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Production Tool 2: Vertical Lines Plot")
    parser.add_argument('--symbols', type=str, required=True, help='Comma-separated symbols (e.g., XAUUSD,USDCAD)')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--interval', type=int, default=60, help='Refresh interval in seconds (default: 60)')
    parser.add_argument('--cleanup', action='store_true', help='Generate cleanup scripts only')
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("PRODUCTION TOOL 2: Vertical Lines Plot")
    print("="*60)
    print(f"Symbols: {args.symbols}")
    print(f"Mode: {'Cleanup' if args.cleanup else 'Once' if args.once else f'Loop ({args.interval}s)'}")
    print(f"Scripts folder: {MQL5_SCRIPTS_DIR}")
    print("="*60)
    
    if not MT5_AVAILABLE:
        print("\n❌ MetaTrader5 not installed!")
        print("Install: pip install MetaTrader5")
        return 1
    
    try:
        # Connect to MT5
        connect_mt5()
        
        # Parse symbols while preserving case and spaces; strip optional quotes
        parts = [s.strip() for s in args.symbols.split(',') if s.strip()]
        symbols = [p[1:-1] if (len(p) >= 2 and ((p.startswith('"') and p.endswith('"')) or (p.startswith("'") and p.endswith("'")))) else p for p in parts]
        
        # Cleanup mode
        if args.cleanup:
            for symbol in symbols:
                save_cleanup_script(symbol)
            print("\n✓ Cleanup scripts generated")
            return 0
        
        # Plot mode
        if args.once:
            for symbol in symbols:
                plot_vertical_lines(symbol)
            print("\n✓ All scripts generated")
        else:
            import time
            print(f"\n[LOOP] Starting continuous mode (every {args.interval}s)")
            print("[LOOP] Press Ctrl+C to stop\n")
            
            try:
                while True:
                    for symbol in symbols:
                        plot_vertical_lines(symbol)
                    print(f"[LOOP] Sleeping {args.interval}s...")
                    time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\n[LOOP] Stopped by user")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        if MT5_AVAILABLE:
            mt5.shutdown()
            print("\n[MT5] Disconnected")


if __name__ == "__main__":
    exit(main())
