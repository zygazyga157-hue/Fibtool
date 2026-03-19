from __future__ import annotations

import os
import json
from datetime import datetime, timezone, timedelta
import time
from typing import List, Optional

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None
import csv
import traceback
from datetime import time as _time
try:
    import config as _config
except Exception:
    _config = None

class AsiaSweepStrategy:
    """Pure Asia Sweep implementation — no S9 or Wyckoff dependencies.

    Implements the exact logic from the specification:
    - Build AsiaHigh/AsiaLow (00:00-07:59 local time)
    - Detect sweep (current bar high > AsiaHigh or low < AsiaLow)
    - Compute 5-minute MSS using prior 3 completed M5 candles
    - Place 0.71 retracement limit entry (dry-run emit only)
    - Enforce tradedToday per calendar day
    """

    OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'outputs')
    SIGNAL_JSONL = os.path.join(OUTPUT_DIR, 'asia_mss_signals.jsonl')
    SIGNAL_CSV = os.path.join(OUTPUT_DIR, 'asia_mss_signals.csv')
    STATE_FILE = os.path.join(OUTPUT_DIR, 'asia_mss_state.json')
    ORDERS_CSV = os.path.join(OUTPUT_DIR, 'asia_mss_orders.csv')

    def __init__(self, symbols: Optional[List[str]] = None):
        self.symbols = symbols or []
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        # runtime options (dry-run by default)
        self.dry_run = True
        self.risk_pct = 1.0
        self.time_zone = 'UTC'
        self.session_time_zone = 'Europe/London'
        self.time_offset_hours = 0.0
        self.session_time_offset_hours = None
        self.state = self._load_state()

    def _require_pandas(self):
        if pd is None:
            raise RuntimeError("pandas is required for AsiaSweepStrategy (install pandas to use this strategy).")

    def _cfg(self, key: str, default):
        """Read config.py knobs without hard-depending on config existence."""
        try:
            if _config is not None and hasattr(_config, key):
                v = getattr(_config, key)
                return default if v is None else v
        except Exception:
            pass
        return default

    def _parse_hhmm(self, value: str, default: str) -> str:
        """Validate HH:MM strings; return default on invalid."""
        raw = value if isinstance(value, str) else ''
        raw = raw.strip()
        if not raw:
            return default
        try:
            datetime.strptime(raw, "%H:%M")
            return raw
        except Exception:
            return default

    def _parse_time(self, value: str, default: _time) -> _time:
        raw = value if isinstance(value, str) else ''
        raw = raw.strip()
        if not raw:
            return default
        try:
            return datetime.strptime(raw, "%H:%M").time()
        except Exception:
            return default

    def configure(
        self,
        *,
        dry_run: bool = True,
        risk_pct: float = 1.0,
        time_zone: str = 'UTC',
        session_time_zone: str = None,
        mt5_account: str = None,
        order_size: float = None,
        log_orders: str = None,
    ):
        self.dry_run = bool(dry_run)
        try:
            self.risk_pct = float(risk_pct)
        except Exception:
            self.risk_pct = 1.0
        self.time_zone = time_zone or 'UTC'
        self.session_time_zone = session_time_zone or self.time_zone or 'UTC'
        # Offset-only time zones are supported as a fallback (no DST support).
        self.time_offset_hours = self._parse_time_offset_hours(self.time_zone)
        self.session_time_offset_hours = self._parse_time_offset_hours(self.session_time_zone)
        # Optional runtime wiring for MT5 and order logging
        self.mt5_account = mt5_account
        self.order_size = float(order_size) if order_size is not None else None
        if log_orders:
            # allow overriding default orders CSV path
            self.ORDERS_CSV = log_orders
        # If running live, attempt to initialize MT5 helpers
        if not self.dry_run:
            try:
                leb = self._init_mt5(live=True)
                # keep reference for later use
                self.leb = leb
            except Exception:
                self.leb = None

    def _parse_time_offset_hours(self, tz_value):
        """Parse UTC-offset-style inputs. Returns float hours or None for named zones."""
        try:
            if isinstance(tz_value, (int, float)):
                return float(tz_value)
            if not isinstance(tz_value, str):
                return None
            tzs = tz_value.strip()
            if not tzs:
                return None
            u = tzs.upper()
            if u in ('UTC', 'GMT', 'Z'):
                return 0.0
            # Accept: UTC+2, UTC-3, +2, -3, 2
            raw = tzs
            if u.startswith('UTC'):
                raw = tzs[3:].strip()
            if u.startswith('GMT'):
                raw = tzs[3:].strip()
            if not raw:
                return 0.0

            sign = 1.0
            if raw.startswith('+'):
                raw = raw[1:]
            elif raw.startswith('-'):
                raw = raw[1:]
                sign = -1.0

            if raw.count(':') == 1:
                hh, mm = raw.split(':', 1)
                if hh.isdigit() and mm.isdigit():
                    return sign * (float(int(hh)) + float(int(mm)) / 60.0)
                return None

            try:
                return sign * float(raw)
            except Exception:
                return None
        except Exception:
            return None

    def _fixed_offset_tz(self, offset_hours):
        try:
            return timezone(timedelta(hours=float(offset_hours)))
        except Exception:
            return timezone.utc

    def _to_utc_timestamp(self, ts):
        self._require_pandas()
        t = pd.to_datetime(ts)
        if getattr(t, 'tz', None) is None:
            return t.tz_localize('UTC')
        return t.tz_convert('UTC')

    def _to_utc_index(self, idx):
        self._require_pandas()
        out = pd.to_datetime(idx)
        if getattr(out, 'tz', None) is None:
            return out.tz_localize('UTC')
        return out.tz_convert('UTC')

    def _to_target_timezone(self, ts_utc, tz_name, offset_hours):
        base = self._to_utc_timestamp(ts_utc)
        if isinstance(tz_name, str) and tz_name and tz_name.upper() not in ('UTC', 'GMT', 'Z'):
            try:
                return base.tz_convert(tz_name)
            except Exception:
                pass
        if offset_hours not in (None, 0, 0.0):
            try:
                return base.tz_convert(self._fixed_offset_tz(offset_hours))
            except Exception:
                pass
        return base

    def _index_to_target_timezone(self, idx_utc, tz_name, offset_hours):
        base = self._to_utc_index(idx_utc)
        if isinstance(tz_name, str) and tz_name and tz_name.upper() not in ('UTC', 'GMT', 'Z'):
            try:
                return base.tz_convert(tz_name)
            except Exception:
                pass
        if offset_hours not in (None, 0, 0.0):
            try:
                return base.tz_convert(self._fixed_offset_tz(offset_hours))
            except Exception:
                pass
        return base

    def _load_admin_settings(self):
        # Try outputs/admin_settings.json for risk and defaults
        admin_path = os.path.join(self.OUTPUT_DIR, 'admin_settings.json')
        defaults = {
            'rr_min': 1.5,
            'rr_max': 10.0,
            'risk_pct': 1.0,
            'margin_safety_buffer': 0.8,
            'max_total_open_risk_pct': 20.0,
            'daily_loss_limit_pct': 5.0,
            'default_lot': 0.1
        }
        try:
            if os.path.exists(admin_path):
                with open(admin_path, 'r') as f:
                    data = json.load(f)
                defaults.update({k: data.get(k, defaults[k]) for k in defaults.keys()})
        except Exception:
            pass

        # Optional config overrides (useful for "capture mode" without editing admin_settings.json).
        try:
            rr_min_cfg = self._cfg('ASIA_SWEEP_RR_MIN', None)
            rr_max_cfg = self._cfg('ASIA_SWEEP_RR_MAX', None)
            if rr_min_cfg is not None:
                defaults['rr_min'] = float(rr_min_cfg)
            if rr_max_cfg is not None:
                defaults['rr_max'] = float(rr_max_cfg)
        except Exception:
            pass
        return defaults

    def _compute_lots(self, symbol: str, entry: float, stop: float, risk_pct: Optional[float] = None) -> float:
        # Try to use live helpers if present; fallback to default_lot from admin settings
        risk_pct = risk_pct if risk_pct is not None else self.risk_pct
        admin = self._load_admin_settings()
        # Attempt to use existing mt5 sizing helper if available
        try:
            import live_entry_bot_mt5 as leb
            # get account equity via helper if available
            acct = None
            try:
                acct = leb._get_total_portfolio_risk()
            except Exception:
                acct = None
            balance = acct.get('equity') if isinstance(acct, dict) and acct.get('equity') else None
            if balance is None:
                # fallback to leb account_info if present
                try:
                    balance = leb.mt5.account_info().balance
                except Exception:
                    balance = None

            if balance is not None:
                lots = leb._risk_position_size(symbol, risk_pct, balance, entry, stop)
                return float(lots)
        except Exception:
            pass

        # fallback: return default lot from admin settings
        try:
            return float(admin.get('default_lot', 0.01))
        except Exception:
            return 0.01

    def _load_state(self):
        try:
            if os.path.exists(self.STATE_FILE):
                with open(self.STATE_FILE, 'r') as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
                data.setdefault('tradedToday', {})
                data.setdefault('tradedDate', None)
                data.setdefault('sweeps', {})
                return data
        except Exception:
            pass
        return {'tradedToday': {}, 'tradedDate': None, 'sweeps': {}}


    def _load_auto_state(self):
        # Try outputs/auto_state.json then live_entry_bot_mt5.AUTO_STATE_PATH
        p = os.path.join(self.OUTPUT_DIR, 'auto_state.json')
        try:
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    return json.load(f) or {}
        except Exception:
            pass
        # try live_entry_bot_mt5 fallback
        try:
            import live_entry_bot_mt5 as leb
            try:
                ap = getattr(leb, 'AUTO_STATE_PATH', None)
                if ap and os.path.exists(ap):
                    with open(ap, 'r', encoding='utf-8') as f:
                        return json.load(f) or {}
            except Exception:
                pass
        except Exception:
            pass
        return {}

    def _audit(self, symbol: str, action: str, details: dict):
        fn = os.path.join(self.OUTPUT_DIR, 'asia_mss_audit.jsonl')
        out = {'timestamp': datetime.utcnow().isoformat() + 'Z', 'symbol': symbol, 'action': action, 'details': details}
        try:
            with open(fn, 'a', encoding='utf-8') as f:
                f.write(json.dumps(self._to_json_safe(out), default=str) + '\n')
        except Exception:
            pass

    def _to_json_safe(self, value):
        """Convert nested structures to JSON-safe objects (stringify non-serializable keys)."""
        if isinstance(value, dict):
            safe = {}
            for k, v in value.items():
                safe[str(k)] = self._to_json_safe(v)
            return safe
        if isinstance(value, (list, tuple, set)):
            return [self._to_json_safe(v) for v in value]
        if isinstance(value, (pd.Timestamp, datetime)):
            try:
                return value.isoformat()
            except Exception:
                return str(value)
        try:
            if hasattr(value, 'item'):
                return value.item()
        except Exception:
            pass
        return value

    def _init_mt5(self, live: bool = False):
        # Best-effort initializer: import leb and call ensure_mt5_connected if available
        try:
            import live_entry_bot_mt5 as leb
            try:
                if live:
                    leb.ensure_mt5_connected()
                return leb
            except Exception:
                return leb
        except Exception:
            return None

    def _save_state(self):
        with open(self.STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2, default=str)

    def _ensure_daily_state(self, current_local_ts):
        """Reset tradedToday when the session calendar day rolls over."""
        self._require_pandas()
        try:
            day_key = pd.to_datetime(current_local_ts).date().isoformat()
        except Exception:
            day_key = datetime.utcnow().date().isoformat()

        if self.state.get('tradedDate') != day_key:
            self.state['tradedDate'] = day_key
            self.state['tradedToday'] = {}
            # Reset sweep memory each new session day.
            self.state['sweeps'] = {}
            try:
                self._save_state()
            except Exception:
                pass

    def _bars_path(self, symbol: str) -> str:
        return os.path.join(self.OUTPUT_DIR, f"{symbol.lower()}_bars.csv")

    def load_bars(self, symbol: str) -> Optional[pd.DataFrame]:
        self._require_pandas()
        path = self._bars_path(symbol)
        if not os.path.exists(path):
            return None
        try:
            df = pd.read_csv(path, parse_dates=['time'], index_col='time')
            try:
                # Keep canonical UTC index; convert to session/local time only for comparisons.
                df.index = self._to_utc_index(df.index)
                df.sort_index(inplace=True)
            except Exception:
                pass
            return df
        except Exception:
            try:
                df = pd.read_csv(path, parse_dates=['time'])
                if 'time' in df.columns:
                    df.set_index('time', inplace=True)
                    try:
                        df.index = self._to_utc_index(df.index)
                        df.sort_index(inplace=True)
                    except Exception:
                        pass
                return df
            except Exception:
                return None

    def _emit_signal(self, record: dict):
        safe_record = self._to_json_safe(record)
        # Always write JSONL using stdlib to ensure persistence even if pandas fails
        try:
            with open(self.SIGNAL_JSONL, 'a', encoding='utf-8') as f:
                f.write(json.dumps(safe_record, default=str) + "\n")
        except Exception:
            # Best-effort fallback: try binary write
            try:
                with open(self.SIGNAL_JSONL, 'ab') as f:
                    f.write((json.dumps(safe_record, default=str) + "\n").encode('utf-8'))
            except Exception:
                pass

        # Also append a flattened CSV trace for easy inspection without pandas
        try:
            write_header = not os.path.exists(self.SIGNAL_CSV)
            os.makedirs(os.path.dirname(self.SIGNAL_CSV), exist_ok=True)
            with open(self.SIGNAL_CSV, 'a', newline='', encoding='utf-8') as csvfile:
                flat = {}
                for k, v in safe_record.items():
                    if isinstance(v, (str, int, float, bool)) or v is None:
                        flat[k] = v
                    else:
                        try:
                            flat[k] = json.dumps(v, default=str)
                        except Exception:
                            flat[k] = str(v)
                fieldnames = list(flat.keys())
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                if write_header:
                    writer.writeheader()
                writer.writerow(flat)
        except Exception:
            try:
                fb = self.SIGNAL_CSV + '.fallback'
                with open(fb, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(safe_record, default=str) + "\n")
            except Exception:
                pass

    def _submit_order(self, symbol: str, trade_setup: dict, pretrade: dict):
        """Write an order line to the ORDERS_CSV. In dry-run mode this only logs the intended order.

        Fields: timestamp,symbol,side,entry,stop_loss,take_profit,lots,rr,estimated_margin,balance,method,dry_run,status,notes
        """
        # Keep orders CSV schema stable even as we add columns over time.
        # If the file already exists with an older header, migrate it once so
        # subsequent appends don't shift values under the wrong header columns.
        ORDERS_FIELDS = [
            'timestamp',
            'symbol',
            'side',
            'order_type',   # human label: Limit/Stop/Market
            'order_kind',   # mt5 kind: limit/stop/market
            'entry',
            'stop_loss',
            'take_profit',
            'lots',
            'rr',
            'estimated_margin',
            'balance',
            'method',
            'dry_run',
            'status',
            'notes',
        ]

        def _migrate_orders_csv_add_order_kind(path: str):
            try:
                if not os.path.exists(path):
                    return
                with open(path, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                if not rows:
                    return
                header = rows[0]
                if 'order_kind' in header:
                    return
                # Only handle the known legacy header that lacks order_kind.
                if 'order_type' not in header:
                    return

                insert_at = header.index('order_type') + 1
                new_header = header[:insert_at] + ['order_kind'] + header[insert_at:]
                out_rows = [new_header]
                old_len = len(header)
                new_len = len(new_header)

                for r in rows[1:]:
                    # Old rows: length == old header length => insert blank order_kind
                    if len(r) == old_len:
                        rr = r[:insert_at] + [''] + r[insert_at:]
                        out_rows.append(rr)
                        continue
                    # Newer rows that were already written with order_kind included (but header wasn't updated):
                    # keep as-is if it matches the new length.
                    if len(r) == new_len:
                        out_rows.append(r)
                        continue
                    # Otherwise pad/truncate to new header length.
                    if len(r) < new_len:
                        out_rows.append(r + [''] * (new_len - len(r)))
                    else:
                        out_rows.append(r[:new_len])

                tmp = path + '.tmp'
                with open(tmp, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerows(out_rows)
                try:
                    os.replace(tmp, path)
                except Exception:
                    # best-effort fallback
                    os.remove(path)
                    os.rename(tmp, path)
            except Exception:
                # Never block order submission just because a migration failed.
                return

        # Migrate legacy orders CSV if needed (fixes header/value misalignment).
        _migrate_orders_csv_add_order_kind(self.ORDERS_CSV)

        os.makedirs(os.path.dirname(self.ORDERS_CSV), exist_ok=True)
        write_header = not os.path.exists(self.ORDERS_CSV)
        row = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'symbol': symbol,
            'side': trade_setup.get('type'),
            'order_type': 'Limit',
            'order_kind': 'limit',
            'entry': trade_setup.get('entry'),
            'stop_loss': trade_setup.get('stop_loss'),
            'take_profit': trade_setup.get('take_profit'),
            'lots': pretrade.get('lots'),
            'rr': pretrade.get('rr'),
            'estimated_margin': pretrade.get('estimated_margin'),
            'balance': pretrade.get('balance'),
            'method': trade_setup.get('method'),
            'dry_run': bool(self.dry_run),
            'status': 'simulated' if self.dry_run else 'pending',
            'notes': None
        }

        # If live-mode requested, attempt to send via live_entry_bot_mt5; fall back to logging
        if not self.dry_run:
            try:
                import live_entry_bot_mt5 as leb
                # attempt a best-effort send; this may raise/return error
                try:
                    side_raw = str(trade_setup.get('type') or '').strip().lower()
                    if side_raw in ('long', 'buy'):
                        side_norm = 'long'
                    elif side_raw in ('short', 'sell'):
                        side_norm = 'short'
                    else:
                        side_norm = side_raw or 'long'

                    volume = row['lots'] if row['lots'] is not None else self.order_size
                    if volume is None:
                        volume = 0.01

                    # Decide pending order kind: limit vs stop based on current bid/ask.
                    # - Buy Limit: entry < ask
                    # - Sell Limit: entry > bid
                    # Otherwise use a Stop order so MT5 doesn't reject it as an invalid pending price.
                    order_kind = 'limit'
                    try:
                        tick = getattr(leb, 'mt5', None).symbol_info_tick(symbol) if getattr(leb, 'mt5', None) is not None else None
                        bid = float(getattr(tick, 'bid', 0.0) or 0.0) if tick is not None else 0.0
                        ask = float(getattr(tick, 'ask', 0.0) or 0.0) if tick is not None else 0.0
                        entry = float(row['entry']) if row.get('entry') is not None else None
                        if entry is not None and bid > 0 and ask > 0:
                            if side_norm == 'long':
                                order_kind = 'limit' if entry < ask else 'stop'
                            else:
                                order_kind = 'limit' if entry > bid else 'stop'
                    except Exception:
                        order_kind = 'limit'

                    row['order_kind'] = order_kind
                    row['order_type'] = 'Stop' if order_kind == 'stop' else 'Limit'

                    res = leb.send_order(
                        symbol=symbol,
                        side=side_norm,
                        volume=float(volume),
                        price=float(row['entry']),
                        stop=float(row['stop_loss']),
                        tp=float(row['take_profit']),
                        comment=f'asia_sweep_071_{order_kind}',
                        dry_run=self.dry_run,
                        order_kind=order_kind,
                    )

                    status = None
                    if isinstance(res, dict):
                        status = res.get('status')
                        # If live_entry_bot_mt5 adjusted the kind internally, capture it.
                        if res.get('order_kind_used'):
                            row['order_kind'] = res.get('order_kind_used')
                    row['status'] = str(status) if status else ('sent' if res else 'failed')
                    row['notes'] = str(res)
                except Exception as e:
                    row['status'] = 'error'
                    row['notes'] = str(e)
            except Exception:
                row['status'] = 'no_live_module'
                row['notes'] = 'live_entry_bot_mt5 not available'

        # Append to CSV
        try:
            with open(self.ORDERS_CSV, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=ORDERS_FIELDS, extrasaction='ignore')
                if write_header:
                    writer.writeheader()
                writer.writerow(row)
        except Exception:
            # best-effort fallback: write json line
            try:
                with open(self.ORDERS_CSV + '.fallback', 'a', encoding='utf-8') as f:
                    f.write(json.dumps(row, default=str) + "\n")
            except Exception:
                pass

        # (Signal CSV write moved to _emit_signal)

    def _compute_asia_range(self, df: pd.DataFrame):
        self._require_pandas()
        # Asia session 00:00-07:59 in the configured session timezone.
        if not isinstance(df.index, pd.DatetimeIndex):
            try:
                df.index = pd.to_datetime(df.index)
            except Exception:
                return None, None, 0, 0

        try:
            session_df = df.copy()
            session_df.index = self._index_to_target_timezone(
                df.index,
                getattr(self, 'session_time_zone', 'UTC'),
                getattr(self, 'session_time_offset_hours', None),
            )
            session_df.sort_index(inplace=True)
        except Exception:
            session_df = df

        if len(session_df) == 0:
            return None, None, 0, 0

        last_dt = session_df.index[-1]
        day = last_dt.date()

        day_df = session_df[session_df.index.date == day]
        asia_start = self._parse_hhmm(self._cfg('ASIA_SWEEP_ASIA_START', '00:00'), '00:00')
        asia_end = self._parse_hhmm(self._cfg('ASIA_SWEEP_ASIA_END', '07:59'), '07:59')
        asia_df = day_df.between_time(asia_start, asia_end)
        if asia_df.empty:
            try:
                prev_day = (last_dt - pd.Timedelta(days=1)).date()
                prev_day_df = session_df[session_df.index.date == prev_day]
                asia_df = prev_day_df.between_time(asia_start, asia_end)
            except Exception:
                pass

        if asia_df.empty:
            return None, None, 0, 0

        asia_high = float(asia_df['high'].max())
        asia_low = float(asia_df['low'].min())

        # Detect EQH (Equal Highs) and EQL (Equal Lows) liquidity pools
        # Count bars that touched the session high/low (within tolerance for floating point)
        tolerance = 1e-5  # Small tolerance for floating point comparison
        eqh_count = int((asia_df['high'] >= asia_high - tolerance).sum())
        eql_count = int((asia_df['low'] <= asia_low + tolerance).sum())

        return asia_high, asia_low, eqh_count, eql_count

    def _resample_m5(self, df: pd.DataFrame) -> pd.DataFrame:
        self._require_pandas()
        # Ensure DatetimeIndex and numeric cols exist
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        # Keep M5 in canonical UTC and convert only for session comparisons.
        ohlc = df[['open', 'high', 'low', 'close']].resample('5min').agg(
            {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
        )

        ohlc.dropna(how='any', inplace=True)
        return ohlc

    def _mss_flags(self, m5: pd.DataFrame, current_m5_time: pd.Timestamp = None) -> Optional[dict]:
        self._require_pandas()
        # Need at least 4 completed M5 candles: previous 3 + current
        if len(m5) < 4:
            return None

        # If caller provides a floored current m5 timestamp, align to it
        try:
            if current_m5_time is not None:
                # try exact match first
                if current_m5_time in m5.index:
                    curr = m5.loc[current_m5_time]
                    # prev3 are the 3 rows immediately before this index
                    prior = m5.loc[:current_m5_time]
                    if len(prior) < 4:
                        return None
                    prev3 = prior.iloc[-4:-1]
                else:
                    # if exact timestamp not present, find the latest index <= current_m5_time
                    le_idx = m5.index[m5.index <= current_m5_time]
                    if len(le_idx) == 0:
                        return None
                    target = le_idx[-1]
                    curr = m5.loc[target]
                    prior = m5.loc[:target]
                    if len(prior) < 4:
                        return None
                    prev3 = prior.iloc[-4:-1]
            else:
                # fallback: use last row as current
                curr = m5.iloc[-1]
                prev3 = m5.iloc[-4:-1]
        except Exception:
            return None

        try:
            bull = bool(curr['close'] > prev3['high'].max())
        except Exception:
            bull = False
        try:
            bear = bool(curr['close'] < prev3['low'].min())
        except Exception:
            bear = False

        return {'bullMSS': bull, 'bearMSS': bear, 'current_m5': curr.to_dict(), 'prev3': prev3.to_dict()}

    def _mss_series(self, m5: pd.DataFrame, lookback: int) -> Optional[pd.DataFrame]:
        """Compute bull/bear MSS flags for every M5 candle (close-based)."""
        self._require_pandas()
        try:
            lb = int(lookback)
        except Exception:
            lb = 3
        if lb < 1:
            lb = 1
        if len(m5) < lb + 1:
            return None

        bull = []
        bear = []
        for i in range(len(m5)):
            if i < lb:
                bull.append(False)
                bear.append(False)
                continue
            prev = m5.iloc[i - lb:i]
            try:
                bull.append(bool(m5.iloc[i]['close'] > prev['high'].max()))
            except Exception:
                bull.append(False)
            try:
                bear.append(bool(m5.iloc[i]['close'] < prev['low'].min()))
            except Exception:
                bear.append(False)

        out = m5.copy()
        out['bullMSS'] = bull
        out['bearMSS'] = bear
        return out

    def generate_for_symbol(self, symbol: str) -> Optional[dict]:
        self._require_pandas()
        df = self.load_bars(symbol)
        if df is None or len(df) < 20:
            return None

        asia_high, asia_low, eqh_count, eql_count = self._compute_asia_range(df)

        last_bar = df.iloc[-1]
        # Build UTC/session/local timestamps for deterministic session logic and DST safety.
        try:
            idx_utc = self._to_utc_timestamp(df.index[-1])
        except Exception:
            idx_utc = pd.Timestamp.now(tz='UTC')

        try:
            idx_session = self._to_target_timezone(
                idx_utc,
                getattr(self, 'session_time_zone', 'UTC'),
                getattr(self, 'session_time_offset_hours', None),
            )
        except Exception:
            idx_session = idx_utc

        try:
            idx_local = self._to_target_timezone(
                idx_utc,
                getattr(self, 'time_zone', 'UTC'),
                getattr(self, 'time_offset_hours', None),
            )
        except Exception:
            idx_local = idx_utc

        # Session flags in the canonical session timezone (default should be Europe/London).
        in_london = False
        in_asia = False
        asia_start_t = self._parse_time(self._cfg('ASIA_SWEEP_ASIA_START', '00:00'), _time(0, 0))
        asia_end_t = self._parse_time(self._cfg('ASIA_SWEEP_ASIA_END', '07:59'), _time(7, 59))
        london_start_t = self._parse_time(self._cfg('ASIA_SWEEP_LONDON_START', '08:00'), _time(8, 0))
        london_end_t = self._parse_time(self._cfg('ASIA_SWEEP_LONDON_END', '14:00'), _time(14, 0))
        try:
            # Use `.time()` (naive) instead of `.timetz()` (tz-aware) so comparisons don't TypeError.
            # Pandas Timestamp in a tz will otherwise create offset-aware times that can't be compared
            # to naive HH:MM times, and the exception would silently force in_london/in_asia False.
            session_t = idx_session.time() if getattr(idx_session, 'time', None) else idx_session
            in_asia = (session_t >= asia_start_t and session_t <= asia_end_t)
            in_london = (session_t >= london_start_t and session_t <= london_end_t)
        except Exception:
            pass

        # Local audit flags in configured local/reporting timezone.
        try:
            local_t = idx_local.time() if getattr(idx_local, 'time', None) else idx_local
            in_asia_local = (local_t >= asia_start_t and local_t <= asia_end_t)
            in_london_local = (local_t >= london_start_t and local_t <= london_end_t)
        except Exception:
            in_asia_local = bool(in_asia)
            in_london_local = bool(in_london)

        # coerce to booleans
        try:
            in_asia_local = bool(in_asia_local)
        except Exception:
            in_asia_local = False
        try:
            in_london_local = bool(in_london_local)
        except Exception:
            in_london_local = False

        # Ensure booleans (not string representations) for downstream logic
        try:
            in_asia = bool(in_asia)
        except Exception:
            in_asia = False
        try:
            in_london = bool(in_london)
        except Exception:
            in_london = False

        # Keep tradedToday bounded to the current session calendar day.
        self._ensure_daily_state(idx_session)

        # Build M5 and MSS flags (snapshot + series for event gating)
        m5 = self._resample_m5(df)

        # compute floored current M5 bar time using same offset rules as resampling
        try:
            current_m5_time = pd.to_datetime(df.index[-1]).floor('5min')
        except Exception:
            current_m5_time = None

        mss = self._mss_flags(m5, current_m5_time=current_m5_time)
        # Ensure MSS boolean flags are real bools
        try:
            if isinstance(mss, dict):
                mss['bullMSS'] = bool(mss.get('bullMSS'))
                mss['bearMSS'] = bool(mss.get('bearMSS'))
        except Exception:
            pass

        fib_ratio = 0.71
        fib_long = None
        fib_short = None
        if isinstance(mss, dict):
            curr_m5 = mss.get('current_m5') or {}
            try:
                m5_low = float(curr_m5['low'])
                m5_high = float(curr_m5['high'])
                m5_range = (m5_high - m5_low)
                fib_long = m5_low + (m5_range * fib_ratio)
                fib_short = m5_high - (m5_range * fib_ratio)
            except Exception:
                fib_long = None
                fib_short = None

        # Gate knobs (configurable; keep defaults if not present)
        try:
            mss_lookback = int(self._cfg('ASIA_SWEEP_MSS_LOOKBACK', 3))
        except Exception:
            mss_lookback = 3
        try:
            confirm_window_bars = int(self._cfg('ASIA_SWEEP_CONFIRM_WINDOW_BARS', 12))
        except Exception:
            confirm_window_bars = 12
        if confirm_window_bars < 1:
            confirm_window_bars = 1

        # Compute MSS series across all M5 bars (close-based) and convert to session TZ for day/window filtering.
        m5_series = self._mss_series(m5, mss_lookback)
        if m5_series is None:
            # Not enough M5 data for MSS lookback; still emit a trace record.
            m5_series = m5.copy()
            m5_series['bullMSS'] = False
            m5_series['bearMSS'] = False

        try:
            m5_session = m5_series.copy()
            m5_session.index = self._index_to_target_timezone(
                m5_series.index,
                getattr(self, 'session_time_zone', 'UTC'),
                getattr(self, 'session_time_offset_hours', None),
            )
            m5_session.sort_index(inplace=True)
        except Exception:
            m5_session = m5_series

        session_day = None
        try:
            session_day = idx_session.date()
        except Exception:
            session_day = None

        # Sweep events are defined over London window (08:00-14:00) in session TZ.
        sweep_high_time = None
        sweep_low_time = None
        try:
            if session_day is not None and asia_high is not None and asia_low is not None and len(m5_session) > 0:
                m5_day = m5_session[m5_session.index.date == session_day]
                sweep_start = self._parse_hhmm(self._cfg('ASIA_SWEEP_SWEEP_START', self._cfg('ASIA_SWEEP_LONDON_START', '08:00')), '08:00')
                sweep_end = self._parse_hhmm(self._cfg('ASIA_SWEEP_SWEEP_END', self._cfg('ASIA_SWEEP_LONDON_END', '14:00')), '14:00')
                m5_london = m5_day.between_time(sweep_start, sweep_end)

                if not m5_london.empty:
                    sh = m5_london[m5_london['high'] > float(asia_high)]
                    sl = m5_london[m5_london['low'] < float(asia_low)]
                    if not sh.empty:
                        sweep_high_time = sh.index[0]
                    if not sl.empty:
                        sweep_low_time = sl.index[0]
        except Exception:
            sweep_high_time = None
            sweep_low_time = None

        sweep_high = bool(sweep_high_time is not None)
        sweep_low = bool(sweep_low_time is not None)

        # Fallback to persisted sweep memory if today's bars don't include the sweep anymore.
        try:
            if (not sweep_high and not sweep_low) and isinstance(self.state.get('sweeps'), dict):
                mem = self.state['sweeps'].get(symbol)
                if isinstance(mem, dict) and mem.get('session_day') == (session_day.isoformat() if hasattr(session_day, 'isoformat') else str(session_day)):
                    mem_dir = str(mem.get('dir') or '').strip().lower()
                    mem_time = mem.get('time')
                    if mem_dir in ('high', 'low') and mem_time:
                        t_utc = pd.to_datetime(mem_time)
                        if getattr(t_utc, 'tz', None) is None:
                            t_utc = t_utc.tz_localize('UTC')
                        else:
                            t_utc = t_utc.tz_convert('UTC')
                        t_sess = self._to_target_timezone(
                            t_utc,
                            getattr(self, 'session_time_zone', 'UTC'),
                            getattr(self, 'session_time_offset_hours', None),
                        )
                        if mem_dir == 'high':
                            sweep_high_time = t_sess
                            sweep_high = True
                        else:
                            sweep_low_time = t_sess
                            sweep_low = True
        except Exception:
            pass

        # Persist latest sweep event in state so polling cadence can't miss it.
        try:
            if sweep_high or sweep_low:
                candidates = []
                if sweep_high_time is not None:
                    candidates.append(('high', sweep_high_time))
                if sweep_low_time is not None:
                    candidates.append(('low', sweep_low_time))
                # Choose earliest sweep for the day (as per spec).
                candidates.sort(key=lambda x: x[1])
                sdir, stime = candidates[0]
                try:
                    stime_utc = stime.tz_convert('UTC') if getattr(stime, 'tz', None) is not None else stime
                except Exception:
                    stime_utc = stime
                self.state.setdefault('sweeps', {})[symbol] = {
                    'dir': sdir,
                    'time': stime_utc.isoformat() if getattr(stime_utc, 'isoformat', None) else str(stime_utc),
                    'session_day': session_day.isoformat() if hasattr(session_day, 'isoformat') else str(session_day),
                }
                self._save_state()
        except Exception:
            pass

        signal = {
            'timestamp': idx_utc.isoformat(),
            'timestamp_session': idx_session.isoformat(),
            'timestamp_local': idx_local.isoformat(),
            'session_tz': getattr(self, 'session_time_zone', 'UTC'),
            'local_tz': getattr(self, 'time_zone', 'UTC'),
            'symbol': symbol,
            'current_price': float(last_bar['close']),
            'asia_high': asia_high,
            'asia_low': asia_low,
            'eqh_liquidity_pool': eqh_count > 1,  # True if multiple bars touched the high
            'eql_liquidity_pool': eql_count > 1,  # True if multiple bars touched the low
            'eqh_touch_count': eqh_count,
            'eql_touch_count': eql_count,
            'in_london': in_london,
            'in_asia': in_asia,
            'in_london_local': in_london_local,
            'in_asia_local': in_asia_local,
            'sweep_high': sweep_high,
            'sweep_low': sweep_low,
            'm5': m5.iloc[-1].to_dict() if len(m5) else {},
            'mss': mss,
            'fib_ratio': fib_ratio,
            'fib_long': fib_long,
            'fib_short': fib_short,
            'note': 'pure Asia Sweep v1 (0.71 fib, M5 MSS)'
        }

        traded = self.state.get('tradedToday', {}).get(symbol, False)
        signal['skipped_tradedToday'] = bool(traded)

        # Gate breakdown + qualification using sweep->MSS confirmation window.
        gates = {
            'in_london': bool(in_london),
            'skipped_tradedToday': bool(traded),
            'confirm_window_bars': int(confirm_window_bars),
            'mss_lookback': int(mss_lookback),
            'sweep_dir': None,
            'sweep_time': None,
            'mss_dir': None,
            'mss_time': None,
            'pending_confirmation': False,
        }

        trade_setup = {'valid': False, 'reason': None}

        # Determine the primary sweep (for status) as the earliest sweep found.
        sweep_dir = None
        sweep_time = None
        try:
            candidates = []
            if sweep_high_time is not None:
                candidates.append(('high', sweep_high_time))
            if sweep_low_time is not None:
                candidates.append(('low', sweep_low_time))
            if candidates:
                candidates.sort(key=lambda x: x[1])
                sweep_dir, sweep_time = candidates[0]
        except Exception:
            sweep_dir, sweep_time = None, None

        if sweep_time is not None and sweep_dir is not None:
            gates['sweep_dir'] = str(sweep_dir)
            gates['sweep_time'] = sweep_time.isoformat()

        # If we can’t trade now, set deterministic reason and stop early (but still emit gates).
        if traded:
            trade_setup['reason'] = 'Already traded today'
        elif not in_london:
            trade_setup['reason'] = 'Not in London window'
        else:
            # Find confirmation MSS after each sweep within the window.
            try:
                m5_day = m5_session[m5_session.index.date == session_day] if session_day is not None else m5_session
                london_start = self._parse_hhmm(self._cfg('ASIA_SWEEP_LONDON_START', '08:00'), '08:00')
                london_end = self._parse_hhmm(self._cfg('ASIA_SWEEP_LONDON_END', '14:00'), '14:00')
                m5_london = m5_day.between_time(london_start, london_end)
            except Exception:
                m5_london = None

            long_confirm = None
            short_confirm = None

            if isinstance(m5_london, pd.DataFrame) and not m5_london.empty:
                # Long: sweep low then bull MSS.
                if sweep_low_time is not None:
                    try:
                        win_end = sweep_low_time + pd.Timedelta(minutes=5 * int(confirm_window_bars))
                        bull = m5_london[(m5_london.index >= sweep_low_time) & (m5_london.index <= win_end) & (m5_london['bullMSS'] == True)]
                        if not bull.empty:
                            long_confirm = bull.index[0]
                    except Exception:
                        long_confirm = None

                # Short: sweep high then bear MSS.
                if sweep_high_time is not None:
                    try:
                        win_end = sweep_high_time + pd.Timedelta(minutes=5 * int(confirm_window_bars))
                        bear = m5_london[(m5_london.index >= sweep_high_time) & (m5_london.index <= win_end) & (m5_london['bearMSS'] == True)]
                        if not bear.empty:
                            short_confirm = bear.index[0]
                    except Exception:
                        short_confirm = None

            # Choose earliest confirmation if both exist.
            chosen = None
            if long_confirm is not None and short_confirm is not None:
                chosen = ('Long', long_confirm) if long_confirm <= short_confirm else ('Short', short_confirm)
            elif long_confirm is not None:
                chosen = ('Long', long_confirm)
            elif short_confirm is not None:
                chosen = ('Short', short_confirm)

            if chosen is not None:
                side, confirm_time = chosen
                gates['mss_dir'] = 'bull' if side == 'Long' else 'bear'
                gates['mss_time'] = confirm_time.isoformat()

                # Use confirmation candle range for entry/SL.
                try:
                    row = m5_london.loc[confirm_time]
                    c_low = float(row['low'])
                    c_high = float(row['high'])
                    rng = (c_high - c_low)

                    if side == 'Long':
                        entry = c_low + (rng * fib_ratio)
                        stop = c_low
                        tp = asia_high
                        method = 'SweepLow->BullMSS+0.71'
                        signal['fib_long'] = entry
                    else:
                        entry = c_high - (rng * fib_ratio)
                        stop = c_high
                        tp = asia_low
                        method = 'SweepHigh->BearMSS+0.71'
                        signal['fib_short'] = entry

                    trade_setup = {
                        'valid': True,
                        'type': side,
                        'entry': float(entry),
                        'stop_loss': float(stop),
                        'take_profit': float(tp) if tp is not None else None,
                        'method': method,
                    }
                except Exception:
                    trade_setup = {'valid': False, 'reason': 'Qualified but failed to compute trade levels'}
            else:
                # No confirmation yet: pending vs expired depends on whether we are still inside the window.
                if sweep_time is None:
                    trade_setup['reason'] = 'No sweep yet'
                else:
                    try:
                        win_end = sweep_time + pd.Timedelta(minutes=5 * int(confirm_window_bars))
                        if idx_session <= win_end:
                            gates['pending_confirmation'] = True
                            trade_setup['reason'] = 'Sweep seen; waiting for MSS confirmation'
                        else:
                            trade_setup['reason'] = 'Sweep expired (no MSS within window)'
                    except Exception:
                        trade_setup['reason'] = 'Sweep seen; waiting for MSS confirmation'

        signal['trade_setup'] = trade_setup
        signal['gates'] = gates

        # Emit and optionally mark tradedToday when submitting (dry-run: still mark as per spec)
        # Pre-trade checks and sizing (dry-run mode: compute and log, don't send orders)
        pretrade = {'passed': False, 'reason': None, 'lots': None, 'rr': None}
        if trade_setup.get('valid') and not traded:
            # compute RR
            try:
                entry = float(trade_setup['entry'])
                stop = float(trade_setup['stop_loss'])
                tp = float(trade_setup['take_profit']) if trade_setup.get('take_profit') is not None else None
                if tp and entry != stop:
                    rr = (abs(tp - entry) / abs(entry - stop)) if abs(entry - stop) > 0 else None
                else:
                    rr = None
                pretrade['rr'] = rr
            except Exception:
                pretrade['rr'] = None

            admin = self._load_admin_settings()
            rr_min = admin.get('rr_min', 1.5)
            rr_max = admin.get('rr_max', 10.0)

            if pretrade['rr'] is None:
                pretrade['passed'] = False
                pretrade['reason'] = 'RR calculation failed or missing TP/SL'
            elif pretrade['rr'] < rr_min or pretrade['rr'] > rr_max:
                pretrade['passed'] = False
                pretrade['reason'] = f'RR {pretrade["rr"]} outside bounds [{rr_min},{rr_max}]'
            else:
                # compute lots (best-effort)
                lots = self._compute_lots(symbol, entry, stop, risk_pct=self.risk_pct)
                pretrade['lots'] = lots

                # compute distance and ticks if point info available
                try:
                    point = float(df['point'].iloc[-1]) if 'point' in df.columns else None
                except Exception:
                    point = None

                try:
                    distance = abs(entry - stop)
                except Exception:
                    distance = None

                distance_ticks = None
                if distance is not None and point:
                    try:
                        distance_ticks = distance / point
                    except Exception:
                        distance_ticks = None

                pretrade['distance'] = distance
                pretrade['distance_ticks'] = distance_ticks
                pretrade['point'] = point

                # Try to estimate required margin using live helper if available
                est_margin = None
                balance = None
                try:
                    import live_entry_bot_mt5 as leb
                    try:
                        acct = leb._get_total_portfolio_risk()
                        balance = acct.get('equity') if isinstance(acct, dict) else None
                    except Exception:
                        try:
                            balance = leb.mt5.account_info().balance
                        except Exception:
                            balance = None

                    # leb._order_calc_margin(request) expects order params; we approximate using volume from lots
                    if hasattr(leb, '_order_calc_margin') and lots is not None:
                        try:
                            # Build a minimal request dict for margin calc (symbol, volume, price)
                            req = {'symbol': symbol, 'volume': float(lots), 'price': float(entry)}
                            est = leb._order_calc_margin('BUY' if trade_setup.get('type') == 'Long' else 'SELL', symbol, float(lots), float(entry))
                            est_margin = float(est) if est is not None else None
                        except Exception:
                            est_margin = None
                except Exception:
                    est_margin = None

                pretrade['estimated_margin'] = est_margin
                pretrade['balance'] = balance

                # Additional gating checks
                auto_state = self._load_auto_state()
                # If live mode and auto-trade disabled globally, block
                if (not self.dry_run) and (not auto_state.get('auto_trade', False)):
                    pretrade['passed'] = False
                    pretrade['reason'] = 'Auto-trade globally disabled'
                    self._audit(symbol, 'pretrade_block', {'reason': pretrade['reason']})
                else:
                    # enforce max open positions if admin sets a cap
                    max_open = admin.get('max_open_positions') or admin.get('max_total_open_positions')
                    open_count = len([s for s, v in self.state.get('tradedToday', {}).items() if v])
                    if max_open and open_count >= int(max_open):
                        pretrade['passed'] = False
                        pretrade['reason'] = f'max_open_positions reached ({open_count}/{max_open})'
                        self._audit(symbol, 'pretrade_block', {'reason': pretrade['reason'], 'open_count': open_count})
                    else:
                        # margin safety: require estimated margin to be within available balance * buffer
                        try:
                            buffer_mul = float(admin.get('margin_safety_buffer', 1.0))
                        except Exception:
                            buffer_mul = 1.0
                        if pretrade.get('estimated_margin') is not None and pretrade.get('balance') is not None:
                            try:
                                if float(pretrade['estimated_margin']) > float(pretrade['balance']) * buffer_mul:
                                    pretrade['passed'] = False
                                    pretrade['reason'] = 'Insufficient free margin per safety buffer'
                                    self._audit(symbol, 'pretrade_block', {'reason': pretrade['reason'], 'estimated_margin': pretrade.get('estimated_margin'), 'balance': pretrade.get('balance'), 'buffer_mul': buffer_mul})
                                else:
                                    pretrade['passed'] = True
                                    pretrade['reason'] = 'Pre-trade checks passed'
                            except Exception:
                                pretrade['passed'] = True
                                pretrade['reason'] = 'Pre-trade checks passed (margin eval skipped)'
                        else:
                            # no margin info, allow but audit
                            pretrade['passed'] = True
                            pretrade['reason'] = 'Pre-trade checks passed (no margin info)'

                # sizing enforcement: cap lots to admin limits
                try:
                    max_lot = float(admin.get('max_lot', admin.get('max_per_trade_lot', admin.get('default_lot', 0.01))))
                except Exception:
                    max_lot = None
                if pretrade.get('lots') is not None and max_lot is not None:
                    try:
                        if float(pretrade['lots']) > float(max_lot):
                            self._audit(symbol, 'sizing_cap', {'requested_lots': pretrade.get('lots'), 'capped_to': max_lot})
                            pretrade['lots'] = float(max_lot)
                    except Exception:
                        pass

                # Notifications: inform admin of pretrade pass/fail and simulated order
                try:
                    # try to use live_entry_bot_mt5 notification helpers
                    import live_entry_bot_mt5 as leb
                    try:
                        # send signal (won't send if dry_run)
                        leb.send_telegram_signal({'symbol': symbol, 'side': trade_setup.get('type'), 'entry': trade_setup.get('entry'), 'tp': trade_setup.get('take_profit'), 'sl': trade_setup.get('stop_loss'), 'rr': pretrade.get('rr'), 'timestamp': datetime.utcnow().isoformat()}, dry_run=self.dry_run)
                    except Exception:
                        pass
                except Exception:
                    # fallback to launcher.send_telegram for admin alert
                    try:
                        import launcher as _launcher
                        msg = f"AsiaSweep {symbol}: pretrade={'passed' if pretrade.get('passed') else 'blocked'}; reason={pretrade.get('reason')}" \
                              f"; lots={pretrade.get('lots')} rr={pretrade.get('rr')}"
                        _launcher.send_telegram(msg, destination='admin')
                    except Exception:
                        pass

            signal['pretrade'] = pretrade

            # Ensure reason is populated for blocked pretrades (helpful for audits/tests)
            if not pretrade.get('passed') and not pretrade.get('reason'):
                try:
                    auto_state = self._load_auto_state()
                    if (not self.dry_run) and (not auto_state.get('auto_trade', True)):
                        pretrade['reason'] = 'Auto-trade globally disabled'
                        self._audit(symbol, 'pretrade_block', {'reason': pretrade['reason']})
                    else:
                        pretrade['reason'] = 'Pretrade blocked'
                except Exception:
                    pretrade['reason'] = 'Pretrade blocked'

            # Emit, log order (dry-run or simulated) and mark tradedToday when submitting
            self._emit_signal(signal)
            if pretrade.get('passed'):
                try:
                    self._submit_order(symbol, trade_setup, pretrade)
                except Exception:
                    pass
                self.state.setdefault('tradedToday', {})[symbol] = True
                self._save_state()
            return signal

        # always emit trace when not a qualifying trade
        # ensure non-qualifying traces include a reason for diagnostics
        if not pretrade.get('reason'):
            if not trade_setup.get('valid'):
                pretrade['reason'] = trade_setup.get('reason') or 'Not qualified'
            else:
                pretrade['reason'] = pretrade.get('reason') or 'Not executed'
        signal['pretrade'] = pretrade
        self._emit_signal(signal)
        return signal

    def run(self, symbols: Optional[List[str]] = None) -> List[dict]:
        symbols = symbols or self.symbols
        results = []
        for sym in symbols:
            try:
                r = self.generate_for_symbol(sym)
                if r is not None:
                    results.append(r)
            except Exception as e:
                results.append({'symbol': sym, 'error': str(e)})
        return results

    def run_live(self, interval_seconds: int = 60, once: bool = False, symbols: Optional[List[str]] = None):
        """Run the strategy in a loop suitable for live execution.

        - Calls `generate_for_symbol` which handles pretrade checks and submission.
        - Respects `self.dry_run` (default True). If not dry_run, ensure MT5 helpers initialized.
        - `once=True` will run a single pass and return.
        """
        symbols = symbols or self.symbols
        if not symbols:
            return

        # Ensure MT5 helpers available when live
        if not self.dry_run:
            try:
                self.leb = self._init_mt5(live=True) or getattr(self, 'leb', None)
            except Exception:
                pass

        try:
            while True:
                start = datetime.now(timezone.utc)
                results = []
                for sym in symbols:
                    try:
                        r = self.generate_for_symbol(sym)
                        results.append({'symbol': sym, 'result': r})
                    except Exception as e:
                        results.append({'symbol': sym, 'error': str(e)})

                # audit loop completion
                self._audit('run_live', 'loop_complete', {'timestamp': start.isoformat(), 'processed': len(results)})

                if once:
                    return results

                # Sleep until next iteration
                try:
                    time.sleep(max(1, int(interval_seconds)))
                except Exception:
                    break
        except KeyboardInterrupt:
            return


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Asia Sweep London MSS 0.71 dry-run')
    parser.add_argument('--symbols', nargs='*', help='Symbols to process (e.g. EURUSD USDJPY)')
    args = parser.parse_args()

    strategy = AsiaSweepStrategy(symbols=args.symbols)
    out = strategy.run()
    print(f"Processed {len(out)} symbols")
