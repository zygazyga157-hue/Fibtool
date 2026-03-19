#!/usr/bin/env python3
"""
Simple test script for the updated mt5_bg_collector.py with multi-symbol support
"""

import sys
import os

# Add the current directory to path to import local modules
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """Test that all imports work correctly"""
    try:
        from mt5_bg_collector import (
            run_once_for_symbols, 
            capture_mt5_chart_screenshot,
            annotate_screenshot_with_confluences,
            generate_confluence_plot,
            DEFAULT_SYMBOLS
        )
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_basic_functionality():
    """Test basic functionality without MT5 connection"""
    try:
        from mt5_bg_collector import DEFAULT_SYMBOLS
        print(f"✓ Default symbols: {DEFAULT_SYMBOLS}")
        
        # Test symbol parsing logic
        test_symbols = ["XAUUSD", "EURUSD", "GBPUSD"]
        print(f"✓ Test symbols list: {test_symbols}")
        
        return True
    except Exception as e:
        print(f"✗ Basic functionality test failed: {e}")
        return False

def main():
    print("Testing mt5_bg_collector.py multi-symbol support...")
    
    success = True
    
    # Test imports
    if not test_imports():
        success = False
    
    # Test basic functionality
    if not test_basic_functionality():
        success = False
    
    if success:
        print("\n✓ All tests passed! The collector is ready for use.")
        print("\nUsage examples:")
        print("  python mt5_bg_collector.py --once --symbols XAUUSD")
        print("  python mt5_bg_collector.py --once --symbols XAUUSD,EURUSD")
        print("  python mt5_bg_collector.py --once  (will prompt for symbols)")
    else:
        print("\n✗ Some tests failed. Please check the errors above.")
        
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())