import argparse
import csv
import json
import subprocess
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple

import requests

try:
    from config import TELEGRAM_BOT_TOKEN, TELEGRAM_GROUP_ID, TELEGRAM_ADMIN_ID
except Exception:
    TELEGRAM_BOT_TOKEN = None
    TELEGRAM_GROUP_ID = None
    TELEGRAM_ADMIN_ID = None
try:
    # Optional comma-separated extra heartbeat recipients
    from config import TELEGRAM_HEARTBEAT_EXTRA_IDS as _CFG_HEARTBEAT_EXTRA_IDS
except Exception:
    _CFG_HEARTBEAT_EXTRA_IDS = None

"""
Orchestrator for multi-symbol / multi-timeframe live_entry_bot_mt5.
- Reads allow-list from symbols_timeframes.json
- Supervises child processes with restart-on-crash (exponential backoff)
- Logs events to outputs/orchestrator_log.csv and status to outputs/orchestrator_status.json
- Sends periodic health heartbeat to Telegram (admin or group)
"""

ROOT = Path(__file__).parent
CONFIG = ROOT / "symbols_timeframes.json"
OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(parents=True, exist_ok=True)
ORCH_LOG = OUTPUTS / "orchestrator_log.csv"
ORCH_STATUS = OUTPUTS / "orchestrator_status.json"
ADMIN_SETTINGS = OUTPUTS / "admin_settings.json"
OUTPUT_DIR = OUTPUTS  # alias for compatibility in heartbeat code


def load_config():
    if not CONFIG.exists():
        return {"symbols": ["XAUUSD"], "timeframes": ["H1"]}
    with CONFIG.open("r", encoding="utf-8") as f:
        return json.load(f)


def log_event(event: str, symbol: str, timeframe: str, pid: int = 0, returncode: int = 0, retries: int = 0, message: str = ""):
    file_exists = ORCH_LOG.exists()
    with ORCH_LOG.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "timestamp", "event", "symbol", "timeframe", "pid", "returncode", "retries", "message"
        ])
        if not file_exists:
            w.writeheader()
        w.writerow({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "symbol": symbol,
            "timeframe": timeframe,
            "pid": pid,
            "returncode": returncode,
            "retries": retries,
            "message": message,
        })


def _load_admin_settings_local() -> dict:
    try:
        if ADMIN_SETTINGS.exists():
            with ADMIN_SETTINGS.open("r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _parse_extra_ids_csv(csv_like: str | None) -> list[str]:
    if not csv_like:
        return []
    try:
        parts = [p.strip() for p in str(csv_like).split(",") if p.strip()]
        return parts
    except Exception:
        return []


def _heartbeat_recipients(destination: str) -> list[str]:
    # base recipient
    base_id = TELEGRAM_ADMIN_ID if destination != "group" else TELEGRAM_GROUP_ID
    ids: list[str] = []
    if base_id:
        ids.append(str(base_id))
    # extras from admin settings
    s = _load_admin_settings_local()
    extra_list = s.get("heartbeat_extra_chat_ids")
    if isinstance(extra_list, list):
        ids.extend([str(x) for x in extra_list if x is not None])
    # extras from config/env
    env_csv = os.getenv("TELEGRAM_HEARTBEAT_EXTRA_IDS")
    if not env_csv and _CFG_HEARTBEAT_EXTRA_IDS:
        env_csv = _CFG_HEARTBEAT_EXTRA_IDS
    ids.extend(_parse_extra_ids_csv(env_csv))
    # dedupe preserving order
    dedup = []
    seen = set()
    for x in ids:
        if not x or x in seen:
            continue
        dedup.append(x)
        seen.add(x)
    return dedup


def _split_message(text: str, limit: int = 3900) -> list[str]:
    """Split text into chunks under the limit, trying to break on line boundaries."""
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    current = []
    current_len = 0
    for line in text.splitlines():
        # +1 for newline that we rejoin later
        l = len(line) + 1
        if current_len + l > limit and current:
            parts.append("\n".join(current))
            current = [line]
            current_len = l
        else:
            current.append(line)
            current_len += l
    if current:
        parts.append("\n".join(current))
    return parts


def send_telegram(text: str, destination: str = "admin") -> bool:
    token = TELEGRAM_BOT_TOKEN
    if not token:
        return False
    recipients = _heartbeat_recipients(destination)
    if not recipients:
        # log empty recipient resolution for visibility
        try:
            log_event("heartbeat_send", "*", "*", message=f"No recipients for dest={destination}")
        except Exception:
            pass
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    any_ok = False
    results: list[dict] = []
    chunks = _split_message(text, 3900)
    for chat_id in recipients:
        chat_any_ok = False
        for idx, chunk in enumerate(chunks, start=1):
            payload = {
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
            try:
                r = requests.post(url, json=payload, timeout=10)
                if r.status_code == 200:
                    any_ok = True
                    chat_any_ok = True
                results.append({"chat_id": str(chat_id), "part": idx, "status": r.status_code})
            except Exception as e:
                results.append({"chat_id": str(chat_id), "part": idx, "error": str(e)})
    # best-effort event log for diagnostics
    try:
        msg = json.dumps({"dest": destination, "recipients": recipients, "results": results})
        log_event("heartbeat_send", "*", "*", message=msg)
    except Exception:
        pass
    return any_ok


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--interval", type=int, default=60)
    p.add_argument("--risk-pct", type=float, default=1.0)
    p.add_argument("--confirm-window", type=int, default=0)
    p.add_argument("--st-period", type=int, default=14)
    p.add_argument("--st-multiplier", type=float, default=3.0)
    p.add_argument("--ut-atr-coef", type=float, default=2.0)
    p.add_argument("--ut-atr-len", type=int, default=1)
    p.add_argument("--allow-multiple", action="store_true")
    p.add_argument("--heartbeat-interval", type=int, default=300, help="Seconds between health heartbeats")
    p.add_argument("--heartbeat-dest", choices=["admin", "group", "off"], default="admin")
    p.add_argument("--max-retries", type=int, default=5)
    p.add_argument("--backoff-base", type=int, default=5, help="Seconds base for backoff")
    p.add_argument("--backoff-cap", type=int, default=300, help="Max seconds backoff")
    args = p.parse_args()

    cfg = load_config()
    symbols = cfg.get("symbols", ["XAUUSD"])  # edit symbols_timeframes.json to add more
    tfs = cfg.get("timeframes", ["H1"])      # edit symbols_timeframes.json to add more

    children: Dict[Tuple[str, str], dict] = {}

    def spawn(sym: str, tf: str, start_admin_poller: bool = False):
        cmd = [
            sys.executable,
            str(ROOT / "live_entry_bot_mt5.py"),
            "--symbol", sym,
            "--timeframe", tf,
            "--interval", str(args.interval),
            "--risk-pct", str(args.risk_pct),
            "--confirm-window", str(args.confirm_window),
            "--st-period", str(args.st_period),
            "--st-multiplier", str(args.st_multiplier),
            "--ut-atr-coef", str(args.ut_atr_coef),
            "--ut-atr-len", str(args.ut_atr_len),
        ]
        if args.allow_multiple:
            cmd.append("--allow-multiple")
        if start_admin_poller:
            cmd.append("--start-admin-poller")
        proc = subprocess.Popen(cmd)
        info = {
            "proc": proc,
            "cmd": cmd,
            "retries": 0,
            "last_start": time.time(),
            "next_start_after": 0.0,
            "has_admin_poller": start_admin_poller,
        }
        children[(sym, tf)] = info
        admin_note = " (with admin poller)" if start_admin_poller else ""
        log_event("spawn", sym, tf, pid=proc.pid, message=f"Launched{admin_note}")

    # initial spawn
    first_instance = True
    for sym in symbols:
        for tf in tfs:
            # Only the first instance should start the admin poller to avoid duplicate command handling
            spawn(sym, tf, start_admin_poller=first_instance)
            first_instance = False

    last_heartbeat = 0.0
    try:
        while True:
            # supervise
            for (sym, tf), info in list(children.items()):
                proc = info["proc"]
                rc = proc.poll()
                if rc is None:
                    continue  # still running
                # crashed or exited
                log_event("exit", sym, tf, pid=proc.pid, returncode=rc, retries=info["retries"], message="Child exited")
                if info["retries"] >= args.max_retries:
                    log_event("giveup", sym, tf, pid=proc.pid, returncode=rc, retries=info["retries"], message="Max retries reached")
                    # leave it stopped
                    del children[(sym, tf)]
                    continue
                # schedule restart with backoff
                info["retries"] += 1
                delay = min(args.backoff_cap, args.backoff_base * (2 ** (info["retries"] - 1)))
                info["next_start_after"] = time.time() + delay
                children[(sym, tf)] = info
                log_event("restart_scheduled", sym, tf, retries=info["retries"], message=f"Backoff {delay}s")

            # perform due restarts
            now = time.time()
            for (sym, tf), info in list(children.items()):
                if info.get("next_start_after", 0) and now >= info["next_start_after"] and info.get("proc") and info["proc"].poll() is not None:
                    spawn(sym, tf, start_admin_poller=info.get("has_admin_poller", False))

            # heartbeat
            if args.heartbeat_dest != "off" and (now - last_heartbeat) >= max(30, args.heartbeat_interval):
                last_heartbeat = now
                status = {}
                
                # Check auto-trade status
                try:
                    auto_state_path = OUTPUT_DIR / "auto_state.json"
                    with auto_state_path.open("r", encoding="utf-8") as f:
                        auto_state = json.load(f)
                    auto_trade_on = auto_state.get("auto_trade", False)
                except Exception:
                    auto_trade_on = False
                
                # Check recent activity from orders.csv
                recent_signals = 0
                recent_trades = 0
                try:
                    orders_path = OUTPUT_DIR / "orders.csv"
                    if orders_path.exists():
                        with orders_path.open("r", encoding="utf-8") as f:
                            lines = f.readlines()
                        # Count last 10 entries for recent activity
                        recent_entries = lines[-11:] if len(lines) > 10 else lines[1:] # Skip header
                        for line in recent_entries:
                            if line.strip() and not line.startswith("timestamp"):
                                parts = line.strip().split(",")
                                if len(parts) > 11:
                                    retcode = parts[11] if len(parts) > 11 else ""
                                    if retcode != "DRY-RUN":
                                        recent_signals += 1
                                    if retcode not in ("DRY-RUN", "AUTO-OFF", "INVALID-TP-SL", "INVALID-TP-SL-RR"):
                                        recent_trades += 1
                except Exception:
                    pass
                
                lines = [
                    "🤖 <b>Orchestrator Heartbeat</b>",
                    "",
                    f"🔄 <b>Auto-Trade:</b> {'ON' if auto_trade_on else 'OFF'}",
                    f"📊 <b>Recent Activity:</b> {recent_signals} signals, {recent_trades} trades",
                    "",
                    "<b>Process Status:</b>"
                ]
                
                for (sym, tf), info in children.items():
                    proc = info.get("proc")
                    pid = proc.pid if proc else 0
                    alive = proc.poll() is None if proc else False
                    retries = info.get("retries", 0)
                    uptime = int(now - info.get("last_start", now)) if alive else 0
                    status_key = f"{sym}|{tf}"
                    status[status_key] = {
                        "pid": pid,
                        "alive": alive,
                        "retries": retries,
                        "uptime_sec": uptime,
                    }
                    status_emoji = "✅" if alive else "❌"
                    lines.append(f"{status_emoji} <code>{sym} {tf}</code>: {'UP' if alive else 'DOWN'} | PID: {pid} | Retries: {retries} | Uptime: {uptime}s")
                
                # persist status json with auto-trade info
                status_data = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "auto_trade": auto_trade_on,
                    "recent_signals": recent_signals,
                    "recent_trades": recent_trades,
                    "status": status
                }
                with ORCH_STATUS.open("w", encoding="utf-8") as f:
                    json.dump(status_data, f, indent=2)
                    
                # send telegram heartbeat (admin by default)
                send_telegram("\n".join(lines), destination=args.heartbeat_dest)

            time.sleep(1)

    except KeyboardInterrupt:
        log_event("shutdown", "*", "*", message="Orchestrator interrupted")
        for (sym, tf), info in children.items():
            proc = info.get("proc")
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    log_event("terminate", sym, tf, pid=proc.pid, message="Sent terminate")
                except Exception:
                    pass


if __name__ == "__main__":
    main()
