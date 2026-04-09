"""
Harmonic trading helper implementing the core pieces from harmonic_trading.md
Uses ancient-science-of-numbers (digital root helpers) when available.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List

try:
    # package provides digital root and related utilities
    from ancient_science_of_numbers import digital_root as ason_digital_root
except Exception:
    def ason_digital_root(n: int) -> int:
        # fallback simple digital root
        if n == 0:
            return 0
        return 1 + (abs(n) - 1) % 9

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None

import pandas as pd
import os
import json
from datetime import datetime, timezone, timedelta



def digital_root_value(n: int) -> int:
    return ason_digital_root(int(n))


def price_phase(price_move: float) -> int:
    try:
        return digital_root_value(round(price_move))
    except Exception:
        return digital_root_value(int(price_move))


def time_phase(bars_elapsed: int) -> int:
    return digital_root_value(int(bars_elapsed))


def harmonic_square(price_move: float, bars_elapsed: int, harmonic_hit: bool) -> bool:
    if not harmonic_hit:
        return False
    return price_phase(price_move) == time_phase(bars_elapsed)


def volatility_phase(current_atr: float, atr_mean: float) -> str:
    if atr_mean is None or atr_mean == 0:
        return "UNKNOWN"
    ratio = float(current_atr) / float(atr_mean)
    if ratio < 0.85:
        return "COMPRESSION"
    elif ratio <= 1.15:
        return "NORMAL"
    elif ratio <= 1.45:
        return "EXPANSION"
    else:
        return "EXTREME"


SESSION_WEIGHTS = {
    "ASIA": 0.7,
    "LONDON": 1.0,
    "NEW_YORK": 1.2,
    "DEAD_ZONE": 0.5,
}


def weighted_resonance(resonance_strength: str, session: str, cfg=None) -> float:
    """Compute weighted resonance score based on strength and trading session.
    Uses config defaults if cfg not provided.
    """
    if cfg is None:
        try:
            import config as cfg
        except Exception:
            cfg = None
    
    # Use config values if available, else fallback to hardcoded
    strong = getattr(cfg, 'HARMONIC_RESONANCE_STRONG', 1.0) if cfg else 1.0
    moderate = getattr(cfg, 'HARMONIC_RESONANCE_MODERATE', 0.6) if cfg else 0.6
    weak = getattr(cfg, 'HARMONIC_RESONANCE_WEAK', 0.2) if cfg else 0.2
    
    base = {"STRONG": strong, "MODERATE": moderate, "WEAK": weak}.get(resonance_strength.upper(), 0.0)
    return base * SESSION_WEIGHTS.get(session.upper(), 1.0)


def signal_gate(harmonic_hit: bool, squared: bool, vol_phase: str, weighted_score: float, confirmations: int, cfg=None) -> bool:
    """Gate harmonic signals. 
    
    If HARMONIC_REQUIRE_SQUARED is True, squared is required.
    If False, squared is used as a damping factor instead.
    """
    if cfg is None:
        try:
            import config as cfg
        except Exception:
            cfg = None
    
    require_squared = getattr(cfg, 'HARMONIC_REQUIRE_SQUARED', False) if cfg else False
    squared_damping = getattr(cfg, 'HARMONIC_SQUARED_DAMPING', 0.8) if cfg else 0.8
    min_score = getattr(cfg, 'HARMONIC_WEIGHTED_SCORE_MIN', 0.7) if cfg else 0.7
    min_confirmations = getattr(cfg, 'HARMONIC_MIN_CONFIRMATIONS', 1) if cfg else 1
    
    # Always require harmonic_hit
    allow_extreme = getattr(cfg, 'HARMONIC_ALLOW_EXTREME', False) if cfg else False
    if not harmonic_hit:
        return False
    # Block EXTREME volatility unless explicitly allowed by config
    if vol_phase == "EXTREME" and not allow_extreme:
        return False
    
    # If squared is required, enforce it
    if require_squared and not squared:
        return False
    
    # Apply weighted_score threshold (possibly with squared damping)
    if not squared and not require_squared:
        # Apply damping if squared is False but not required
        weighted_score *= squared_damping
    
    return weighted_score >= min_score and confirmations >= min_confirmations


def nearest_harmonic_level(close: float, harmonic_levels: List[dict]) -> Optional[dict]:
    """Return nearest harmonic level dict to close, or None."""
    if not harmonic_levels:
        return None
    try:
        return min(
            harmonic_levels,
            key=lambda lvl: abs(float(lvl.get('level', 0.0)) - float(close)),
        )
    except Exception:
        return None


def build_harmonic_zone(level: Optional[dict], atr: Optional[float], point: float, atr_mult: float) -> dict:
    """Build zone boundaries around a harmonic level."""
    if not level:
        return {'zone_low': None, 'zone_mid': None, 'zone_high': None, 'zone_half_width': None}
    try:
        level_price = float(level.get('level', 0.0))
        level_tol = float(level.get('tolerance', 0.0))
        atr_half = float(atr or 0.0) * float(atr_mult)
        zone_half = max(level_tol, atr_half, float(point or 0.0))
        return {
            'zone_low': level_price - zone_half,
            'zone_mid': level_price,
            'zone_high': level_price + zone_half,
            'zone_half_width': zone_half,
        }
    except Exception:
        return {'zone_low': None, 'zone_mid': None, 'zone_high': None, 'zone_half_width': None}


def is_downtrend(df: pd.DataFrame) -> bool:
    """Downtrend when SMA50 < SMA200; fallback to negative SMA50 slope."""
    try:
        if len(df) >= 200:
            sma50 = df['close'].rolling(50).mean().iloc[-1]
            sma200 = df['close'].rolling(200).mean().iloc[-1]
            if pd.notna(sma50) and pd.notna(sma200):
                return bool(sma50 < sma200)
        sma50_series = df['close'].rolling(50).mean().dropna()
        if len(sma50_series) >= 10:
            slope = float(sma50_series.iloc[-1] - sma50_series.iloc[-10])
            return slope < 0
    except Exception:
        pass
    return False


def volume_confirmed(resonance_strength: str, min_level: str = "MODERATE") -> bool:
    """Return True when resonance_strength meets or exceeds min_level."""
    rank = {"WEAK": 0, "MODERATE": 1, "STRONG": 2}
    try:
        rs = rank.get(str(resonance_strength or "").upper(), 0)
        ml = rank.get(str(min_level or "MODERATE").upper(), 1)
        return rs >= ml
    except Exception:
        return False


def detect_buy_acceptance(candle: dict, zone: dict) -> bool:
    """Body-above-zone acceptance."""
    try:
        z_hi = zone.get('zone_high')
        if z_hi is None:
            return False
        o = float(candle['open'])
        c = float(candle['close'])
        return bool(c > z_hi and c > o and o <= z_hi)
    except Exception:
        return False


def detect_sell_rejection(candle: dict, zone: dict, wick_ratio_min: float = 1.2) -> bool:
    """Upper-wick rejection with bearish failure below zone midline."""
    try:
        z_mid = zone.get('zone_mid')
        z_hi = zone.get('zone_high')
        if z_mid is None or z_hi is None:
            return False
        o = float(candle['open'])
        h = float(candle['high'])
        c = float(candle['close'])
        body = abs(c - o)
        if body <= 0:
            return False
        upper_wick = h - max(o, c)
        return bool(
            upper_wick >= float(wick_ratio_min) * body
            and h >= z_hi
            and c < z_mid
            and c < o
        )
    except Exception:
        return False


def detect_sell_bearish_acceptance_downtrend(candle: dict, zone: dict, downtrend: bool) -> bool:
    """Bearish acceptance below zone in downtrend."""
    try:
        z_lo = zone.get('zone_low')
        if z_lo is None or not downtrend:
            return False
        o = float(candle['open'])
        c = float(candle['close'])
        return bool(c < o and c < z_lo)
    except Exception:
        return False


def compute_elapsed_bar_anchor(df: pd.DataFrame, lookback: int = 20) -> dict:
    """Compute a simple impulse anchor for time/price squaring.

    Returns:
      anchor_idx: int
      anchor_price: float
      anchor_time: str|None
      anchor_kind: str
      bars_elapsed: int
    """
    try:
        n = int(len(df))
        if n <= 1:
            return {
                'anchor_idx': 0,
                'anchor_price': float(df['close'].iloc[-1]) if n == 1 else 0.0,
                'anchor_time': str(df['time'].iloc[-1]) if n == 1 and 'time' in df else None,
                'anchor_kind': 'fallback',
                'bars_elapsed': 1,
            }

        lb = int(lookback) if int(lookback) > 0 else 20
        lb = min(lb, n - 1)
        start = max(0, n - 1 - lb)

        # Direction bias: use SMA50 slope when possible; fallback to 10-bar delta.
        direction = 'UP'
        try:
            sma50 = df['close'].rolling(50).mean().dropna()
            if len(sma50) >= 10:
                slope = float(sma50.iloc[-1] - sma50.iloc[-10])
                direction = 'UP' if slope >= 0 else 'DOWN'
            else:
                k = min(10, n - 1)
                direction = 'UP' if float(df['close'].iloc[-1] - df['close'].iloc[-1 - k]) >= 0 else 'DOWN'
        except Exception:
            pass

        anchor_idx = start
        anchor_price = float(df['close'].iloc[start])
        anchor_kind = 'fallback'

        hi = df['high']
        lo = df['low']
        # Search last swing extreme in the lookback window (simple 1-bar fractal).
        if direction == 'UP':
            found = False
            for i in range(n - 2, max(start, 1), -1):
                try:
                    if float(lo.iloc[i]) < float(lo.iloc[i - 1]) and float(lo.iloc[i]) <= float(lo.iloc[i + 1]):
                        anchor_idx = i
                        anchor_price = float(lo.iloc[i])
                        anchor_kind = 'swing_low'
                        found = True
                        break
                except Exception:
                    continue
            if not found:
                try:
                    sub = lo.iloc[start:n - 1]
                    anchor_idx = int(sub.idxmin())
                    anchor_price = float(lo.iloc[anchor_idx])
                    anchor_kind = 'range_low'
                except Exception:
                    pass
        else:
            found = False
            for i in range(n - 2, max(start, 1), -1):
                try:
                    if float(hi.iloc[i]) > float(hi.iloc[i - 1]) and float(hi.iloc[i]) >= float(hi.iloc[i + 1]):
                        anchor_idx = i
                        anchor_price = float(hi.iloc[i])
                        anchor_kind = 'swing_high'
                        found = True
                        break
                except Exception:
                    continue
            if not found:
                try:
                    sub = hi.iloc[start:n - 1]
                    anchor_idx = int(sub.idxmax())
                    anchor_price = float(hi.iloc[anchor_idx])
                    anchor_kind = 'range_high'
                except Exception:
                    pass

        bars_elapsed = (n - 1) - int(anchor_idx)
        if bars_elapsed <= 0:
            bars_elapsed = 1

        anchor_time = None
        try:
            if 'time' in df.columns:
                anchor_time = str(df['time'].iloc[int(anchor_idx)])
        except Exception:
            anchor_time = None

        return {
            'anchor_idx': int(anchor_idx),
            'anchor_price': float(anchor_price),
            'anchor_time': anchor_time,
            'anchor_kind': str(anchor_kind),
            'bars_elapsed': int(bars_elapsed),
        }
    except Exception:
        return {'anchor_idx': 0, 'anchor_price': 0.0, 'anchor_time': None, 'anchor_kind': 'fallback', 'bars_elapsed': 1}


def generate_signal(context: Dict[str, Any], cfg=None) -> Optional[str]:
    if cfg is None:
        try:
            import config as cfg
        except Exception:
            cfg = None
    gates = context.get("gates", {})
    if not signal_gate(
        gates.get("harmonic_hit", False),
        gates.get("squared", False),
        gates.get("vol_phase", "UNKNOWN"),
        gates.get("weighted_score", 0.0),
        gates.get("confirmations", 0),
        cfg=cfg,
    ):
        return None

    use_v2 = getattr(cfg, 'HARMONIC_SPEC_V2_ENABLED', False) if cfg else False
    if use_v2:
        meta = context.get('meta', {}) or {}
        structure = context.get('structure', {}) or {}
        regime = str(meta.get('regime', 'UNKNOWN')).upper()
        block_unknown = getattr(cfg, 'HARMONIC_BLOCK_UNKNOWN_REGIME', True) if cfg else True
        if block_unknown and regime == 'UNKNOWN':
            return None

        if not bool(structure.get('volume_confirmed', False)):
            return None

        buy_acceptance = bool(structure.get('buy_acceptance', False))
        sell_rejection = bool(structure.get('sell_rejection', False))
        sell_bear_acceptance = bool(structure.get('sell_bearish_acceptance_downtrend', False))

        buy_allowed = regime in ('TRENDING', 'EXPANSION')
        sell_allowed = (regime == 'BALANCED' and sell_rejection) or sell_bear_acceptance

        if buy_allowed and buy_acceptance:
            return "BUY"
        if sell_allowed and (sell_rejection or sell_bear_acceptance):
            return "SELL"
        return None

    if context.get("acceptance"):
        return "BUY"
    if context.get("rejection"):
        return "SELL"
    return None


# --- New: Heatmap persistence and stress estimation ---
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'outputs')
HEATMAP_PATH = os.path.join(OUTPUT_DIR, 'harmonic_heatmap.json')


def _load_heatmap() -> dict:
    try:
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR, exist_ok=True)
        if os.path.exists(HEATMAP_PATH):
            with open(HEATMAP_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_heatmap(hm: dict):
    try:
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(HEATMAP_PATH, 'w', encoding='utf-8') as f:
            json.dump(hm, f, default=str)
    except Exception:
        pass


def record_resonance_event(symbol: str, price: float, window_days: int = 30):
    hm = _load_heatmap()
    sym = hm.get(symbol, {})
    events = sym.get('events', [])
    events.append({'price': float(price), 'ts': datetime.now(timezone.utc).isoformat()})
    # prune old events
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    events = [e for e in events if datetime.fromisoformat(e['ts']) >= cutoff]
    sym['events'] = events
    hm[symbol] = sym
    _save_heatmap(hm)


def stress_level_for_symbol(symbol: str, bucket_size: float = 0.5, window_days: int = 30):
    """Return LOW/MODERATE/HIGH based on counts of resonance events near latest price.
    bucket_size is an approximate price bucket (in price units) to collapse similar events.
    """
    hm = _load_heatmap()
    sym = hm.get(symbol, {})
    events = sym.get('events', [])
    if not events:
        return 'LOW'
    # count events per rounded bucket
    counts = {}
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    for e in events:
        try:
            ts = datetime.fromisoformat(e['ts'])
            if ts < cutoff:
                continue
            p = float(e.get('price', 0.0))
            b = round(p / bucket_size) * bucket_size
            counts[b] = counts.get(b, 0) + 1
        except Exception:
            continue
    if not counts:
        return 'LOW'
    maxc = max(counts.values())
    if maxc >= 5:
        return 'HIGH'
    if maxc >= 3:
        return 'MODERATE'
    return 'LOW'


# --- Market regime classifier ---
def classify_regime(df: pd.DataFrame) -> str:
    """Return one of: COMPRESSION, NORMAL, EXPANSION, EXTREME, TRENDING, BALANCED, UNKNOWN
    Heuristic combining ATR ratio and SMA slope.
    """
    try:
        if len(df) < 30:
            return 'UNKNOWN'
        atr = compute_atr(df, period=14)
        # compute historical mean ATR over 50 bars
        try:
            atr_series = []
            if 'high' in df and 'low' in df and 'close' in df:
                prev_close = df['close'].shift()
                tr = pd.concat([(df['high'] - df['low']), (df['high'] - prev_close).abs(), (df['low'] - prev_close).abs()], axis=1).max(axis=1)
                atr_series = tr.rolling(14).mean()
            atr_mean = float(atr_series.dropna().iloc[-14:].mean()) if len(atr_series.dropna()) >= 14 else (atr or 0.0)
        except Exception:
            atr_mean = atr or 0.0

        # ATR-based phases
        if atr_mean == 0 or atr is None:
            atr_ratio = 1.0
        else:
            atr_ratio = (atr or 0.0) / atr_mean
        if atr_ratio < 0.85:
            vol_phase = 'COMPRESSION'
        elif atr_ratio <= 1.15:
            vol_phase = 'NORMAL'
        elif atr_ratio <= 1.45:
            vol_phase = 'EXPANSION'
        else:
            vol_phase = 'EXTREME'

        # Detect trend using SMA50 vs SMA200 when available
        try:
            sma50 = df['close'].rolling(50).mean().iloc[-1]
            sma200 = df['close'].rolling(200).mean().iloc[-1] if len(df) >= 200 else None
            if sma200 is not None:
                if sma50 > sma200:
                    trend = True
                else:
                    trend = False
            else:
                # fallback: slope of sma50 over last 10 bars
                sma50_series = df['close'].rolling(50).mean()
                if len(sma50_series.dropna()) >= 10:
                    slope = sma50_series.dropna().iloc[-1] - sma50_series.dropna().iloc[-10]
                    trend = slope > 0
                else:
                    trend = False
        except Exception:
            trend = False

        if vol_phase == 'EXTREME':
            return 'EXPANSION'
        if trend:
            return 'TRENDING'
        # otherwise use vol_phase mapping
        if vol_phase in ('COMPRESSION', 'NORMAL', 'EXPANSION'):
            # Map expansion to EXPANSION, normal -> BALANCED
            if vol_phase == 'NORMAL':
                return 'BALANCED'
            return vol_phase
        return 'UNKNOWN'
    except Exception:
        return 'UNKNOWN'


def session_for_utc(dt: Optional[datetime] = None) -> str:
    """Heuristic session detector based on UTC hour with env var override.
    
    Returns one of: 'ASIA', 'LONDON', 'NEW_YORK', 'DEAD_ZONE'.
    
    Session windows (UTC):
      ASIA:      21:00 - 06:59
      LONDON:    07:00 - 12:59
      NEW_YORK:  13:00 - 16:59
      DEAD_ZONE: 17:00 - 20:59
    """
    # Check for env var override first
    try:
        import os
        override = os.getenv('HARMONIC_SESSION')
        if override and override.upper() in ('ASIA', 'LONDON', 'NEW_YORK', 'DEAD_ZONE'):
            return override.upper()
    except Exception:
        pass
    
    try:
        if dt is None:
            dt = datetime.now(timezone.utc)
        if getattr(dt, 'tzinfo', None) is not None:
            dt = dt.astimezone(timezone.utc)
        h = int(dt.hour)
        if h >= 21 or h < 7:      # 21:00-23:59 and 00:00-06:59
            return 'ASIA'
        if 7 <= h < 13:           # 07:00-12:59
            return 'LONDON'
        if 13 <= h < 17:          # 13:00-16:59
            return 'NEW_YORK'
        return 'DEAD_ZONE'        # 17:00-20:59
    except Exception:
        return 'NEW_YORK'


# --- MT5 / Bars Integration ---
def fetch_bars_mt5(symbol: str, timeframe: str = "H1", count: int = 500) -> pd.DataFrame:
    """Fetch bars from MT5 and return a DataFrame with time/open/high/low/close/volume/point."""
    if mt5 is None:
        raise RuntimeError("MetaTrader5 package not available")
    # map common timeframe labels
    tf_map = {
        "M1": getattr(mt5, 'TIMEFRAME_M1', None),
        "M5": getattr(mt5, 'TIMEFRAME_M5', None),
        "M15": getattr(mt5, 'TIMEFRAME_M15', None),
        "M30": getattr(mt5, 'TIMEFRAME_M30', None),
        "H1": getattr(mt5, 'TIMEFRAME_H1', None),
        "H4": getattr(mt5, 'TIMEFRAME_H4', None),
        "D1": getattr(mt5, 'TIMEFRAME_D1', None),
    }
    tf = tf_map.get(timeframe.upper())
    if tf is None:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    utc_to = pd.Timestamp.now(tz='UTC').to_pydatetime()
    rates = mt5.copy_rates_from(symbol, tf, utc_to, count)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No bars for {symbol} {timeframe}")
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    for c in ['open', 'high', 'low', 'close']:
        df[c] = df[c].astype(float)
    if 'tick_volume' in df.columns:
        df.rename(columns={'tick_volume': 'volume'}, inplace=True)
    if 'point' not in df.columns:
        # best-effort point/digits
        try:
            info = mt5.symbol_info(symbol)
            pt = getattr(info, 'point', None)
        except Exception:
            pt = 0.01
        df['point'] = pt
    return df.reset_index(drop=True)


def compute_atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    if len(df) < period + 1:
        return None
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift()
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    try:
        return float(atr)
    except Exception:
        return None


def load_market_harmonics(path: Optional[str] = None) -> dict:
    """Load market harmonics JSON from docs/data/market_harmonics.json by default."""
    try:
        if path is None:
            path = os.path.join(os.path.dirname(__file__), 'docs', 'data', 'market_harmonics.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def compute_harmonic_levels(symbol: str, ref_price: float, base_units: List[float], atr: Optional[float], point: float,
                            multiples: List[int] = (1, 2, 3), tol_frac: float = 0.5) -> List[dict]:
    """Compute price levels from harmonic base units and multiples.

    - ref_price: reference price (e.g., current close or pivot)
    - base_units: list of integer harmonic units (from market_harmonics)
    - atr: current ATR in price units
    - point: instrument point size
    - multiples: list of integer multiples to include
    - tol_frac: fraction of ATR to use as tolerance (fallback to point)
    """
    levels = []
    try:
        tol = max(point or 1e-6, (atr or 0.0) * tol_frac)
        scale = float(point or 1.0)
        for u in base_units:
            for m in multiples:
                offset = float(u) * float(m) * scale
                up = float(ref_price) + offset
                dn = float(ref_price) - offset
                levels.append({'level': up, 'harmonic': f"{u}x{m}", 'tolerance': tol})
                levels.append({'level': dn, 'harmonic': f"-{u}x{m}", 'tolerance': tol})
        # sort by distance from ref_price
        levels.sort(key=lambda x: abs(x['level'] - float(ref_price)))
    except Exception:
        pass
    return levels


def compute_multiples_tp_sl(
    symbol: str,
    side: str,
    entry: float,
    atr: float,
    point: float,
    base_harmonics: List[float],
    common_multiples: List[float],
    k_atr: float = 0.25,
) -> Dict[str, Any]:
    """Compute SL + multi-level TP ladder from harmonic multiples.

    Risk floor: risk = max(max(base_harmonics) * point, k_atr * ATR)
    Scaling:    scale = ceil(risk / (min(common_multiples) * point))
    TP ladder:  tp_i  = entry ± common_multiples[i] * scale * point

    Returns dict with: entry, sl, risk, scale, tp_levels, rr_levels,
    be_trigger_0618.
    """
    import math as _m
    try:
        side_u = str(side).upper()
        entry_f = float(entry)
        atr_f = float(atr) if atr else 0.0
        point_f = float(point) if point else 1e-6

        structural_risk = max(float(h) for h in base_harmonics) * point_f
        atr_floor = k_atr * atr_f
        risk = max(structural_risk, atr_floor)
        if risk <= 0:
            risk = atr_f * 0.25 or point_f

        if side_u in ('BUY', 'LONG'):
            sl = round(entry_f - risk, 8)
        else:
            sl = round(entry_f + risk, 8)

        raw_step = min(float(m) for m in common_multiples) * point_f
        if raw_step <= 0:
            raw_step = point_f
        scale = max(1, _m.ceil(risk / raw_step))

        tp_levels = []
        rr_levels = []
        for mult in sorted(float(m) for m in common_multiples):
            offset = mult * scale * point_f
            if side_u in ('BUY', 'LONG'):
                tp = round(entry_f + offset, 8)
            else:
                tp = round(entry_f - offset, 8)
            tp_levels.append(tp)
            rr = round(abs(tp - entry_f) / risk, 4) if risk > 0 else 0.0
            rr_levels.append(rr)

        be_offset = 0.618 * risk
        if side_u in ('BUY', 'LONG'):
            be_trigger = round(entry_f + be_offset, 8)
        else:
            be_trigger = round(entry_f - be_offset, 8)

        return {
            'symbol': symbol,
            'side': side_u,
            'entry': entry_f,
            'sl': sl,
            'risk': round(risk, 8),
            'scale': scale,
            'tp_levels': tp_levels,
            'rr_levels': rr_levels,
            'be_trigger_0618': be_trigger,
            'base_harmonics': list(base_harmonics),
            'common_multiples': list(common_multiples),
            'k_atr': k_atr,
            'point': point_f,
        }
    except Exception:
        return {}


def get_harmonic_trade_setup(
    symbol: str,
    side: str,
    entry: float,
    atr: float,
    point: float,
    k_atr: float = 0.25,
) -> Dict[str, Any]:
    """Load harmonics for *symbol* from market_harmonics.json and compute TP/SL.

    Returns the output of compute_multiples_tp_sl or {} if no harmonics found.
    """
    mh = load_market_harmonics()
    # try exact key, then uppercase strip
    key = symbol.replace('/', '').upper()
    entry_data = mh.get(key) or mh.get(symbol) or mh.get(symbol.upper())
    # fallback: try common MT5 aliases (e.g. US500 -> US SP 500)
    if not entry_data:
        _aliases = {
            'US500': 'US SP 500', 'USTEC': 'US Tech 100', 'USTEC100': 'US Tech 100',
            'US30': 'Wall Street 30', 'NAS100': 'US Tech 100', 'SP500': 'US SP 500',
        }
        mapped = _aliases.get(key)
        if mapped:
            entry_data = mh.get(mapped)
    if not entry_data:
        return {}
    base = entry_data.get('base_harmonics', [])
    multiples = entry_data.get('common_multiples', [])
    if not base or not multiples:
        return {}
    return compute_multiples_tp_sl(symbol, side, entry, atr, point, base, multiples, k_atr=k_atr)


def analyze_symbol_live(symbol: str, timeframe: str = 'H1', count: int = 500, harmonics: Optional[list] = None,
                        session: str = 'NEW_YORK') -> Dict[str, Any]:
    """Fetch recent bars for `symbol` and produce a signal analysis dict.

    If `session=='auto'`, the session will be detected from current UTC time.
    """
    try:
        import config as cfg_mod
    except Exception:
        cfg_mod = None
    # allow auto-detection of session (env override > config override > UTC windows)
    if isinstance(session, str) and session.lower() == 'auto':
        try:
            env_override = os.getenv('HARMONIC_SESSION')
            if env_override and env_override.upper() in ('ASIA', 'LONDON', 'NEW_YORK', 'DEAD_ZONE'):
                session = env_override.upper()
            else:
                cfg_override = getattr(cfg_mod, 'HARMONIC_SESSION', None) if cfg_mod else None
                if cfg_override and str(cfg_override).upper() in ('ASIA', 'LONDON', 'NEW_YORK', 'DEAD_ZONE') and str(cfg_override).lower() != 'auto':
                    session = str(cfg_override).upper()
                else:
                    session = session_for_utc()
        except Exception:
            session = session_for_utc()
    df = fetch_bars_mt5(symbol, timeframe, count)
    atr = compute_atr(df)
    # mean ATR over previous window (use 50 periods as baseline)
    atr_mean = None
    try:
        if len(df) >= 50:
            atr_series = pd.concat([(df['high'] - df['low']), (df['high'] - df['close'].shift()).abs(), (df['low'] - df['close'].shift()).abs()], axis=1).max(axis=1)
            atr_mean = atr_series.rolling(14).mean().mean()
    except Exception:
        atr_mean = atr

    vol_phase = volatility_phase(atr or 0.0, atr_mean or (atr or 0.0))

    # classify market regime (don't block signals, dampen instead)
    regime = classify_regime(df)
    regime_dampen = 1.0
    if regime == 'UNKNOWN':
        regime_dampen = getattr(cfg_mod, 'HARMONIC_REGIME_DAMPEN_UNKNOWN', 0.5) if cfg_mod else 0.5

    # Latest close and last-bar move (reference)
    try:
        close = float(df['close'].iloc[-1])
    except Exception:
        close = 0.0
    try:
        last_bar_move = float(df['close'].iloc[-1] - df['close'].iloc[-2])
    except Exception:
        last_bar_move = 0.0

    # Real elapsed-bar anchor for time/price squaring.
    try:
        bars_window = int(getattr(cfg_mod, 'HARMONIC_BARS_ELAPSED_WINDOW', 20)) if cfg_mod else 20
    except Exception:
        bars_window = 20
    anchor = compute_elapsed_bar_anchor(df, lookback=bars_window)
    bars_elapsed = int(anchor.get('bars_elapsed', 1) or 1)
    anchor_price = float(anchor.get('anchor_price', close) or close)
    anchor_time = anchor.get('anchor_time')
    anchor_kind = anchor.get('anchor_kind')

    # Detect harmonic hit: if explicit harmonics provided as price levels use them,
    # otherwise try to load base units from docs/data/market_harmonics.json and compute levels
    harmonic_hit = False
    harmonic_levels = []
    # determine instrument point size for tolerance calculations
    point_value = 0.01
    try:
        if 'point' in df.columns:
            point_value = float(df['point'].iloc[-1])
        else:
            try:
                info = mt5.symbol_info(symbol) if mt5 is not None else None
                point_value = float(getattr(info, 'point', 0.01)) if info is not None else 0.01
            except Exception:
                point_value = 0.01
    except Exception:
        point_value = 0.01
    try:
        if harmonics and isinstance(harmonics, list) and len(harmonics) > 0:
            # treat harmonics as explicit price levels
            for lvl in harmonics:
                try:
                    lvlf = float(lvl)
                except Exception:
                    continue
                tol = max(point_value * 0.1, (atr or (abs(close) * 0.001)) * 0.2)
                harmonic_levels.append({'level': lvlf, 'harmonic': 'explicit', 'tolerance': tol})
        else:
            # load from market harmonics reference
            mh = load_market_harmonics()
            key = symbol.replace('/', '').upper()
            entry = mh.get(key) or mh.get(symbol.upper())
            base_units = []
            if entry:
                base_units = entry.get('base_harmonics') or []
            if base_units:
                harmonic_levels = compute_harmonic_levels(symbol, close, base_units, atr, point_value, multiples=(1,2,3), tol_frac=0.5)
        # determine hit
        for lvl in harmonic_levels:
            try:
                if abs(close - float(lvl['level'])) <= float(lvl.get('tolerance', 0.0)):
                    harmonic_hit = True
                    break
            except Exception:
                continue
    except Exception:
        harmonic_hit = False

    price_move_anchor = float(close) - float(anchor_price)
    try:
        price_move_points = abs(float(price_move_anchor)) / float(point_value) if float(point_value) != 0 else abs(float(price_move_anchor))
    except Exception:
        price_move_points = abs(float(price_move_anchor))
    squared = harmonic_square(price_move_points, bars_elapsed, harmonic_hit)
    # Use per-instrument normalized volume: median-based to avoid outliers
    weighted_score = 0.0
    resonance_strength = 'WEAK'
    vol = 0.0
    avg_vol = 0.0
    vol_strong_ratio = getattr(cfg_mod, 'HARMONIC_VOLUME_STRONG_RATIO', 1.2) if cfg_mod else 1.2
    vol_moderate_ratio = getattr(cfg_mod, 'HARMONIC_VOLUME_MODERATE_RATIO', 0.8) if cfg_mod else 0.8
    vol_window = getattr(cfg_mod, 'HARMONIC_VOLUME_WINDOW', 50) if cfg_mod else 50
    
    try:
        if 'volume' in df.columns and len(df) > 0:
            vol = float(df['volume'].iloc[-1])
            # Use median over larger window for better normalization
            window = min(vol_window, len(df))
            if window > 0:
                avg_vol = float(df['volume'].iloc[-window:].median())
            else:
                avg_vol = vol
            
            # Avoid division by zero or zero-volume bars
            if avg_vol == 0:
                avg_vol = vol if vol > 0 else 1.0
            
            # Classify resonance strength
            vol_ratio = vol / avg_vol if avg_vol > 0 else 1.0
            if vol_ratio >= vol_strong_ratio:
                resonance_strength = 'STRONG'
            elif vol_ratio >= vol_moderate_ratio:
                resonance_strength = 'MODERATE'
            else:
                resonance_strength = 'WEAK'
        else:
            # No volume data; default to WEAK
            resonance_strength = 'WEAK'
            avg_vol = vol
        
        weighted_score = weighted_resonance(resonance_strength, session)
        # Apply regime dampen factor if regime is UNKNOWN
        weighted_score *= regime_dampen
    except Exception:
        weighted_score = weighted_resonance('WEAK', session) * regime_dampen

    # Debug print to help diagnose why weighted_score may be zero
    try:
        print(f"HARMONIC_DEBUG: {symbol} vol={vol} avg_vol={avg_vol} resonance_strength={resonance_strength} weighted_score={weighted_score}")
    except Exception:
        pass

    # confirmations: harmonic_hit counts as 1, additional checks add more
    confirmations = 0
    if harmonic_hit:
        confirmations += 1  # hit on harmonic level = confirmation
    try:
        if len(df) >= 50:
            sma50 = df['close'].rolling(50).mean().iloc[-1]
            if close > sma50:  # price above SMA50 = trend confirmation
                confirmations += 1
    except Exception:
        pass
    # Note: volume spike used to add confirmation, but removed as too strict

    # Heatmap stress adjustment
    try:
        stress = stress_level_for_symbol(symbol)
        # Reduce weighted_score on repeated resonance events
        if stress == 'MODERATE':
            weighted_score = weighted_score * 0.6
        elif stress == 'HIGH':
            weighted_score = weighted_score * 0.2
    except Exception:
        stress = 'LOW'

    acceptance = False
    rejection = False
    try:
        acceptance = (df['close'].iloc[-1] > df['open'].iloc[-1])
        rejection = (df['close'].iloc[-1] < df['open'].iloc[-1])
    except Exception:
        pass

    structure = {
        'nearest_level': None,
        'zone_low': None,
        'zone_mid': None,
        'zone_high': None,
        'buy_acceptance': False,
        'sell_rejection': False,
        'sell_bearish_acceptance_downtrend': False,
        'downtrend': False,
        'volume_confirmed': False,
    }
    try:
        atr_mult = getattr(cfg_mod, 'HARMONIC_ZONE_ATR_MULT', 0.25) if cfg_mod else 0.25
        wick_ratio = getattr(cfg_mod, 'HARMONIC_REJECTION_WICK_BODY_RATIO', 1.2) if cfg_mod else 1.2
        min_vol = getattr(cfg_mod, 'HARMONIC_VOLUME_CONFIRM_MIN', 'MODERATE') if cfg_mod else 'MODERATE'
        nearest_level = nearest_harmonic_level(close, harmonic_levels)
        zone = build_harmonic_zone(nearest_level, atr, point_value, atr_mult)
        downtrend = is_downtrend(df)
        candle = {
            'open': float(df['open'].iloc[-1]),
            'high': float(df['high'].iloc[-1]),
            'low': float(df['low'].iloc[-1]),
            'close': close,
        }
        buy_acceptance = detect_buy_acceptance(candle, zone)
        sell_rejection = detect_sell_rejection(candle, zone, wick_ratio_min=wick_ratio)
        sell_bear_acc = detect_sell_bearish_acceptance_downtrend(candle, zone, downtrend)
        vol_ok = volume_confirmed(resonance_strength, min_level=min_vol)
        structure = {
            'nearest_level': float(nearest_level['level']) if nearest_level and 'level' in nearest_level else None,
            'zone_low': zone.get('zone_low'),
            'zone_mid': zone.get('zone_mid'),
            'zone_high': zone.get('zone_high'),
            'buy_acceptance': bool(buy_acceptance),
            'sell_rejection': bool(sell_rejection),
            'sell_bearish_acceptance_downtrend': bool(sell_bear_acc),
            'downtrend': bool(downtrend),
            'volume_confirmed': bool(vol_ok),
        }
    except Exception:
        pass

    ctx = {
        'gates': {
            'harmonic_hit': harmonic_hit,
            'squared': squared,
            'vol_phase': vol_phase,
            'weighted_score': weighted_score,
            'confirmations': confirmations,
        },
        'acceptance': acceptance,
        'rejection': rejection,
        'structure': structure,
        'meta': {
            'symbol': symbol,
            'timeframe': timeframe,
            'price_move': price_move_anchor,
            'price_move_last_bar': last_bar_move,
            'price_move_anchor': price_move_anchor,
            'price_move_points': price_move_points,
            'bars_elapsed': bars_elapsed,
            'anchor_price': anchor_price,
            'anchor_time': anchor_time,
            'anchor_kind': anchor_kind,
            'atr': atr,
            'atr_mean': atr_mean,
            'volume': vol,
            'avg_volume': avg_vol,
            'resonance_strength': resonance_strength,
            'close': close,
            'regime': regime,
            'stress': stress,
            'harmonic_levels': harmonic_levels,
        }
    }

    sig = generate_signal(ctx, cfg=cfg_mod)
    # Record resonance event when a signal is produced
    try:
        if sig is not None:
            record_resonance_event(symbol, close)
    except Exception:
        pass

    return {'signal': sig, 'context': ctx, 'regime': regime, 'stress': stress}


if __name__ == "__main__":
    # Simple smoke test
    sample = {
        "gates": {
            "harmonic_hit": True,
            "squared": True,
            "vol_phase": "NORMAL",
            "weighted_score": 0.8,
            "confirmations": 2,
        },
        "acceptance": True,
        "rejection": False,
    }
    print("digital_root(17)", digital_root_value(17))
    print("price_phase(26)", price_phase(26))
    print("harmonic_square(10, 10, True)", harmonic_square(10, 10, True))
    print("generate_signal ->", generate_signal(sample))
