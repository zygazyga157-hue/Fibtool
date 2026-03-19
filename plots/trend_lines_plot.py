"""
Production Tool 4: Trend Lines Plot
====================================

Draws trend lines connecting pivot points on MT5 charts.

Features:
- Plots diagonal trend lines from ACTUAL pivot timestamps to confluence prices
- Reads real pivot data from bars CSV with pivot detection
- Quality-based ray extension (projects high-quality trends forward)
- Angle/slope filtering (excludes flat or erratic trends)
- Color-coded by side (red=resistance, blue=support)
- Smart line width based on trend quality + slope
- Shows relationship between pivots and confluences

Usage:
    python plots/trend_lines_plot.py --symbols XAUUSD --once
    python plots/trend_lines_plot.py --symbols XAUUSD --timeframes H1,H4,D1 --once
    python plots/trend_lines_plot.py --symbols XAUUSD,USDCAD --interval 60
    python plots/trend_lines_plot.py --symbols XAUUSD --cleanup
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


# Configuration
OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
OBJECT_PREFIX = "fibtool_trend"
MT5_DATA_FOLDER = Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "D0E8209F77C8CF37AD8BF550E51FF075"
MQL5_SCRIPTS_DIR = MT5_DATA_FOLDER / "MQL5" / "Scripts"

# MT5 timeframe mapping
MT5_TIMEFRAMES = {
    'M1': 1, 'M5': 5, 'M15': 15, 'M30': 30,
    'H1': 16385, 'H4': 16388, 'D1': 16408, 'W1': 32769, 'MN1': 49153
}

# Pivot detection configuration
DEFAULT_PIVOT_BARS = 5         # left/right bars for pivot detection
PIVOT_MATCH_TOLERANCE = 0.005  # 0.5% price tolerance for pivot matching

# Angle filter bounds
MIN_EXTENSION_ANGLE = 5.0      # degrees - too flat
MAX_EXTENSION_ANGLE = 75.0     # degrees - too steep

# ---- Gann angle configuration (defaults) ----
# unit_mode: 'point' uses instrument points as the base unit;
#            'atr' uses a fraction of ATR per bar as base unit
GANN_UNIT_MODE = 'point'       # 'point' | 'atr'
GANN_UNIT_POINTS = 100         # how many points constitute 1x1 (only when unit_mode='point')
GANN_ATR_PERIOD = 14           # ATR period (only when unit_mode='atr')
GANN_ATR_RATIO = 0.25          # 1x1 = 0.25 ATR per bar (only when unit_mode='atr')
GANN_TOLERANCE = 0.2           # 20% tolerance to consider slope near a canonical Gann angle
GANN_EXTEND_LABELS = ["1x1", "2x1"]  # labels that qualify for ray extension when quality also passes
ANGLE_CLUSTER_WINDOW_MIN = 120  # minutes window to consider cluster of similar Gann labels
GANN_CANONICAL = [
    ("1x8", 0.125), ("1x4", 0.25), ("1x2", 0.5), ("1x1", 1.0),
    ("2x1", 2.0), ("4x1", 4.0), ("8x1", 8.0)
]

# Gann degrees reference for labels
GANN_DEGREES = {
    "1x8": 7.5, "1x4": 15.0, "1x2": 26.25, "1x1": 45.0,
    "2x1": 63.75, "3x1": 71.25, "4x1": 75.0, "8x1": 82.5
}


def symbol_slug(symbol: str, timeframe: str | None = None) -> str:
    """Filesystem-safe slug for a symbol (lowercase, non-alnum -> _)."""
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


def normalize_timestamp(ts: str | datetime | pd.Timestamp) -> datetime:
    """
    Convert any timestamp format to timezone-aware UTC datetime.
    
    Args:
        ts: Timestamp in various formats (ISO string, datetime, pd.Timestamp)
    
    Returns:
        Timezone-aware datetime in UTC
    """
    if isinstance(ts, pd.Timestamp):
        if ts.tzinfo is None:
            return ts.tz_localize('UTC').to_pydatetime()
        return ts.to_pydatetime()
    elif isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts
    else:
        # String format - clean and parse
        ts_clean = str(ts).replace('+00:00', '').replace('Z', '')
        dt = datetime.fromisoformat(ts_clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt


def load_confluences(symbol: str, timeframe: str | None = None) -> list[dict]:
    """Load latest confluences from CSV."""
    slug = symbol_slug(symbol, timeframe)
    csv_path = OUTPUT_DIR / f"{slug}_confluences.csv"
    
    if not csv_path.exists():
        # Try without timeframe if specific file not found
        if timeframe:
            csv_path_alt = OUTPUT_DIR / f"{symbol_slug(symbol)}_confluences.csv"
            if csv_path_alt.exists():
                print(f"[CSV] Using {csv_path_alt.name} for {symbol} {timeframe}")
                csv_path = csv_path_alt
            else:
                print(f"[CSV] No data found for {symbol} {timeframe}")
                return []
        else:
            print(f"[CSV] No data found for {symbol}")
            return []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    
    if not rows:
        return []
    
    # Get latest batch
    latest_ts = max(r.get('timestamp', '') for r in rows)
    latest = [r for r in rows if r.get('timestamp') == latest_ts]
    
    tf_label = f" {timeframe}" if timeframe else ""
    print(f"[CSV] Loaded {len(latest)} confluences from {latest_ts}{tf_label}")
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
    Get visual style for a trend line.
    
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
        style = "STYLE_DASH"
    
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


def load_bars_data(symbol: str, timeframe: str | None = None) -> pd.DataFrame:
    """
    Load historical bars data from CSV.
    
    Args:
        symbol: Trading symbol
        timeframe: Optional timeframe (H1, H4, D1, etc.)
    
    Returns:
        DataFrame with columns: time, open, high, low, close, volume
    """
    slug = symbol_slug(symbol, timeframe)
    csv_path = OUTPUT_DIR / f"{slug}_bars.csv"
    
    if not csv_path.exists():
        # Try without timeframe if specific file not found
        if timeframe:
            csv_path_alt = OUTPUT_DIR / f"{symbol_slug(symbol)}_bars.csv"
            if csv_path_alt.exists():
                print(f"[BARS] Using {csv_path_alt.name} for {symbol} {timeframe}")
                csv_path = csv_path_alt
            else:
                print(f"[BARS] No bars data found for {symbol} {timeframe}")
                return pd.DataFrame()
        else:
            print(f"[BARS] No bars data found for {symbol}")
            return pd.DataFrame()

    # Read and normalize bars dataframe
    try:
        df = pd.read_csv(csv_path)
        # Normalize time column
        if 'time' not in df.columns and 'timestamp' in df.columns:
            df = df.rename(columns={'timestamp': 'time'})
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'], utc=True, errors='coerce')
        else:
            # If no time column, create a monotonic index-based time starting now at 1-minute intervals
            base = pd.Timestamp.utcnow().floor('T')
            df.insert(0, 'time', [base + pd.Timedelta(minutes=i) for i in range(len(df))])
        # Ensure numeric types for price columns if present
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        # Drop rows without time or prices
        df = df.dropna(subset=['time']).sort_values('time').reset_index(drop=True)
        tf_label = f" {timeframe}" if timeframe else ""
        print(f"[BARS] Loaded {len(df)} bars for {symbol}{tf_label}")
        return df
    except Exception as e:
        print(f"[BARS] Error loading bars for {symbol}: {e}")
        return pd.DataFrame()


def _get_symbol_point(symbol: str, bars_df: pd.DataFrame) -> float:
    """Best-effort retrieval of symbol point size (minimum tick in price units)."""
    # Try MT5 symbol info first
    if MT5_AVAILABLE and mt5 is not None:
        try:
            info = mt5.symbol_info(symbol)
            if info and getattr(info, 'point', None):
                return float(info.point)
        except Exception:
            pass
    # Fallback: infer decimals from last close
    try:
        if not bars_df.empty and 'close' in bars_df.columns:
            sample = float(bars_df['close'].iloc[-1])
            s = f"{sample:.10f}"
            if '.' in s:
                dec = len(s.rstrip('0').split('.')[-1])
                dec = min(max(dec, 1), 10)
                return 10 ** (-dec)
    except Exception:
        pass
    # Conservative default
    return 0.01


def _calc_atr(df: pd.DataFrame, period: int = 14) -> float | None:
    try:
        if df.empty or len(df) < period + 1:
            return None
        high = df['high'].astype(float)
        low = df['low'].astype(float)
        close = df['close'].astype(float)
        prev_close = close.shift(1)
        tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        atr = tr.rolling(period).mean().iloc[-1]
        return float(atr) if pd.notna(atr) else None
    except Exception:
        return None


def classify_gann_angle(pivot_price: float, conf_price: float, pivot_idx: int, conf_time: str,
                        bars_df: pd.DataFrame, symbol: str,
                        unit_mode: str = GANN_UNIT_MODE,
                        unit_points: int = GANN_UNIT_POINTS,
                        atr_period: int = GANN_ATR_PERIOD,
                        atr_ratio: float = GANN_ATR_RATIO,
                        tolerance: float = GANN_TOLERANCE) -> tuple[str | None, float | None, float | None]:
    """
    Classify the trend slope between pivot and confluence into a Gann angle label.

    Returns: (label, ratio_to_unit, slope_per_bar)
      - label: one of GANN_CANONICAL names or None
      - ratio_to_unit: slope_per_bar / unit_per_bar
      - slope_per_bar: absolute price change per bar
    """
    try:
        # Determine bar index for confluence time
        # Parse ISO, ensure tz-aware
        conf_time_clean = conf_time.replace('+00:00', '').replace('Z', '') if isinstance(conf_time, str) else str(conf_time)
        conf_dt = datetime.fromisoformat(conf_time_clean)
        if conf_dt.tzinfo is None:
            conf_dt = conf_dt.replace(tzinfo=timezone.utc)

        # Find index of bar at/after conf time
        conf_idx = len(bars_df) - 1
        for i in range(pivot_idx, len(bars_df)):
            bt = bars_df.loc[i, 'time']
            if isinstance(bt, pd.Timestamp):
                if bt.tzinfo is None:
                    bt = bt.tz_localize('UTC')
                bt_dt = bt.to_pydatetime()
            elif isinstance(bt, datetime):
                bt_dt = bt if bt.tzinfo else bt.replace(tzinfo=timezone.utc)
            else:
                bt_dt = datetime.fromisoformat(str(bt)).replace(tzinfo=timezone.utc)
            if bt_dt >= conf_dt:
                conf_idx = i
                break

        bars_distance = max(1, conf_idx - pivot_idx)
        slope_per_bar = abs(conf_price - pivot_price) / bars_distance

        # Determine unit per bar
        unit_per_bar = None
        if unit_mode == 'point':
            point = _get_symbol_point(symbol, bars_df)
            unit_per_bar = point * max(1, int(unit_points))
        elif unit_mode == 'atr':
            atr = _calc_atr(bars_df, period=atr_period)
            if atr is not None:
                unit_per_bar = float(atr) * float(atr_ratio)

        if not unit_per_bar or unit_per_bar <= 0:
            return None, None, slope_per_bar

        ratio = slope_per_bar / unit_per_bar

        # Find nearest canonical Gann angle by ratio
        best_label = None
        best_err = 1e9
        for name, canon in GANN_CANONICAL:
            err = abs(ratio - canon) / canon
            if err < best_err:
                best_err = err
                best_label = name

        if best_err <= max(0.05, float(tolerance)):
            return best_label, ratio, slope_per_bar
        return None, ratio, slope_per_bar
    except Exception:
        return None, None, None


def _load_gann_config(config_path: str | None) -> dict:
    """Load optional Gann settings JSON file.

    Expected shape:
    {
      "defaults": { "unit_mode": "point|atr", "unit_points": 100, "atr_period": 14, "atr_ratio": 0.25, "tolerance": 0.2, "extend_labels": ["1x1","2x1"], "cluster_window_min": 120 },
      "symbols": { "XAUUSD": { ... overrides ... }, "EURUSD": { ... } }
    }
    """
    if not config_path:
        return {}
    p = Path(config_path)
    if not p.exists():
        return {}
    try:
        import json
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"[GANN] Failed to load config {config_path}: {e}")
        return {}


def _resolve_gann_settings(symbol: str, args, gann_cfg: dict) -> dict:
    """Merge defaults, config, per-symbol overrides, and CLI args to compute final Gann settings for a symbol."""
    s = {
        'unit_mode': GANN_UNIT_MODE,
        'unit_points': GANN_UNIT_POINTS,
        'atr_period': GANN_ATR_PERIOD,
        'atr_ratio': GANN_ATR_RATIO,
        'tolerance': GANN_TOLERANCE,
        'extend_labels': list(GANN_EXTEND_LABELS),
        'cluster_window_min': ANGLE_CLUSTER_WINDOW_MIN,
        # Fan drawing additions
        'draw_fan': False,
        'fan_forward': 200,
        'fan_back': 0,
        'fan_labels': True,
        # Concentration controls
        'min_quality': 2.80,
        'max_lines_per_side': 4,
        'keep_fib_pcts': None,  # e.g., ["38.2","61.8","90","111"] as strings or floats
        'require_cluster_min': 1,
        'enforce_angle_filter': False,
        'min_angle_deg': 5.0,
        'max_angle_deg': 75.0,
    }
    try:
        if isinstance(gann_cfg, dict):
            defaults = gann_cfg.get('defaults', {}) or {}
            if isinstance(defaults, dict):
                for k in s.keys():
                    if k in defaults:
                        s[k] = defaults[k]
            per = (gann_cfg.get('symbols', {}) or {}).get(symbol, {})
            if isinstance(per, dict):
                for k in s.keys():
                    if k in per:
                        s[k] = per[k]
    except Exception:
        pass
    # CLI args override
    if hasattr(args, 'gann_unit_mode') and args.gann_unit_mode:
        s['unit_mode'] = args.gann_unit_mode
    if hasattr(args, 'gann_unit_points') and args.gann_unit_points is not None:
        s['unit_points'] = int(args.gann_unit_points)
    if hasattr(args, 'gann_atr_period') and args.gann_atr_period is not None:
        s['atr_period'] = int(args.gann_atr_period)
    if hasattr(args, 'gann_atr_ratio') and args.gann_atr_ratio is not None:
        s['atr_ratio'] = float(args.gann_atr_ratio)
    if hasattr(args, 'gann_tolerance') and args.gann_tolerance is not None:
        s['tolerance'] = float(args.gann_tolerance)
    if hasattr(args, 'gann_extend_labels') and args.gann_extend_labels:
        try:
            s['extend_labels'] = [x.strip() for x in str(args.gann_extend_labels).split(',') if x.strip()]
        except Exception:
            pass
    if hasattr(args, 'gann_cluster_window_min') and args.gann_cluster_window_min is not None:
        s['cluster_window_min'] = int(args.gann_cluster_window_min)
    # Fan-related CLI overrides
    if hasattr(args, 'gann_draw_fan') and args.gann_draw_fan:
        s['draw_fan'] = True
    if hasattr(args, 'gann_fan_forward') and args.gann_fan_forward is not None:
        s['fan_forward'] = int(args.gann_fan_forward)
    if hasattr(args, 'gann_fan_back') and args.gann_fan_back is not None:
        s['fan_back'] = int(args.gann_fan_back)
    if hasattr(args, 'gann_fan_labels') and args.gann_fan_labels is not None:
        s['fan_labels'] = bool(args.gann_fan_labels)
    # Concentration CLI overrides
    if hasattr(args, 'min_quality') and args.min_quality is not None:
        s['min_quality'] = float(args.min_quality)
    if hasattr(args, 'max_lines_per_side') and args.max_lines_per_side is not None:
        s['max_lines_per_side'] = int(args.max_lines_per_side)
    if hasattr(args, 'keep_fib_pcts') and args.keep_fib_pcts:
        try:
            vals = [v.strip() for v in str(args.keep_fib_pcts).split(',') if v.strip()]
            s['keep_fib_pcts'] = vals
        except Exception:
            pass
    if hasattr(args, 'require_cluster_min') and args.require_cluster_min is not None:
        s['require_cluster_min'] = max(1, int(args.require_cluster_min))
    if hasattr(args, 'enforce_angle_filter') and args.enforce_angle_filter:
        s['enforce_angle_filter'] = True
    if hasattr(args, 'min_angle_deg') and args.min_angle_deg is not None:
        s['min_angle_deg'] = float(args.min_angle_deg)
    if hasattr(args, 'max_angle_deg') and args.max_angle_deg is not None:
        s['max_angle_deg'] = float(args.max_angle_deg)
    return s


def detect_pivots(df: pd.DataFrame, left_bars: int = DEFAULT_PIVOT_BARS, right_bars: int = DEFAULT_PIVOT_BARS) -> pd.DataFrame:
    """
    Detect pivot highs and lows in price data.
    
    Args:
        df: DataFrame with 'high' and 'low' columns
        left_bars: Number of bars to the left for comparison
        right_bars: Number of bars to the right for comparison
    
    Returns:
        DataFrame with additional columns: pivot_high, pivot_low
    """
    if df.empty or len(df) < left_bars + right_bars + 1:
        return df
    
    df = df.copy()
    df['pivot_high'] = 0.0
    df['pivot_low'] = 0.0
    
    # Detect pivot highs
    for i in range(left_bars, len(df) - right_bars):
        is_pivot_high = True
        center_high = df.loc[i, 'high']
        
        # Check left bars
        for j in range(i - left_bars, i):
            if df.loc[j, 'high'] > center_high:
                is_pivot_high = False
                break
        
        # Check right bars
        if is_pivot_high:
            for j in range(i + 1, i + right_bars + 1):
                if df.loc[j, 'high'] > center_high:
                    is_pivot_high = False
                    break
        
        if is_pivot_high:
            df.loc[i, 'pivot_high'] = center_high
    
    # Detect pivot lows
    for i in range(left_bars, len(df) - right_bars):
        is_pivot_low = True
        center_low = df.loc[i, 'low']
        
        # Check left bars
        for j in range(i - left_bars, i):
            if df.loc[j, 'low'] < center_low:
                is_pivot_low = False
                break
        
        # Check right bars
        if is_pivot_low:
            for j in range(i + 1, i + right_bars + 1):
                if df.loc[j, 'low'] < center_low:
                    is_pivot_low = False
                    break
        
        if is_pivot_low:
            df.loc[i, 'pivot_low'] = center_low
    
    return df


def find_matching_pivot(bars_df: pd.DataFrame, conf: dict) -> tuple:
    """
    Find the actual pivot point that corresponds to a confluence.
    Uses price proximity as primary criterion and time proximity as tiebreaker.
    
    Args:
        bars_df: DataFrame with pivot_high and pivot_low columns
        conf: Confluence dict with pivot_low, pivot_high, origin, timestamp
    
    Returns:
        tuple: (pivot_price, pivot_time_str, pivot_idx) or (None, None, None)
    """
    if bars_df.empty:
        return None, None, None
    
    # Get target pivot price from confluence
    origin = conf.get('origin', '').lower()
    pivot_target = float(conf.get('pivot_low', 0) or 0) if origin == 'low' else float(conf.get('pivot_high', 0) or 0)
    
    if pivot_target == 0:
        return None, None, None
    
    # Parse confluence timestamp for time-proximity tiebreaker
    try:
        conf_dt = normalize_timestamp(conf.get('timestamp', ''))
    except Exception:
        conf_dt = None
    
    # Find matching pivot in bars
    if origin == 'low':
        pivots = bars_df[bars_df['pivot_low'] > 0].copy()
        if pivots.empty:
            return None, None, None
        
        # Calculate price difference
        pivots['price_diff'] = (pivots['pivot_low'] - pivot_target).abs()
        
        # Filter by tolerance
        pivots = pivots[pivots['price_diff'] < pivot_target * PIVOT_MATCH_TOLERANCE]
        if pivots.empty:
            return None, None, None
        
        # Add time proximity as tiebreaker if available
        if conf_dt is not None:
            try:
                pivots['time_diff'] = pivots['time'].apply(lambda t: abs((normalize_timestamp(t) - conf_dt).total_seconds()))
                # Sort by price first, then time
                pivots = pivots.sort_values(['price_diff', 'time_diff'])
            except Exception:
                pivots = pivots.sort_values('price_diff')
        else:
            pivots = pivots.sort_values('price_diff')
        
        best = pivots.iloc[0]
        pivot_time = best['time']
        pivot_time_str = pivot_time.strftime("%Y.%m.%d %H:%M") if hasattr(pivot_time, 'strftime') else str(pivot_time)
        return float(best['pivot_low']), pivot_time_str, int(best.name)
    
    else:  # origin == 'high'
        pivots = bars_df[bars_df['pivot_high'] > 0].copy()
        if pivots.empty:
            return None, None, None
        
        # Calculate price difference
        pivots['price_diff'] = (pivots['pivot_high'] - pivot_target).abs()
        
        # Filter by tolerance
        pivots = pivots[pivots['price_diff'] < pivot_target * PIVOT_MATCH_TOLERANCE]
        if pivots.empty:
            return None, None, None
        
        # Add time proximity as tiebreaker if available
        if conf_dt is not None:
            try:
                pivots['time_diff'] = pivots['time'].apply(lambda t: abs((normalize_timestamp(t) - conf_dt).total_seconds()))
                # Sort by price first, then time
                pivots = pivots.sort_values(['price_diff', 'time_diff'])
            except Exception:
                pivots = pivots.sort_values('price_diff')
        else:
            pivots = pivots.sort_values('price_diff')
        
        best = pivots.iloc[0]
        pivot_time = best['time']
        pivot_time_str = pivot_time.strftime("%Y.%m.%d %H:%M") if hasattr(pivot_time, 'strftime') else str(pivot_time)
        return float(best['pivot_high']), pivot_time_str, int(best.name)
    
    return None, None, None


def calculate_trend_angle(pivot_price: float, conf_price: float, pivot_idx: int, conf_time: str, bars_df: pd.DataFrame) -> float:
    """
    Calculate the angle/slope of a trend line.
    
    Args:
        pivot_price: Starting pivot price
        conf_price: Ending confluence price
        pivot_idx: Index of pivot in bars_df
        conf_time: Confluence timestamp string
        bars_df: DataFrame with time index
    
    Returns:
        Angle in degrees (positive = uptrend, negative = downtrend)
    """
    try:
        # Normalize timestamps
        conf_dt = normalize_timestamp(conf_time)
        pivot_time = normalize_timestamp(bars_df.loc[pivot_idx, 'time'])
        
        # Find confluence index in bars
        conf_idx = len(bars_df) - 1  # Default to last bar
        for i in range(pivot_idx, len(bars_df)):
            bar_time = normalize_timestamp(bars_df.loc[i, 'time'])
            if bar_time >= conf_dt:
                conf_idx = i
                break
        
        bars_distance = max(1, conf_idx - pivot_idx)
        price_change = conf_price - pivot_price
        
        # Calculate slope (price change per bar)
        slope = price_change / bars_distance
        
        # Convert to angle (arctangent)
        # Normalize by average price to get percentage slope
        avg_price = (pivot_price + conf_price) / 2.0
        normalized_slope = slope / avg_price * 100  # Percentage change per bar
        
        # Calculate angle in degrees
        angle = math.degrees(math.atan(normalized_slope))
        
        return angle
        
    except Exception as e:
        print(f"[ANGLE] Error calculating angle: {e}")
        return 0.0


def should_extend_ray(conf: dict, angle: float, gann_label: str | None = None, extend_labels: list[str] | None = None) -> tuple:
    """
    Determine if trend line should extend as ray based on quality and angle.
    
    Args:
        conf: Confluence dict with quality metrics
        angle: Trend angle in degrees
        gann_label: Optional Gann angle classification
        extend_labels: Optional whitelist of Gann labels that qualify for extension
    
    Returns:
        tuple: (extend_right: bool, extend_left: bool)
    """
    strength_score = float(conf.get('strength_score', 0) or 0)
    severity = float(conf.get('severity', 0) or 0)
    quality = (strength_score + severity) / 2
    
    # Only extend high-quality trends
    if quality < 2.75:
        return False, False
    
    # Filter by angle (exclude flat or too steep trends)
    abs_angle = abs(angle)
    if abs_angle < MIN_EXTENSION_ANGLE or abs_angle > MAX_EXTENSION_ANGLE:
        return False, False
    
    # Gate by Gann alignment if extend_labels provided
    if extend_labels:
        allowed = set(x.strip().lower() for x in extend_labels)
        if not (gann_label and gann_label.lower() in allowed):
            return False, False

    # Extend forward for high-quality trends
    extend_right = quality >= 2.80
    extend_left = False  # Don't extend backward
    
    return extend_right, extend_left


def generate_mql5_script(symbol: str, timeframe: str | None, confluences: list[dict], bars_df: pd.DataFrame, gann_settings: dict | None = None) -> str:
    """
    Generate MQL5 script for trend lines with actual pivot data.
    
    Args:
        symbol: Trading symbol
        timeframe: Optional timeframe (H1, H4, D1, etc.)
        confluences: List of confluence dictionaries
        bars_df: DataFrame with pivot detection results
        gann_settings: Optional Gann configuration dictionary
    
    Returns:
        Complete MQL5 script as string
    """
    timestamp = datetime.now(timezone.utc)
    ts_str = timestamp.strftime("%Y%m%dT%H%M%SZ")
    tf_const = f"PERIOD_{timeframe}" if timeframe else "PERIOD_CURRENT"
    tf_label = f"_{timeframe}" if timeframe else ""
    
    # Helper: escape strings for MQL5 string literals
    def mql_escape(s: str) -> str:
        try:
            return str(s).replace('\\', r'\\').replace('"', r'\"').replace('\n', r'\n').replace('\r', '')
        except Exception:
            return str(s)

    # Resolve Gann settings once at the start to avoid duplication in loop
    gs = gann_settings or {}
    unit_mode = gs.get('unit_mode', GANN_UNIT_MODE)
    unit_points = gs.get('unit_points', GANN_UNIT_POINTS)
    atr_period = gs.get('atr_period', GANN_ATR_PERIOD)
    atr_ratio = gs.get('atr_ratio', GANN_ATR_RATIO)
    tolerance = gs.get('tolerance', GANN_TOLERANCE)
    extend_labels = gs.get('extend_labels', GANN_EXTEND_LABELS)
    min_quality_req = float(gs.get('min_quality', 2.80))
    max_lines_per_side = int(gs.get('max_lines_per_side', 4))
    keep_fib_list = gs.get('keep_fib_pcts')
    require_cluster_min = int(gs.get('require_cluster_min', 1))
    enforce_angle_filter = bool(gs.get('enforce_angle_filter', False))
    min_angle_deg = float(gs.get('min_angle_deg', MIN_EXTENSION_ANGLE))
    max_angle_deg = float(gs.get('max_angle_deg', MAX_EXTENSION_ANGLE))
    
    # Compute unit per bar for Gann projections (shared)
    unit_per_bar = None
    if unit_mode == 'point':
        try:
            point = _get_symbol_point(symbol, bars_df)
            unit_per_bar = point * max(1, int(unit_points))
        except Exception:
            unit_per_bar = None
    else:  # 'atr'
        unit_per_bar = _calc_atr(bars_df, period=int(atr_period))
        if unit_per_bar is not None:
            unit_per_bar = float(unit_per_bar) * float(atr_ratio)
    
    # Build drawing commands
    draw_commands = []
    # For cluster tagging, keep recent times per Gann label
    from collections import defaultdict, deque
    label_times: dict[str, deque] = defaultdict(deque)
    cw_minutes = int(gs.get('cluster_window_min', ANGLE_CLUSTER_WINDOW_MIN))
    cluster_window = timedelta(minutes=cw_minutes)
    drawn_count = 0
    skipped_no_pivot = 0
    skipped_angle = 0
    per_side_drawn = {'above': 0, 'below': 0}
    
    # Ensure chronological order for clustering logic
    try:
        confluences_sorted = sorted(confluences, key=lambda c: c.get('timestamp',''))
    except Exception:
        confluences_sorted = confluences

    for idx, conf in enumerate(confluences_sorted):
        try:
            price = float(conf.get('fib_price', 0))
            if price == 0:
                continue
            
            conf_id = conf.get('conf_id', f'conf{idx}')
            strength = conf.get('strength', 'moderate')
            fib_pct = conf.get('fib_pct', '?')
            side = conf.get('side', 'unknown').lower()
            timestamp_str = conf.get('timestamp', '')

            # Filter by allowed fib percentages if provided
            if keep_fib_list:
                try:
                    fp = str(fib_pct).replace('%','').strip()
                    allowed = set(s.replace('%','').strip() for s in keep_fib_list)
                    if fp not in allowed:
                        continue
                except Exception:
                    pass
            
            # Find actual pivot from bars data
            pivot_price, pivot_time_str, pivot_idx = find_matching_pivot(bars_df, conf)
            
            if pivot_price is None or pivot_time_str is None:
                skipped_no_pivot += 1
                continue
            
            # Calculate angle and classify Gann angle proximity
            angle = calculate_trend_angle(pivot_price, price, pivot_idx, timestamp_str, bars_df)
            gann_label, gann_ratio, slope_per_bar = classify_gann_angle(
                pivot_price, price, pivot_idx, timestamp_str, bars_df, symbol,
                unit_mode=unit_mode, unit_points=unit_points,
                atr_period=atr_period, atr_ratio=atr_ratio, tolerance=tolerance
            )

            # Cluster tagging (look-back only within window) and gating by required cluster size
            cluster_tag = ""
            cluster_count = 1
            try:
                if gann_label:
                    # Parse current time using centralized function
                    cur_dt = normalize_timestamp(timestamp_str)
                    dq = label_times[gann_label]
                    # drop old
                    while dq and (cur_dt - dq[0]) > cluster_window:
                        dq.popleft()
                    # count existing in window (before adding current)
                    prev_count = len(dq)
                    cluster_count = prev_count + 1
                    dq.append(cur_dt)
                    if prev_count >= 1:
                        cluster_tag = f" | Cluster x{cluster_count}"
            except Exception:
                pass

            extend_right, extend_left = should_extend_ray(conf, angle, gann_label=gann_label, extend_labels=extend_labels)
            
            # Calculate quality for display
            quality = (float(conf.get('strength_score', 0) or 0) + float(conf.get('severity', 0) or 0)) / 2

            # Apply concentration filters
            if quality < min_quality_req:
                continue
            if enforce_angle_filter:
                if abs(angle) < min_angle_deg or abs(angle) > max_angle_deg:
                    skipped_angle += 1
                    continue
            if require_cluster_min > 1:
                if cluster_count < require_cluster_min:
                    continue
            if side in per_side_drawn and per_side_drawn[side] >= max_lines_per_side:
                continue
            
            # Skip if angle is out of range (only for quality trends)
            if not extend_right and quality >= 2.85:
                skipped_angle += 1
                # continue  # Uncomment to skip filtered trends entirely
            
            # Parse timestamp for end point
            mql_time = parse_timestamp(timestamp_str)
            
            # Object names
            line_name = f"{OBJECT_PREFIX}_{symbol}_{conf_id}_{ts_str}"
            label_name = f"{line_name}_label"
            
            # Get styling
            style = get_line_style(conf)
            color = style['color']
            width = style['width']
            line_style = style['style']
            
            font_size = 8 if quality >= 2.90 else 7
            
            # Label text with angle and Gann annotation if available
            strength_symbol = "★★" if quality >= 2.90 else "★" if quality >= 2.80 else "●" if quality >= 2.70 else "○"
            side_arrow = "▼" if side == 'above' else "▲" if side == 'below' else "◆"
            gann_text = f" {gann_label}" if gann_label else ""
            label_text_raw = f"{side_arrow}{strength_symbol} {fib_pct}% ({angle:.1f}°{gann_text})"
            label_text = mql_escape(label_text_raw)
            
            # Ray extension indicator
            ray_indicator = " ⟶" if extend_right else ""
            
            # Alert message mirrors the label/tooltip
            alert_msg_raw = f"{symbol} | {strength.upper()} trend {side.upper()} | Fib {fib_pct}% | {pivot_price} → {price} | Angle {angle:.1f}°{(' | ' + gann_label) if gann_label else ''}{cluster_tag}"
            alert_msg = mql_escape(alert_msg_raw)

            # MQL5 code for this trend line
            draw_cmd = f"""
   // ═══════════════════════════════════════════════════════════════
   // TrendLine #{idx + 1}: {strength.upper()}{ray_indicator}
   // Pivot: {pivot_price} @ {pivot_time_str} → Confluence: {price} @ {mql_time}
   // Side: {side.upper()} | Quality: {quality:.2f} | Angle: {angle:.1f}°
   // ═══════════════════════════════════════════════════════════════
   
   // Create trend line from actual pivot to confluence
   datetime trendStart_{idx} = StringToTime("{pivot_time_str}");
   datetime trendEnd_{idx} = StringToTime("{mql_time}");
   
   if(!ObjectCreate(chartId, "{line_name}", OBJ_TREND, 0, trendStart_{idx}, {pivot_price}, trendEnd_{idx}, {price}))
   {{
      Print("✗ Error creating trend line #{idx + 1}: ", GetLastError());
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
      ObjectSetInteger(chartId, "{line_name}", OBJPROP_RAY_RIGHT, {str(extend_right).lower()});  // Quality-based extension
            ObjectSetInteger(chartId, "{line_name}", OBJPROP_RAY_LEFT, {str(extend_left).lower()});
        ObjectSetString(chartId, "{line_name}", OBJPROP_TOOLTIP, "{mql_escape(f"{strength.upper()} trend ({angle:.1f}°{(' ' + gann_label) if gann_label else ''})\nPivot: {pivot_price} → Fib{fib_pct}%: {price}{cluster_tag}")}");
        Print("✓ Trend #{idx + 1}: ", {pivot_price}, " → ", {price}, " | Angle: {angle:.1f}°{(' ' + gann_label) if gann_label else ''} | Ray: {extend_right}{cluster_tag}");
    // Alerts
    if(Enable_Alerts) Alert("{alert_msg}");
    if(Enable_Push)   SendNotification("{alert_msg}");
    if(Enable_Email)  SendMail(Email_Subject, "{alert_msg}");
   }}
   
   // Text label at midpoint
   datetime labelTime_{idx} = trendStart_{idx} + (trendEnd_{idx} - trendStart_{idx}) / 2;
   double labelPrice_{idx} = ({pivot_price} + {price}) / 2.0;
   
   if(!ObjectCreate(chartId, "{label_name}", OBJ_TEXT, 0, labelTime_{idx}, labelPrice_{idx}))
   {{
      Print("✗ Error creating label #{idx + 1}: ", GetLastError());
   }}
   else
   {{
    ObjectSetString(chartId, "{label_name}", OBJPROP_TEXT, "{label_text}");
      ObjectSetString(chartId, "{label_name}", OBJPROP_FONT, "Arial");
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_COLOR, {color});
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_FONTSIZE, {font_size});
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_ANCHOR, ANCHOR_CENTER);
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_BACK, false);
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_SELECTABLE, true);
      ObjectSetInteger(chartId, "{label_name}", OBJPROP_HIDDEN, false);
      Print("✓ Label #{idx + 1}: {label_text}");
   }}
"""
            draw_commands.append(draw_cmd)
            if side in per_side_drawn:
                per_side_drawn[side] += 1

            # Add optional Gann fan drawing from pivot when quality and Gann criteria allow
            if gs.get('draw_fan', False) and extend_right and (unit_per_bar is not None and unit_per_bar > 0):
                try:
                    fan_forward = max(1, int(gs.get('fan_forward', 200)))
                    fan_back = max(0, int(gs.get('fan_back', 0)))  # reserved for future use
                    fan_labels = bool(gs.get('fan_labels', True))
                    seconds_per_bar_expr = "PeriodSeconds(PERIOD_CURRENT)"
                    # Determine ratios set by origin
                    origin_flag = (conf.get('origin','') or '').lower()
                    if origin_flag == 'low':
                        ratios = [
                            ("1x1", 1.0), ("2x1", 2.0), ("3x1", 3.0), ("4x1", 4.0), ("8x1", 8.0)
                        ]
                        direction = +1
                    else:
                        ratios = [
                            ("1x1", 1.0), ("1x2", 0.5), ("1x4", 0.25), ("1x8", 0.125)
                        ]
                        direction = -1

                    for ridx, (rlabel, r) in enumerate(ratios):
                        deg = GANN_DEGREES.get(rlabel, 0)
                        price_delta = direction * unit_per_bar * r * fan_forward
                        start_time_var = f"trendStart_{idx}"
                        end_time_var = f"gannEnd_{idx}_{ridx}"
                        end_price = pivot_price + price_delta
                        fan_name = f"{OBJECT_PREFIX}_{symbol}_fan_{conf_id}_{rlabel}_{ts_str}"
                        fan_label = f"{fan_name}_label"
                        fan_tooltip = mql_escape(f"Gann {rlabel} ({deg:.2f}°) from {pivot_price} to {end_price:.2f}")
                        fan_text = mql_escape(f"{rlabel} ({deg:.0f}°)")
                        fan_cmd = f"""
   // Gann fan {rlabel}
   int seconds_per_bar = {seconds_per_bar_expr};
   datetime {end_time_var} = {start_time_var} + seconds_per_bar * {fan_forward};
   if(!ObjectCreate(chartId, "{fan_name}", OBJ_TREND, 0, {start_time_var}, {pivot_price}, {end_time_var}, {end_price}))
   {{
      Print("✗ Error creating Gann {rlabel} line: ", GetLastError());
   }}
   else
   {{
      ObjectSetInteger(chartId, "{fan_name}", OBJPROP_COLOR, clrDarkGray);
      ObjectSetInteger(chartId, "{fan_name}", OBJPROP_WIDTH, 1);
      ObjectSetInteger(chartId, "{fan_name}", OBJPROP_STYLE, STYLE_DOT);
      ObjectSetInteger(chartId, "{fan_name}", OBJPROP_BACK, false);
      ObjectSetInteger(chartId, "{fan_name}", OBJPROP_SELECTABLE, true);
      ObjectSetInteger(chartId, "{fan_name}", OBJPROP_SELECTED, false);
      ObjectSetInteger(chartId, "{fan_name}", OBJPROP_HIDDEN, false);
      ObjectSetString(chartId, "{fan_name}", OBJPROP_TOOLTIP, "{fan_tooltip}");
   }}
"""
                        if fan_labels:
                            fan_cmd += f"""
   // Label for Gann fan {rlabel}
   datetime {end_time_var}_lb = {end_time_var};
   if(!ObjectCreate(chartId, "{fan_label}", OBJ_TEXT, 0, {end_time_var}_lb, {end_price}))
   {{
      Print("✗ Error creating Gann label {rlabel}: ", GetLastError());
   }}
   else
   {{
      ObjectSetString(chartId, "{fan_label}", OBJPROP_TEXT, "{fan_text}");
      ObjectSetString(chartId, "{fan_label}", OBJPROP_FONT, "Arial");
      ObjectSetInteger(chartId, "{fan_label}", OBJPROP_COLOR, clrDarkGray);
      ObjectSetInteger(chartId, "{fan_label}", OBJPROP_FONTSIZE, 7);
      ObjectSetInteger(chartId, "{fan_label}", OBJPROP_ANCHOR, ANCHOR_LEFT);
      ObjectSetInteger(chartId, "{fan_label}", OBJPROP_BACK, false);
      ObjectSetInteger(chartId, "{fan_label}", OBJPROP_SELECTABLE, true);
      ObjectSetInteger(chartId, "{fan_label}", OBJPROP_HIDDEN, false);
   }}
"""
                        draw_commands.append(fan_cmd)
                except Exception:
                    pass
            drawn_count += 1
            
        except Exception as e:
            print(f"[ERROR] Skipping confluence {idx}: {e}")
            continue
    
    # Print summary
    total = len(confluences)
    print(f"\n[TREND LINES SUMMARY]")
    print(f"  Total confluences: {total}")
    print(f"  Drawn: {drawn_count}")
    print(f"  Skipped (no pivot): {skipped_no_pivot}")
    print(f"  Skipped (angle filter): {skipped_angle}")
    
    # Complete script
    script = f"""//+------------------------------------------------------------------+
//|                           FibtoolTrendLines_{symbol}{tf_label}.mq5 |
//|                        Production Tool 4: Trend Lines            |
//|                        Draws diagonal lines from pivots           |
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
   Print("  FIBTOOL - Trend Lines Plot");
   Print("═══════════════════════════════════════════════════");
   Print("Symbol: ", Symbol_Input);
   Print("Drawing {len(draw_commands)} trend lines...");
   Print("═══════════════════════════════════════════════════");
   Print("");
   
   long chartId = ChartID();
   
   // Verify symbol and timeframe
    if(Symbol() != Symbol_Input)
    {{
        Print("⚠ WARNING: Running on ", Symbol(), " but targeting ", Symbol_Input);
        // Try to switch the current chart to the target symbol and timeframe
        if(!ChartSetSymbolPeriod(chartId, Symbol_Input, {tf_const}))
        {{
            Print("⚠ Failed to switch chart: ", GetLastError());
        }}
        else
        {{
            Print("✓ Chart switched to: ", Symbol_Input, " {timeframe or 'Current'}");
        }}
    }}
   
   Print("Drawing trend lines on chart ", chartId, "...");
   Print("");
{''.join(draw_commands)}
   
   Print("");
   Print("═══════════════════════════════════════════════════");
   Print("✓ DRAWING COMPLETE!");
   Print("═══════════════════════════════════════════════════");
   Print("Trend lines drawn: {len(draw_commands)}");
   Print("Use Ctrl+B to view all objects");
   Print("═══════════════════════════════════════════════════");
   
   ChartRedraw(chartId);
}}
//+------------------------------------------------------------------+
"""
    
    return script


def save_script(symbol: str, timeframe: str | None, script_content: str) -> Path:
    """Save MQL5 script to MT5 Scripts folder."""
    MQL5_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    
    tf_label = f"_{timeframe}" if timeframe else ""
    script_path = MQL5_SCRIPTS_DIR / f"FibtoolTrendLines_{symbol}{tf_label}.mq5"
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    print(f"[MQL] ✓ Script saved: {script_path}")
    return script_path


def generate_cleanup_script(symbol: str, timeframe: str | None = None) -> str:
    """Generate cleanup script for trend lines."""
    tf_label = f"_{timeframe}" if timeframe else ""
    tf_display = f" {timeframe}" if timeframe else ""
    script = f"""//+------------------------------------------------------------------+
//|                     FibtoolTrendLines_{symbol}{tf_label}_Cleanup.mq5 |
//|                        Cleanup trend lines objects                |
//+------------------------------------------------------------------+
#property copyright "Fibtool"
#property version   "1.00"

void OnStart()
{{
   Print("═══════════════════════════════════════════════════");
   Print("  Cleaning up trend lines for {symbol}{tf_display}");
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


def save_cleanup_script(symbol: str, timeframe: str | None = None):
    """Save cleanup script."""
    script_content = generate_cleanup_script(symbol, timeframe)
    tf_label = f"_{timeframe}" if timeframe else ""
    cleanup_path = MQL5_SCRIPTS_DIR / f"FibtoolTrendLines_{symbol}{tf_label}_Cleanup.mq5"
    
    with open(cleanup_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    print(f"[MQL] ✓ Cleanup script saved: {cleanup_path}")


def plot_trend_lines(symbol: str, timeframe: str | None = None, gann_settings: dict | None = None):
    """Main function to plot trend lines for a symbol."""
    tf_label = f" {timeframe}" if timeframe else ""
    print(f"\n{'='*60}")
    print(f"[{symbol}{tf_label}] Generating trend lines plot...")
    print(f"{'='*60}")
    
    # Load confluences
    confluences = load_confluences(symbol, timeframe)
    
    if not confluences:
        print(f"[{symbol}{tf_label}] No confluences to plot")
        return
    
    # Load and process bars data
    print(f"[{symbol}{tf_label}] Loading bars data...")
    bars_df = load_bars_data(symbol, timeframe)
    
    if bars_df.empty:
        print(f"[{symbol}{tf_label}] ⚠️ No bars data found, using fallback (no pivot matching)")
        bars_df = pd.DataFrame()  # Empty DataFrame for fallback
    else:
        bars_df = detect_pivots(bars_df)
        pivot_lows = len(bars_df[bars_df['pivot_low'] > 0])
        pivot_highs = len(bars_df[bars_df['pivot_high'] > 0])
        print(f"[{symbol}{tf_label}] Detected {pivot_lows} pivot lows, {pivot_highs} pivot highs")
    
    # Generate script
    script_content = generate_mql5_script(symbol, timeframe, confluences, bars_df, gann_settings=gann_settings)
    
    # Save script
    script_path = save_script(symbol, timeframe, script_content)
    
    script_name = f"FibtoolTrendLines_{symbol}{'_' + timeframe if timeframe else ''}"
    print(f"\n[{symbol}{tf_label}] ✓ Ready to execute")
    print(f"[{symbol}{tf_label}] To run:")
    print(f"  1. Open MT5")
    print(f"  2. Open {symbol}{tf_label} chart")
    print(f"  3. Navigator → Scripts → {script_name}")
    print(f"  4. Drag to chart or double-click")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Production Tool 4: Trend Lines Plot")
    parser.add_argument('--symbols', type=str, required=True, help='Comma-separated symbols (e.g., XAUUSD,USDCAD)')
    parser.add_argument('--timeframes', type=str, default='', help='Comma-separated MT5 timeframes (M1,M5,M15,M30,H1,H4,D1,W1,MN1). If empty, uses current/default.')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--interval', type=int, default=60, help='Refresh interval in seconds (default: 60)')
    parser.add_argument('--cleanup', action='store_true', help='Generate cleanup scripts only')
    # Gann configuration CLI overrides
    parser.add_argument('--gann-config', type=str, default=None, help='Path to JSON config for Gann settings (defaults + per-symbol overrides)')
    parser.add_argument('--gann-unit-mode', type=str, choices=['point','atr'], help="Gann unit mode: 'point' or 'atr'")
    parser.add_argument('--gann-unit-points', type=int, help='Points per bar for 1x1 when unit-mode=point (e.g., 100)')
    parser.add_argument('--gann-atr-period', type=int, help='ATR period for ATR-based unit')
    parser.add_argument('--gann-atr-ratio', type=float, help='ATR fraction per bar for 1x1 (e.g., 0.25)')
    parser.add_argument('--gann-tolerance', type=float, help='Tolerance ratio for classifying to canonical Gann angles (e.g., 0.2=20%%)')
    parser.add_argument('--gann-extend-labels', type=str, help="Comma-separated labels (e.g., '1x1,2x1') that qualify for ray extension")
    parser.add_argument('--gann-cluster-window-min', type=int, help='Minutes window to tag clusters of similar Gann labels (default: 120)')
    parser.add_argument('--gann-draw-fan', action='store_true', help='Draw a Gann fan from the qualifying pivot (requires ray extension pass)')
    parser.add_argument('--gann-fan-forward', type=int, help='Forward bars for Gann fan projection (default: 200)')
    parser.add_argument('--gann-fan-back', type=int, help='Backward bars for Gann fan projection (currently unused; default: 0)')
    parser.add_argument('--gann-fan-labels', type=int, choices=[0,1], help='Whether to draw labels on Gann fan lines (1=yes,0=no)')
    # Concentration controls
    parser.add_argument('--min-quality', type=float, help='Minimum quality threshold (avg of strength_score and severity) to draw')
    parser.add_argument('--max-lines-per-side', type=int, help='Maximum lines to draw per side (above/below)')
    parser.add_argument('--keep-fib-pcts', type=str, help="Only include these Fib percentages (comma-separated, e.g., '38.2,61.8,90')")
    parser.add_argument('--require-cluster-min', type=int, help='Require at least this many occurrences of the same Gann label in the window to draw')
    parser.add_argument('--enforce-angle-filter', action='store_true', help='Enforce angle range filter for drawing (not just extension)')
    parser.add_argument('--min-angle-deg', type=float, help='Minimum absolute angle in degrees to draw (default 5)')
    parser.add_argument('--max-angle-deg', type=float, help='Maximum absolute angle in degrees to draw (default 75)')
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("PRODUCTION TOOL 4: Trend Lines Plot")
    print("="*60)
    print(f"Symbols: {args.symbols}")
    print(f"Timeframes: {args.timeframes if args.timeframes else 'Default/Current'}")
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
        symbols = [
            p[1:-1] if (
                len(p) >= 2 and (
                    (p.startswith('"') and p.endswith('"')) or (p.startswith("'") and p.endswith("'"))
                )
            ) else p for p in parts
        ]
        
        # Parse timeframes
        timeframes = [tf.strip().upper() for tf in args.timeframes.split(',') if tf.strip()] if args.timeframes else [None]
        # Validate timeframes
        for tf in timeframes:
            if tf and tf not in MT5_TIMEFRAMES:
                print(f"❌ Invalid timeframe: {tf}. Valid options: {', '.join(MT5_TIMEFRAMES.keys())}")
                return 1
        
        # Load Gann JSON config if provided
        gann_cfg = _load_gann_config(args.gann_config)
        
        # Cleanup mode
        if args.cleanup:
            for symbol in symbols:
                for tf in timeframes:
                    save_cleanup_script(symbol, tf)
            print("\n✓ Cleanup scripts generated")
            return 0
        
        # Plot mode
        if args.once:
            for symbol in symbols:
                settings = _resolve_gann_settings(symbol, args, gann_cfg)
                for tf in timeframes:
                    plot_trend_lines(symbol, tf, gann_settings=settings)
            print("\n✓ All scripts generated")
        else:
            import time
            print(f"\n[LOOP] Starting continuous mode (every {args.interval}s)")
            print("[LOOP] Press Ctrl+C to stop\n")
            
            try:
                while True:
                    for symbol in symbols:
                        settings = _resolve_gann_settings(symbol, args, gann_cfg)
                        for tf in timeframes:
                            plot_trend_lines(symbol, tf, gann_settings=settings)
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
