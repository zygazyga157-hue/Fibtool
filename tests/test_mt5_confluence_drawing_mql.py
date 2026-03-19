"""
MT5 Confluence Drawing via MQL5 Script Generation

This approach generates an MQL5 script that MT5 compiles and executes to draw objects.
Works with any MT5 Python package version since it doesn't rely on object_* functions.

Architecture:
1. Python reads confluence data from CSV
2. Python generates an .mq5 script file with drawing commands
3. Python copies script to MT5's Scripts folder
4. Python triggers script compilation and execution via MT5 API
5. MQL5 script draws objects and exits
6. Python monitors for completion

Usage:
    python test_mt5_confluence_drawing_mql.py --once
    python test_mt5_confluence_drawing_mql.py --interval 60
    python test_mt5_confluence_drawing_mql.py --cleanup-all
"""

import argparse
import csv
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

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


# Constants
SYMBOL = "XAUUSD"
TIMEFRAME = "H1"
TIMEFRAME_ENUM = mt5.TIMEFRAME_H1 if MT5_AVAILABLE else None
OUTPUT_DIR = Path(__file__).parent / "outputs"
CONFLUENCES_CSV = OUTPUT_DIR / "xauusd_confluences.csv"
OBJECT_PREFIX = "fibtool"

# MQL5 script paths
# Use MT5's actual data folder in AppData (user has write access)
MT5_DATA_FOLDER = Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "D0E8209F77C8CF37AD8BF550E51FF075"
MQL5_SCRIPTS_DIR = MT5_DATA_FOLDER / "MQL5" / "Scripts"
SCRIPT_NAME = "FibtoolConfluenceDrawer"
SCRIPT_FILE = f"{SCRIPT_NAME}.mq5"


def ensure_mt5_connected():
    """Initialize and login to MT5 terminal."""
    if not MT5_AVAILABLE:
        raise RuntimeError("MetaTrader5 package not installed. Run: pip install MetaTrader5")
    
    if not mt5.initialize(MT5_PATH):
        err = mt5.last_error()
        raise RuntimeError(f"MT5 initialize failed: {err}")
    
    try:
        logged_in = mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
        if not logged_in:
            err = mt5.last_error()
            print(f"[WARNING] MT5 login failed: {err}. Continuing anyway...")
    except Exception as e:
        print(f"[WARNING] MT5 login exception: {e}. Continuing anyway...")
    
    print(f"[MT5] Connected to {MT5_SERVER}")
    account_info = mt5.account_info()
    if account_info:
        print(f"[MT5] Account: {account_info.login}")


def load_latest_confluences(symbol: str) -> list[dict]:
    """
    Load the most recent confluences from symbol-specific CSV.
    
    Args:
        symbol: Symbol name (e.g., 'XAUUSD', 'USDCAD')
    
    Returns:
        List of confluence dictionaries
    """
    # Build symbol-specific CSV path
    confluences_csv = Path(f"outputs/{symbol.lower()}_confluences.csv")
    
    if not confluences_csv.exists():
        print(f"[WARNING] Confluences CSV not found: {confluences_csv}")
        return []
    
    try:
        with open(confluences_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        if not rows:
            print(f"[WARNING] No confluences found in CSV for {symbol}")
            return []
        
        # Get the latest timestamp
        latest_ts = max(r.get('timestamp', '') for r in rows)
        
        # Filter to only latest batch
        latest_confs = [r for r in rows if r.get('timestamp') == latest_ts]
        
        print(f"[CSV] Loaded {len(latest_confs)} confluences from {latest_ts}")
        return latest_confs
        
    except Exception as e:
        print(f"[CSV] ✗ Failed to load confluences: {e}")
        return []


def get_confluence_visual_style(conf: dict) -> dict:
    """
    Return visual styling based on confluence quality metrics.
    
    Uses strength_score, severity, and side to determine:
    - Color (gradient from weak to perfect)
    - Line width (1-3 pixels)
    - Line style (solid, dash, dot)
    
    Returns dict with keys: color, width, style, style_constant
    """
    strength = conf.get('strength', 'moderate').lower()
    strength_score = float(conf.get('strength_score', 0) or 0)
    severity = float(conf.get('severity', 0) or 0)
    side = conf.get('side', 'unknown').lower()
    
    # Combined quality score
    quality = (strength_score + severity) / 2
    
    # Base styling on quality first
    if quality >= 2.95:  # Near perfect
        width = 3
        style_const = "STYLE_SOLID"
    elif quality >= 2.85:  # Very strong
        width = 3
        style_const = "STYLE_SOLID"
    elif quality >= 2.75:  # Strong
        width = 2
        style_const = "STYLE_SOLID"
    elif quality >= 2.60:  # Moderate-strong
        width = 2
        style_const = "STYLE_SOLID"
    else:  # Weaker
        width = 1
        style_const = "STYLE_DASH"
    
    # Color based on side and quality
    if side == 'above':  # Resistance - RED tones
        if quality >= 2.90:
            color = "clrRed"  # Bright red for strongest resistance
        elif quality >= 2.80:
            color = "clrOrangeRed"  # Orange-red for very strong
        elif quality >= 2.70:
            color = "clrOrange"  # Orange for strong
        else:
            color = "clrGold"  # Gold for moderate
    elif side == 'below':  # Support - BLUE tones
        if quality >= 2.90:
            color = "clrBlue"  # Bright blue for strongest support
        elif quality >= 2.80:
            color = "clrDodgerBlue"  # Dodger blue for very strong
        elif quality >= 2.70:
            color = "clrDeepSkyBlue"  # Sky blue for strong
        else:
            color = "clrCornflowerBlue"  # Cornflower for moderate
    else:
        # Fallback neutral color
        color = "clrSilver"
    
    return {
        'color': color,
        'width': width,
        'style': style_const
    }


def generate_mql5_script(confluences: list[dict], timestamp: datetime, cleanup_age_seconds: int) -> str:
    """
    Generate MQL5 script content that draws confluences and cleans up old objects.
    
    Returns:
        MQL5 script source code as string
    """
    ts_str = timestamp.strftime("%Y%m%dT%H%M%SZ")
    
    # Build drawing commands
    draw_commands = []
    
    # Pre-calculate alert variables once
    alert_setup = """
   // Get current price for alert checks
   double currentPrice = SymbolInfoDouble(Symbol_Input, SYMBOL_BID);
   Print("Current price: ", currentPrice);
"""
    
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
            line_name = f"{OBJECT_PREFIX}_{SYMBOL}_{conf_id}_{ts_str}"
            label_name = f"{line_name}_label"
            zone_name = f"{line_name}_zone"
            
            # Get visual styling based on confluence quality
            visual = get_confluence_visual_style(conf)
            color = visual['color']
            width = visual['width']
            style = visual['style']
            
            # Font size and styling based on strength and quality
            quality = (float(conf.get('strength_score', 0) or 0) + float(conf.get('severity', 0) or 0)) / 2
            
            if quality >= 2.90:
                font_size = "11"
                font_weight = "bold"
            elif quality >= 2.80:
                font_size = "10"
                font_weight = "bold"
            elif quality >= 2.70:
                font_size = "9"
                font_weight = "normal"
            else:
                font_size = "8"
                font_weight = "normal"
            
            # Label text with enhanced formatting
            strength_symbol = "★★" if quality >= 2.90 else "★" if quality >= 2.80 else "●" if quality >= 2.70 else "○"
            side_arrow = "▼" if side == 'above' else "▲" if side == 'below' else "◆"
            label_text = f"{side_arrow} {strength_symbol} {strength.upper()} | Fib{fib_pct}% | S9:{nearest_s9} | Δ{distance}"
            
            # Calculate zone boundaries using configurable zone size
            zone_range_pct = f"ZoneSizePercent / 100.0"
            zone_top = f"{price} * (1 + {zone_range_pct})"
            zone_bottom = f"{price} * (1 - {zone_range_pct})"
            
            # Zone color based on side
            if side == 'above':  # Resistance zones
                zone_color = "ResistanceZoneColor"
            else:  # Support zones
                zone_color = "SupportZoneColor"
            
            # Calculate alert threshold for this confluence
            alert_threshold = price * 0.002  # 0.2% threshold
            
            # Build label text based on user settings
            label_parts = []
            if f"ShowDirectionArrows":
                label_parts.append(f"{side_arrow}")
            if f"ShowStrengthSymbols":
                label_parts.append(f"{strength_symbol}")
            label_parts.append(f"{strength.upper()}")
            if f"ShowFibLevel":
                label_parts.append(f"Fib{fib_pct}%")
            if f"ShowS9Level":
                label_parts.append(f"S9:{nearest_s9}")
            if f"ShowDistance":
                label_parts.append(f"Δ{distance}")
            
            dynamic_label_text = " | ".join(label_parts)
            
            # Generate MQL5 code for this confluence
            draw_cmd = f"""
   // ═══════════════════════════════════════════════════════════════
   // Confluence #{idx + 1}: {strength.upper()} @ {price}
   // Side: {side.upper()} | Quality: {quality:.2f}
   // ═══════════════════════════════════════════════════════════════
   
   // Check if this confluence should be displayed
   if(!ShouldDisplay("{strength.upper()}", "{side.upper()}", {quality:.2f}))
   {{
      Print("⊗ Confluence #{idx + 1} filtered out by display settings");
   }}
   else
   {{
      // Calculate zone boundaries
      double zoneTopPrice_{idx} = {zone_top};
      double zoneBottomPrice_{idx} = {zone_bottom};
      
      // Zone rectangle (if enabled)
      if(ShowZones)
      {{
         string zoneRect_{idx} = "{zone_name}";
         
         // Calculate time range for rectangle (past to future)
         datetime zoneTimeStart_{idx} = TimeCurrent() - PeriodSeconds(PERIOD_CURRENT) * 100;
         datetime zoneTimeEnd_{idx} = TimeCurrent() + PeriodSeconds(PERIOD_CURRENT) * 200;
         
         if(!ObjectCreate(chartId, zoneRect_{idx}, OBJ_RECTANGLE, 0, zoneTimeStart_{idx}, zoneTopPrice_{idx}, zoneTimeEnd_{idx}, zoneBottomPrice_{idx}))
         {{
            Print("ERROR creating zone rectangle {idx + 1}: ", GetLastError());
         }}
         else
         {{
            ObjectSetInteger(chartId, zoneRect_{idx}, OBJPROP_COLOR, {zone_color});
            ObjectSetInteger(chartId, zoneRect_{idx}, OBJPROP_BACK, ZonesInBackground);
            ObjectSetInteger(chartId, zoneRect_{idx}, OBJPROP_FILL, true);
            ObjectSetInteger(chartId, zoneRect_{idx}, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(chartId, zoneRect_{idx}, OBJPROP_SELECTED, false);
            ObjectSetInteger(chartId, zoneRect_{idx}, OBJPROP_HIDDEN, false);
            ObjectSetInteger(chartId, zoneRect_{idx}, OBJPROP_ZORDER, 0);
            ObjectSetInteger(chartId, zoneRect_{idx}, OBJPROP_WIDTH, 0);  // No border
            ObjectSetInteger(chartId, zoneRect_{idx}, OBJPROP_STYLE, STYLE_SOLID);
            Print("✓ Zone rectangle {idx + 1} created: ", zoneBottomPrice_{idx}, " - ", zoneTopPrice_{idx});
         }}
      }}
      
      // Main horizontal line (if enabled)
      if(ShowMainLines)
      {{
         if(!ObjectCreate(chartId, "{line_name}", OBJ_HLINE, 0, 0, {price}))
         {{
            Print("ERROR creating main line {idx + 1}: ", GetLastError());
         }}
         else
         {{
            color finalColor_{idx} = GetLineColor({color}, "{side.upper()}");
            int finalWidth_{idx} = GetLineWidth({width});
            ENUM_LINE_STYLE finalStyle_{idx} = (ManualLineColor != clrNONE) ? ManualLineStyle : {style};
            
            ObjectSetInteger(chartId, "{line_name}", OBJPROP_COLOR, finalColor_{idx});
            ObjectSetInteger(chartId, "{line_name}", OBJPROP_WIDTH, finalWidth_{idx});
            ObjectSetInteger(chartId, "{line_name}", OBJPROP_STYLE, finalStyle_{idx});
            ObjectSetInteger(chartId, "{line_name}", OBJPROP_BACK, false);
            ObjectSetInteger(chartId, "{line_name}", OBJPROP_SELECTABLE, true);
            ObjectSetInteger(chartId, "{line_name}", OBJPROP_SELECTED, false);
            ObjectSetInteger(chartId, "{line_name}", OBJPROP_HIDDEN, false);
            ObjectSetInteger(chartId, "{line_name}", OBJPROP_ZORDER, 1);
            ObjectSetString(chartId, "{line_name}", OBJPROP_TOOLTIP, "{strength.upper()} confluence at {price}\\nFib {fib_pct}% | S9: {nearest_s9} | Distance: {distance}");
            Print("✓ Line #{idx + 1} at ", {price});
         }}
      }}
      
      // Label (if enabled)
      if(ShowLabels)
      {{
         datetime labelTime_{idx} = TimeCurrent() + PeriodSeconds(PERIOD_CURRENT) * 5;
         if(!ObjectCreate(chartId, "{label_name}", OBJ_TEXT, 0, labelTime_{idx}, {price}))
         {{
            Print("ERROR creating label {idx + 1}: ", GetLastError());
         }}
         else
         {{
            string labelText_{idx} = "{dynamic_label_text}";
            color labelColor_{idx} = GetLineColor({color}, "{side.upper()}");
            int fontSize_{idx} = LabelFontSize + ({font_size} - 9);  // Adjust based on quality
            
            ObjectSetString(chartId, "{label_name}", OBJPROP_TEXT, labelText_{idx});
            ObjectSetString(chartId, "{label_name}", OBJPROP_FONT, LabelFontName);
            ObjectSetInteger(chartId, "{label_name}", OBJPROP_COLOR, labelColor_{idx});
            ObjectSetInteger(chartId, "{label_name}", OBJPROP_FONTSIZE, fontSize_{idx});
            ObjectSetInteger(chartId, "{label_name}", OBJPROP_ANCHOR, ANCHOR_LEFT);
            ObjectSetInteger(chartId, "{label_name}", OBJPROP_BACK, false);
            ObjectSetInteger(chartId, "{label_name}", OBJPROP_SELECTABLE, true);
            ObjectSetInteger(chartId, "{label_name}", OBJPROP_HIDDEN, false);
            ObjectSetInteger(chartId, "{label_name}", OBJPROP_ZORDER, 2);
            Print("✓ Label #{idx + 1}: ", labelText_{idx});
         }}
      }}
   }}
   
   // Price alert check
   double distancePercent_{idx} = (MathAbs(currentPrice - {price}) / {price}) * 100.0;
   
   if(ShouldAlert("{conf_id}", "{strength.upper()}", distancePercent_{idx}))
   {{
      string alertType_{idx} = (currentPrice > {price}) ? "ABOVE" : "BELOW";
      string alertMsg_{idx} = StringFormat(
         "🔔 %s CONFLUENCE ALERT 🔔\\n" +
         "Symbol: %s\\n" +
         "Price: %.2f is %.2f%% %s confluence @ %.2f\\n" +
         "Strength: %s | Fib: %s%% | S9: %s\\n" +
         "Distance: %s points | Side: {side.upper()}\\n" +
         "Action: Watch for reaction at this level!",
         "{strength.upper()}",
         Symbol_Input,
         currentPrice, distancePercent_{idx}, alertType_{idx}, {price},
         "{strength.upper()}", "{fib_pct}", "{nearest_s9}",
         "{distance}"
      );
      
      TriggerAlert("{conf_id}", alertMsg_{idx});
   }}
"""
            draw_commands.append(draw_cmd)
            
        except Exception as e:
            print(f"[MQL] Skipping confluence {idx}: {e}")
            continue
    
    # Remove automatic cleanup: user requested no chart cleanup
    cleanup_code = ""  # intentionally empty: do not delete any objects on chart
    
    # Complete script template
    script = f"""//+------------------------------------------------------------------+
//|                                      {SCRIPT_NAME}.mq5 |
//|                        Auto-generated by Fibtool                 |
//|                        Draws confluence zones on chart            |
//+------------------------------------------------------------------+
#property copyright "Fibtool"
#property version   "2.00"
#property script_show_inputs

//--- Input parameters
input string Symbol_Input = "{SYMBOL}";  // Symbol to draw on
input int MaxAgeSeconds = {cleanup_age_seconds};  // Max age before cleanup

//--- Alert settings
input group "═══════ Alert Settings ═══════"
input bool EnableAlerts = true;  // Enable price alerts
input bool EnableSound = true;  // Play sound on alert
input bool EnablePopup = true;  // Show popup notification
input bool EnablePush = false;  // Send push notification to mobile
input double AlertThresholdPercent = 0.2;  // Alert threshold (% of price)
input bool AlertOnlyOnce = true;  // Alert only once per confluence
input bool AlertOnStrongerOnly = true;  // Alert only for Strong/Perfect confluences

//--- Visual settings
input group "═══════ Visual Settings ═══════"
input bool ShowMainLines = true;  // Show main horizontal lines
input bool ShowZones = true;  // Show zone boundaries (dotted lines)
input bool ShowLabels = true;  // Show text labels
input double ZoneSizePercent = 0.1;  // Zone size (% of price)

//--- Line styling
input group "═══════ Line Style ═══════"
input int LineWidthMultiplier = 1;  // Line width multiplier (1-3)
input bool UseColorCoding = true;  // Use color coding (Red=Resistance, Blue=Support)
input color ManualLineColor = clrNONE;  // Manual line color (overrides coding)
input ENUM_LINE_STYLE ManualLineStyle = STYLE_SOLID;  // Manual line style

//--- Label styling
input group "═══════ Label Style ═══════"
input int LabelFontSize = 9;  // Base label font size (6-14)
input string LabelFontName = "Arial Bold";  // Label font name
input bool ShowStrengthSymbols = true;  // Show strength symbols (★ ● ○)
input bool ShowDirectionArrows = true;  // Show direction arrows (▲ ▼)
input bool ShowFibLevel = true;  // Show Fib percentage
input bool ShowS9Level = true;  // Show S9 degree
input bool ShowDistance = true;  // Show distance to S9

//--- Zone styling
input group "═══════ Zone Style ═══════"
input color SupportZoneColor = clrLightSkyBlue;  // Support zone color
input color ResistanceZoneColor = clrLightCoral;  // Resistance zone color
input ENUM_LINE_STYLE ZoneLineStyle = STYLE_DOT;  // Zone boundary line style
input bool ZonesInBackground = true;  // Draw zones in background

//--- Filter settings
input group "═══════ Filter Settings ═══════"
input bool ShowOnlyStrong = false;  // Show only Strong/Perfect confluences
input bool ShowSupportOnly = false;  // Show only Support levels
input bool ShowResistanceOnly = false;  // Show only Resistance levels
input double MinQualityScore = 0.0;  // Minimum quality score (0-3)

//--- Global variables for alert tracking
string g_AlertedLevels[];  // Track which levels already alerted
int g_AlertCount = 0;

//+------------------------------------------------------------------+
//| Check if confluence should be displayed based on filters          |
//+------------------------------------------------------------------+
bool ShouldDisplay(string strength, string side, double quality)
{{
   // Check quality filter
   if(quality < MinQualityScore)
      return false;
   
   // Check strength filter
   if(ShowOnlyStrong)
   {{
      if(strength != "STRONG" && strength != "PERFECT")
         return false;
   }}
   
   // Check side filters
   if(ShowSupportOnly && side != "BELOW")
      return false;
   
   if(ShowResistanceOnly && side != "ABOVE")
      return false;
   
   return true;
}}

//+------------------------------------------------------------------+
//| Get final line color based on settings                            |
//+------------------------------------------------------------------+
color GetLineColor(color autoColor, string side)
{{
   // If manual color is set, use it
   if(ManualLineColor != clrNONE)
      return ManualLineColor;
   
   // If color coding disabled, use default
   if(!UseColorCoding)
      return clrGold;
   
   // Otherwise use auto color
   return autoColor;
}}

//+------------------------------------------------------------------+
//| Get final line width based on settings                            |
//+------------------------------------------------------------------+
int GetLineWidth(int autoWidth)
{{
   int width = autoWidth * LineWidthMultiplier;
   if(width < 1) width = 1;
   if(width > 5) width = 5;
   return width;
}}

//+------------------------------------------------------------------+
//| Check if we should alert for this confluence                      |
//+------------------------------------------------------------------+
bool ShouldAlert(string confId, string strength, double distance)
{{
   // Check if alerts are enabled
   if(!EnableAlerts)
      return false;
   
   // Check if we only alert on stronger confluences
   if(AlertOnStrongerOnly)
   {{
      if(strength != "STRONG" && strength != "PERFECT")
         return false;
   }}
   
   // Check if we already alerted for this level
   if(AlertOnlyOnce)
   {{
      for(int i = 0; i < g_AlertCount; i++)
      {{
         if(g_AlertedLevels[i] == confId)
            return false;  // Already alerted
      }}
   }}
   
   // Check distance threshold
   if(distance > AlertThresholdPercent)
      return false;
   
   return true;
}}

//+------------------------------------------------------------------+
//| Trigger alert with configured options                             |
//+------------------------------------------------------------------+
void TriggerAlert(string confId, string message)
{{
   // Log to terminal
   Print("🔔 ", message);
   
   // Show popup
   if(EnablePopup)
      Alert(message);
   
   // Play sound
   if(EnableSound)
      PlaySound("alert.wav");
   
   // Send push notification to mobile
   if(EnablePush)
      SendNotification(message);
   
   // Track that we alerted
   if(AlertOnlyOnce)
   {{
      ArrayResize(g_AlertedLevels, g_AlertCount + 1);
      g_AlertedLevels[g_AlertCount] = confId;
      g_AlertCount++;
   }}
}}

//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
void OnStart()
{{
   Print("═══════════════════════════════════════════════════");
   Print("    FIBTOOL CONFLUENCE DRAWER v2.0");
   Print("═══════════════════════════════════════════════════");
   Print("Symbol: ", Symbol_Input);
   Print("Drawing {len(draw_commands)} confluences...");
   Print("");
   Print("📊 VISUAL SETTINGS:");
   Print("  ✓ Lines: ", ShowMainLines ? "ON" : "OFF", " <<< MUST BE ON TO SEE LINES!");
   Print("  ✓ Zones: ", ShowZones ? "ON" : "OFF", " (", ZoneSizePercent, "%)");
   Print("  ✓ Labels: ", ShowLabels ? "ON" : "OFF", " (", LabelFontSize, "pt)", " <<< MUST BE ON TO SEE LABELS!");
   Print("  Color Coding: ", UseColorCoding ? "ON" : "OFF");
   Print("  Line Width: x", LineWidthMultiplier);
   if(!ShowMainLines)
      Print("  ⚠️ WARNING: Main lines are OFF - only zones will be visible!");
   if(!ShowLabels)
      Print("  ⚠️ WARNING: Labels are OFF - no text will be visible!");
   Print("");
   Print("🔔 ALERT SETTINGS:");
   Print("  Enabled: ", EnableAlerts ? "YES" : "NO");
   Print("  Sound: ", EnableSound ? "YES" : "NO");
   Print("  Popup: ", EnablePopup ? "YES" : "NO");
   Print("  Push: ", EnablePush ? "YES" : "NO");
   Print("  Threshold: ", AlertThresholdPercent, "%");
   Print("  Only Once: ", AlertOnlyOnce ? "YES" : "NO");
   Print("  Stronger Only: ", AlertOnStrongerOnly ? "YES" : "NO");
   Print("");
   Print("🔍 FILTER SETTINGS:");
   Print("  Strong Only: ", ShowOnlyStrong ? "YES" : "NO");
   Print("  Support Only: ", ShowSupportOnly ? "YES" : "NO");
   Print("  Resistance Only: ", ShowResistanceOnly ? "YES" : "NO");
   Print("  Min Quality: ", MinQualityScore);
   Print("═══════════════════════════════════════════════════");
   Print("");
   
   // Get the current chart ID (the chart this script is running on)
   long chartId = ChartID();
   Print("Chart ID: ", chartId);
   Print("Current Symbol: ", Symbol());
   Print("Current Period: ", Period());
   Print("");
   
   // Verify we're on the right chart
   if(Symbol() != Symbol_Input)
   {{
      Print("WARNING: Script running on ", Symbol(), " but should be on ", Symbol_Input);
      Print("Objects will be drawn on current chart anyway...");
   }}
   
    // (Cleanup disabled) Previous versions removed old objects; cleanup is intentionally disabled now.
    // {cleanup_code} is empty by design when cleanup is disabled.
   
   Print("Drawing new confluences on chart ", chartId, "...");
{alert_setup}
{''.join(draw_commands)}
   
   // ═══════════════════════════════════════════════════════════════
   // FORCE CHART TO SHOW ALL OBJECTS
   // ═══════════════════════════════════════════════════════════════
   Print("Auto-scaling chart to show all confluence levels...");
   
   // Find min and max prices from all confluences
   double minPrice = 999999.0;
   double maxPrice = 0.0;
   
   for(int i = 0; i < ObjectsTotal(chartId, 0, OBJ_HLINE); i++)
   {{
      string name = ObjectName(chartId, i, 0, OBJ_HLINE);
      if(StringFind(name, "{OBJECT_PREFIX}_{SYMBOL}_") == 0)
      {{
         double price = ObjectGetDouble(chartId, name, OBJPROP_PRICE);
         if(price > 0)
         {{
            if(price < minPrice) minPrice = price;
            if(price > maxPrice) maxPrice = price;
         }}
      }}
   }}
   
   Print("Price range: ", minPrice, " - ", maxPrice);
   
   // Disable auto-scroll and shift
   ChartSetInteger(chartId, CHART_AUTOSCROLL, false);
   ChartSetInteger(chartId, CHART_SHIFT, false);
   ChartSetInteger(chartId, CHART_SCALEFIX, false);
   ChartSetInteger(chartId, CHART_SCALE_PT_PER_BAR, false);
   
   // Set price range with 5% padding
   double priceRange = maxPrice - minPrice;
   double padding = priceRange * 0.05;
   double chartMin = minPrice - padding;
   double chartMax = maxPrice + padding;
   
   Print("Setting chart range: ", chartMin, " - ", chartMax);
   
   // Force set the price scale
   ChartSetDouble(chartId, CHART_PRICE_MIN, chartMin);
   ChartSetDouble(chartId, CHART_PRICE_MAX, chartMax);
   ChartSetInteger(chartId, CHART_SCALEFIX, true);
   ChartSetDouble(chartId, CHART_FIXED_MIN, chartMin);
   ChartSetDouble(chartId, CHART_FIXED_MAX, chartMax);
   
   // Navigate to latest bar
   ChartNavigate(chartId, CHART_END, 0);
   Sleep(200);
   
   // Force multiple redraws
   ChartRedraw(chartId);
   Sleep(100);
   ChartRedraw(chartId);
   Sleep(100);
   ChartRedraw(chartId);
   
   Print("✓ Chart scale enforced to show price range ", chartMin, " - ", chartMax);
   
   Print("");
   Print("═══════════════════════════════════════════════════");
   Print("    DRAWING COMPLETE!");
   Print("═══════════════════════════════════════════════════");
   Print("Total objects drawn: {len(draw_commands)}");
   Print("Total alerts triggered: ", g_AlertCount);
   Print("Chart scaled and centered");
   Print("");
   
   if(g_AlertCount > 0)
   {{
      Print("⚠️ ACTIVE ALERTS: Price is near ", g_AlertCount, " confluence(s)!");
      Print("Check your notifications and watch for price reaction.");
   }}
   else
   {{
      Print("✓ No immediate alerts. Price is clear of all confluences.");
   }}
   
   Print("");
   Print("💡 Troubleshooting:");
   Print("  1. Right-click chart -> Objects -> Objects List (Ctrl+B)");
   Print("  2. Look for 'fibtool_{SYMBOL}_...' entries");
   Print("  3. Double-click an object to jump to it");
   Print("  4. Try pressing 'Home' key to zoom to fit all data");
   Print("");
   Print("💡 Alert Settings: Drag script again to modify alert options");
   Print("═══════════════════════════════════════════════════");
}}

//+------------------------------------------------------------------+
//| Parse timestamp string to datetime                                |
//+------------------------------------------------------------------+
bool ParseTimestamp(string tsStr, datetime &result)
{{
   // Format: 20251020T103000Z
   if(StringLen(tsStr) != 16)
      return false;
   
   string year = StringSubstr(tsStr, 0, 4);
   string month = StringSubstr(tsStr, 4, 2);
   string day = StringSubstr(tsStr, 6, 2);
   string hour = StringSubstr(tsStr, 9, 2);
   string minute = StringSubstr(tsStr, 11, 2);
   string second = StringSubstr(tsStr, 13, 2);
   
   MqlDateTime dt;
   dt.year = (int)StringToInteger(year);
   dt.mon = (int)StringToInteger(month);
   dt.day = (int)StringToInteger(day);
   dt.hour = (int)StringToInteger(hour);
   dt.min = (int)StringToInteger(minute);
   dt.sec = (int)StringToInteger(second);
   dt.day_of_week = 0;
   dt.day_of_year = 0;
   
   result = StructToTime(dt);
   return true;
}}
//+------------------------------------------------------------------+
"""
    
    return script


def save_mql5_script(script_content: str, symbol: str = None) -> Path:
    """
    Save MQL5 script to MT5 scripts folder.
    
    Args:
        script_content: The MQL5 script source code
        symbol: Symbol name to include in filename (if None, uses global SYMBOL)
    
    Returns:
        Path to the saved script file
    """
    if not MQL5_SCRIPTS_DIR:
        raise RuntimeError("Scripts directory not configured")
    
    # Create our local scripts folder
    MQL5_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Include symbol in filename for multi-symbol support
    symbol_name = symbol or SYMBOL
    script_filename = f"FibtoolConfluenceDrawer_{symbol_name}.mq5"
    script_path = MQL5_SCRIPTS_DIR / script_filename
    
    try:
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        print(f"[MQL] ✓ Script saved: {script_path}")
        
        return script_path
        
    except Exception as e:
        raise RuntimeError(f"Failed to save MQL5 script: {e}")


def compile_and_run_script() -> bool:
    """
    Trigger MT5 to compile and run the script.
    
    Note: Direct compilation via Python API is limited. We rely on MT5's
    auto-compilation when the script is first accessed.
    """
    try:
        # Switch to the symbol to ensure chart is active
        result = mt5.symbol_select(SYMBOL, True)
        if not result:
            print(f"[WARNING] Could not select symbol {SYMBOL}")
        
        print(f"[MT5] Script ready for manual execution or auto-compile")
        print(f"[MT5] To run manually: Open MT5 -> Navigator -> Scripts -> {SCRIPT_NAME}")
        
        # Alternative: We can try to trigger via terminal command if available
        # For now, we'll document that the script is ready
        
        return True
        
    except Exception as e:
        print(f"[MT5] ✗ Error preparing script: {e}")
        return False


def generate_cleanup_script() -> str:
    """Generate an MQL5 script that only cleans up old objects."""
    script = f"""//+------------------------------------------------------------------+
//|                                {SCRIPT_NAME}_Cleanup.mq5 |
//|                        Auto-generated by Fibtool                 |
//|                        Cleans up old confluence objects           |
//+------------------------------------------------------------------+
#property copyright "Fibtool"
#property version   "1.00"
#property script_show_inputs

input string Symbol_Input = "{SYMBOL}";  // Symbol to clean

void OnStart()
{{
   Print("=== Fibtool Object Cleanup ===");
   
   int totalObjects = ObjectsTotal(0, 0, -1);
   int cleaned = 0;
   
   for(int i = totalObjects - 1; i >= 0; i--)
   {{
      string name = ObjectName(0, i, 0, -1);
      
      if(StringFind(name, "{OBJECT_PREFIX}_{SYMBOL}_") == 0)
      {{
         ObjectDelete(0, name);
         ObjectDelete(0, name + "_label");
         cleaned++;
      }}
   }}
   
   ChartRedraw(0);
   
   Print("=== Cleanup complete! ===");
   Print("Objects removed: ", cleaned);
}}
"""
    return script


def test_drawing_cycle(symbol: str, interval_seconds: int):
    """
    Run one complete cycle:
    1. Load latest confluences for the symbol
    2. Generate MQL5 script
    3. Save to MT5 Scripts folder with symbol-specific filename
    4. Instructions for execution
    """
    print("\n" + "="*60)
    print(f"[CYCLE] Starting drawing cycle at {datetime.now(timezone.utc).isoformat()}")
    print("="*60)
    
    # Step 1: Load confluences for this symbol
    confluences = load_latest_confluences(symbol)
    
    if not confluences:
        print(f"[CYCLE] ⚠ No confluences to draw for {symbol}")
        return
    
    # Step 2: Generate script
    timestamp = datetime.now(timezone.utc)
    max_age = interval_seconds * 2
    script_content = generate_mql5_script(confluences, timestamp, max_age)
    
    print(f"[MQL] Generated script with {len(confluences)} confluences")
    
    # Step 3: Save script with symbol-specific filename
    script_path = save_mql5_script(script_content, symbol)
    
    # Step 4: Prepare for execution
    compile_and_run_script()
    
    script_name = f"FibtoolConfluenceDrawer_{symbol}"
    print(f"\n[CYCLE] ✓ Script ready at: {script_path}")
    print(f"[CYCLE] To draw on MT5 chart:")
    print(f"  1. Open MT5 terminal")
    print(f"  2. Open {symbol} H1 chart")
    print(f"  3. Navigator -> Scripts -> {script_name}")
    print(f"  4. Drag script onto chart or double-click")
    print("="*60 + "\n")


def save_cleanup_script():
    """Save a cleanup-only script to MT5 Scripts folder."""
    script_content = generate_cleanup_script()
    cleanup_path = MQL5_SCRIPTS_DIR / f"{SCRIPT_NAME}_Cleanup.mq5"
    
    try:
        with open(cleanup_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        print(f"[MQL] ✓ Cleanup script saved: {cleanup_path}")
        print(f"[MQL] Run this script to remove ALL {OBJECT_PREFIX} objects from {SYMBOL}")
        
    except Exception as e:
        print(f"[MQL] ✗ Failed to save cleanup script: {e}")


def main():
    parser = argparse.ArgumentParser(description="Test MT5 confluence drawing via MQL5 script generation")
    parser.add_argument('--interval', type=int, default=300, help='Refresh interval in seconds (default: 300)')
    parser.add_argument('--cleanup-all', action='store_true', help='Generate cleanup script only')
    parser.add_argument('--once', action='store_true', help='Run once and exit (no loop)')
    parser.add_argument('--symbols', type=str, default=None, help='Comma-separated symbols to process (e.g., XAUUSD,USDCAD). If not provided, uses config SYMBOL.')
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("MT5 CONFLUENCE DRAWING TEST (MQL5 Script Method)")
    print("="*60)
    print(f"Symbol: {SYMBOL}")
    print(f"Timeframe: {TIMEFRAME}")
    print(f"Interval: {args.interval}s")
    print(f"Max age before cleanup: {args.interval * 2}s")
    print(f"Scripts folder: {MQL5_SCRIPTS_DIR}")
    print("="*60 + "\n")
    
    if not MT5_AVAILABLE:
        print("❌ MetaTrader5 package not installed!")
        print("Install with: pip install MetaTrader5")
        return 1
    
    if not MQL5_SCRIPTS_DIR or not Path(MT5_PATH).exists():
        print("❌ MT5_PATH not configured or invalid!")
        print(f"Current MT5_PATH: {MT5_PATH}")
        return 1
    
    try:
        # Connect to MT5
        ensure_mt5_connected()
        
        # Determine which symbols to process
        if args.symbols:
            symbols_to_process = [s.strip().upper() for s in args.symbols.split(',')]
        else:
            symbols_to_process = [SYMBOL]
        
        print(f"[SYMBOLS] Processing: {', '.join(symbols_to_process)}")
        
        # Cleanup script generation mode
        if args.cleanup_all:
            save_cleanup_script()
            print("\n✓ Cleanup script generated. Run it from MT5 Navigator.")
            return 0
        
        # Main drawing cycle
        if args.once:
            for symbol in symbols_to_process:
                print(f"\n[{symbol}] Generating script...")
                test_drawing_cycle(symbol, args.interval)
            print("\n✓ All scripts generated. Execute from MT5 to see results.")
        else:
            print(f"[LOOP] Starting continuous loop (every {args.interval}s)")
            print("[LOOP] Each cycle generates a new script for each symbol")
            print("[LOOP] Press Ctrl+C to stop\n")
            
            try:
                while True:
                    for symbol in symbols_to_process:
                        print(f"\n[{symbol}] Generating script...")
                        test_drawing_cycle(symbol, args.interval)
                    print(f"\n[LOOP] Sleeping for {args.interval}s...")
                    time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\n\n[LOOP] Interrupted by user")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        if MT5_AVAILABLE:
            mt5.shutdown()
            print("\n[MT5] Disconnected")


if __name__ == "__main__":
    exit(main())
