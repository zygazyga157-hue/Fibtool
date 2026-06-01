"""
Background collector for XAUUSD (Gold) that connects to MetaTrader5, fetches bars,
runs DegreeFactor and FibonacciSquareOfNine strategies, and appends analysis to CSVs.

Notes:
- Requires `MetaTrader5` package and terminal logged-in.
- Uses `config.py` in the same folder for MT5 credentials/path.
- Appends one row per run into `outputs/xauusd_analysis.csv` and stores raw bars to
  `outputs/xauusd_bars.csv` when first run.
"""

import time
import os
import csv
import math
from datetime import datetime, timezone

import pandas as pd

# Local imports from the workspace
from config import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, MT5_PATH
from degreefactor import DegreeFactor
from fib_square_strategy import FibonacciSquareOfNine

# Optional import for MetaTrader5; handle gracefully if not installed
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except Exception:
    mt5 = None
    MT5_AVAILABLE = False

# Optional plotting support (disabled)
# Matplotlib disabled to avoid optional dependency at runtime.
plt = None
mdates = None
MPL_AVAILABLE = False

# Pillow for image annotation (used when taking MT5 screenshot)
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None
    PIL_AVAILABLE = False

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'outputs')
# Legacy paths for backward compatibility (XAUUSD)
ANALYSIS_CSV = os.path.join(OUTPUT_DIR, 'symbols_analysis.csv')
CONFLUENCE_INDEX = os.path.join(OUTPUT_DIR, 'confluence_index.json')
CONFLUENCE_TTL_MINUTES = 60

# Default timeframe is H4 (user requested only H4)
TIMEFRAME = mt5.TIMEFRAME_H1 if MT5_AVAILABLE else None

# Compute number of bars to fetch from MT5 based on desired history length.
# Previously this was a fixed 500 bars. For better accuracy use ~6 months
# of history by default (approximate month = 30 days). We compute an
# estimate depending on the timeframe (M1, M5, M15, M30, H1, H4, D1, W1, MN1).
DEFAULT_HISTORY_MONTHS = 12
MAX_BATCH_BARS = 100_000  # safety cap to avoid extremely large requests

def _estimate_bars_for_timeframe(tf, months: int = DEFAULT_HISTORY_MONTHS) -> int:
    days = int(months * 30)
    # If MT5 not available or timeframe unknown, assume hourly bars
    if not MT5_AVAILABLE or tf is None:
        return min(days * 24, MAX_BATCH_BARS)
    try:
        if tf == mt5.TIMEFRAME_M1:
            return min(days * 24 * 60, MAX_BATCH_BARS)
        if tf == mt5.TIMEFRAME_M5:
            return min(days * 24 * 12, MAX_BATCH_BARS)
        if tf == mt5.TIMEFRAME_M15:
            return min(days * 24 * 4, MAX_BATCH_BARS)
        if tf == mt5.TIMEFRAME_M30:
            return min(days * 24 * 2, MAX_BATCH_BARS)
        if tf == mt5.TIMEFRAME_H1:
            return min(days * 24, MAX_BATCH_BARS)
        if tf == mt5.TIMEFRAME_H4:
            return min(days * 6, MAX_BATCH_BARS)
        if tf == mt5.TIMEFRAME_D1:
            return min(days, MAX_BATCH_BARS)
        if tf == mt5.TIMEFRAME_W1:
            return min(max(1, days // 7), MAX_BATCH_BARS)
        if tf == mt5.TIMEFRAME_MN1:
            return min(max(1, days // 30), MAX_BATCH_BARS)
    except Exception:
        pass
    # fallback (assume H1)
    return min(days * 24, MAX_BATCH_BARS)

# Final computed batch size
BATCH_BARS = int(_estimate_bars_for_timeframe(TIMEFRAME))
SLEEP_SECONDS = 60 * 15  # run every 15 minutes by default

# Default symbols list; will be overridden by CLI or caller
DEFAULT_SYMBOLS = ['XAUUSD']


def symbol_slug(symbol: str) -> str:
        """Create a filesystem-safe slug for a symbol.
        - Lowercase
        - Replace non-alphanumeric with underscores
        Examples:
            "XAUUSD" -> "xauusd"
            "Crash 1000 Index" -> "crash_1000_index"
            "BTC/USD" -> "btc_usd"
        """
        try:
                return ''.join(ch if ch.isalnum() else '_' for ch in str(symbol)).lower().strip('_')
        except Exception:
                return str(symbol).replace('/', '_').replace(' ', '_').lower()


def ensure_mt5_connected():
    """Initialize MT5 connection using credentials from config.py."""
    if not MT5_AVAILABLE:
        raise RuntimeError("MetaTrader5 package not installed")

    # Initialize MT5
    if not mt5.initialize(MT5_PATH):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")

    # Try login - in many setups this will already be logged in by terminal
    try:
        logged = mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
        if not logged:
            # some MT5 setups return False but still allow data reads; log warning instead
            print(f"MT5 login returned False, check terminal login: {mt5.last_error()}")
    except Exception as e:
        print(f"MT5 login attempt raised: {e}")


def fetch_bars(symbol: str, timeframe, count: int = 500) -> pd.DataFrame:
    """Fetch recent bars and return a pandas DataFrame with OHLCV and time columns."""
    if not MT5_AVAILABLE:
        raise RuntimeError("MetaTrader5 package not installed")

    utc_to = datetime.now(timezone.utc)
    rates = mt5.copy_rates_from(symbol, timeframe, utc_to, count)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No bars returned for {symbol}")

    df = pd.DataFrame(rates)
    # convert time in seconds to pandas datetime and set as index
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=False)
    # Ensure numeric columns are float
    for c in ['open', 'high', 'low', 'close']:
        if c in df.columns:
            df[c] = df[c].astype(float)
    if 'tick_volume' in df.columns:
        df.rename(columns={'tick_volume': 'volume'}, inplace=True)

    # Ensure a 'point' column from MT5 symbol metadata (preferred), fallback to inference
    if 'point' not in df.columns:
        pt = None
        try:
            info = mt5.symbol_info(symbol)
            if info is not None:
                pt = getattr(info, 'trade_tick_size', None) or getattr(info, 'point', None)
        except Exception:
            pt = None
        if pt is None:
            # fallback to decimal inference only if metadata unavailable
            sample = df['close'].iloc[-1]
            decimals = 5
            try:
                s = f"{sample:.8f}"
                if '.' in s:
                    decimals = len(s.rstrip('0').split('.')[-1])
            except Exception:
                pass
            pt = 10 ** -decimals
        try:
            df['point'] = float(pt)
        except Exception:
            df['point'] = pt

    return df


def append_analysis_row(analysis: dict):
    """Append a single-row summary of analysis to CSV."""
    fieldnames = ['timestamp', 'symbol', 'current_price', 'pivot_low', 'pivot_high',
                  'trade_valid', 'trade_type', 'entry', 'stop_loss', 'take_profit',
                  'rr_ratio', 'strong_confluence_count']

    row = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'symbol': analysis.get('symbol', 'UNKNOWN'),
        'current_price': analysis.get('current_price'),
        'pivot_low': analysis.get('pivot_low'),
        'pivot_high': analysis.get('pivot_high'),
        'trade_valid': analysis.get('trade_setup', {}).get('valid', False),
        'trade_type': analysis.get('trade_setup', {}).get('type'),
        'entry': analysis.get('trade_setup', {}).get('entry'),
        'stop_loss': analysis.get('trade_setup', {}).get('stop_loss'),
        'take_profit': analysis.get('trade_setup', {}).get('take_profit'),
        'rr_ratio': analysis.get('trade_setup', {}).get('rr_ratio'),
        'strong_confluence_count': len(analysis.get('strong_confluence_zones', []))
    }

    file_exists = os.path.exists(ANALYSIS_CSV)
    with open(ANALYSIS_CSV, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def append_confluences(confluences: list, analysis_meta: dict):
    """Append strong confluence zone rows to a dedicated CSV per symbol."""
    symbol = analysis_meta.get('symbol', 'UNKNOWN')
    # Use a consistent, filesystem-safe slug for filenames; keep original symbol for data fields
    symbol_safe = symbol_slug(symbol)
    
    # Symbol-specific paths
    confluence_csv = os.path.join(OUTPUT_DIR, f'{symbol_safe}_confluences.csv')
    bars_csv = os.path.join(OUTPUT_DIR, f'{symbol_safe}_bars.csv')
    
    fieldnames = ['timestamp', 'symbol', 'origin', 'fib_pct', 'fib_price',
                  'nearest_s9', 'distance', 's9_degree', 'strength', 'strength_score',
                  'severity', 'side', 'conf_id', 'pivot_low', 'pivot_high', 'current_price']

    def _ensure_confluence_header(path: str, desired_fields: list):
        """Ensure the CSV at path has the desired header. If not, rewrite the file
        preserving existing rows and adding empty values for new columns.
        """
        if not os.path.exists(path):
            return
        try:
            with open(path, 'r', newline='', encoding='utf-8') as rf:
                reader = csv.reader(rf)
                try:
                    existing_header = next(reader)
                except StopIteration:
                    existing_header = []

            # If headers already match exactly, nothing to do
            if existing_header == desired_fields:
                return

            # Read existing rows with existing header and rewrite with desired header
            with open(path, 'r', newline='', encoding='utf-8') as rf:
                old_reader = csv.DictReader(rf, fieldnames=existing_header)
                rows = list(old_reader)

            # Skip the header row if it was included as a data row
            if rows and all(k == v for k, v in zip(existing_header, rows[0].values())):
                rows = rows[1:]

            # Write back with desired header
            with open(path, 'w', newline='', encoding='utf-8') as wf:
                writer = csv.DictWriter(wf, fieldnames=desired_fields)
                writer.writeheader()
                for r in rows:
                    new_row = {k: r.get(k, '') for k in desired_fields}
                    writer.writerow(new_row)
        except Exception:
            # If anything goes wrong, don't block recording; leave file as-is
            return

    # Ensure CSV header matches our expected fields before appending
    _ensure_confluence_header(confluence_csv, fieldnames)
    file_exists = os.path.exists(confluence_csv)
    # Load or initialize confluence index (simple JSON map of conf_id -> last_seen_iso)
    index = {}
    try:
        if os.path.exists(CONFLUENCE_INDEX):
            import json
            with open(CONFLUENCE_INDEX, 'r', encoding='utf-8') as idxf:
                index = json.load(idxf)
    except Exception:
        index = {}
    with open(confluence_csv, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        ts = datetime.now(timezone.utc)
        # compute ATR for severity normalization using real bars when available
        atr = None
        try:
            # Prefer computing ATR from the saved bars CSV (most recent snapshot)
            if os.path.exists(bars_csv):
                bars_df = pd.read_csv(bars_csv, parse_dates=['time'])
                # Ensure required columns present
                if {'high', 'low', 'close'}.issubset(bars_df.columns) and len(bars_df) >= 14:
                    bars_df = bars_df.sort_values('time').reset_index(drop=True)
                    bars_df['prev_close'] = bars_df['close'].shift()
                    tr1 = bars_df['high'] - bars_df['low']
                    tr2 = (bars_df['high'] - bars_df['prev_close']).abs()
                    tr3 = (bars_df['low'] - bars_df['prev_close']).abs()
                    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                    atr_series = tr.rolling(14).mean()
                    atr = float(atr_series.dropna().iloc[-1]) if not atr_series.dropna().empty else None
        except Exception:
            atr = None

        # fallback: crude ATR proxy from analysis_meta price_range
        if atr is None:
            try:
                price_range = analysis_meta.get('price_range')
                if price_range:
                    atr = float(price_range) / 14.0
            except Exception:
                atr = None

        for conf in confluences:
            # Only log strong/perfect confluences
            if conf.get('strength') not in ('Perfect', 'Strong'):
                continue

            # compute conf_id as a short hash of fib_pct + nearest_s9 + pivot_low + pivot_high
            try:
                import hashlib, json
                conf_key = json.dumps([
                    conf.get('fib_pct'),
                    conf.get('nearest_s9'),
                    round(float(analysis_meta.get('pivot_low', 0)), 6),
                    round(float(analysis_meta.get('pivot_high', 0)), 6)
                ], sort_keys=True)
                conf_id = hashlib.sha1(conf_key.encode('utf-8')).hexdigest()
            except Exception:
                conf_id = None

            # Deduplication: skip if seen within TTL
            skip = False
            if conf_id and conf_id in index:
                try:
                    last_seen = datetime.fromisoformat(index[conf_id])
                    age_minutes = (ts - last_seen).total_seconds() / 60.0
                    if age_minutes < CONFLUENCE_TTL_MINUTES:
                        skip = True
                except Exception:
                    pass

            if skip:
                continue

            # compute severity: combine strength_score and distance normalized by ATR
            strength_score = conf.get('strength_score', 0) or 0
            distance = float(conf.get('distance') or 0)
            if atr and atr > 0:
                distance_norm = distance / atr
            else:
                # if no ATR, normalize by a small fixed scale
                distance_norm = distance / max(1.0, float(analysis_meta.get('pivot_high', 1)) * 0.001)

            severity = round(float(strength_score) / (1.0 + distance_norm), 4)

            # determine side relative to current price
            cur_price = analysis_meta.get('current_price')
            side = 'unknown'
            try:
                if cur_price is not None:
                    cur_price_f = float(cur_price)
                    if conf.get('fib_price') is not None:
                        if float(conf.get('fib_price')) >= cur_price_f:
                            side = 'above'
                        else:
                            side = 'below'
            except Exception:
                side = 'unknown'

            row = {
                'timestamp': ts.isoformat(),
                'symbol': analysis_meta.get('symbol', 'UNKNOWN'),
                'origin': conf.get('origin', ''),
                'fib_pct': conf.get('fib_pct'),
                'fib_price': conf.get('fib_price'),
                'nearest_s9': conf.get('nearest_s9'),
                'distance': conf.get('distance'),
                's9_degree': conf.get('s9_degree'),
                'strength': conf.get('strength'),
                'strength_score': strength_score,
                'severity': severity,
                'side': side,
                'conf_id': conf_id,
                'pivot_low': analysis_meta.get('pivot_low'),
                'pivot_high': analysis_meta.get('pivot_high'),
                'current_price': analysis_meta.get('current_price')
            }
            writer.writerow(row)

            # update index
            if conf_id:
                index[conf_id] = ts.isoformat()

    # persist index safely
    try:
        import json
        with open(CONFLUENCE_INDEX, 'w', encoding='utf-8') as idxf:
            json.dump(index, idxf)
    except Exception:
        pass


def _normalize_bars_for_storage(df: pd.DataFrame) -> pd.DataFrame:
    """Return a CSV-friendly bars dataframe with UTC-naive `time` and unique timestamps."""
    if df is None or df.empty:
        return pd.DataFrame(columns=['time'])

    out = df.copy()

    # Ensure `time` is a regular column.
    if 'time' not in out.columns:
        out = out.reset_index()
        if 'time' not in out.columns and len(out.columns) > 0:
            out.rename(columns={out.columns[0]: 'time'}, inplace=True)

    if 'time' not in out.columns:
        return pd.DataFrame(columns=['time'])

    # Normalize time to UTC and store as naive timestamps for backward compatibility.
    out['time'] = pd.to_datetime(out['time'], errors='coerce', utc=True)
    out = out.dropna(subset=['time'])
    out['time'] = out['time'].dt.tz_convert('UTC').dt.tz_localize(None)

    out.sort_values('time', inplace=True)
    out.drop_duplicates(subset=['time'], keep='last', inplace=True)

    preferred = ['time', 'open', 'high', 'low', 'close', 'volume', 'point']
    ordered = [c for c in preferred if c in out.columns]
    ordered.extend([c for c in out.columns if c not in ordered])
    out = out[ordered]
    out.reset_index(drop=True, inplace=True)
    return out


def save_bars_once(df: pd.DataFrame, symbol: str):
    """Upsert raw bars CSV for a symbol on every run (dedupe by `time`)."""
    # store per-symbol bars file to avoid collisions
    symbol_safe = symbol_slug(symbol)
    bars_path = os.path.join(OUTPUT_DIR, f"{symbol_safe}_bars.csv")

    incoming = _normalize_bars_for_storage(df)
    if incoming.empty:
        return bars_path

    existing = pd.DataFrame()
    if os.path.exists(bars_path):
        try:
            existing = pd.read_csv(bars_path, parse_dates=['time'])
            existing = _normalize_bars_for_storage(existing)
        except Exception:
            existing = pd.DataFrame()

    if existing.empty:
        merged = incoming
    else:
        merged = pd.concat([existing, incoming], ignore_index=True, sort=False)
        merged = _normalize_bars_for_storage(merged)

    # Keep a bounded rolling history (about one fetch window by default).
    try:
        keep_rows = max(len(incoming), int(BATCH_BARS))
    except Exception:
        keep_rows = len(incoming)
    if keep_rows > 0 and len(merged) > keep_rows:
        merged = merged.iloc[-keep_rows:].reset_index(drop=True)

    merged.to_csv(bars_path, index=False, date_format='%Y-%m-%d %H:%M:%S')
    return bars_path


from typing import Optional
import json
import requests
try:
    from harmonic_trader import analyze_symbol_live, session_for_utc
except Exception:
    analyze_symbol_live = None
    session_for_utc = None
import config as _cfg

def capture_mt5_chart_screenshot(symbol: str, out_path: str, width: Optional[int] = None, height: Optional[int] = None, timeout_s: int = 6) -> bool:
    """Attempt to capture a chart screenshot using MetaTrader5 API.
    Returns True when file exists at out_path, False otherwise.
    The mt5.chart_screen_shot signature varies by MT5/python build; try a couple of variants.
    """
    if not MT5_AVAILABLE:
        return False
    try:
        # Try simple filename-only call first
        try:
            ok = mt5.chart_screen_shot(out_path)
        except TypeError:
            # Try (symbol, timeframe, filename) variant if available
            try:
                ok = mt5.chart_screen_shot(symbol, TIMEFRAME, out_path)
            except Exception:
                # Last resort: attempt filename-only again and accept whatever it returns
                ok = mt5.chart_screen_shot(out_path)
        
        # Some MT5 builds return True/False, others return None but still create the file.
        # Wait briefly for file to appear.
        waited = 0.0
        poll = 0.25
        while waited < timeout_s:
            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                return True
            time.sleep(poll)
            waited += poll
    except Exception:
        return False
    return os.path.exists(out_path) and os.path.getsize(out_path) > 0


def annotate_screenshot_with_confluences(base_img_path: str, df: pd.DataFrame, analysis: dict, confluences: list, out_path: str) -> str:
    """Open base image (MT5 screenshot) and draw confluence horizontal lines + labels with Pillow.
    Returns path to annotated image (out_path) or None on failure.
    """
    if not PIL_AVAILABLE:
        return None
    try:
        img = Image.open(base_img_path).convert("RGBA")
        w, h = img.size
        draw = ImageDraw.Draw(img)

        # determine price scaling from dataframe (fallback to pivot extremes)
        try:
            prices = pd.concat([df['high'], df['low'], df['close']]).astype(float)
            pmin = float(prices.min())
            pmax = float(prices.max())
            if pmax == pmin:
                pmin -= 1.0
                pmax += 1.0
        except Exception:
            pmin = float(analysis.get('pivot_low', 0)) or 0.0
            pmax = float(analysis.get('pivot_high', pmin + 1)) or (pmin + 1.0)

        def price_to_y(price: float) -> int:
            # map price -> y coordinate (0 top)
            ratio = (price - pmin) / (pmax - pmin)
            # invert so higher prices are toward top of image
            y = int((1.0 - ratio) * (h - 1))
            return max(1, min(h - 2, y))

        # choose a font if available
        try:
            font = ImageFont.truetype("arial.ttf", 14)
            small_font = ImageFont.truetype("arial.ttf", 12)
        except Exception:
            font = ImageFont.load_default()
            small_font = font

        # Header box with symbol/timestamp/pivots
        header_text = f"{analysis.get('symbol', '')}  H1  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        piv_text = f"pivot_low={analysis.get('pivot_low')}  pivot_high={analysis.get('pivot_high')}"
        pad = 8
        
        try:
            tw, th = draw.textsize(header_text, font=font)
            tw2, th2 = draw.textsize(piv_text, font=small_font)
        except AttributeError:
            # For newer PIL versions
            bbox = draw.textbbox((0, 0), header_text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            bbox2 = draw.textbbox((0, 0), piv_text, font=small_font)
            tw2, th2 = bbox2[2] - bbox2[0], bbox2[3] - bbox2[1]
        
        box_w = max(tw, tw2) + pad * 2
        box_h = th + th2 + pad * 2
        # semi-transparent rectangle
        box = Image.new("RGBA", (box_w, box_h), (255, 255, 255, 200))
        img.paste(box, (10, 10), box)

        draw.text((10 + pad, 10 + pad), header_text, fill=(0, 0, 0, 255), font=font)
        draw.text((10 + pad, 10 + pad + th), piv_text, fill=(0, 0, 0, 255), font=small_font)

        # draw each confluence as horizontal line + label at right edge
        for conf in confluences:
            try:
                fp = conf.get('fib_price')
                if fp is None:
                    continue
                fp = float(fp)
                y = price_to_y(fp)
                strength = (conf.get('strength') or '').lower()
                if strength == 'perfect':
                    color = (148, 103, 189, 220)  # purple
                    width = 3
                elif strength == 'strong':
                    color = (255, 127, 14, 200)   # orange
                    width = 2
                else:
                    color = (127, 127, 127, 160)
                    width = 1

                # line
                draw.line([(0, y), (w, y)], fill=color, width=width)

                # label background
                label = f"{conf.get('origin','')} {conf.get('fib_pct')}%  {conf.get('nearest_s9')}  d={conf.get('distance')}"
                try:
                    lw, lh = draw.textsize(label, font=small_font)
                except AttributeError:
                    bbox = draw.textbbox((0, 0), label, font=small_font)
                    lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    
                bx = w - lw - 14
                by = y - (lh // 2)
                rect = Image.new("RGBA", (lw + 8, lh + 4), (255, 255, 255, 220))
                img.paste(rect, (bx - 4, max(0, by - 2)), rect)
                draw.text((bx, by), label, fill=(10, 10, 10, 255), font=small_font)
            except Exception:
                continue

        # save annotated image
        img.save(out_path, format="PNG")
        return out_path
    except Exception:
        return None


def generate_confluence_plot(symbol: str, df: pd.DataFrame, analysis: dict, confluences: list, outdir: str = OUTPUT_DIR):
    """Create a high-quality annotated PNG showing price and confluence zones (matplotlib fallback).
    Returns path to the saved image or None if plotting not available.
    """
    if not MPL_AVAILABLE:
        return None

    try:
        os.makedirs(outdir, exist_ok=True)
        # Prepare time series
        if 'time' in df.columns:
            times = pd.to_datetime(df['time'])
        else:
            # if index is datetime-like
            times = pd.to_datetime(df.index)

        closes = df['close'].astype(float)

        fig, ax = plt.subplots(figsize=(14, 8), dpi=200)
        ax.plot(times, closes, linewidth=1.2, color='#1f77b4', label='Close')

        # pivot lines
        pivot_low = analysis.get('pivot_low')
        pivot_high = analysis.get('pivot_high')
        if pivot_low is not None:
            ax.axhline(float(pivot_low), color='green', linestyle='--', linewidth=1, label='Pivot Low')
        if pivot_high is not None:
            ax.axhline(float(pivot_high), color='red', linestyle='--', linewidth=1, label='Pivot High')

        # annotate confluences as horizontal bands/lines
        for conf in confluences:
            try:
                fp = conf.get('fib_price')
                if fp is None:
                    continue
                fp = float(fp)
                strength = conf.get('strength', '').lower()
                # color by strength
                color = '#9467bd' if strength == 'perfect' else ('#ff7f0e' if strength == 'strong' else '#7f7f7f')
                ax.axhline(fp, color=color, linewidth=1.5, alpha=0.9)
                # label at the right side
                txt = f"{conf.get('fib_pct')}% | {conf.get('nearest_s9')} | {conf.get('distance')}"
                ax.text(times.iloc[-1], fp, f" {txt}", va='center', ha='left', fontsize=8, color=color,
                        bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', pad=1))
            except Exception:
                continue

        # formatting
        ax.set_title(f"{symbol} — H1 confluence zones", fontsize=14)
        ax.set_xlabel("Time (UTC)")
        ax.set_ylabel("Price")
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(mdates.AutoDateLocator()))
        ax.grid(True, linestyle=':', linewidth=0.6, alpha=0.6)
        ax.legend(loc='upper left', fontsize=9)

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        symbol_safe = symbol.replace('/', '_')
        img_path = os.path.join(outdir, f"{symbol_safe}_confluence_{ts}.png")
        fig.tight_layout()
        fig.savefig(img_path, dpi=300, bbox_inches='tight')
        plt.close(fig)
        return img_path
    except Exception:
        return None


def run_once_fetch_and_analyze_for_symbol(symbol: str):
    """Fetch bars, run strategies for a single symbol, append results and generate plot."""
    # Ensure MT5 available
    if MT5_AVAILABLE:
        ensure_mt5_connected()
    else:
        raise RuntimeError("MetaTrader5 not available in this Python environment")

    df = fetch_bars(symbol, TIMEFRAME, BATCH_BARS)

    # Save raw bars once (per-symbol)
    bars_path = save_bars_once(df, symbol)

    # Build DF for strategy usage - keep typical OHLCV
    strat_df = df[['open', 'high', 'low', 'close', 'volume', 'point']].copy()

    # DegreeFactor usage - use low from last BATCH_BARS (default 5 decimals is fine for most instruments)
    # Factors extend from 17.5% to 150% above pivot low in steps
    dfactor = DegreeFactor(user_input="0.175, 0.35, 0.525, 0.7, 0.875, 1.05, 1.225, 1.4, 1.5")
    # pivot low from recent section
    pivot_low = strat_df['low'].min()
    dfactor.calculate_price_lines(low_value=pivot_low)

    # FibonacciSquareOfNine usage - prefer MT5 tick size for point value
    try:
        info = mt5.symbol_info(symbol)
    except Exception:
        info = None
    point_val = None
    if info is not None:
        point_val = getattr(info, 'trade_tick_size', None) or getattr(info, 'point', None)
    if point_val is None:
        try:
            point_val = float(strat_df['point'].iloc[-1])
        except Exception:
            point_val = None
    if point_val is not None:
        try:
            strat_df['point'] = float(point_val)
        except Exception:
            strat_df['point'] = point_val
    fs9 = FibonacciSquareOfNine(point_value=point_val if point_val is not None else strat_df['point'].iloc[-1])
    pivot_high = strat_df['high'].max()

    analysis = fs9.analyze_market(strat_df, pivot_low=pivot_low, pivot_high=pivot_high)
    # attach symbol info and pivot values for meta
    analysis['symbol'] = symbol
    analysis['pivot_low'] = pivot_low
    analysis['pivot_high'] = pivot_high
    analysis['current_price'] = strat_df['close'].iloc[-1] if not strat_df.empty else None

    append_analysis_row(analysis)
    # Log only the already-filtered strong confluence zones from analysis
    strong_confs = analysis.get('strong_confluence_zones', [])
    append_confluences(strong_confs, analysis)

    # Attempt to capture MT5 chart screenshot and annotate it with Pillow (best-effort)
    img_path = None
    try:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        symbol_safe = symbol.replace('/', '_')
        base_img = os.path.join(OUTPUT_DIR, f"{symbol_safe}_mt5_base_{ts}.png")
        annotated_img = os.path.join(OUTPUT_DIR, f"{symbol_safe}_confluence_{ts}.png")

        got = False
        if MT5_AVAILABLE:
            got = capture_mt5_chart_screenshot(symbol, base_img)
        # If MT5 screenshot succeeded and PIL available, annotate
        if got and PIL_AVAILABLE:
            ann = annotate_screenshot_with_confluences(base_img, df, analysis, strong_confs, annotated_img)
            if ann:
                img_path = ann
        else:
            # Fallback: if no MT5 screenshot, try previous matplotlib generator (if available)
            img_path = generate_confluence_plot(symbol, df, analysis, strong_confs, outdir=OUTPUT_DIR) if MPL_AVAILABLE else None
        if img_path:
            analysis['plot_image'] = img_path
    except Exception:
        # silent fallback
        pass

    # Optional: call candlestick reporter (conservative; disabled by default in config)
    try:
        import config as _cfg
        if getattr(_cfg, 'CANDLE_REPORTS_ENABLED', False):
            try:
                from candlesticks.candlestick_signals import run_report_for_bars
                chat = _cfg.TELEGRAM_GROUP_ID or _cfg.TELEGRAM_ADMIN_ID
                token = _cfg.TELEGRAM_BOT_TOKEN
                # First do a dry-run to inspect the computed signal without sending
                preview = run_report_for_bars(bars_path, chat, token,
                                              persist_path=getattr(_cfg, 'CANDLES_DEDUPE_PERSIST', None),
                                              min_seconds=getattr(_cfg, 'CANDLES_DEDUPE_MIN_SECONDS', 3600),
                                              min_score_delta=getattr(_cfg, 'CANDLES_DEDUPE_MIN_SCORE_DELTA', 0.5),
                                              dry_run=True)
                sig = preview.get('signal', {}) if isinstance(preview, dict) else {}
                action = sig.get('signal') if isinstance(sig, dict) else None
                # If the preview suggests a BUY or SELL, force-send to ensure trade signals are delivered
                if action in ('buy', 'sell'):
                    resp = run_report_for_bars(bars_path, chat, token,
                                               persist_path=getattr(_cfg, 'CANDLES_DEDUPE_PERSIST', None),
                                               min_seconds=getattr(_cfg, 'CANDLES_DEDUPE_MIN_SECONDS', 3600),
                                               min_score_delta=getattr(_cfg, 'CANDLES_DEDUPE_MIN_SCORE_DELTA', 0.5),
                                               force=True, dry_run=False)
                else:
                    # For neutral signals, perform a normal send (respects dedupe)
                    resp = run_report_for_bars(bars_path, chat, token,
                                               persist_path=getattr(_cfg, 'CANDLES_DEDUPE_PERSIST', None),
                                               min_seconds=getattr(_cfg, 'CANDLES_DEDUPE_MIN_SECONDS', 3600),
                                               min_score_delta=getattr(_cfg, 'CANDLES_DEDUPE_MIN_SCORE_DELTA', 0.5),
                                               dry_run=False)
                print(f"Candlestick report result for {symbol}: {resp}")
            except Exception as e:
                print(f"Candlestick reporter error for {symbol}: {e}")
    except Exception:
        pass

    # Optional: candlestick auto-trade (mechanical gates; disabled by default in config)
    try:
        import config as _cfg
        if getattr(_cfg, "CANDLE_AUTOTRADE_ENABLED", False):
            try:
                from candlesticks.candlestick_autotrade import run_autotrade_for_symbol
                res = run_autotrade_for_symbol(
                    symbol=symbol,
                    bars_path=bars_path,
                    mt5=mt5,
                    cfg=_cfg,
                    outputs_dir=OUTPUT_DIR,
                )
                print(f"Candlestick autotrade result for {symbol}: {res.get('status')}")
            except Exception as e:
                print(f"Candlestick autotrade error for {symbol}: {e}")
    except Exception:
        pass

    # Optional: run harmonic analysis, Telegram signal, and autotrade
    try:
        if getattr(_cfg, 'HARMONIC_SIGNALS_ENABLED', False) and analyze_symbol_live is not None:
            session = os.getenv('HARMONIC_SESSION', getattr(_cfg, 'HARMONIC_SESSION', 'auto'))
            hres = analyze_symbol_live(symbol, timeframe='H1', count=BATCH_BARS, harmonics=None, session=session)

            # Rich Telegram signal (HTML formatter + JSONL persist)
            try:
                from harmonic_signals import run_harmonic_signal_for_symbol
                run_harmonic_signal_for_symbol(symbol, hres, _cfg, OUTPUT_DIR)
            except Exception as e:
                print(f"Harmonic signal error for {symbol}: {e}")

            # Autotrade evaluation + execution
            try:
                if getattr(_cfg, 'HARMONIC_AUTOTRADE_ENABLED', False):
                    from harmonic_autotrade import run_harmonic_autotrade_for_symbol
                    at_res = run_harmonic_autotrade_for_symbol(symbol, hres, mt5, _cfg, OUTPUT_DIR)
                    print(f"Harmonic autotrade result for {symbol}: {at_res.get('status')}")
            except Exception as e:
                print(f"Harmonic autotrade error for {symbol}: {e}")
    except Exception:
        pass

    # Shutdown mt5 connection if we initialized it
    try:
        if MT5_AVAILABLE:
            mt5.shutdown()
    except Exception:
        pass

    return analysis


def run_once_for_symbols(symbols: list):
    """Run analysis once for a list of symbols and return a dict of results."""
    results = {}
    for s in symbols:
        try:
            results[s] = run_once_fetch_and_analyze_for_symbol(s)
        except Exception as e:
            results[s] = {'error': str(e)}
    return results


def run_once_fetch_and_analyze():
    """Legacy function for backward compatibility - uses DEFAULT_SYMBOLS."""
    results = run_once_for_symbols(DEFAULT_SYMBOLS)
    # Return first result for backward compatibility
    if results:
        return list(results.values())[0]
    return {}


def background_loop(run_once_fn, sleep_seconds=SLEEP_SECONDS):
    """Run the `run_once_fn` periodically in a resilient loop."""
    print(f"Starting background collector, writing to {ANALYSIS_CSV}")

    while True:
        try:
            analysis = run_once_fn()
            # analysis may be per-symbol dict
            if isinstance(analysis, dict):
                for sym, res in analysis.items():
                    cp = res.get('current_price') if isinstance(res, dict) else None
                    print(f"[{datetime.now(timezone.utc).isoformat()}] Collected analysis for {sym}: price={cp}")
            else:
                print(f"[{datetime.now(timezone.utc).isoformat()}] Collected analysis: {analysis}")
        except Exception as e:
            print(f"Error during collection: {e}")
        time.sleep(sleep_seconds)


if __name__ == '__main__':
    # For running interactively; keep loop off by default to avoid long runs in tests
    import argparse

    parser = argparse.ArgumentParser(description='MT5 background collector (H1 only) for symbol(s)')
    parser.add_argument('--once', action='store_true', help='Run only once and exit')
    parser.add_argument('--interval', type=int, default=SLEEP_SECONDS, help='Interval in seconds')
    parser.add_argument('--symbols', type=str, help='Comma-separated symbols to analyze (e.g. XAUUSD,EURUSD)')
    args = parser.parse_args()

    # Determine symbols to run
    if args.symbols:
        # Preserve original case and spaces within symbol names
        # Support comma-separated list, allowing quotes around items if user prefers
        raw = args.symbols
        # Split by comma only; keep inner spaces
        parts = [p.strip() for p in raw.split(',') if p.strip()]
        # Strip optional surrounding single/double quotes without changing inner spaces/case
        symbols = [p[1:-1] if (len(p) >= 2 and ((p.startswith('"') and p.endswith('"')) or (p.startswith("'") and p.endswith("'")))) else p for p in parts]
    else:
        # interactive prompt if not provided
        try:
            usr = input(f"Enter symbol(s) to analyze (comma-separated) [default: {','.join(DEFAULT_SYMBOLS)}]: ").strip()
            if usr:
                parts = [s.strip() for s in usr.split(',') if s.strip()]
                symbols = [p[1:-1] if (len(p) >= 2 and ((p.startswith('"') and p.endswith('"')) or (p.startswith("'") and p.endswith("'")))) else p for p in parts]
            else:
                symbols = DEFAULT_SYMBOLS
        except Exception:
            symbols = DEFAULT_SYMBOLS

    if args.once:
        try:
            out = run_once_for_symbols(symbols)
            print('Done. Summary:', out)
        except Exception as e:
            print('Run failed:', e)
    else:
        # wrap the run_once function for the loop
        loop_fn = lambda: run_once_for_symbols(symbols)
        background_loop(loop_fn, sleep_seconds=args.interval)
