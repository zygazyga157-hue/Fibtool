import pandas as pd
import numpy as np

class SuperTrend:
    """
    Python implementation of SuperTrend strategy from MQL5.
    SuperTrend is a trend-following indicator that uses ATR to calculate support and resistance levels.
    """
    
    def __init__(self, period=10, multiplier=3.0, show_filling=True,
                 price_decimals: int = 5, point_value: float | None = None):
        """Initialize the SuperTrend strategy."""
        self.period = period
        self.multiplier = multiplier
        self.show_filling = show_filling
        self.price_decimals = price_decimals
        self.point_value = point_value if point_value is not None else (10 ** -price_decimals)
        
    def _calculate_atr(self, high, low, close, period):
        """
        Calculate Average True Range (ATR).
        
        Parameters:
        high (array): High prices.
        low (array): Low prices.
        close (array): Close prices.
        period (int): ATR period.
        
        Returns:
        array: ATR values
        """
        tr1 = np.abs(high - low)
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        
        # For the first element, use high-low only
        tr2[0] = tr1[0]
        tr3[0] = tr1[0]
        
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        atr = np.zeros_like(tr)
        
        # Simple moving average for first 'period' elements
        atr[:period] = np.cumsum(tr[:period]) / np.arange(1, period + 1)
        
        # Exponential moving average for the rest
        for i in range(period, len(tr)):
            atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
            
        return atr
        
    def calculate(self, df, high_col='high', low_col='low', close_col='close'):
        """
        Calculate SuperTrend values for a DataFrame.
        
        Parameters:
        df (pandas.DataFrame): DataFrame with OHLCV data.
        high_col (str): Name of the high price column.
        low_col (str): Name of the low price column.
        close_col (str): Name of the close price column.
        
        Returns:
        pandas.DataFrame: DataFrame with added SuperTrend columns.
        """
        result = df.copy()
        
        high = df[high_col].values
        low = df[low_col].values
        close = df[close_col].values
        
        # Calculate ATR
        atr = self._calculate_atr(high, low, close, self.period)
        
        # Initialize arrays
        up = np.zeros_like(close)
        down = np.zeros_like(close)
        middle = np.zeros_like(close)
        trend = np.zeros_like(close)
        supertrend = np.zeros_like(close)
        
        # Initial calculation
        for i in range(len(close)):
            if i == 0:
                middle[i] = (high[i] + low[i]) / 2
                up[i] = middle[i] + (self.multiplier * atr[i])
                down[i] = middle[i] - (self.multiplier * atr[i])
                trend[i] = 0  # No trend for first candle
                supertrend[i] = close[i]  # Initial value
                continue
                
            # Calculate middle, upper, and lower bands
            middle[i] = (high[i] + low[i]) / 2
            up[i] = middle[i] + (self.multiplier * atr[i])
            down[i] = middle[i] - (self.multiplier * atr[i])
            
            # Determine trend
            change_of_trend = False
            
            # Trend calculation
            if close[i] > up[i-1]:
                trend[i] = 1
                if trend[i-1] == -1:
                    change_of_trend = True
            elif close[i] < down[i-1]:
                trend[i] = -1
                if trend[i-1] == 1:
                    change_of_trend = True
            else:
                trend[i] = trend[i-1]
                change_of_trend = False
                
            # Flag calculations for adjusting bands
            flag = 1 if trend[i] < 0 and trend[i-1] > 0 else 0
            flagh = 1 if trend[i] > 0 and trend[i-1] < 0 else 0
            
            # Adjust bands based on trend
            if trend[i] > 0 and down[i] < down[i-1]:
                down[i] = down[i-1]
                
            if trend[i] < 0 and up[i] > up[i-1]:
                up[i] = up[i-1]
                
            if flag == 1:
                up[i] = middle[i] + (self.multiplier * atr[i])
                
            if flagh == 1:
                down[i] = middle[i] - (self.multiplier * atr[i])
                
            # Calculate SuperTrend value
            if trend[i] == 1:
                supertrend[i] = down[i]
                if change_of_trend and i >= 2:
                    supertrend[i-1] = supertrend[i-2]
            elif trend[i] == -1:
                supertrend[i] = up[i]
                if change_of_trend and i >= 2:
                    supertrend[i-1] = supertrend[i-2]
            else:
                supertrend[i] = supertrend[i-1]  # Maintain previous value if no clear trend
        
        # Add calculated values to result DataFrame
        result['atr'] = np.round(atr, self.price_decimals)
        # Round price-like arrays
        result['supertrend_middle'] = np.round(middle, self.price_decimals)
        result['supertrend_up'] = np.round(up, self.price_decimals)
        result['supertrend_down'] = np.round(down, self.price_decimals)
        result['supertrend'] = np.round(supertrend, self.price_decimals)
        result['supertrend_trend'] = trend
        return result
    
    def generate_signals(self, df):
        """
        Generate trading signals based on SuperTrend.
        
        Parameters:
        df (pandas.DataFrame): DataFrame with SuperTrend values.
        
        Returns:
        pandas.DataFrame: DataFrame with added signal columns.
        """
        result = df.copy()
        
        # Create signal columns
        result['signal'] = 0
        result['signal_price'] = np.nan
        
        # Buy signal when trend changes from -1 to 1
        buy_condition = (result['supertrend_trend'] == 1) & (result['supertrend_trend'].shift(1) == -1)
        result.loc[buy_condition, 'signal'] = 1
        result.loc[buy_condition, 'signal_price'] = result['close']
        
        # Sell signal when trend changes from 1 to -1
        sell_condition = (result['supertrend_trend'] == -1) & (result['supertrend_trend'].shift(1) == 1)
        result.loc[sell_condition, 'signal'] = -1
        result.loc[sell_condition, 'signal_price'] = result['close']
        
        return result
