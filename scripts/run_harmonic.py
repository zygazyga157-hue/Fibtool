"""Small CLI harness to exercise harmonic_trader functions."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from harmonic_trader import generate_signal, price_phase, digital_root_value

parser = argparse.ArgumentParser()
parser.add_argument("--symbol", default=None, help="Symbol to fetch from MT5 (e.g., XAUUSD)")
parser.add_argument("--timeframe", default="H1")
parser.add_argument("--count", type=int, default=720)
parser.add_argument("--session", default="auto", help="Session name or 'auto' to detect from UTC")
args = parser.parse_args()

if args.symbol:
    out = None
    try:
        from harmonic_trader import analyze_symbol_live, session_for_utc, fetch_bars_mt5
        sess = args.session
        if isinstance(sess, str) and sess.lower() == 'auto':
            sess = session_for_utc()
        # harmonics will be loaded from docs/data/market_harmonics.json internally
        out = analyze_symbol_live(args.symbol, timeframe=args.timeframe, count=args.count, harmonics=None, session=sess)
    except Exception as e:
        print(f"Error analyzing live symbol via MT5: {e}")
        # Fallback: try loading from local CSV if it exists
        try:
            import pandas as pd
            from harmonic_trader import generate_signal, weighted_resonance, compute_atr, classify_regime, stress_level_for_symbol, session_for_utc
            symbol_safe = args.symbol.lower().replace('/', '_')
            csv_path = os.path.join('outputs', f'{symbol_safe}_bars.csv')
            if os.path.exists(csv_path):
                print(f"Falling back to local CSV: {csv_path}")
                df = pd.read_csv(csv_path, parse_dates=['time'])
                sess = args.session.upper() if isinstance(args.session, str) and args.session.lower() != 'auto' else session_for_utc()
                
                # Compute basic metrics
                atr = compute_atr(df)
                regime = classify_regime(df)
                stress = stress_level_for_symbol(args.symbol)
                vol = float(df['volume'].iloc[-1]) if 'volume' in df.columns else 0.0
                avg_vol = float(df['volume'].iloc[-20:].mean()) if 'volume' in df.columns and len(df) >= 20 else vol
                resonance_strength = 'STRONG' if avg_vol and vol >= 1.2 * avg_vol else ('MODERATE' if vol >= 0.8 * avg_vol else 'WEAK')
                weighted_score = weighted_resonance(resonance_strength, sess)
                
                out = {
                    'symbol': args.symbol,
                    'session': sess,
                    'regime': regime,
                    'stress': stress,
                    'volume': vol,
                    'avg_volume': avg_vol,
                    'resonance_strength': resonance_strength,
                    'weighted_score': weighted_score,
                    'atr': atr,
                    'csv_source': csv_path,
                }
            else:
                print(f"No CSV found at {csv_path}")
        except Exception as e2:
            print(f"CSV fallback also failed: {e2}")
    print(out)
else:
    print("No symbol provided. Use --symbol to analyze live MT5 data or run the original demo.")
