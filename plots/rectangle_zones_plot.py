"""
Production Tool 3: Rectangle Zones Plot
========================================

Draws filled rectangle zones around confluence levels on MT5 charts.

Features:
- Plots filled rectangles spanning time range around confluence prices
- Creates visual zones for support/resistance areas
- Color-coded by side (light red=resistance, light blue=support)
- Quality-based zone transparency
- Spans past and future bars for visibility
- Clean, minimal design for production use

Usage:
    python plots/rectangle_zones_plot.py --symbols XAUUSD --once
    python plots/rectangle_zones_plot.py --symbols XAUUSD,USDCAD --interval 60
    python plots/rectangle_zones_plot.py --symbols XAUUSD --cleanup
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
OBJECT_PREFIX = "fibtool_zone"
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


def get_zone_style(conf: dict) -> dict:
    """
    Get visual style for a confluence zone.
    
    Returns:
        dict with keys: color, transparency
    """
    strength_score = float(conf.get('strength_score', 0) or 0)
    severity = float(conf.get('severity', 0) or 0)
    side = conf.get('side', 'unknown').lower()
    
    # Quality score (0-3)
    quality = (strength_score + severity) / 2
    
    # Transparency based on quality (lower = more opaque)
    if quality >= 2.90:
        transparency = 50  # More opaque for stronger
    elif quality >= 2.75:
        transparency = 70
    else:
        transparency = 85  # More transparent for weaker
    
    # Color based on side
    if side == 'above':  # Resistance
        color = "clrLightCoral"
    elif side == 'below':  # Support
        color = "clrLightSkyBlue"
    else:
        color = "clrSilver"
    
    return {
        'color': color,
        'transparency': transparency
    }


def generate_mql5_script(symbol: str, confluences: list[dict]) -> str:
    """Generate MQL5 script for rectangle zones."""
    
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
            nearest_s9 = conf.get('nearest_s9', '?')
            side = conf.get('side', 'unknown').lower()
            
            # Object name
            zone_name = f"{OBJECT_PREFIX}_{symbol}_{conf_id}_{ts_str}"
            
            # Get styling
            style = get_zone_style(conf)
            color = style['color']
            transparency = style['transparency']
            
            # Quality score
            quality = (float(conf.get('strength_score', 0) or 0) + float(conf.get('severity', 0) or 0)) / 2
            
            # Zone size (default 0.1% of price)
            zone_size_pct = 0.1
            
            # Alert message mirrors the zone description
            alert_msg = f"{symbol} | {strength.upper()} zone {side.upper()} @ {price} | Fib {fib_pct}% | S9: {nearest_s9}"

            # MQL5 code for this zone
            draw_cmd = f"""
   // ═══════════════════════════════════════════════════════════════
   // Zone #{idx + 1}: {strength.upper()} @ {price}
   // Side: {side.upper()} | Quality: {quality:.2f}
   // ═══════════════════════════════════════════════════════════════
   
   // Calculate zone boundaries ({zone_size_pct}% of price)
   double zoneTop_{idx} = {price} * (1 + {zone_size_pct} / 100.0);
   double zoneBottom_{idx} = {price} * (1 - {zone_size_pct} / 100.0);
   
   // Calculate time range (100 bars back, 200 bars forward)
   datetime zoneTimeStart_{idx} = TimeCurrent() - PeriodSeconds(PERIOD_CURRENT) * 100;
   datetime zoneTimeEnd_{idx} = TimeCurrent() + PeriodSeconds(PERIOD_CURRENT) * 200;
   
   // Create rectangle zone
   if(!ObjectCreate(chartId, "{zone_name}", OBJ_RECTANGLE, 0, zoneTimeStart_{idx}, zoneTop_{idx}, zoneTimeEnd_{idx}, zoneBottom_{idx}))
   {{
      Print("✗ Error creating zone #{idx + 1}: ", GetLastError());
   }}
   else
   {{
      ObjectSetInteger(chartId, "{zone_name}", OBJPROP_COLOR, {color});
      ObjectSetInteger(chartId, "{zone_name}", OBJPROP_FILL, true);
      ObjectSetInteger(chartId, "{zone_name}", OBJPROP_BACK, true);
      ObjectSetInteger(chartId, "{zone_name}", OBJPROP_SELECTABLE, true);
      ObjectSetInteger(chartId, "{zone_name}", OBJPROP_SELECTED, false);
      ObjectSetInteger(chartId, "{zone_name}", OBJPROP_HIDDEN, false);
      ObjectSetInteger(chartId, "{zone_name}", OBJPROP_ZORDER, 0);
      ObjectSetInteger(chartId, "{zone_name}", OBJPROP_WIDTH, 0);  // No border
      ObjectSetInteger(chartId, "{zone_name}", OBJPROP_STYLE, STYLE_SOLID);
      
      // Set transparency using built-in ColorToARGB
      // Alpha: 0=transparent, 255=opaque (so we use 255 - transparency%)
      uchar alpha_{idx} = (uchar)(255 - (255 * {transparency} / 100));
      uint zoneColor_{idx} = ColorToARGB({color}, alpha_{idx});
      ObjectSetInteger(chartId, "{zone_name}", OBJPROP_COLOR, zoneColor_{idx});
      
    ObjectSetString(chartId, "{zone_name}", OBJPROP_TOOLTIP, "{strength.upper()} zone @ {price}\\nFib {fib_pct}% | S9: {nearest_s9}\\nRange: " + DoubleToString(zoneBottom_{idx}, _Digits) + " - " + DoubleToString(zoneTop_{idx}, _Digits));
    Print("✓ Zone #{idx + 1}: ", zoneBottom_{idx}, " - ", zoneTop_{idx});
    // Alerts
    if(Enable_Alerts) Alert("{alert_msg}");
    if(Enable_Push)   SendNotification("{alert_msg}");
    if(Enable_Email)  SendMail(Email_Subject, "{alert_msg}");
   }}
"""
            draw_commands.append(draw_cmd)
            
        except Exception as e:
            print(f"[ERROR] Skipping confluence {idx}: {e}")
            continue
    
    # Complete script
    script = f"""//+------------------------------------------------------------------+
//|                           FibtoolRectangleZones_{symbol}.mq5 |
//|                        Production Tool 3: Rectangle Zones        |
//|                        Draws filled zones around confluences      |
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
   Print("  FIBTOOL - Rectangle Zones Plot");
   Print("═══════════════════════════════════════════════════");
   Print("Symbol: ", Symbol_Input);
   Print("Drawing {len(draw_commands)} rectangle zones...");
   Print("═══════════════════════════════════════════════════");
   Print("");
   
   long chartId = ChartID();
   
   // Verify symbol
   if(Symbol() != Symbol_Input)
   {{
      Print("⚠ WARNING: Running on ", Symbol(), " but targeting ", Symbol_Input);
   }}
   
   Print("Drawing zones on chart ", chartId, "...");
   Print("");
{''.join(draw_commands)}
   
   Print("");
   Print("═══════════════════════════════════════════════════");
   Print("✓ DRAWING COMPLETE!");
   Print("═══════════════════════════════════════════════════");
   Print("Zones drawn: {len(draw_commands)}");
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
    
    script_path = MQL5_SCRIPTS_DIR / f"FibtoolRectangleZones_{symbol}.mq5"
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    print(f"[MQL] ✓ Script saved: {script_path}")
    return script_path


def generate_cleanup_script(symbol: str) -> str:
    """Generate cleanup script for rectangle zones."""
    script = f"""//+------------------------------------------------------------------+
//|                     FibtoolRectangleZones_{symbol}_Cleanup.mq5 |
//|                        Cleanup rectangle zones objects            |
//+------------------------------------------------------------------+
#property copyright "Fibtool"
#property version   "1.00"

void OnStart()
{{
   Print("═══════════════════════════════════════════════════");
   Print("  Cleaning up rectangle zones for {symbol}");
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
    cleanup_path = MQL5_SCRIPTS_DIR / f"FibtoolRectangleZones_{symbol}_Cleanup.mq5"
    
    with open(cleanup_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    print(f"[MQL] ✓ Cleanup script saved: {cleanup_path}")


def plot_rectangle_zones(symbol: str):
    """Main function to plot rectangle zones for a symbol."""
    print(f"\n{'='*60}")
    print(f"[{symbol}] Generating rectangle zones plot...")
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
    print(f"  3. Navigator → Scripts → FibtoolRectangleZones_{symbol}")
    print(f"  4. Drag to chart or double-click")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Production Tool 3: Rectangle Zones Plot")
    parser.add_argument('--symbols', type=str, required=True, help='Comma-separated symbols (e.g., XAUUSD,USDCAD)')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--interval', type=int, default=60, help='Refresh interval in seconds (default: 60)')
    parser.add_argument('--cleanup', action='store_true', help='Generate cleanup scripts only')
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("PRODUCTION TOOL 3: Rectangle Zones Plot")
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
                plot_rectangle_zones(symbol)
            print("\n✓ All scripts generated")
        else:
            import time
            print(f"\n[LOOP] Starting continuous mode (every {args.interval}s)")
            print("[LOOP] Press Ctrl+C to stop\n")
            
            try:
                while True:
                    for symbol in symbols:
                        plot_rectangle_zones(symbol)
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
