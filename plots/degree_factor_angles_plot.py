"""
Production Tool 5: Degree Factor Gann Angles Plot
=================================================

Draws right-extended trend lines (rays) from recent pivots using DegreeFactor levels
and Gann angle ratios. For lows, projects bullish angles (1x1,2x1,3x1,4x1,8x1); for highs,
projects bearish angles (1x1,1x2,1x4,1x8). Levels are based on DegreeFactor multipliers
applied to the pivot price.

Usage:
    python plots/degree_factor_angles_plot.py --symbols XAUUSD --once \
      --timeframes H1,H4,D1 \
      --df-lows "0.175,0.35,0.525,0.7,0.875" --df-highs "0.175,0.35,0.525" \
      --gann-unit-mode atr --gann-atr-period 14 --gann-atr-ratio 0.25 \
      --bars-cap 240
"""

import argparse
import csv
import sys
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd

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

from degreefactor import DegreeFactor

# Configuration
OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
OBJECT_PREFIX = "fibtool_df_gann"
MT5_DATA_FOLDER = Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "D0E8209F77C8CF37AD8BF550E51FF075"
MQL5_SCRIPTS_DIR = MT5_DATA_FOLDER / "MQL5" / "Scripts"

# MT5 timeframe mapping
MT5_TIMEFRAMES = {
    'M1': 1, 'M5': 5, 'M15': 15, 'M30': 30,
    'H1': 16385, 'H4': 16388, 'D1': 16408, 'W1': 32769, 'MN1': 49153
}

# Gann reference
GANN_DEGREES = {
    "1x8": 7.5, "1x4": 15.0, "1x2": 26.25, "1x1": 45.0,
    "2x1": 63.75, "3x1": 71.25, "4x1": 75.0, "8x1": 82.5
}


def symbol_slug(symbol: str, timeframe: str | None = None) -> str:
    try:
        base = ''.join(ch if ch.isalnum() else '_' for ch in str(symbol)).lower().strip('_')
        if timeframe:
            return f"{base}_{timeframe.lower()}"
        return base
    except Exception:
        base = str(symbol).replace('/', '_').replace(' ', '_').lower()
        if timeframe:
            return f"{base}_{timeframe.lower()}"
        return base


def connect_mt5():
    if not MT5_AVAILABLE:
        raise RuntimeError("MetaTrader5 not installed. Run: pip install MetaTrader5")
    if not mt5.initialize(MT5_PATH):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
    except:
        pass
    print(f"[MT5] Connected to {MT5_SERVER}")


def load_bars(symbol: str, timeframe: str | None = None) -> pd.DataFrame:
    slug = symbol_slug(symbol, timeframe)
    p = OUTPUT_DIR / f"{slug}_bars.csv"
    if not p.exists():
        # Try without timeframe if specific file not found
        if timeframe:
            p_alt = OUTPUT_DIR / f"{symbol_slug(symbol)}_bars.csv"
            if p_alt.exists():
                print(f"[BARS] Using {p_alt.name} for {symbol} {timeframe}")
                p = p_alt
            else:
                print(f"[BARS] No bars for {symbol} {timeframe}")
                return pd.DataFrame()
        else:
            print(f"[BARS] No bars for {symbol}")
            return pd.DataFrame()
    try:
        df = pd.read_csv(p)
        # normalize time
        if 'time' not in df.columns and 'timestamp' in df.columns:
            df = df.rename(columns={'timestamp':'time'})
        df['time'] = pd.to_datetime(df['time'], utc=True, errors='coerce')
        for c in ['open','high','low','close','volume']:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
        df = df.dropna(subset=['time']).sort_values('time').reset_index(drop=True)
        tf_label = f" {timeframe}" if timeframe else ""
        print(f"[BARS] Loaded {len(df)} bars for {symbol}{tf_label}")
        return df
    except Exception as e:
        print(f"[BARS] Error reading {p}: {e}")
        return pd.DataFrame()


def detect_pivots(df: pd.DataFrame, left: int = 5, right: int = 5) -> pd.DataFrame:
    if df.empty or len(df) < left + right + 1:
        return df
    df = df.copy()
    df['pivot_low'] = 0.0
    df['pivot_high'] = 0.0
    for i in range(left, len(df)-right):
        ch = float(df.loc[i,'high'])
        cl = float(df.loc[i,'low'])
        is_h = True
        is_l = True
        for j in range(i-left, i):
            if float(df.loc[j,'high']) > ch:
                is_h = False
            if float(df.loc[j,'low']) < cl:
                is_l = False
        if is_h:
            for j in range(i+1, i+right+1):
                if float(df.loc[j,'high']) > ch:
                    is_h = False
                    break
        if is_l:
            for j in range(i+1, i+right+1):
                if float(df.loc[j,'low']) < cl:
                    is_l = False
                    break
        if is_h:
            df.loc[i,'pivot_high'] = ch
        if is_l:
            df.loc[i,'pivot_low'] = cl
    return df


def _get_symbol_point(symbol: str, bars_df: pd.DataFrame) -> float:
    if MT5_AVAILABLE and mt5 is not None:
        try:
            info = mt5.symbol_info(symbol)
            if info and getattr(info,'point',None):
                return float(info.point)
        except Exception:
            pass
    try:
        if not bars_df.empty and 'close' in bars_df.columns:
            sample = float(bars_df['close'].iloc[-1])
            s = f"{sample:.10f}"
            if '.' in s:
                dec = len(s.rstrip('0').split('.')[-1])
                dec = min(max(dec,1),10)
                return 10**(-dec)
    except Exception:
        pass
    return 0.01


def _calc_atr(df: pd.DataFrame, period: int = 14) -> float | None:
    try:
        if df.empty or len(df) < period + 1:
            return None
        high = df['high'].astype(float)
        low = df['low'].astype(float)
        close = df['close'].astype(float)
        prev_close = close.shift(1)
        tr = pd.concat([(high-low), (high-prev_close).abs(), (low-prev_close).abs()], axis=1).max(axis=1)
        atr = tr.rolling(period).mean().iloc[-1]
        return float(atr) if pd.notna(atr) else None
    except Exception:
        return None


def parse_time_for_mql(ts: pd.Timestamp | datetime) -> str:
    if isinstance(ts, pd.Timestamp):
        if ts.tzinfo is None:
            ts = ts.tz_localize('UTC')
        dt = ts.to_pydatetime()
    elif isinstance(ts, datetime):
        dt = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    else:
        dt = datetime.fromisoformat(str(ts)).replace(tzinfo=timezone.utc)
    return dt.strftime("%Y.%m.%d %H:%M")


def generate_script(symbol: str, timeframe: str | None, df: pd.DataFrame, unit_mode: str, unit_points: int, atr_period: int,
                    atr_ratio: float, df_lows: list[float], df_highs: list[float], max_pivots: int,
                    bars_cap: int) -> str:
    ts_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tf_const = f"PERIOD_{timeframe}" if timeframe else "PERIOD_CURRENT"
    tf_label = f"_{timeframe}" if timeframe else ""

    def mql_escape(s: str) -> str:
        try:
            return str(s).replace('\\', r'\\').replace('"', r'\"').replace('\n', r'\n').replace('\r','')
        except Exception:
            return str(s)

    # Unit per bar
    unit_per_bar = None
    if unit_mode == 'point':
        point = _get_symbol_point(symbol, df)
        unit_per_bar = point * max(1, int(unit_points))
    else:
        atr = _calc_atr(df, period=int(atr_period))
        if atr is not None:
            unit_per_bar = float(atr) * float(atr_ratio)

    if not unit_per_bar or unit_per_bar <= 0:
        print(f"[GANN] Cannot determine unit_per_bar for {symbol}; no fan/angles will be drawn")

    # Select recent pivots
    dpf = detect_pivots(df)
    lows = dpf[dpf['pivot_low'] > 0][['time','pivot_low']].tail(max_pivots)
    highs = dpf[dpf['pivot_high'] > 0][['time','pivot_high']].tail(max_pivots)

    draw_cmds: list[str] = []
    chart_header = f"""
//+------------------------------------------------------------------+
//|                   FibtoolDegreeFactorGann_{symbol}{tf_label}.mq5          |
//+------------------------------------------------------------------+
#property version   "1.00"
#property script_show_inputs

input string Symbol_Input = "{symbol}";

void OnStart()
{{
   long chartId = ChartID();
   if(Symbol() != Symbol_Input)
   {{
      if(!ChartSetSymbolPeriod(chartId, Symbol_Input, {tf_const}))
         Print("⚠ Failed to switch chart: ", GetLastError());
   }}
    // Predeclare reusable variables to avoid redeclaration errors
    int seconds_per_bar = PeriodSeconds({tf_const});
    datetime end_time;
"""

    # Helper to add a line and label
    def add_line(name: str, start_time_mql: str, start_price: float, bars_needed: int, end_price: float,
                 color: str, text: str):
        draw_cmds.append(f"""
    end_time = StringToTime("{start_time_mql}") + seconds_per_bar * {max(1,int(bars_needed))};
   if(!ObjectCreate(chartId, "{name}", OBJ_TREND, 0, StringToTime("{start_time_mql}"), {start_price}, end_time, {end_price}))
   {{
      Print("✗ Error creating line {name}: ", GetLastError());
   }}
   else
   {{
      ObjectSetInteger(chartId, "{name}", OBJPROP_COLOR, {color});
      ObjectSetInteger(chartId, "{name}", OBJPROP_WIDTH, 1);
      ObjectSetInteger(chartId, "{name}", OBJPROP_STYLE, STYLE_DOT);
      ObjectSetInteger(chartId, "{name}", OBJPROP_RAY_RIGHT, true);
      ObjectSetInteger(chartId, "{name}", OBJPROP_BACK, false);
      ObjectSetString(chartId, "{name}", OBJPROP_TOOLTIP, "{mql_escape(text)}");
   }}
""")

    # Build from lows (bullish)
    for i, row in lows.iterrows():
        base_t = parse_time_for_mql(row['time'])
        base_p = float(row['pivot_low'])
        for factor in df_lows:
            level = base_p * (1.0 + float(factor))
            for rlabel, ratio in [("1x1",1.0),("2x1",2.0),("3x1",3.0),("4x1",4.0),("8x1",8.0)]:
                if unit_per_bar and unit_per_bar > 0:
                    bars_needed = (level - base_p) / (unit_per_bar * ratio)
                    if bars_needed <= 0:
                        continue
                    bars_needed = min(int(round(bars_needed)), int(bars_cap))
                    if bars_needed < 1:
                        continue
                    deg = GANN_DEGREES.get(rlabel, 0)
                    line_name = f"{OBJECT_PREFIX}_{symbol}_low_{ts_str}_{int(base_p)}_{int(float(factor)*10000)}_{rlabel}"
                    text = f"DF {float(factor)*100:.2f}% | {rlabel} ({deg:.2f}°)"
                    add_line(line_name, base_t, base_p, bars_needed, level, "clrDarkGreen", text)

    # Build from highs (bearish)
    for i, row in highs.iterrows():
        base_t = parse_time_for_mql(row['time'])
        base_p = float(row['pivot_high'])
        for factor in df_highs:
            level = base_p * (1.0 - float(factor))
            for rlabel, ratio in [("1x1",1.0),("1x2",0.5),("1x4",0.25),("1x8",0.125)]:
                if unit_per_bar and unit_per_bar > 0:
                    bars_needed = (base_p - level) / (unit_per_bar * ratio)
                    if bars_needed <= 0:
                        continue
                    bars_needed = min(int(round(bars_needed)), int(bars_cap))
                    if bars_needed < 1:
                        continue
                    deg = GANN_DEGREES.get(rlabel, 0)
                    line_name = f"{OBJECT_PREFIX}_{symbol}_high_{ts_str}_{int(base_p)}_{int(float(factor)*10000)}_{rlabel}"
                    text = f"DF {float(factor)*100:.2f}% | {rlabel} ({deg:.2f}°)"
                    add_line(line_name, base_t, base_p, bars_needed, level, "clrMaroon", text)

    footer = """
   ChartRedraw(chartId);
}
//+------------------------------------------------------------------+
"""
    return chart_header + "\n".join(draw_cmds) + footer


def save_script(symbol: str, timeframe: str | None, content: str) -> Path:
    MQL5_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    tf_label = f"_{timeframe}" if timeframe else ""
    p = MQL5_SCRIPTS_DIR / f"FibtoolDegreeFactorGann_{symbol}{tf_label}.mq5"
    with open(p, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"[MQL] ✓ Script saved: {p}")
    return p


def main():
    ap = argparse.ArgumentParser(description="Production Tool 5: Degree Factor Gann Angles Plot")
    ap.add_argument('--symbols', required=True, type=str, help='Comma-separated symbols (case sensitive allowed via quotes)')
    ap.add_argument('--timeframes', type=str, default='', help='Comma-separated MT5 timeframes (M1,M5,M15,M30,H1,H4,D1,W1,MN1). If empty, uses current/default.')
    ap.add_argument('--once', action='store_true', help='Run once and exit')
    ap.add_argument('--interval', type=int, default=90, help='Refresh seconds for loop mode')
    ap.add_argument('--df-lows', type=str, default="0.175,0.35,0.525,0.7,0.875", help='DegreeFactor percentages for lows')
    ap.add_argument('--df-highs', type=str, default="0.175,0.35,0.525,0.7", help='DegreeFactor percentages for highs')
    ap.add_argument('--max-pivots', type=int, default=1, help='Number of most recent lows/highs to project from')
    ap.add_argument('--bars-cap', type=int, default=240, help='Max bars to project forward')
    # Gann scaling
    ap.add_argument('--gann-unit-mode', type=str, choices=['point','atr'], default='atr')
    ap.add_argument('--gann-unit-points', type=int, default=100)
    ap.add_argument('--gann-atr-period', type=int, default=14)
    ap.add_argument('--gann-atr-ratio', type=float, default=0.25)

    args = ap.parse_args()

    print("\n"+"="*60)
    print("PRODUCTION TOOL 5: Degree Factor Gann Angles Plot")
    print("="*60)
    print(f"Symbols: {args.symbols}")
    print(f"Timeframes: {args.timeframes if args.timeframes else 'Default/Current'}")
    print(f"Mode: {'Once' if args.once else f'Loop ({args.interval}s)'}")
    print(f"Scripts folder: {MQL5_SCRIPTS_DIR}")
    print("="*60)

    if not MT5_AVAILABLE:
        print("\n❌ MetaTrader5 not installed!\nInstall: pip install MetaTrader5")
        return 1

    connect_mt5()

    # parse symbols respecting quotes
    parts = [s.strip() for s in args.symbols.split(',') if s.strip()]
    symbols = [p[1:-1] if (len(p)>=2 and ((p.startswith('"') and p.endswith('"')) or (p.startswith("'") and p.endswith("'")))) else p for p in parts]

    # parse timeframes
    timeframes = [tf.strip().upper() for tf in args.timeframes.split(',') if tf.strip()] if args.timeframes else [None]
    # Validate timeframes
    for tf in timeframes:
        if tf and tf not in MT5_TIMEFRAMES:
            print(f"❌ Invalid timeframe: {tf}. Valid options: {', '.join(MT5_TIMEFRAMES.keys())}")
            return 1

    def run_once():
        for sym in symbols:
            for tf in timeframes:
                tf_label = f" {tf}" if tf else ""
                bars = load_bars(sym, tf)
                if bars.empty:
                    print(f"[{sym}{tf_label}] No bars; skipping")
                    continue
                df_lows = [float(x.strip()) for x in str(args.df_lows).split(',') if x.strip()]
                df_highs = [float(x.strip()) for x in str(args.df_highs).split(',') if x.strip()]
                script = generate_script(
                    sym, tf, bars,
                    unit_mode=args.gann_unit_mode,
                    unit_points=args.gann_unit_points,
                    atr_period=args.gann_atr_period,
                    atr_ratio=args.gann_atr_ratio,
                    df_lows=df_lows,
                    df_highs=df_highs,
                    max_pivots=int(args.max_pivots),
                    bars_cap=int(args.bars_cap)
                )
                save_script(sym, tf, script)
                script_name = f"FibtoolDegreeFactorGann_{sym}{'_'+tf if tf else ''}"
                print(f"[{sym}{tf_label}] ✓ Ready: Navigator → Scripts → {script_name}")

    if args.once:
        run_once()
    else:
        import time
        while True:
            run_once()
            print(f"[LOOP] Sleeping {args.interval}s...")
            time.sleep(args.interval)

    mt5.shutdown()
    print("\n[MT5] Disconnected")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
