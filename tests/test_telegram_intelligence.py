#!/usr/bin/env python3
"""Test script for Telegram intelligence features."""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from live_entry_bot_mt5 import send_admin_notification, _build_telegram_signal_text, _build_ai_followup_text

def test_admin_notification():
    """Test admin notification functionality."""
    print("Testing admin notification...")
    
    # Test basic notification
    result1 = send_admin_notification("🧪 Test notification - Admin notifications are working!")
    print(f"Basic notification sent: {result1}")
    
    # Test order notification
    test_order = {
        "symbol": "XAUUSD",
        "side": "long",
        "price": 2650.50,
        "volume": 0.10,
        "result_retcode": "10009",
        "order": "12345",
        "deal": "67890"
    }
    
    result2 = send_admin_notification("✅ Test auto-trade executed", test_order)
    print(f"Order notification sent: {result2}")

def test_message_formatting():
    """Test signal and AI message formatting."""
    print("\nTesting message formatting...")
    
    test_signal = {
        'symbol': 'EURUSD',
        'timeframe': 'M15',
        'side': 'long',
        'entry_price': 1.0850,
        'tp': 1.0920,
        'sl': 1.0800,
        'rr': 1.4,
        'tp_dist_atr': 2.1,
        'sl_dist_atr': 1.5,
        'comment': 'Test signal for validation',
        'ai_summary': 'Buy signal with bullish momentum expected. Good entry at support level.',
        'ai_confidence': 78
    }
    
    main_msg = _build_telegram_signal_text(test_signal)
    ai_msg = _build_ai_followup_text(test_signal)
    
    print("Main signal message:")
    print(main_msg)
    print("\nAI follow-up message:")
    print(ai_msg)
    print(f"\nMessage lengths - Main: {len(main_msg)} chars, AI: {len(ai_msg)} chars")

if __name__ == "__main__":
    print("🧪 Testing Telegram Intelligence Features")
    print("=" * 50)
    
    test_admin_notification()
    test_message_formatting()
    
    print("\n✅ All tests completed!")
    print("\nKey improvements implemented:")
    print("• AI analysis messages reply to main signal (threaded)")
    print("• Admin notifications for all auto-trade executions")
    print("• Enhanced heartbeat with auto-trade status and activity")
    print("• Clean HTML formatting for all messages")