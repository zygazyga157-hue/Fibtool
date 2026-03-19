import pandas as pd
import numpy as np
import math
import logging
from typing import Dict, List, Tuple, Optional, Union
from datetime import datetime

logger = logging.getLogger('FibSquareStrategy')

class FibonacciSquareOfNine:
    """
    Advanced trading strategy combining Square of Nine geometry with Fibonacci levels.
    This strategy implements the Square of Nine + Fibonacci Trading System with Time Analysis.
    """
    
    def __init__(self, point_value: Optional[float] = None, price_decimals: Optional[int] = None):
        """Initialize the Fibonacci Square of Nine strategy.
        
        Args:
            point_value: Instrument tick size (e.g., 0.01 for stocks, 0.0001 for FX). If provided and price_decimals is None,
                         decimals will be inferred from this value.
            price_decimals: Number of decimals to round prices to. If None, inferred from point_value when available,
                            otherwise defaults to 5.
        """
        # Standard Fibonacci ratios for price analysis
        self.fibonacci_levels = [
            0, 11.1, 18.79, 21.78, 28.12, 30.40, 33.3, 36.8, 38.2, 41.16, 46.01, 
            49.18, 50, 54.4, 61.12, 61.8, 66.6, 70.7, 72.53, 78.6, 88.6, 90, 
            92.2, 100, 111, 118, 122.43, 128.76, 133.3, 136.8, 138.2, 149.18, 
            154.4, 161.12, 161.8, 166.6, 170.7, 172.53, 178.6, 188.6, 190, 
            192.2, 200
        ]
        
        # Time Fibonacci mappings for Wyckoff cycle analysis
        self.time_fib_mapping = {
            0: 0,
            11.1: 29,
            18.79: 49,
            21.78: 57,
            28.12: 74,
            30.40: 80,
            33.3: 87,
            36.8: 96,
            38.2: 100,
            41.16: 108,
            46.01: 121,
            49.18: 129,
            54.4: 142,
            61.12: 160,
            61.8: 162,
            66.6: 174,
            70.7: 185,
            72.53: 190,
            78.6: 206,
            88.6: 232,
            90: 236,
            92.2: 241,
            100: 262,
            111: 291,
            118: 309,
            122.43: 321,
            128.76: 337,
            133.3: 349,
            136.8: 358,
            138.2: 362,
            149.18: 391,
            154.4: 405,
            161.12: 422,
            161.8: 424,
            170.7: 447,
            178.6: 468,
            192.2: 503,
            200: 524
        }
        
        # Degree to factor conversion for Square of Nine
        self.degree_to_factor = {
            22.5: 0.125,
            45.0: 0.25,
            90.0: 0.5,
            180.0: 1.0,
            270.0: 1.5,
            360.0: 2.0,
            450.0: 2.5,
            540.0: 3.0,
            630.0: 3.5,
            720.0: 4.0
        }

        # Precision settings
        self.point_value = point_value
        # Infer decimals from point if not explicitly set
        if price_decimals is None and point_value is not None and point_value > 0:
            try:
                self.price_decimals = max(0, int(round(-math.log10(point_value))))
            except Exception:
                self.price_decimals = 5
        else:
            self.price_decimals = 5 if price_decimals is None else int(price_decimals)

    def _round_price(self, price: float) -> float:
        try:
            return round(price, self.price_decimals)
        except Exception:
            return price

    def _get_point_value_from_df(self, df: pd.DataFrame) -> Optional[float]:
        if self.point_value is not None:
            return self.point_value
        if isinstance(df, pd.DataFrame) and 'point' in df.columns and len(df) > 0:
            try:
                return float(df['point'].iloc[-1])
            except Exception:
                return None
        return None
    
    def calculate_s9_levels(self, pivot_price: float, degrees: List[float] = None) -> Dict[float, float]:
        """
        Calculate Square of Nine support/resistance levels for given pivot price and degrees.
        
        Parameters:
        pivot_price (float): The pivot price (high or low) to use as base.
        degrees (List[float], optional): Degrees of rotation to calculate. 
                                        Defaults to [45.0, 90.0, 180.0, 270.0, 360.0].
        
        Returns:
        Dict[float, float]: Dictionary mapping degrees to calculated price levels.
        """
        if degrees is None:
            # Use the full mapping of known degrees by default (includes 22.5°, 45°, 90°, ..., 720°)
            try:
                degrees = sorted(list(self.degree_to_factor.keys()))
            except Exception:
                degrees = [22.5, 45.0, 90.0, 180.0, 270.0, 360.0, 450.0, 540.0, 630.0, 720.0]
        
        result = {}

        pivot_sqrt = math.sqrt(pivot_price)
        for degree in degrees:
            factor = self.degree_to_factor.get(degree)
            if factor is None:
                continue

            # Calculate resistance (adding factor)
            resistance = (pivot_sqrt + factor) ** 2
            result[degree] = self._round_price(resistance)

            # Calculate support (subtracting factor)
            support = (pivot_sqrt - factor) ** 2
            result[-degree] = self._round_price(support)
        
        return result
    
    def calculate_fib_price_levels(self, low: float, high: float) -> Dict[float, float]:
        """
        Calculate Fibonacci price levels for a given range.
        
        Parameters:
        low (float): The low price of the range (Fib 0%).
        high (float): The high price of the range (Fib 100%).
        
        Returns:
        Dict[float, float]: Dictionary mapping Fibonacci percentages to price levels.
        """
        price_range = high - low
        result = {}
        
        for fib in self.fibonacci_levels:
            price = low + (price_range * (fib / 100))
            result[fib] = self._round_price(price)
        
        return result
    
    def find_confluence_zones(self, fib_levels: Dict[float, float], s9_levels: Dict[float, float], 
                             tolerance: float = 5.0) -> List[Dict]:
        """
        Find confluence zones between Fibonacci and Square of Nine levels.
        
        Parameters:
        fib_levels (Dict[float, float]): Fibonacci price levels.
        s9_levels (Dict[float, float]): Square of Nine price levels.
        tolerance (float, optional): Maximum distance for strong confluence. Defaults to 5.0.
        
        Returns:
        List[Dict]: List of confluence zones with strength assessment.
        """
        # Convert S9 levels to a flat list of prices
        s9_prices = list(s9_levels.values())
        
        confluences = []
        for fib_pct, fib_price in fib_levels.items():
            # Find the closest S9 level
            closest_s9 = min(s9_prices, key=lambda s9: abs(s9 - fib_price))
            distance = abs(closest_s9 - fib_price)
            
            # Determine the S9 degree that produced this price (float-safe, nearest by value)
            nearest_degree = min(s9_levels.items(), key=lambda kv: abs(kv[1] - closest_s9))[0] if s9_levels else None
            s9_degree_str = f"{nearest_degree}°" if nearest_degree is not None else "unknown"
            
            # Determine confluence strength
            if distance == 0:
                strength = "Perfect"; strength_score = 4
            elif distance <= tolerance:
                strength = "Strong"; strength_score = 3
            elif distance <= tolerance * 1.5:
                strength = "Moderate"; strength_score = 2
            else:
                strength = "Weak"; strength_score = 1
            
            confluences.append({
                'fib_pct': fib_pct,
                'fib_price': fib_price,
                'nearest_s9': closest_s9,
                'distance': round(distance, 2),
                's9_degree': s9_degree_str,
                'strength': strength,
                'strength_score': strength_score
            })
        
        # Sort by strength (Perfect > Strong > Moderate > Weak)
        confluences.sort(key=lambda x: (-x['strength_score'], x['distance']))
        
        return confluences
    
    def identify_market_phase(self, df: pd.DataFrame, pivot_idx: int, is_accumulation: bool = True) -> Dict:
        """
        Identify Wyckoff market phase based on Time Fibonacci from a pivot point.
        
        Parameters:
        df (pd.DataFrame): DataFrame with price data.
        pivot_idx (int): Index of the pivot point (SC for accumulation, BC for distribution).
        is_accumulation (bool): True if analyzing accumulation, False for distribution.
        
        Returns:
        Dict: Information about current market phase.
        """
        if pivot_idx >= len(df):
            logger.error("Pivot index out of bounds")
            return {}
        
        # Number of bars since pivot
        current_idx = len(df) - 1
        bars_since_pivot = current_idx - pivot_idx
        
        # Calculate percentage of cycle - adjust based on timeframe
        # Determine timeframe based on the dataframe
        avg_time_diff = 60  # Default to minutes (assuming H1)
        if 'time' in df.columns:
            # Try to determine timeframe from data
            if len(df) > 5:
                time_diffs = []
                for i in range(1, 5):
                    if isinstance(df['time'].iloc[i], datetime) and isinstance(df['time'].iloc[i-1], datetime):
                        diff_seconds = (df['time'].iloc[i] - df['time'].iloc[i-1]).total_seconds()
                        time_diffs.append(diff_seconds)
                if time_diffs:
                    avg_time_diff = sum(time_diffs) / len(time_diffs) / 60  # Convert to minutes
        
        # Adjust cycle length based on estimated timeframe
        full_cycle = 262  # Base cycle length for H1
        
        if avg_time_diff <= 1:
            full_cycle = 262 * 60  # 1-minute timeframe
        elif avg_time_diff <= 5:
            full_cycle = 262 * 12  # 5-minute timeframe
        elif avg_time_diff <= 15:
            full_cycle = 262 * 4   # 15-minute timeframe
        elif avg_time_diff <= 30:
            full_cycle = 262 * 2   # 30-minute timeframe
        
        cycle_pct = min(100, (bars_since_pivot / full_cycle) * 100)
        
        # Identify the phase
        phase_info = {}
        
        if cycle_pct < 23:
            phase_name = "SC → AR" if is_accumulation else "BC → AR"
            phase_info = {
                'phase': phase_name,
                'time_zone': f"0-23%",
                'bars': f"0-61",
                'behavior': "Selling Climax → Automatic Rally" if is_accumulation else "Buying Climax → Automatic Reaction",
                'trading_focus': "No entry. Observe low test." if is_accumulation else "No short yet. Observe high test."
            }
        elif cycle_pct < 39:
            phase_name = "Phase 1" 
            phase_info = {
                'phase': phase_name,
                'time_zone': f"23-39%",
                'bars': f"61-101",
                'behavior': "Secondary Test near lows." if is_accumulation else "Secondary Test in Distribution (ST in D).",
                'trading_focus': "Watch for selling exhaustion." if is_accumulation else "Watch for buying exhaustion."
            }
        elif cycle_pct < 62:
            phase_name = "Phase 2"
            phase_info = {
                'phase': phase_name,
                'time_zone': f"39-62%",
                'bars': f"101-161",
                'behavior': "Sideways range. Higher lows forming." if is_accumulation else "Sideways range. Lower highs forming.",
                'trading_focus': "Conservative Long Entry near range lows." if is_accumulation else "Conservative Short Entry near range highs."
            }
        else:
            phase_name = "Phase 3"
            phase_info = {
                'phase': phase_name,
                'time_zone': f"62-100%",
                'bars': f"161-262",
                'behavior': "Springboard Breakout OR Terminal Shakeout" if is_accumulation else "Breakdown Launch OR Upthrust After Distribution",
                'trading_focus': "Aggressive Long Entry on breakout." if is_accumulation else "Aggressive Short Entry on breakdown."
            }
        
        phase_info.update(
            {
            'cycle_percentage': round(cycle_pct, 2),
            'bars_since_pivot': bars_since_pivot,
            'cycle_type': "Accumulation" if is_accumulation else "Distribution",
            'pivot_date': df.iloc[pivot_idx].name if isinstance(df.iloc[pivot_idx].name, pd.Timestamp) else None
        })
        
        return phase_info
    
    def find_pivot_points(self, df: pd.DataFrame, window: int = 20) -> Dict[str, List[int]]:
        """
        Find potential pivot points (highs and lows) in the price data.
        
        Parameters:
        df (pd.DataFrame): DataFrame with price data.
        window (int): Window size to identify local extremes.
        
        Returns:
        Dict[str, List[int]]: Dictionary with indices of pivot highs and lows.
        """
        highs = []
        lows = []
        
        for i in range(window, len(df) - window):
            # Check if this is a local maximum
            if df['high'].iloc[i] == max(df['high'].iloc[i-window:i+window+1]):
                highs.append(i)
            
            # Check if this is a local minimum
            if df['low'].iloc[i] == min(df['low'].iloc[i-window:i+window+1]):
                lows.append(i)
        
        return {'highs': highs, 'lows': lows}
    
    def generate_trade_setup(self, df: pd.DataFrame, market_phase: Dict, 
                            fib_levels: Dict[float, float], 
                            current_price: float, is_accumulation: bool = True,
                            max_entry_deviation_pct: float = 0.5,
                            max_entry_deviation_points: Optional[float] = None) -> Dict:
        """
        Generate trade setup based on market phase and Fibonacci levels.
        
        Parameters:
        df (pd.DataFrame): DataFrame with price data.
        market_phase (Dict): Current market phase information.
        fib_levels (Dict[float, float]): Fibonacci price levels.
        current_price (float): Current market price.
        is_accumulation (bool): True if in accumulation phase, False for distribution.
        
        Returns:
        Dict: Trade setup information including entry, stop loss, and take profit.
        """
        if not market_phase or not fib_levels:
            return {}
        
        # Convert to list of tuples for easier processing
        fib_list = [(pct, price) for pct, price in fib_levels.items()]
        fib_list.sort(key=lambda x: x[0])  # Sort by percentage
        
        # Entry level determination based on phase
        phase = market_phase.get('phase', '')
        
        # Default - no trade
        setup = {
            'valid': False,
            'reason': "No valid setup found for current phase"
        }
        
        def within_entry_tolerance(entry_level: float) -> bool:
            if entry_level is None:
                return False
            # Percent deviation check
            pct_dev = abs(current_price - entry_level) / entry_level * 100 if entry_level else float('inf')
            if pct_dev <= max_entry_deviation_pct:
                return True
            # Points deviation check (if provided)
            if max_entry_deviation_points is not None:
                if abs(current_price - entry_level) <= max_entry_deviation_points:
                    return True
            # If df has 'point', allow small multiple
            if 'point' in df:
                pt = float(df['point'].iloc[-1])
                if abs(current_price - entry_level) <= 10 * pt:
                    return True
            return False

        if is_accumulation:
            if "Phase 2" in phase:
                # Conservative long setup
                # Entry near 38.2% Fibonacci level in accumulation
                entry_fib = 38.2
                entry_level = fib_levels.get(entry_fib)
                
                # Find previous Fibonacci level for stop placement
                prev_fib_level = None
                for fib_pct, fib_price in fib_list:
                    if fib_pct >= entry_fib:
                        break
                    prev_fib_level = (fib_pct, fib_price)
                
                if entry_level and prev_fib_level and within_entry_tolerance(entry_level):
                    pv = self._get_point_value_from_df(df)
                    stop_level = prev_fib_level[1] - 2 * pv if pv else prev_fib_level[1] * 0.99
                    
                    # Take profit using Fibonacci extension
                    tp_fib = entry_fib * 1.618034
                    tp_level = None
                    
                    # Find nearest Fibonacci level to the calculated extension
                    for fib_pct, fib_price in fib_list:
                        if fib_pct > tp_fib:
                            tp_level = fib_price
                            break
                    
                    if not tp_level and fib_list:
                        tp_level = fib_list[-1][1]  # Use highest level if no match
                    
                    setup = {
                        'valid': True,
                        'type': 'Conservative Long',
                        'direction': 'BUY',
                        'entry': self._round_price(entry_level),
                        'stop_loss': self._round_price(stop_level),
                        'take_profit': self._round_price(tp_level) if tp_level else None,
                        'entry_fib': entry_fib,
                        'risk_pts': self._round_price(entry_level - stop_level),
                        'reward_pts': self._round_price(tp_level - entry_level) if tp_level else None,
                        'rr_ratio': round((tp_level - entry_level) / (entry_level - stop_level), 2) if tp_level and stop_level != entry_level else None
                    }
            
            elif "Phase 3" in phase:
                # Aggressive long setup on breakout
                # Entry above the high of recent consolidation
                
                # Use 61.8% as the typical breakout level in Phase 3
                entry_fib = 61.8
                entry_level = fib_levels.get(entry_fib)
                
                if entry_level and within_entry_tolerance(entry_level):
                    # Stop loss below the consolidation low (use Phase 2 low)
                    phase2_low = df['low'].iloc[-60:].min()  # Approximate
                    pv = self._get_point_value_from_df(df)
                    stop_level = (phase2_low - 2 * pv) if pv else (phase2_low * 0.99)
                    
                    # Take profit using Fibonacci extension
                    tp_fib = entry_fib * 1.618034
                    nearest_fib = min(self.fibonacci_levels, key=lambda x: abs(x - tp_fib))
                    tp_level = fib_levels.get(nearest_fib, entry_level * 1.1)
                    
                    setup = {
                        'valid': True,
                        'type': 'Aggressive Long',
                        'direction': 'BUY',
                        'entry': self._round_price(entry_level),
                        'stop_loss': self._round_price(stop_level),
                        'take_profit': self._round_price(tp_level),
                        'entry_fib': entry_fib,
                        'risk_pts': self._round_price(entry_level - stop_level),
                        'reward_pts': self._round_price(tp_level - entry_level),
                        'rr_ratio': round((tp_level - entry_level) / (entry_level - stop_level), 2) if stop_level != entry_level else None
                    }
        else:  # Distribution
            if "Phase 2" in phase:
                # Conservative short setup
                entry_fib = 61.8  # Sell at Fib 61.8 in distribution
                entry_level = fib_levels.get(entry_fib)
                
                # Find previous Fibonacci level for stop placement
                prev_fib_level = None
                for fib_pct, fib_price in reversed(fib_list):
                    if fib_pct <= entry_fib:
                        break
                    prev_fib_level = (fib_pct, fib_price)
                
                if entry_level and prev_fib_level and within_entry_tolerance(entry_level):
                    pv = self._get_point_value_from_df(df)
                    stop_level = prev_fib_level[1] + 2 * pv if pv else prev_fib_level[1] * 1.01
                    
                    # Take profit using Fibonacci contraction
                    tp_fib = entry_fib * 0.618034
                    tp_level = None
                    
                    # Find nearest Fibonacci level to the calculated contraction
                    for fib_pct, fib_price in reversed(fib_list):
                        if fib_pct < tp_fib:
                            tp_level = fib_price
                            break
                    
                    if not tp_level and fib_list:
                        tp_level = fib_list[0][1]  # Use lowest level if no match
                    
                    setup = {
                        'valid': True,
                        'type': 'Conservative Short',
                        'direction': 'SELL',
                        'entry': self._round_price(entry_level),
                        'stop_loss': self._round_price(stop_level),
                        'take_profit': self._round_price(tp_level) if tp_level else None,
                        'entry_fib': entry_fib,
                        'risk_pts': self._round_price(stop_level - entry_level),
                        'reward_pts': self._round_price(entry_level - tp_level) if tp_level else None,
                        'rr_ratio': round((entry_level - tp_level) / (stop_level - entry_level), 2) if tp_level and stop_level != entry_level else None
                    }
            
            elif "Phase 3" in phase:
                # Aggressive short setup on breakdown
                # Entry below the low of recent consolidation
                
                # Use 38.2% as the typical breakdown level in Phase 3 distribution
                entry_fib = 38.2
                entry_level = fib_levels.get(entry_fib)
                
                if entry_level and within_entry_tolerance(entry_level):
                    # Stop loss above the consolidation high (use Phase 2 high)
                    phase2_high = df['high'].iloc[-60:].max()  # Approximate
                    pv = self._get_point_value_from_df(df)
                    stop_level = (phase2_high + 2 * pv) if pv else (phase2_high * 1.01)
                    
                    # Take profit using Fibonacci contraction
                    tp_fib = entry_fib * 0.618034
                    nearest_fib = min(self.fibonacci_levels, key=lambda x: abs(x - tp_fib))
                    tp_level = fib_levels.get(nearest_fib, entry_level * 0.9)
                    
                    setup = {
                        'valid': True,
                        'type': 'Aggressive Short',
                        'direction': 'SELL',
                        'entry': self._round_price(entry_level),
                        'stop_loss': self._round_price(stop_level),
                        'take_profit': self._round_price(tp_level),
                        'entry_fib': entry_fib,
                        'risk_pts': self._round_price(stop_level - entry_level),
                        'reward_pts': self._round_price(entry_level - tp_level),
                        'rr_ratio': round((entry_level - tp_level) / (stop_level - entry_level), 2) if stop_level != entry_level else None
                    }
        
        # Add time info
        setup['market_phase'] = market_phase.get('phase', '')
        setup['cycle_percentage'] = market_phase.get('cycle_percentage', 0)
        
        return setup
    
    def detect_wyckoff_patterns(self, df: pd.DataFrame, lookback: int = 100) -> Dict:
        """
        Detect potential Wyckoff accumulation or distribution patterns.
        
        Parameters:
        df (pd.DataFrame): DataFrame with price data.
        lookback (int): Number of bars to analyze.
        
        Returns:
        Dict: Information about detected patterns.
        """
        if len(df) < lookback:
            return {'detected': False, 'reason': 'Not enough data'}
        
        # Get relevant section of data
        section = df.iloc[-lookback:]
        
        # Calculate some key metrics
        price_range = section['high'].max() - section['low'].min()
        range_percentage = price_range / section['low'].min() * 100
        
        # Simple pattern detection logic
        is_downtrend = section['close'].iloc[0] > section['close'].iloc[-20]
        is_sideways = range_percentage < 5  # Less than 5% range is considered sideways
        
        # Check if volume is declining
        volume_trend = None
        if 'volume' in section.columns:
            recent_vol_avg = section['volume'].iloc[-10:].mean()
            older_vol_avg = section['volume'].iloc[-30:-10].mean()
            volume_trend = 'declining' if recent_vol_avg < older_vol_avg else 'increasing'
        
        # Check for higher lows (accumulation) or lower highs (distribution)
        has_higher_lows = False
        has_lower_highs = False
        
        # Divide into segments to check for pattern
        segments = 3
        segment_size = len(section) // segments
        
        segment_lows = []
        segment_highs = []
        
        for i in range(segments):
            start = i * segment_size
            end = start + segment_size if i < segments - 1 else len(section)
            segment = section.iloc[start:end]
            segment_lows.append(segment['low'].min())
            segment_highs.append(segment['high'].max())
        
        has_higher_lows = segment_lows[0] < segment_lows[1] < segment_lows[2]
        has_lower_highs = segment_highs[0] > segment_highs[1] > segment_highs[2]
        
        # Pattern classification
        pattern = None
        confidence = 0.0
        
        if is_downtrend and is_sideways and has_higher_lows:
            pattern = 'Wyckoff Accumulation'
            confidence = 0.7
            pivot_label = section['low'].idxmin()
            try:
                pivot_idx = df.index.get_loc(pivot_label) if pivot_label in df.index else int(pivot_label)
            except Exception:
                # Fallback to last lookback bar position if label cannot be located
                pivot_idx = max(0, len(df) - len(section) + section['low'].values.argmin())
            is_accumulation = True
        elif not is_downtrend and is_sideways and has_lower_highs:
            pattern = 'Wyckoff Distribution'
            confidence = 0.7
            pivot_label = section['high'].idxmax()
            try:
                pivot_idx = df.index.get_loc(pivot_label) if pivot_label in df.index else int(pivot_label)
            except Exception:
                pivot_idx = max(0, len(df) - len(section) + section['high'].values.argmax())
            is_accumulation = False
        else:
            return {'detected': False, 'reason': 'No clear Wyckoff pattern detected'}
        
        # If volume data supports the pattern, increase confidence
        if volume_trend == 'declining' and pattern == 'Wyckoff Accumulation':
            confidence += 0.1
        elif volume_trend == 'increasing' and pattern == 'Wyckoff Distribution':
            confidence += 0.1
        
        return {
            'detected': True,
            'pattern': pattern,
            'confidence': min(confidence, 1.0),
            'pivot_idx': pivot_idx,
            'is_accumulation': is_accumulation,
            'price_range': price_range,
            'range_percentage': range_percentage,
            'volume_trend': volume_trend
        }
    
    def is_tradable(self, df: pd.DataFrame) -> bool:
        """
        Check if the current market conditions are suitable for this strategy
        
        Args:
            df: Market data DataFrame with OHLCV data
            
        Returns:
            Boolean indicating if the strategy should be traded now
        """
        # Make sure we have enough data
        if len(df) < 200:
            return False
            
        # Get basic market analysis
        analysis = self.analyze_market(df)
        
        # Check if we have a valid trade setup
        trade_setup = analysis.get('trade_setup', {})
        if not trade_setup.get('valid', False):
            return False
            
        # Check R:R ratio (higher for lower timeframes to filter noise)
        rr_ratio = trade_setup.get('rr_ratio', 0)
        
        # Determine approximate timeframe
        avg_time_diff = 60  # Default to minutes (assuming H1)
        if 'time' in df.columns:
            if len(df) > 5:
                time_diffs = []
                for i in range(1, 5):
                    if isinstance(df['time'].iloc[i], datetime) and isinstance(df['time'].iloc[i-1], datetime):
                        diff_seconds = (df['time'].iloc[i] - df['time'].iloc[i-1]).total_seconds()
                        time_diffs.append(diff_seconds)
                if time_diffs:
                    avg_time_diff = sum(time_diffs) / len(time_diffs) / 60  # Convert to minutes
        
        # Adjust minimum R:R ratio based on timeframe
        min_rr_ratio = 2.0  # Default
        if avg_time_diff <= 1:
            min_rr_ratio = 3.0  # More strict for M1
        elif avg_time_diff <= 5:
            min_rr_ratio = 2.5  # More strict for M5
        
        if rr_ratio < min_rr_ratio:
            return False
            
        # Check confluence strength (need stronger confluence for lower timeframes)
        confluence_zones = analysis.get('strong_confluence_zones', [])
        min_strength = 3
        
        if avg_time_diff <= 5:
            min_strength = 4  # Require stronger confluence for lower timeframes
            
        if not confluence_zones or confluence_zones[0].get('strength_score', 0) < min_strength:
            return False
            
        # Check market cycle phase
        cycle_type = analysis.get('market_phase', {}).get('cycle_type', '')
        # Only trade in accumulation or distribution cycles
        if str(cycle_type).lower() not in ('accumulation', 'distribution'):
            return False
            
        # Check volume conditions
        if 'volume' in df.columns:
            # We want above average volume, higher threshold for lower timeframes
            avg_volume = df['volume'].rolling(20).mean().iloc[-1]
            current_volume = df['volume'].iloc[-1]
            volume_multiplier = 1.2
            
            if avg_time_diff <= 5:
                volume_multiplier = 1.5  # Higher volume requirement for lower timeframes
                
            if current_volume < avg_volume * volume_multiplier:
                return False
        
        # For lower timeframes, check for noise and volatility
        if avg_time_diff <= 15:
            # Calculate ATR for volatility
            if 'high' in df.columns and 'low' in df.columns:
                # Simple ATR calculation
                high_low = df['high'] - df['low']
                high_close = abs(df['high'] - df['close'].shift())
                low_close = abs(df['low'] - df['close'].shift())
                true_ranges = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                atr = true_ranges.rolling(14).mean().iloc[-1]
                avg_atr = true_ranges.rolling(14).mean().rolling(5).mean().iloc[-1]
                
                # Skip low volatility conditions on lower timeframes
                if atr < avg_atr * 0.8:
                    return False
                
                # Skip extreme volatility conditions
                if atr > avg_atr * 2.5:
                    return False
                
        # All checks passed
        return True
    
    def analyze_market(self, df: pd.DataFrame, pivot_low: float = None, pivot_high: float = None) -> Dict:
        """
        Complete market analysis combining Square of Nine, Fibonacci, and Wyckoff.
        
        Parameters:
        df (pd.DataFrame): DataFrame with price data.
        pivot_low (float): Pivot low price. If None, will attempt to detect.
        pivot_high (float): Pivot high price. If None, will attempt to detect.
        
        Returns:
        Dict: Complete market analysis.
        """
        if len(df) < 200:
            return {'error': 'Not enough data for analysis'}
            
        # Detect pivots if not provided
        if pivot_low is None or pivot_high is None:
            pivots = self.find_pivot_points(df)
            if pivots['lows'] and pivot_low is None:
                pivot_low = df['low'].iloc[pivots['lows'][-1]]
            if pivots['highs'] and pivot_high is None:
                pivot_high = df['high'].iloc[pivots['highs'][-1]]
        
        # Ensure we have pivots
        if pivot_low is None:
            pivot_low = df['low'].min()
        if pivot_high is None:
            pivot_high = df['high'].max()
        
        # Get current price
        current_price = df['close'].iloc[-1]
        
        # 1. Calculate Square of Nine levels from pivot low
        s9_levels_from_low = self.calculate_s9_levels(pivot_low)

        # 2. Calculate Square of Nine levels from pivot high
        s9_levels_from_high = self.calculate_s9_levels(pivot_high)
        
        # 3. Calculate Fibonacci price levels using low-high range
        fib_levels = self.calculate_fib_price_levels(pivot_low, pivot_high)
        
        # 4. Find confluence zones
        confluence_from_low = [dict(conf, origin='low') for conf in self.find_confluence_zones(fib_levels, s9_levels_from_low)]
        confluence_from_high = [dict(conf, origin='high') for conf in self.find_confluence_zones(fib_levels, s9_levels_from_high)]
        
        # 5. Detect Wyckoff patterns
        wyckoff = self.detect_wyckoff_patterns(df)
        
        # 6. Identify market phase (only if Wyckoff pattern detected)
        market_phase = {}
        if wyckoff['detected']:
            pivot_idx = wyckoff['pivot_idx']
            is_accumulation = wyckoff['is_accumulation']
            market_phase = self.identify_market_phase(df, pivot_idx, is_accumulation)
        
        # 7. Generate trade setup based on market phase
        trade_setup = {'valid': False, 'reason': 'No market phase detected'}
        if market_phase:
            trade_setup = self.generate_trade_setup(
                df, market_phase, fib_levels, current_price, wyckoff.get('is_accumulation', True)
            )
        
        # 8. Compile analysis results
        # Merge and sort confluences by strength and distance
        all_confluences = (confluence_from_low + confluence_from_high)
        all_confluences.sort(key=lambda x: (-x.get('strength_score', 0), x.get('distance', float('inf'))))

        analysis = {
            'current_price': current_price,
            'pivot_low': pivot_low,
            'pivot_high': pivot_high,
            'price_range': pivot_high - pivot_low,
            'current_position': {
                'price': current_price,
                'range_percentage': (current_price - pivot_low) / (pivot_high - pivot_low) * 100 if pivot_high != pivot_low else 0
            },
            'wyckoff_analysis': wyckoff,
            'market_phase': market_phase,
            'confluence_from_low': confluence_from_low,
            'confluence_from_high': confluence_from_high,
            'strong_confluence_zones': [
                conf for conf in all_confluences 
                if conf.get('strength') in ('Perfect', 'Strong')
            ],
            'trade_setup': trade_setup
        }
        
        return analysis
