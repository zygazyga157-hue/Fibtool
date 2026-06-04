"""Small CLI harness to exercise harmonic_trader functions."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from harmonic_trader import generate_signal, price_phase, digital_root_value

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("--symbol", action="append", help="Single symbol to fetch from MT5 (repeatable). e.g. --symbol XAUUSD")
group.add_argument("--symbols", help="Comma-separated symbols list (e.g. EURUSD,GBPUSD)")
parser.add_argument("--timeframe", default="H1")
parser.add_argument("--count", type=int, default=7200, help="Bars to fetch per symbol (default 7200)")
parser.add_argument("--session", default="auto", help="Session name or 'auto' to detect from UTC")
parser.add_argument("--parallel", action="store_true", help="Run symbols in parallel (background jobs). Use with caution for MT5 load.")
args = parser.parse_args()

def _normalize_symbol_list(args) -> list[str]:
    syms: list[str] = []
    if args.symbol:
        # args.symbol via append -> list. Accept values like "EURUSD,GBPUSD" too.
        for entry in args.symbol:
            if not entry:
                continue
            if ',' in entry:
                parts = [p.strip() for p in entry.split(',') if p.strip()]
                syms.extend(parts)
            else:
                syms.append(entry)
    if args.symbols:
        parts = [p.strip() for p in str(args.symbols).split(",") if p.strip()]
        syms.extend(parts)
    # dedupe while preserving order
    out: list[str] = []
    seen = set()
    for s in syms:
        up = s.strip()
        if not up:
            continue
        if up in seen:
            continue
        seen.add(up)
        out.append(up)
    return out


def _analyze_symbol(symbol: str, timeframe: str, count: int, session: str) -> dict | None:
    try:
        from harmonic_trader import analyze_symbol_live
        return analyze_symbol_live(symbol, timeframe=timeframe, count=count, harmonics=None, session=session)
    except Exception as e:
        print(f"Error analyzing {symbol} via MT5: {e}")
        # CSV fallback
        try:
            import pandas as pd
            from harmonic_trader import generate_signal, weighted_resonance, compute_atr, classify_regime, stress_level_for_symbol, session_for_utc
            symbol_safe = symbol.lower().replace('/', '_')
            csv_path = os.path.join('outputs', f'{symbol_safe}_bars.csv')
            if os.path.exists(csv_path):
                print(f"Falling back to local CSV: {csv_path}")
                df = pd.read_csv(csv_path, parse_dates=['time'])
                sess = session.upper() if isinstance(session, str) and session.lower() != 'auto' else session_for_utc()
                atr = compute_atr(df)
                regime = classify_regime(df)
                stress = stress_level_for_symbol(symbol)
                vol = float(df['volume'].iloc[-1]) if 'volume' in df.columns else 0.0
                avg_vol = float(df['volume'].iloc[-20:].mean()) if 'volume' in df.columns and len(df) >= 20 else vol
                resonance_strength = 'STRONG' if avg_vol and vol >= 1.2 * avg_vol else ('MODERATE' if vol >= 0.8 * avg_vol else 'WEAK')
                weighted_score = weighted_resonance(resonance_strength, sess)
                return {
                    'symbol': symbol,
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
            print(f"CSV fallback also failed for {symbol}: {e2}")
    return None


def main() -> int:
    symbols = _normalize_symbol_list(args)
    if not symbols:
        print("No symbols provided after parsing. Use --symbol or --symbols.")
        return 2

    results = {}
    if args.parallel:
        # Use simple multiprocessing via subprocesses to avoid MT5 threading issues
        procs = []
        for s in symbols:
            cmd = [sys.executable, os.path.abspath(__file__), '--symbol', s, '--timeframe', args.timeframe, '--count', str(args.count), '--session', args.session]
            p = subprocess.Popen(cmd)
            procs.append((s, p))
        for s, p in procs:
            p.wait()
            print(f"Symbol {s} finished with rc={p.returncode}")
    else:
        for s in symbols:
            print(f"Analyzing {s} ...")
            out = _analyze_symbol(s, args.timeframe, args.count, args.session)
            print(out)
            results[s] = out

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
