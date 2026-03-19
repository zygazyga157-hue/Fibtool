import json
from live_entry_bot_mt5 import _build_telegram_signal_text, _build_ai_followup_text

# Test with JSON AI summary
json_sig = {
    'symbol': 'USDJPY',
    'timeframe': 'H1',
    'side': 'long',
    'entry_price': 149.50,
    'tp': 150.20,
    'sl': 149.00,
    'rr': 1.4,
    'tp_dist_atr': 2.3,
    'sl_dist_atr': 1.6,
    'comment': 'Trend alignment (short & ultra term), pivot breakout',
    'ai_summary': json.dumps({'summary':'Buy signal with bullish momentum expected, good entry at support level','confidence':75}),
    'ai_confidence': 75
}

print("===== AI FOLLOW-UP WITH JSON SUMMARY =====")
print(_build_ai_followup_text(json_sig))
print()

# Test with raw text AI summary
text_sig = {
    'symbol': 'XAUUSD',
    'timeframe': 'H1',
    'side': 'short',
    'entry_price': 3684.29,
    'tp': 3626.69,
    'sl': 3703.06,
    'rr': 3.07,
    'tp_dist_atr': 6.4,
    'sl_dist_atr': 2.1,
    'comment': 'Trend alignment (short & ultra term), pivot breakout',
    'ai_summary': 'Short bias with pivot confirmation. Expected strong momentum if break continues. Watch news at 2 PM EST.',
    'ai_confidence': 88
}

print("===== AI FOLLOW-UP WITH RAW TEXT SUMMARY =====")
print(_build_ai_followup_text(text_sig))
