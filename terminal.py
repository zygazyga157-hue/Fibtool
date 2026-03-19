from pathlib import Path
import os
import json
import csv
import argparse
from datetime import datetime
from playwright.sync_api import sync_playwright

OUT_CSV = Path("outputs/webterminalxauusd.csv")

def sanitize_credentials(login, password, server):
    if not login or not password or not server:
        raise ValueError("Missing login/password/server. Provide via --login/--password/--server or env vars WEBTERM_LOGIN / WEBTERM_PASS / WEBTERM_SERVER")
    return str(login), str(password), str(server)

def write_bars_to_csv(bars):
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    header = ["timestamp","open","high","low","close","volume","source_raw"]
    write_header = not OUT_CSV.exists()
    with OUT_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(header)
        for b in bars:
            w.writerow([
                b.get("timestamp"),
                b.get("open"),
                b.get("high"),
                b.get("low"),
                b.get("close"),
                b.get("volume"),
                json.dumps(b.get("raw", ""), ensure_ascii=False)
            ])

def try_extract_bars_from_payload(payload_text, target_symbol="XAUUSD"):
    # Heuristic JSON parse and extract known bar/candles shapes.
    # Return list of dicts like {timestamp, open, high, low, close, volume, raw}
    bars = []
    try:
        data = json.loads(payload_text)
    except Exception:
        # Not necessarily JSON — some frames are binary or compressed; skip
        return bars

    # Heuristics: check for common keys
    # 1) If payload contains 'candles' or 'bars' list
    if isinstance(data, dict):
        # adjust these keys to match the terminal's actual payload
        for key in ("candles", "bars", "ohlc", "rates"):
            if key in data and isinstance(data[key], list):
                for item in data[key]:
                    # try to find a symbol match
                    sym = (data.get("symbol") or data.get("instrument") or "").upper()
                    if target_symbol.upper() in sym or not sym:
                        # item could be [ts, o, h, l, c, v] or dict
                        if isinstance(item, list) and len(item) >= 5:
                            ts = item[0]
                            if isinstance(ts, (int, float)):
                                ts_iso = datetime.utcfromtimestamp(ts/1000 if ts>1e10 else ts).isoformat()
                            else:
                                ts_iso = str(ts)
                            bars.append({"timestamp": ts_iso, "open": item[1], "high": item[2], "low": item[3], "close": item[4], "volume": item[5] if len(item)>5 else None, "raw": item})
                        elif isinstance(item, dict):
                            ts = item.get("time") or item.get("timestamp") or item.get("t")
                            if ts:
                                try:
                                    ts_iso = datetime.utcfromtimestamp(int(ts)//1000 if int(ts)>1e10 else int(ts)).isoformat()
                                except Exception:
                                    ts_iso = str(ts)
                            else:
                                ts_iso = datetime.utcnow().isoformat()
                            bars.append({"timestamp": ts_iso, "open": item.get("open") or item.get("o"), "high": item.get("high") or item.get("h"), "low": item.get("low") or item.get("l"), "close": item.get("close") or item.get("c"), "volume": item.get("volume") or item.get("v"), "raw": item})
    # 2) Array of updates where each update has instrument and candle
    if isinstance(data, list):
        for element in data:
            if isinstance(element, dict):
                sym = (element.get("s") or element.get("symbol") or "").upper()
                if target_symbol.upper() in sym:
                    # check for candle inside
                    for key in ("candle","bar","bars","ohlc"):
                        if key in element:
                            item = element[key]
                            if isinstance(item, dict):
                                ts = item.get("time") or item.get("timestamp") or item.get("t")
                                ts_iso = datetime.utcnow().isoformat() if ts is None else str(ts)
                                bars.append({"timestamp": ts_iso, "open": item.get("o") or item.get("open"), "high": item.get("h") or item.get("high"), "low": item.get("l") or item.get("low"), "close": item.get("c") or item.get("close"), "volume": item.get("v") or item.get("volume"), "raw": item})
    return bars

def run(login, password, server, url="https://web.metatrader.app/terminal?lang=en", target_symbol="XAUUSD", duration_seconds=30, headless=False):
    collected = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        # Attach websocket listener
        def on_ws(ws):
            def on_frame(frame):
                try:
                    payload = frame.payload
                except Exception:
                    payload = None
                if not payload:
                    return
                # quick lowercase search for symbol to avoid expensive JSON parsing
                try:
                    low = payload.lower()
                except Exception:
                    low = ""
                if target_symbol.lower() in low or any(k in low for k in ("candles","ohlc","bars","candle","bar")):
                    bars = try_extract_bars_from_payload(payload, target_symbol=target_symbol)
                    if bars:
                        collected.extend(bars)
                        # flush to CSV periodically
                        write_bars_to_csv(bars)
            ws.on("framereceived", on_frame)
        context.on("websocket", on_ws)

        page.goto(url, wait_until="networkidle", timeout=60000)

        # Attempt multiple login selector strategies (login, password, server)
        # This is terminal-specific — adapt selectors if needed.
        try:
            # Try to fill server first if there's a server input or select
            try:
                # input[name="server"] or placeholder containing server
                if page.query_selector('input[name="server"]'):
                    page.fill('input[name="server"]', server)
                elif page.query_selector('input[placeholder*="Server"]'):
                    page.fill('input[placeholder*="Server"]', server)
                else:
                    # try select element
                    sel = page.query_selector('select[name="server"]')
                    if sel:
                        # try to pick option matching server string
                        try:
                            sel.select_option(value=server)
                        except Exception:
                            try:
                                sel.select_option(label=server)
                            except Exception:
                                pass
            except Exception:
                pass

            # Fill credentials into obvious fields
            username_filled = False
            password_filled = False
            try:
                if page.query_selector('input[name="username"]'):
                    page.fill('input[name="username"]', login)
                    username_filled = True
                if page.query_selector('input[name="login"]') and not username_filled:
                    page.fill('input[name="login"]', login)
                    username_filled = True
                if page.query_selector('input[placeholder="Login"]') and not username_filled:
                    page.fill('input[placeholder="Login"]', login)
                    username_filled = True
                if page.query_selector('input[name="password"]'):
                    page.fill('input[name="password"]', password)
                    password_filled = True
                if page.query_selector('input[placeholder="Password"]') and not password_filled:
                    page.fill('input[placeholder="Password"]', password)
                    password_filled = True
            except Exception:
                pass

            # If we didn't find explicit username/password fields, try a conservative fallback
            if not username_filled or not password_filled:
                pw = page.query_selector('input[type="password"]')
                if pw:
                    try:
                        # fill the first text input as username if available
                        text_inputs = page.query_selector_all('input[type="text"], input:not([type])')
                        if text_inputs and not username_filled:
                            try:
                                text_inputs[0].fill(login)
                                username_filled = True
                            except Exception:
                                pass
                        try:
                            pw.fill(password)
                            password_filled = True
                        except Exception:
                            pass
                    except Exception:
                        pass

            # Now pick a safe button to submit: avoid buttons that contain 'contact' or 'company'
            try:
                preferred_texts = ("connect", "sign in", "signin", "log in", "login", "submit")
                unsafe_keywords = ("contact", "company")

                # Search for buttons by textual match first
                clicked = False
                for txt in preferred_texts:
                    locator = page.query_selector(f"text=/{txt}/i")
                    if locator:
                        # ensure the button is not the 'contact company' type
                        try:
                            inner = (locator.inner_text() or "").lower()
                        except Exception:
                            inner = ""
                        if any(k in inner for k in unsafe_keywords):
                            continue
                        try:
                            locator.click()
                            clicked = True
                            break
                        except Exception:
                            continue

                # If none matched, search for generic buttons and avoid unsafe ones
                if not clicked:
                    buttons = page.query_selector_all('button')
                    for b in buttons:
                        try:
                            txt = (b.inner_text() or "").strip().lower()
                        except Exception:
                            txt = ""
                        if not txt:
                            continue
                        if any(k in txt for k in unsafe_keywords):
                            continue
                        # prefer buttons shorter than 30 chars to avoid verbose links
                        if len(txt) > 30:
                            continue
                        try:
                            b.click()
                            clicked = True
                            break
                        except Exception:
                            continue
                # last-resort: press Enter if fields were filled
                if not clicked and username_filled and password_filled:
                    try:
                        page.keyboard.press('Enter')
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            # continue — may be already logged in or different flow
            pass

        # Wait some time for web terminal to connect and stream
        page.wait_for_timeout(2000)

        # Optionally, open the XAUUSD chart programmatically by clicking search field
        # This is UI-specific. Try to open the symbol search and click the target symbol.
        try:
            # example: open symbol search and click the symbol text
            # adapt selectors as needed for terminal UI
            search_selector_candidates = [
                'input[placeholder*="symbol"]',
                'input[placeholder*="Search"]',
                'input[type="search"]'
            ]
            for sel in search_selector_candidates:
                if page.query_selector(sel):
                    page.fill(sel, target_symbol)
                    page.keyboard.press("Enter")
                    break
        except Exception:
            pass

        # Let network/websocket run and collect frames
        wait_ms = int(duration_seconds * 1000)
        page.wait_for_timeout(wait_ms)

        # cleanup
        browser.close()

    return collected

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch bars for XAUUSD from web. Use env WEBTERM_LOGIN/WEBTERM_PASS/WEBTERM_SERVER or pass --login/--password/--server")
    parser.add_argument("--login", help="web terminal login (or set WEBTERM_LOGIN)", default=os.getenv("WEBTERM_LOGIN"))
    parser.add_argument("--password", help="web terminal password (or set WEBTERM_PASS)", default=os.getenv("WEBTERM_PASS"))
    parser.add_argument("--server", help="web terminal server (or set WEBTERM_SERVER)", default=os.getenv("WEBTERM_SERVER"))
    parser.add_argument("--url", help="web terminal url", default="https://web.metatrader.app/terminal?lang=en")
    parser.add_argument("--symbol", help="symbol to capture", default="XAUUSD")
    parser.add_argument("--duration", help="seconds to listen", type=int, default=30)
    parser.add_argument("--headless", help="run headless", action="store_true")
    args = parser.parse_args()

    login, password, server = sanitize_credentials(args.login, args.password, args.server)
    bars = run(login, password, server, url=args.url, target_symbol=args.symbol, duration_seconds=args.duration, headless=args.headless)
    if bars:
        print(f"Collected {len(bars)} bars; last sample:")
        print(bars[-1])
    else:
        print("No bars collected. Tweak parsing heuristics or increase duration.")