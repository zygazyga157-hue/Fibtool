import os
import json
from datetime import datetime, timedelta
import csv
import pytest

try:
    import pandas as pd
except Exception:
    pd = None

if pd is None:  # pragma: no cover
    pytest.skip("pandas not installed; skipping Asia Sweep strategy unit tests", allow_module_level=True)

# ensure repo root on path for imports
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from asia_sweep_london_mss import AsiaSweepStrategy


def _make_minute_bars_csv(path, start_dt: datetime, end_dt: datetime):
    rows = []
    t = start_dt
    while t <= end_dt:
        rows.append({'time': t.isoformat(), 'open': 100.0, 'high': 100.0, 'low': 100.0, 'close': 100.0})
        t = t + timedelta(minutes=1)
    # write CSV
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['time','open','high','low','close'])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def _write_rows_csv(path, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['time', 'open', 'high', 'low', 'close'])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def _set_output_paths(strategy: AsiaSweepStrategy, out_dir: Path):
    strategy.OUTPUT_DIR = str(out_dir)
    strategy.SIGNAL_JSONL = str(out_dir / 'asia_mss_signals.jsonl')
    strategy.SIGNAL_CSV = str(out_dir / 'asia_mss_signals.csv')
    strategy.STATE_FILE = str(out_dir / 'asia_mss_state.json')
    strategy.ORDERS_CSV = str(out_dir / 'asia_mss_orders.csv')


def test_submit_order_writes_csv(tmp_path):
    out = tmp_path / 'outputs'
    out.mkdir()
    # simple strategy instance
    s = AsiaSweepStrategy(symbols=['TEST'])
    _set_output_paths(s, out)
    s.configure(dry_run=True, order_size=0.02, log_orders=str(out / 'asia_mss_orders.csv'))

    # call _submit_order directly
    trade_setup = {'type': 'Long', 'entry': 1.23, 'stop_loss': 1.20, 'take_profit': 1.50, 'method': 'unit-test'}
    pretrade = {'lots': 0.01, 'rr': 3.0, 'estimated_margin': None, 'balance': None}
    s._submit_order('TEST', trade_setup, pretrade)

    orders = out / 'asia_mss_orders.csv'
    assert orders.exists(), 'orders CSV not written'
    txt = orders.read_text(encoding='utf-8')
    assert 'TEST' in txt and 'simulated' in txt


def test_pretrade_autostate_blocks_live(tmp_path):
    # Build minute bars covering Asia session and London so logic can run
    start = datetime(2026, 2, 7, 0, 0)
    end = datetime(2026, 2, 7, 8, 5)
    # build rows
    rows = []
    t = start
    while t <= end:
        rows.append({'time': t.isoformat(), 'open': 100.0, 'high': 100.0, 'low': 100.0, 'close': 100.0})
        t = t + timedelta(minutes=1)

    # Make Asia highs large and lows low to produce TP far away
    for r in rows:
        rt = datetime.fromisoformat(r['time'])
        if rt.time() >= datetime(2026,1,1,0,0).time() and rt.time() <= datetime(2026,1,1,7,59).time():
            r['high'] = 200.0
            r['low'] = 90.0

    # craft last block to create sweep_low and bullMSS
    rows[-6]['low'] = 85.0
    rows[-1]['close'] = 110.0

    out = tmp_path / 'outputs'
    out.mkdir()
    csvp = out / 'EURUSD_bars.csv'
    # write CSV
    with open(csvp, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['time','open','high','low','close'])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    s = AsiaSweepStrategy(symbols=['EURUSD'])
    _set_output_paths(s, out)
    # pretend live mode but auto_state disables global auto-trade
    (out / 'auto_state.json').write_text(json.dumps({'auto_trade': False}))
    s.configure(dry_run=False, order_size=0.01, log_orders=str(out / 'asia_mss_orders.csv'))

    res = s.generate_for_symbol('EURUSD')
    assert res is not None
    trade_setup = res.get('trade_setup') or {}
    pre = res.get('pretrade', {})
    # Either there was no qualifying trade_setup (acceptable) OR pretrade is blocked due to auto_state
    if trade_setup.get('valid'):
        # if a trade was qualified, pretrade must be blocked by auto_state
        assert pre.get('passed') is False
        assert 'Auto-trade' in (pre.get('reason') or '')
        assert not (out / 'asia_mss_orders.csv').exists()
    else:
        # no qualifying setup; ensure we haven't written orders
        assert not (out / 'asia_mss_orders.csv').exists()


def test_long_setup_uses_071_fib_with_m5_stop_and_asia_tp(tmp_path):
    start = datetime(2026, 2, 7, 0, 0)
    end = datetime(2026, 2, 7, 8, 4)
    rows = []
    t = start
    while t <= end:
        rows.append({'time': t.isoformat(), 'open': 100.0, 'high': 100.0, 'low': 100.0, 'close': 100.0})
        t = t + timedelta(minutes=1)

    # Asia baseline and a clear AsiaHigh.
    for r in rows:
        rt = datetime.fromisoformat(r['time'])
        if rt.hour < 8:
            r['open'] = 100.0
            r['high'] = 100.0
            r['low'] = 100.0
            r['close'] = 100.0
            if rt.hour == 2 and rt.minute == 0:
                r['high'] = 110.0

        # prior 3 completed M5 bars (07:45, 07:50, 07:55)
        if rt.hour == 7 and rt.minute >= 45:
            r['open'] = 100.2
            r['high'] = 101.0
            r['low'] = 100.0
            r['close'] = 100.4

    # Current M5 (08:00-08:04): sweep below AsiaLow and close above prior3 highs.
    curr = {
        0: (100.4, 101.0, 99.8, 100.2),
        1: (100.2, 102.0, 99.7, 100.8),
        2: (100.8, 103.0, 99.6, 101.5),
        3: (101.5, 104.0, 99.5, 102.2),
        4: (102.2, 104.0, 99.5, 103.0),
    }
    for r in rows:
        rt = datetime.fromisoformat(r['time'])
        if rt.hour == 8 and rt.minute in curr:
            o, h, l, c = curr[rt.minute]
            r['open'] = o
            r['high'] = h
            r['low'] = l
            r['close'] = c

    out = tmp_path / 'outputs'
    out.mkdir()
    _write_rows_csv(out / 'EURUSD_bars.csv', rows)

    s = AsiaSweepStrategy(symbols=['EURUSD'])
    _set_output_paths(s, out)
    s.configure(dry_run=True, order_size=0.01, time_zone='UTC', log_orders=str(out / 'asia_mss_orders.csv'))
    res = s.generate_for_symbol('EURUSD')

    assert res is not None
    ts = res.get('trade_setup') or {}
    assert ts.get('valid') is True
    assert ts.get('type') == 'Long'

    expected_entry = 99.5 + (104.0 - 99.5) * 0.71
    assert ts.get('entry') == pytest.approx(expected_entry)
    assert ts.get('stop_loss') == pytest.approx(99.5)
    assert ts.get('take_profit') == pytest.approx(110.0)
    assert res.get('fib_ratio') == pytest.approx(0.71)
    assert res.get('fib_long') == pytest.approx(expected_entry)


def test_short_setup_uses_071_fib_with_m5_stop_and_asia_tp(tmp_path):
    start = datetime(2026, 2, 7, 0, 0)
    end = datetime(2026, 2, 7, 8, 4)
    rows = []
    t = start
    while t <= end:
        rows.append({'time': t.isoformat(), 'open': 95.0, 'high': 99.0, 'low': 90.0, 'close': 95.0})
        t = t + timedelta(minutes=1)

    # Asia baseline and explicit boundaries.
    for r in rows:
        rt = datetime.fromisoformat(r['time'])
        if rt.hour < 8:
            r['open'] = 95.0
            r['high'] = 99.0
            r['low'] = 90.0
            r['close'] = 95.0
            if rt.hour == 3 and rt.minute == 0:
                r['high'] = 100.0  # AsiaHigh
            if rt.hour == 2 and rt.minute == 0:
                r['low'] = 80.0    # AsiaLow

        # prior 3 completed M5 bars (07:45, 07:50, 07:55)
        if rt.hour == 7 and rt.minute >= 45:
            r['open'] = 97.0
            r['high'] = 99.0
            r['low'] = 96.0
            r['close'] = 97.0

    # Current M5 (08:00-08:04): sweep above AsiaHigh and close below prior3 lows.
    curr = {
        0: (97.0, 100.0, 95.0, 96.5),
        1: (96.5, 101.0, 95.0, 95.8),
        2: (95.8, 101.0, 94.5, 95.4),
        3: (95.4, 101.0, 94.2, 95.1),
        4: (95.1, 101.0, 94.0, 95.0),
    }
    for r in rows:
        rt = datetime.fromisoformat(r['time'])
        if rt.hour == 8 and rt.minute in curr:
            o, h, l, c = curr[rt.minute]
            r['open'] = o
            r['high'] = h
            r['low'] = l
            r['close'] = c

    out = tmp_path / 'outputs'
    out.mkdir()
    _write_rows_csv(out / 'GBPUSD_bars.csv', rows)

    s = AsiaSweepStrategy(symbols=['GBPUSD'])
    _set_output_paths(s, out)
    s.configure(dry_run=True, order_size=0.01, time_zone='UTC', log_orders=str(out / 'asia_mss_orders.csv'))
    res = s.generate_for_symbol('GBPUSD')

    assert res is not None
    ts = res.get('trade_setup') or {}
    assert ts.get('valid') is True
    assert ts.get('type') == 'Short'

    expected_entry = 101.0 - (101.0 - 94.0) * 0.71
    assert ts.get('entry') == pytest.approx(expected_entry)
    assert ts.get('stop_loss') == pytest.approx(101.0)
    assert ts.get('take_profit') == pytest.approx(80.0)
    assert res.get('fib_ratio') == pytest.approx(0.71)
    assert res.get('fib_short') == pytest.approx(expected_entry)


def test_traded_today_resets_on_new_local_day(tmp_path):
    out = tmp_path / 'outputs'
    out.mkdir()
    _make_minute_bars_csv(out / 'EURUSD_bars.csv', datetime(2026, 2, 7, 0, 0), datetime(2026, 2, 7, 8, 4))

    s = AsiaSweepStrategy(symbols=['EURUSD'])
    _set_output_paths(s, out)
    s.configure(dry_run=True, time_zone='UTC', order_size=0.01, log_orders=str(out / 'asia_mss_orders.csv'))
    s.state = {'tradedToday': {'EURUSD': True}, 'tradedDate': '2026-02-06'}

    res = s.generate_for_symbol('EURUSD')
    assert res is not None
    assert res.get('skipped_tradedToday') is False
    assert s.state.get('tradedDate') == '2026-02-07'
    assert s.state.get('tradedToday', {}).get('EURUSD', False) is False


def test_session_timezone_dst_changes_london_window(tmp_path):
    out = tmp_path / 'outputs'
    out.mkdir()

    def _rows_until(ts_utc: datetime):
        rows = []
        t = ts_utc - timedelta(minutes=45)
        while t <= ts_utc:
            rows.append({'time': t.isoformat(), 'open': 100.0, 'high': 100.0, 'low': 100.0, 'close': 100.0})
            t = t + timedelta(minutes=1)
        return rows

    s = AsiaSweepStrategy(symbols=['EURUSD'])
    _set_output_paths(s, out)
    s.configure(
        dry_run=True,
        order_size=0.01,
        time_zone='UTC',
        session_time_zone='Europe/London',
        log_orders=str(out / 'asia_mss_orders.csv'),
    )

    # Winter: 07:30 UTC = 07:30 London (outside 08:00-14:00)
    _write_rows_csv(out / 'EURUSD_bars.csv', _rows_until(datetime(2026, 1, 15, 7, 30)))
    winter = s.generate_for_symbol('EURUSD')
    assert winter is not None
    assert winter.get('in_london') is False
    assert winter.get('session_tz') == 'Europe/London'

    # Summer: 07:30 UTC = 08:30 London (inside 08:00-14:00)
    _write_rows_csv(out / 'EURUSD_bars.csv', _rows_until(datetime(2026, 7, 15, 7, 30)))
    summer = s.generate_for_symbol('EURUSD')
    assert summer is not None
    assert summer.get('in_london') is True
    assert summer.get('session_tz') == 'Europe/London'


def test_long_qualifies_when_mss_after_sweep_within_window(tmp_path):
    # Build a sweep_low at 08:00 and delay bullMSS until 08:10 (still within 60m window).
    start = datetime(2026, 2, 7, 0, 0)
    end = datetime(2026, 2, 7, 8, 14)
    rows = []
    t = start
    while t <= end:
        rows.append({'time': t.isoformat(), 'open': 100.0, 'high': 100.0, 'low': 100.0, 'close': 100.0})
        t = t + timedelta(minutes=1)

    # Set AsiaHigh explicitly.
    for r in rows:
        rt = datetime.fromisoformat(r['time'])
        if rt.hour < 8:
            if rt.hour == 2 and rt.minute == 0:
                r['high'] = 110.0  # AsiaHigh

        # prev3 completed M5 highs (07:45, 07:50, 07:55)
        if rt.hour == 7 and rt.minute >= 45:
            r['high'] = 101.0
            r['low'] = 100.0
            r['close'] = 100.2

    # 08:00-08:04: sweep below AsiaLow (100), but no bullMSS yet (close <= prev3 max high 101)
    for r in rows:
        rt = datetime.fromisoformat(r['time'])
        if rt.hour == 8 and 0 <= rt.minute <= 4:
            r['high'] = 101.0
            r['low'] = 99.0  # sweep_low
            r['close'] = 100.5

    # 08:05-08:09: still no bullMSS
    for r in rows:
        rt = datetime.fromisoformat(r['time'])
        if rt.hour == 8 and 5 <= rt.minute <= 9:
            r['high'] = 101.2
            r['low'] = 100.0
            r['close'] = 100.7

    # 08:10-08:14: bullMSS confirmation candle (close breaks above prior highs)
    for r in rows:
        rt = datetime.fromisoformat(r['time'])
        if rt.hour == 8 and 10 <= rt.minute <= 14:
            r['high'] = 104.0
            r['low'] = 100.0
            r['close'] = 102.0  # bullMSS should trigger here

    out = tmp_path / 'outputs'
    out.mkdir()
    _write_rows_csv(out / 'EURUSD_bars.csv', rows)

    s = AsiaSweepStrategy(symbols=['EURUSD'])
    _set_output_paths(s, out)
    s.configure(dry_run=True, order_size=0.01, time_zone='UTC', session_time_zone='UTC', log_orders=str(out / 'asia_mss_orders.csv'))
    res = s.generate_for_symbol('EURUSD')
    assert res is not None

    ts = res.get('trade_setup') or {}
    assert ts.get('valid') is True
    assert ts.get('type') == 'Long'

    expected_entry = 100.0 + (104.0 - 100.0) * 0.71
    assert ts.get('entry') == pytest.approx(expected_entry)
    assert ts.get('stop_loss') == pytest.approx(100.0)
    assert ts.get('take_profit') == pytest.approx(110.0)

    gates = res.get('gates') or {}
    assert gates.get('pending_confirmation') is False
    assert (gates.get('sweep_dir') or '').lower() in ('low',)
    assert (gates.get('mss_dir') or '').lower() in ('bull',)


def test_short_qualifies_when_mss_after_sweep_within_window(tmp_path):
    # Build a sweep_high at 08:00 and delay bearMSS until 08:10 (still within 60m window).
    start = datetime(2026, 2, 7, 0, 0)
    end = datetime(2026, 2, 7, 8, 14)
    rows = []
    t = start
    while t <= end:
        rows.append({'time': t.isoformat(), 'open': 95.0, 'high': 99.0, 'low': 90.0, 'close': 95.0})
        t = t + timedelta(minutes=1)

    # Set AsiaLow explicitly for TP.
    for r in rows:
        rt = datetime.fromisoformat(r['time'])
        if rt.hour < 8:
            if rt.hour == 2 and rt.minute == 0:
                r['low'] = 80.0  # AsiaLow

        # prev3 completed M5 lows (07:45, 07:50, 07:55)
        if rt.hour == 7 and rt.minute >= 45:
            r['high'] = 99.0
            r['low'] = 96.0
            r['close'] = 97.0

    # 08:00-08:04: sweep above AsiaHigh (99), but no bearMSS yet (close >= prev3 min low 96)
    for r in rows:
        rt = datetime.fromisoformat(r['time'])
        if rt.hour == 8 and 0 <= rt.minute <= 4:
            r['high'] = 101.0  # sweep_high
            r['low'] = 96.0
            r['close'] = 96.8

    # 08:05-08:09: still no bearMSS
    for r in rows:
        rt = datetime.fromisoformat(r['time'])
        if rt.hour == 8 and 5 <= rt.minute <= 9:
            r['high'] = 100.8
            r['low'] = 96.2
            r['close'] = 96.7

    # 08:10-08:14: bearMSS confirmation candle (close breaks below prior lows)
    for r in rows:
        rt = datetime.fromisoformat(r['time'])
        if rt.hour == 8 and 10 <= rt.minute <= 14:
            r['high'] = 101.0
            r['low'] = 94.0
            r['close'] = 95.0  # bearMSS should trigger here vs prior min low ~96

    out = tmp_path / 'outputs'
    out.mkdir()
    _write_rows_csv(out / 'GBPUSD_bars.csv', rows)

    s = AsiaSweepStrategy(symbols=['GBPUSD'])
    _set_output_paths(s, out)
    s.configure(dry_run=True, order_size=0.01, time_zone='UTC', session_time_zone='UTC', log_orders=str(out / 'asia_mss_orders.csv'))
    res = s.generate_for_symbol('GBPUSD')
    assert res is not None

    ts = res.get('trade_setup') or {}
    assert ts.get('valid') is True
    assert ts.get('type') == 'Short'

    expected_entry = 101.0 - (101.0 - 94.0) * 0.71
    assert ts.get('entry') == pytest.approx(expected_entry)
    assert ts.get('stop_loss') == pytest.approx(101.0)
    assert ts.get('take_profit') == pytest.approx(80.0)

    gates = res.get('gates') or {}
    assert gates.get('pending_confirmation') is False
    assert (gates.get('sweep_dir') or '').lower() in ('high',)
    assert (gates.get('mss_dir') or '').lower() in ('bear',)


def test_pending_when_sweep_seen_but_mss_not_yet(tmp_path):
    start = datetime(2026, 2, 7, 0, 0)
    end = datetime(2026, 2, 7, 8, 10)
    rows = []
    t = start
    while t <= end:
        rows.append({'time': t.isoformat(), 'open': 95.0, 'high': 99.0, 'low': 90.0, 'close': 95.0})
        t = t + timedelta(minutes=1)

    # Ensure AsiaHigh is 99 (default highs), and create a sweep_high at 08:00 candle.
    for r in rows:
        rt = datetime.fromisoformat(r['time'])
        if rt.hour == 8 and 0 <= rt.minute <= 4:
            r['high'] = 101.0  # sweep_high
            r['low'] = 96.0
            r['close'] = 96.5   # avoid bearMSS

        # Keep prev3 lows low enough so close stays above trigger.
        if rt.hour == 7 and rt.minute >= 45:
            r['high'] = 99.0
            r['low'] = 96.0
            r['close'] = 97.0

        # IMPORTANT: avoid accidentally triggering bearMSS after the sweep.
        # If we leave default close=95.0 on 08:05, then close can fall below the prev3 lows (96.0)
        # and qualify a Short, which is not what this "pending" test intends.
        if rt.hour == 8 and rt.minute >= 5:
            r['high'] = 100.5
            r['low'] = 96.0
            r['close'] = 96.6

    out = tmp_path / 'outputs'
    out.mkdir()
    _write_rows_csv(out / 'EURUSD_bars.csv', rows)

    s = AsiaSweepStrategy(symbols=['EURUSD'])
    _set_output_paths(s, out)
    s.configure(dry_run=True, order_size=0.01, time_zone='UTC', session_time_zone='UTC', log_orders=str(out / 'asia_mss_orders.csv'))
    res = s.generate_for_symbol('EURUSD')
    assert res is not None

    ts = res.get('trade_setup') or {}
    assert ts.get('valid') is False
    assert ts.get('reason') == 'Sweep seen; waiting for MSS confirmation'

    gates = res.get('gates') or {}
    assert gates.get('pending_confirmation') is True
    assert (gates.get('sweep_dir') or '').lower() == 'high'


def test_sweep_expires_when_no_mss_in_window(tmp_path):
    start = datetime(2026, 2, 7, 0, 0)
    end = datetime(2026, 2, 7, 9, 10)  # > 60m after 08:00 sweep
    rows = []
    t = start
    while t <= end:
        rows.append({'time': t.isoformat(), 'open': 95.0, 'high': 99.0, 'low': 90.0, 'close': 95.0})
        t = t + timedelta(minutes=1)

    for r in rows:
        rt = datetime.fromisoformat(r['time'])
        if rt.hour == 8 and 0 <= rt.minute <= 4:
            r['high'] = 101.0  # sweep_high at 08:00
            r['low'] = 96.0
            r['close'] = 96.5  # avoid bearMSS

        # Keep everything else from ever producing bearMSS (close stays above prev lows).
        if rt.hour >= 8:
            r['low'] = 96.0
            r['close'] = 96.5

        if rt.hour == 7 and rt.minute >= 45:
            r['low'] = 96.0
            r['close'] = 97.0

    out = tmp_path / 'outputs'
    out.mkdir()
    _write_rows_csv(out / 'EURUSD_bars.csv', rows)

    s = AsiaSweepStrategy(symbols=['EURUSD'])
    _set_output_paths(s, out)
    s.configure(dry_run=True, order_size=0.01, time_zone='UTC', session_time_zone='UTC', log_orders=str(out / 'asia_mss_orders.csv'))
    res = s.generate_for_symbol('EURUSD')
    assert res is not None

    ts = res.get('trade_setup') or {}
    assert ts.get('valid') is False
    assert ts.get('reason') == 'Sweep expired (no MSS within window)'

    gates = res.get('gates') or {}
    assert gates.get('pending_confirmation') is False
    assert (gates.get('sweep_dir') or '').lower() == 'high'


def test_asia_range_uses_session_tz_for_day_rollover_summer(tmp_path):
    # Summer in London is UTC+1. Create bars where UTC day is previous day, but session day is next day.
    out = tmp_path / 'outputs'
    out.mkdir()

    rows = []
    t = datetime(2026, 7, 14, 23, 30)  # 00:30 London on 2026-07-15
    end = datetime(2026, 7, 15, 0, 10)
    while t <= end:
        rows.append({'time': t.isoformat(), 'open': 100.0, 'high': 100.0, 'low': 100.0, 'close': 100.0})
        t = t + timedelta(minutes=1)

    # Put a distinctive high inside what should be Asia session in session TZ.
    rows[5]['high'] = 123.0

    _write_rows_csv(out / 'EURUSD_bars.csv', rows)

    s = AsiaSweepStrategy(symbols=['EURUSD'])
    _set_output_paths(s, out)
    s.configure(dry_run=True, order_size=0.01, time_zone='UTC', session_time_zone='Europe/London', log_orders=str(out / 'asia_mss_orders.csv'))

    df = s.load_bars('EURUSD')
    asia_high, asia_low, eqh, eql = s._compute_asia_range(df)

    assert asia_high == pytest.approx(123.0)
    assert asia_low == pytest.approx(100.0)
    assert eqh >= 1 and eql >= 1
