from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset


class SequenceAsiaDataset(Dataset):
    """Sequence dataset built from raw M5 bars and signals.

    Each sample is a sequence of length `seq_len` with features per timestep.
    Labels are determined by presence of a qualified trade in the next `horizon` bars.
    """

    def __init__(self, symbol: str, base_path: Optional[str] = None, seq_len: int = 12, horizon: int = 12):
        # Default base is repo root: <repo>/ml/asia_sweep_london_mss/sequence_dataset.py -> parents[3] == <repo>
        base = Path(base_path) if base_path else Path(__file__).resolve().parents[3]
        # Prefer true M5 bars (plan-aligned naming) so sequence experiments don't accidentally train on M15.
        def _symbol_slug(sym: str) -> str:
            try:
                return ''.join(ch if ch.isalnum() else '_' for ch in str(sym)).lower().strip('_')
            except Exception:
                return str(sym).replace('/', '_').replace(' ', '_').lower()

        bars_path = base / 'outputs' / f"{_symbol_slug(symbol)}_m5.csv"
        signals_path = base / 'outputs' / 'asia_mss_signals.csv'

        if not bars_path.exists():
            raise FileNotFoundError(bars_path)
        self.bars = pd.read_csv(bars_path, parse_dates=['time']).set_index('time').sort_index()

        self.seq_len = int(seq_len)
        self.horizon = int(horizon)

        # compute base features
        df = self.bars.copy()
        df['log_return'] = np.log(df['close']).diff().fillna(0.0)
        df['hl_range'] = (df['high'] - df['low']) / df['close']
        df['atr_5'] = df['hl_range'].rolling(5, min_periods=1).mean().fillna(0.0)
        mins = (pd.DatetimeIndex(df.index).hour * 60 + pd.DatetimeIndex(df.index).minute).astype(float)
        df['tod_sin'] = np.sin(2 * np.pi * mins / (24 * 60))
        df['tod_cos'] = np.cos(2 * np.pi * mins / (24 * 60))

        self.feature_cols = ['log_return', 'atr_5', 'tod_sin', 'tod_cos']
        self.df = df

        # load signals for label matching
        if not signals_path.exists():
            self.signals = pd.DataFrame()
        else:
            sigs = pd.read_csv(signals_path, parse_dates=['timestamp'])
            self.signals = sigs[sigs['symbol'].str.upper() == symbol.upper()].copy()
            # normalize timestamps
            try:
                self.signals['ts_naive'] = pd.to_datetime(self.signals['timestamp'], utc=True).dt.tz_convert('UTC').dt.tz_localize(None)
            except Exception:
                self.signals['ts_naive'] = pd.to_datetime(self.signals['timestamp'])

        # build indices for sequences
        self.timestamps = list(self.df.index[self.seq_len:])

    def __len__(self):
        return len(self.timestamps)

    def __getitem__(self, idx):
        ts = self.timestamps[idx]
        window = self.df.loc[:ts].iloc[-self.seq_len:]
        X = window[self.feature_cols].astype(np.float32).values  # (seq_len, features)

        # determine label: look for qualified trade in next horizon bars
        end_ts = ts + pd.Timedelta(minutes=5 * self.horizon)
        lbl = 0
        if not self.signals.empty:
            for _, r in self.signals.iterrows():
                s_ts = r.get('ts_naive')
                if s_ts is None:
                    continue
                if s_ts >= ts and s_ts <= end_ts:
                    # parse trade_setup
                    try:
                        t = r.get('trade_setup')
                        import json
                        tsu = json.loads(t) if isinstance(t, str) else (t if isinstance(t, dict) else {})
                        if isinstance(tsu, dict) and tsu.get('valid'):
                            typ = tsu.get('type', '')
                            if str(typ).lower().startswith('long'):
                                lbl = 1
                                break
                            if str(typ).lower().startswith('short'):
                                lbl = -1
                                break
                    except Exception:
                        continue

        X = torch.from_numpy(X)
        y = torch.tensor(lbl, dtype=torch.long)
        return X, y
