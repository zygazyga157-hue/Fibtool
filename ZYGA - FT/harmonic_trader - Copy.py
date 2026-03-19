"""
Harmonic trading helper implementing the core pieces from harmonic_trading.md
Uses ancient-science-of-numbers (digital root helpers) when available.
"""
from datetime import datetime
from typing import Optional, Dict, Any

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
from typing import List



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


def generate_signal(context: Dict[str, Any], cfg=None) -> Optional[str]:
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
      ASIA:     21:00 - 06:59 (Asian overlaps with late NY and early London)
      LONDON:   07:00 - 16:59 (London and NY overlap 13:00-16:59)
      NEW_YORK: 13:00 - 21:59 (NY afternoon into evening)
      DEAD_ZONE: 17:00 - 20:59 (thin overlap / pre-NY, post-London)
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
            dt = datetime.utcnow()
        h = int(dt.hour)
        # Corrected windows to avoid DST issues and overlap properly:
        if h >= 21 or h < 7:      # 21:00-23:59 and 00:00-06:59
            return 'ASIA'
        if 7 <= h < 17:           # 07:00-16:59 (covers London and early NY)
            return 'LONDON'
        if 13 <= h < 22:          # 13:00-21:59 (covers NY) — overlaps with LONDON 13-16
            return 'NEW_YORK'      # prefer NY if in overlap
        return 'DEAD_ZONE'         # 17:00-20:59
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


def analyze_symbol_live(symbol: str, timeframe: str = 'H1', count: int = 500, harmonics: Optional[list] = None,
                        session: str = 'NEW_YORK') -> Dict[str, Any]:
    """Fetch recent bars for `symbol` and produce a signal analysis dict.

    If `session=='auto'`, the session will be detected from current UTC time.
    """
    # allow auto-detection of session
    if isinstance(session, str) and session.lower() == 'auto':
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
    try:
        if regime == 'UNKNOWN':
            import config as _cfg
            regime_dampen = getattr(_cfg, 'HARMONIC_REGIME_DAMPEN_UNKNOWN', 0.5)
    except Exception:
        regime_dampen = 0.5

    # Simple price_move: latest close - previous close
    try:
        price_move = float(df['close'].iloc[-1] - df['close'].iloc[-2])
    except Exception:
        price_move = 0.0

    # bars_elapsed placeholder: 1 (could be replaced by pivot detection)
    bars_elapsed = 1

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
        close = float(df['close'].iloc[-1])
        if harmonics and isinstance(harmonics, list) and len(harmonics) > 0:
            # treat harmonics as explicit price levels
            for lvl in harmonics:
                try:
                    lvlf = float(lvl)
                except Exception:
                    continue
                tol = max(point * 0.1, (atr or (abs(close) * 0.001)) * 0.2)
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

    squared = harmonic_square(price_move, bars_elapsed, harmonic_hit)
    # Use per-instrument normalized volume: median-based to avoid outliers
    weighted_score = 0.0
    resonance_strength = 'WEAK'
    vol = 0.0
    avg_vol = 0.0
    try:
        import config as _cfg
        vol_strong_ratio = getattr(_cfg, 'HARMONIC_VOLUME_STRONG_RATIO', 1.2)
        vol_moderate_ratio = getattr(_cfg, 'HARMONIC_VOLUME_MODERATE_RATIO', 0.8)
        vol_window = getattr(_cfg, 'HARMONIC_VOLUME_WINDOW', 50)
    except Exception:
        vol_strong_ratio, vol_moderate_ratio, vol_window = 1.2, 0.8, 50
    
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
        'meta': {
            'symbol': symbol,
            'timeframe': timeframe,
            'price_move': price_move,
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

    sig = generate_signal(ctx, cfg=None)  # Use internal config import
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
