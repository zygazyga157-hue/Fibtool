import pandas as pd
import numpy as np

class UTBot:
    """
    Python implementation of UTBot strategy from MQL5.
    UTBot is a trend-following indicator based on ATR for generating trade signals.
    """
    
    def __init__(self, atr_coef=2.0, atr_len=1, price_decimals: int = 5, point_value: float | None = None):
        """
        Initialize the UTBot strategy.
        
        Parameters:
        atr_coef (float): ATR coefficient (sensitivity).
        atr_len (int): ATR period.
        """
        self.atr_coef = atr_coef
        self.atr_len = atr_len
        self.price_decimals = price_decimals
        self.point_value = point_value if point_value is not None else (10 ** -price_decimals)
    
    def _calculate_atr(self, df, atr_len):
        """
        Calculate Average True Range (ATR).
        
        Parameters:
        df (pandas.DataFrame): DataFrame with OHLC data.
        atr_len (int): ATR period.
        
        Returns:
        pandas.Series: ATR values
        """
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)
        atr = tr.rolling(window=atr_len, min_periods=1).mean()
        return atr
    
    def calculate(self, df):
        """
        Calculate UTBot values for a DataFrame.
        
        Parameters:
        df (pandas.DataFrame): DataFrame with OHLCV data.
        
        Returns:
        pandas.DataFrame: DataFrame with added UTBot columns.
        """
        result = df.copy()
        
        # Calculate ATR
        atr = self._calculate_atr(df, self.atr_len)
        
        # Initialize output arrays
        bull_signals = np.zeros(len(df))
        bear_signals = np.zeros(len(df))
        c1_values = np.zeros(len(df))
        
        # First value can't be calculated
        if len(df) <= self.atr_len:
            result['utbot_bull'] = bull_signals
            result['utbot_bear'] = bear_signals
            result['utbot_c1'] = c1_values
            return result
        
        # Calculate C1, Bull, and Bear values
        for i in range(len(df) - 1, 0, -1):  # Loop from end to beginning (reversed)
            loss = atr.iloc[i] * self.atr_coef
            
            # Calculate t1
            if df['close'].iloc[i] > c1_values[i+1 if i+1 < len(df) else i]:
                t1 = df['close'].iloc[i] - loss
            else:
                t1 = df['close'].iloc[i] + loss
            
            # Calculate t2
            if (df['close'].iloc[i] < c1_values[i+1 if i+1 < len(df) else i] and
                df['close'].iloc[i+1 if i+1 < len(df) else i] < c1_values[i+1 if i+1 < len(df) else i]):
                t2 = min(c1_values[i+1 if i+1 < len(df) else i], df['close'].iloc[i] + loss)
            else:
                t2 = t1
            
            # Calculate C1
            if (df['close'].iloc[i] > c1_values[i+1 if i+1 < len(df) else i] and
                df['close'].iloc[i+1 if i+1 < len(df) else i] > c1_values[i+1 if i+1 < len(df) else i]):
                c1_values[i] = max(c1_values[i+1 if i+1 < len(df) else i], df['close'].iloc[i] - loss)
            else:
                c1_values[i] = t2
            
            # Calculate Bull and Bear signals
            h = abs(df['high'].iloc[i+1 if i+1 < len(df) else i] - df['low'].iloc[i+1 if i+1 < len(df) else i])
            
            if (df['close'].iloc[i] > c1_values[i] and 
                df['close'].iloc[i+1 if i+1 < len(df) else i] <= c1_values[i+1 if i+1 < len(df) else i]):
                bull_signals[i] = df['low'].iloc[i] - h
            else:
                bull_signals[i] = 0
            
            if (df['close'].iloc[i] < c1_values[i] and 
                df['close'].iloc[i+1 if i+1 < len(df) else i] >= c1_values[i+1 if i+1 < len(df) else i]):
                bear_signals[i] = df['high'].iloc[i] + h
            else:
                bear_signals[i] = 0
        
        # Add calculated values to result DataFrame
        # Replace any potential NaNs (shouldn't occur now) and round
        result['utbot_bull'] = np.round(np.nan_to_num(bull_signals, nan=0.0), self.price_decimals)
        result['utbot_bear'] = np.round(np.nan_to_num(bear_signals, nan=0.0), self.price_decimals)
        result['utbot_c1'] = np.round(np.nan_to_num(c1_values, nan=0.0), self.price_decimals)
        return result
    
    def generate_signals(self, df):
        """
        Generate trading signals based on UTBot.
        
        Parameters:
        df (pandas.DataFrame): DataFrame with UTBot values.
        
        Returns:
        pandas.DataFrame: DataFrame with added signal columns.
        """
        result = df.copy()
        
        # Create signal columns
        result['signal'] = 0
        result['signal_price'] = np.nan
        
        # Buy signals
        buy_condition = result['utbot_bull'] > 0
        result.loc[buy_condition, 'signal'] = 1
        result.loc[buy_condition, 'signal_price'] = result.loc[buy_condition, 'close']
        
        # Sell signals
        sell_condition = result['utbot_bear'] > 0
        result.loc[sell_condition, 'signal'] = -1
        result.loc[sell_condition, 'signal_price'] = result.loc[sell_condition, 'close']
        
        return result
