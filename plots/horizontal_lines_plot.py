"""
Production Tool 1: Horizontal Lines Plot
=========================================

Draws horizontal lines with labels on MT5 charts from confluence data.

Features:
- Plots horizontal lines at exact confluence prices
- Adds text labels with confluence information
- Color-coded by side (red=resistance, blue=support)
- Quality-based line width (1-3px)
- Clean, minimal design for production use

Usage:
    =
    python plots/horizontal_lines_plot.py --symbols XAUUSD,USDCAD --interval 60
    python plots/horizontal_lines_plot.py --symbols XAUUSD --cleanup
"""

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

def symbol_slug(symbol: str) -> str:
    """Filesystem-safe slug for a symbol (lowercase, non-alnum -> _)."""
    try:
        return ''.join(ch if ch.isalnum() else '_' for ch in str(symbol)).lower().strip('_')
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
OBJECT_PREFIX = "fibtool_hline"
MT5_DATA_FOLDER = Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "D0E8209F77C8CF37AD8BF550E51FF075"
MQL5_SCRIPTS_DIR = MT5_DATA_FOLDER / "MQL5" / "Scripts"
MQL5_EXPERTS_DIR = MT5_DATA_FOLDER / "MQL5" / "Experts"


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
        style = "STYLE_SOLID"
    
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
    """Generate MQL5 script for horizontal lines."""
    
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
            distance = conf.get('distance', '?')
            side = conf.get('side', 'unknown').lower()
            
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
            
            font_size = 11 if quality >= 2.90 else 10 if quality >= 2.80 else 9 if quality >= 2.70 else 8
            
            # Label text
            strength_symbol = "★★" if quality >= 2.90 else "★" if quality >= 2.80 else "●" if quality >= 2.70 else "○"
            side_arrow = "▼" if side == 'above' else "▲" if side == 'below' else "◆"
            label_text = f"{side_arrow} {strength_symbol} {strength.upper()} | Fib{fib_pct}% | S9:{nearest_s9} | Δ{distance}"
            
            # MQL5 code for this line
            draw_cmd = f"""
   // ═══════════════════════════════════════════════════════════════
   // Line #{idx + 1}: {strength.upper()} @ {price}
   // Side: {side.upper()} | Quality: {quality:.2f}
   // ═══════════════════════════════════════════════════════════════
   
   // Horizontal line
   if(!ObjectCreate(chartId, "{line_name}", OBJ_HLINE, 0, 0, {price}))
   {{
      Print("✗ Error creating line #{idx + 1}: ", GetLastError());
   }}
   else
   {{
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_COLOR, {color});
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_WIDTH, {width});
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_STYLE, {line_style});
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_BACK, false);
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_SELECTABLE, true);
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_SELECTED, false);
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_HIDDEN, false);
      ObjectSetString(chartId, "{line_name}", OBJPROP_TOOLTIP, "{strength.upper()} confluence at {price}\\nFib {fib_pct}% | S9: {nearest_s9} | Distance: {distance}");
      Print("✓ Line #{idx + 1} at ", {price});
   }}
   
   // Text label
   datetime labelTime_{idx} = TimeCurrent() + PeriodSeconds(PERIOD_CURRENT) * 5;
   if(!ObjectCreate(chartId, "{label_name}", OBJ_TEXT, 0, labelTime_{idx}, {price}))
   {{
      Print("✗ Error creating label #{idx + 1}: ", GetLastError());
   }}
   else
   {{
      ObjectSetString(chartId, "{label_name}", OBJPROP_TEXT, "{label_text}");
      ObjectSetString(chartId, "{label_name}", OBJPROP_FONT, "Arial Bold");
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_COLOR, {color});
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_FONTSIZE, {font_size});
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_ANCHOR, ANCHOR_LEFT);
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
//|                           FibtoolHorizontalLines_{symbol}.mq5 |
//|                        Production Tool 1: Horizontal Lines       |
//|                        Draws horizontal confluence lines          |
//+------------------------------------------------------------------+
#property copyright "Fibtool"
#property version   "1.00"
#property script_show_inputs

input string Symbol_Input = "{symbol}";  // Symbol to draw on

//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
void OnStart()
{{
   Print("═══════════════════════════════════════════════════");
   Print("  FIBTOOL - Horizontal Lines Plot");
   Print("═══════════════════════════════════════════════════");
   Print("Symbol: ", Symbol_Input);
   Print("Drawing {len(draw_commands)} horizontal lines...");
   Print("═══════════════════════════════════════════════════");
   Print("");
   
   long chartId = ChartID();
   
   // Verify symbol
   if(Symbol() != Symbol_Input)
   {{
      Print("⚠ WARNING: Running on ", Symbol(), " but targeting ", Symbol_Input);
   }}
   
   Print("Drawing lines on chart ", chartId, "...");
   Print("");
{''.join(draw_commands)}
   
   Print("");
   Print("═══════════════════════════════════════════════════");
   Print("✓ DRAWING COMPLETE!");
   Print("═══════════════════════════════════════════════════");
   Print("Lines drawn: {len(draw_commands)}");
   Print("Use Ctrl+B to view all objects");
   Print("═══════════════════════════════════════════════════");
   
   ChartRedraw(chartId);
}}
//+------------------------------------------------------------------+
"""
    
    return script


def generate_mql5_alert_ea(symbol: str, confluences: list[dict]) -> str:
     """Generate an MQL5 Expert Advisor that monitors horizontal levels and emits
     approach and breakthrough alerts (popup, push, email).
     """
     # Build levels initialization
     level_inits = []
     for idx, conf in enumerate(confluences):
          try:
                price = float(conf.get('fib_price', 0) or 0)
                if price == 0:
                     continue
                conf_id = conf.get('conf_id', f'conf{idx}')
                fib_pct = str(conf.get('fib_pct', '?'))
                side = str(conf.get('side', 'unknown')).lower()
                strength_score = float(conf.get('strength_score', 0) or 0)
                severity = float(conf.get('severity', 0) or 0)
                quality = (strength_score + severity) / 2.0
                strength_symbol = "★★" if quality >= 2.90 else ("★" if quality >= 2.80 else ("●" if quality >= 2.70 else "○"))
                side_arrow = "▼" if side == 'above' else ("▲" if side == 'below' else "◆")
                label_text = f"{side_arrow} {strength_symbol} FIB {fib_pct}%"
                # Sanitize strings for MQL
                def mq(s: str) -> str:
                     return s.replace('"', '\"')
                level_inits.append(
                     f'   add_level({price}, "{mq(conf_id)}", "{mq(side)}", "{mq(fib_pct)}", "{mq(label_text)}");'
                )
          except Exception:
                continue
     levels_code = "\n".join(level_inits) if level_inits else ""

     ea = f"""//+------------------------------------------------------------------+
//|                       FibtoolHorizontalAlerts_{symbol}.mq5 |
//|                   Monitors confluence levels and alerts     |
//+------------------------------------------------------------------+
#property copyright "Fibtool"
#property version   "1.00"
#property strict

input string Symbol_Input = "{symbol}";     // Target symbol
input bool   Enable_Popup  = true;           // Pop-up Alert()
input bool   Enable_Push   = true;           // SendNotification()
input bool   Enable_Email  = false;          // SendMail()
input string Email_Subject = "Fibtool Alert";// Email subject

// Distance settings (in points)
input double ApproachPoints   = 150.0;       // Within this distance => approaching
input double PenetrationPoints= 30.0;        // Minimum penetration beyond level => breakthrough
input int    CooldownSeconds  = 600;         // Minimum seconds between alerts per level per state

struct Level {{
    double price;
    string id;
    string side;   // 'above' (resistance) or 'below' (support)
    string fibpct; // e.g., '50'
    string label;  // compact label glyphs
    bool   approached;
    bool   broken;
    datetime lastApproach;
    datetime lastBreak;
}};

Level levels[];

void add_level(double price, string id, string side, string fibpct, string label)
{{
    int n = ArraySize(levels);
    ArrayResize(levels, n+1);
    levels[n].price = price;
    levels[n].id = id;
    levels[n].side = side;
    levels[n].fibpct = fibpct;
    levels[n].label = label;
    levels[n].approached = false;
    levels[n].broken = false;
    levels[n].lastApproach = 0;
    levels[n].lastBreak = 0;
}}

bool send_alerts(string msg)
{{
    bool ok = false;
    if(Enable_Popup)  {{ Alert(msg); ok = true; }}
    if(Enable_Push)   {{ SendNotification(msg); ok = true; }}
    if(Enable_Email)  {{ SendMail(Email_Subject, msg); ok = true; }}
    return ok;
}}

int OnInit()
{{
    // Initialize levels
{levels_code}
    EventSetTimer(1); // check each second
    Print("[FibtoolAlerts] Initialized for ", Symbol_Input, ", levels=", ArraySize(levels));
    return(INIT_SUCCEEDED);
}}

void OnDeinit(const int reason)
{{
    EventKillTimer();
}}

void OnTimer()
{{
    string sym = Symbol_Input;
    double point = SymbolInfoDouble(sym, SYMBOL_POINT);
    if(point <= 0) point = _Point; // fallback
    double bid = SymbolInfoDouble(sym, SYMBOL_BID);
    double ask = SymbolInfoDouble(sym, SYMBOL_ASK);
    double price = (bid+ask)/2.0; // mid
    datetime now = TimeCurrent();
   
    for(int i=0;i<ArraySize(levels);i++)
    {{
        double L = levels[i].price;
        string side = StringToLower(levels[i].side);
        double dist_points = MathAbs(price - L) / point;
        // Determine directional distance
        double diff = price - L; // positive if price above level
        bool from_below = (diff < 0);
        bool from_above = (diff > 0);

        // Approach condition: within ApproachPoints on the correct side
        bool approach_ok = false;
        if(side == "above") // resistance above current price
            approach_ok = from_below && dist_points <= ApproachPoints;
        else if(side == "below") // support below current price
            approach_ok = from_above && dist_points <= ApproachPoints;
        else
            approach_ok = dist_points <= ApproachPoints;

        if(approach_ok && !levels[i].approached)
        {{
            // cooldown check
            if(levels[i].lastApproach==0 || (now - levels[i].lastApproach) >= CooldownSeconds)
            {{
                string msg = sym+" | Approaching Fib "+levels[i].fibpct+"% @ "+DoubleToString(L, (int)SymbolInfoInteger(sym, SYMBOL_DIGITS))+" | "+levels[i].label;
                send_alerts(msg);
                levels[i].approached = true;
                levels[i].lastApproach = now;
                Print("[FibtoolAlerts] ", msg);
            }}
        }}

        // Breakthrough condition: price penetrates beyond level by PenetrationPoints
        bool break_ok = false;
        if(side == "above")
            break_ok = (price >= L + PenetrationPoints*point);
        else if(side == "below")
            break_ok = (price <= L - PenetrationPoints*point);
        else
            break_ok = dist_points <= PenetrationPoints; // unknown side, treat as touch

        if(break_ok && !levels[i].broken)
        {{
            if(levels[i].lastBreak==0 || (now - levels[i].lastBreak) >= CooldownSeconds)
            {{
                string msg2 = sym+" | Breakthrough Fib "+levels[i].fibpct+"% @ "+DoubleToString(L, (int)SymbolInfoInteger(sym, SYMBOL_DIGITS))+" | "+levels[i].label;
                send_alerts(msg2);
                levels[i].broken = true;
                levels[i].lastBreak = now;
                Print("[FibtoolAlerts] ", msg2);
            }}
        }}

        // Reset logic with hysteresis: if price moves away beyond 2x approach distance, allow re-alerts
        if(dist_points > ApproachPoints*2)
        {{
            levels[i].approached = false;
            levels[i].broken = false;
        }}
    }}
}}
//+------------------------------------------------------------------+
"""
     return ea


def save_script(symbol: str, script_content: str) -> Path:
    """Save MQL5 script to MT5 Scripts folder."""
    MQL5_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    
    script_path = MQL5_SCRIPTS_DIR / f"FibtoolHorizontalLines_{symbol}.mq5"
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    print(f"[MQL] ✓ Script saved: {script_path}")
    return script_path


def save_alert_ea(symbol: str, ea_content: str) -> Path:
    """Save Expert Advisor to the MT5 Experts folder."""
    MQL5_EXPERTS_DIR.mkdir(parents=True, exist_ok=True)
    ea_path = MQL5_EXPERTS_DIR / f"FibtoolHorizontalAlerts_{symbol}.mq5"
    with open(ea_path, 'w', encoding='utf-8') as f:
        f.write(ea_content)
    print(f"[MQL] ✓ Alert EA saved: {ea_path}")
    return ea_path


def generate_cleanup_script(symbol: str) -> str:
    """Generate cleanup script for horizontal lines."""
    script = f"""//+------------------------------------------------------------------+
//|                     FibtoolHorizontalLines_{symbol}_Cleanup.mq5 |
//|                        Cleanup horizontal lines objects           |
//+------------------------------------------------------------------+
#property copyright "Fibtool"
#property version   "1.00"

void OnStart()
{{
   Print("═══════════════════════════════════════════════════");
   Print("  Cleaning up horizontal lines for {symbol}");
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
    cleanup_path = MQL5_SCRIPTS_DIR / f"FibtoolHorizontalLines_{symbol}_Cleanup.mq5"
    
    with open(cleanup_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    print(f"[MQL] ✓ Cleanup script saved: {cleanup_path}")


def plot_horizontal_lines(symbol: str):
    """Main function to plot horizontal lines for a symbol."""
    print(f"\n{'='*60}")
    print(f"[{symbol}] Generating horizontal lines plot...")
    print(f"{'='*60}")
    
    # Load confluences
    confluences = load_confluences(symbol)
    
    if not confluences:
        print(f"[{symbol}] No confluences to plot")
        return
    
    # Generate drawing script
    script_content = generate_mql5_script(symbol, confluences)
    
    # Save script
    script_path = save_script(symbol, script_content)
    
    # Generate and save alert EA
    ea_content = generate_mql5_alert_ea(symbol, confluences)
    ea_path = save_alert_ea(symbol, ea_content)
    
    print(f"\n[{symbol}] ✓ Ready to execute")
    print(f"[{symbol}] To run:")
    print(f"  1. Open MT5")
    print(f"  2. Open {symbol} chart")
    print(f"  3. Navigator → Scripts → FibtoolHorizontalLines_{symbol}")
    print(f"  4. Drag to chart or double-click")
    print(f"  5. Navigator → Experts → FibtoolHorizontalAlerts_{symbol}")
    print(f"  6. Attach the EA to the same {symbol} chart to receive approach/breakthrough alerts")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Production Tool 1: Horizontal Lines Plot")
    parser.add_argument('--symbols', type=str, required=True, help='Comma-separated symbols (e.g., XAUUSD,USDCAD)')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--interval', type=int, default=60, help='Refresh interval in seconds (default: 60)')
    parser.add_argument('--cleanup', action='store_true', help='Generate cleanup scripts only')
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("PRODUCTION TOOL 1: Horizontal Lines Plot")
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
        parts = [p.strip() for p in args.symbols.split(',') if p.strip()]
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
                plot_horizontal_lines(symbol)
            print("\n✓ All scripts generated")
        else:
            import time
            print(f"\n[LOOP] Starting continuous mode (every {args.interval}s)")
            print("[LOOP] Press Ctrl+C to stop\n")
            
            try:
                while True:
                    for symbol in symbols:
                        plot_horizontal_lines(symbol)
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
