import json
from live_entry_bot_mt5 import _build_telegram_signal_text, _render_ai_block

sig = {
    'symbol': 'XAUUSD',
    'timeframe': 'H1',
    'side': 'long',
    'entry_price': 3684.29,
    'tp': 3626.69,
    'sl': 3703.06,
    'rr': 3.07,
    'tp_dist_atr': 6.4,
    'sl_dist_atr': 2.1,
    'comment': 'Trend alignment (short & ultra term), pivot breakout',
}
# large AI
sig['ai_summary'] = 'A' * 2000
sig['ai_confidence'] = 60

print('--- MAIN TEXT (no AI) ---')
print(_build_telegram_signal_text(sig, include_ai=False))
print('\n--- AI BLOCK ---')
print(_render_ai_block(sig))
