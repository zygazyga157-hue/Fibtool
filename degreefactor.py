import pandas as pd
import numpy as np

class DegreeFactor:
    """
    Python implementation of DegreeFactor strategy from MQL5.
    This strategy calculates price levels based on Fibonacci-like factors.
    """
    
    def __init__(self, user_input="0.175, 0.35, 0.525, 0.7, 0.875", low_value=None,
                 price_decimals: int = 5, point_value: float | None = None):
        """
        Initialize the DegreeFactor strategy.
        
        Parameters:
        user_input (str): Comma-separated list of degree factors.
        low_value (float): Base price level. If None, will use current market low.
        """
        self.factors = self._parse_factors_string(user_input)
        self.low_value = low_value
        self.price_lines = []
        self.alerted_levels = []
        self.price_decimals = price_decimals
        # point_value: monetary/price value of a single point (tick); if None infer from decimals
        self.point_value = point_value if point_value is not None else (10 ** -price_decimals)
        
    def _parse_factors_string(self, factors_string):
        """Parse a comma-separated string of factors into a list of floats."""
        return [float(f.strip()) for f in factors_string.split(',')]
        
    def calculate_price_lines(self, low_value=None):
        """
        Calculate price levels based on factors.
        
        Parameters:
        low_value (float): Base price level. Overrides the instance value if provided.
        
        Returns:
        list: Calculated price levels
        """
        if low_value is not None:
            self.low_value = low_value
            
        if self.low_value is None:
            raise ValueError("Low value must be provided either at initialization or when calculating price lines")
            
        self.price_lines = []
        for factor in self.factors:
            price_level = round(self.low_value * (1 + factor), self.price_decimals)
            self.price_lines.append(price_level)
            
        # Reset alert states
        self.alerted_levels = [False] * len(self.price_lines)
        return self.price_lines
    
    def check_alerts(self, current_price, threshold_points, point_value=None):
        """
        Check if price is approaching any of the calculated levels.
        
        Parameters:
        current_price (float): Current market price.
        threshold_points (int): Alert threshold in points.
        point_value (float): Value of one point in price terms.
        
        Returns:
        list: Alerts if price is near any levels, empty list otherwise.
        """
        if not self.price_lines:
            return []
            
        if point_value is None:
            point_value = self.point_value
        threshold = threshold_points * point_value
        alerts = []
        
        for i, level in enumerate(self.price_lines):
            distance = abs(current_price - level)
            
            if distance <= threshold:
                if not self.alerted_levels[i]:
                    direction = "above" if current_price > level else "below"
                    fmt = f"{{:.{self.price_decimals}f}}"
                    message = f"Price approaching {direction} {fmt.format(level)} (Current: {fmt.format(round(current_price, self.price_decimals))})"
                    alerts.append(message)
                    self.alerted_levels[i] = True
            else:
                # Reset alert if price moves away
                self.alerted_levels[i] = False
                
        return alerts
        
    def apply_to_dataframe(self, df, low_column='low'):
        """
        Apply the strategy to a pandas DataFrame.
        
        Parameters:
        df (pandas.DataFrame): DataFrame with OHLCV data.
        low_column (str): Name of the column containing low prices.
        
        Returns:
        pandas.DataFrame: Original dataframe with added DegreeFactor levels as columns.
        """
        if self.low_value is None and not df.empty:
            self.low_value = df[low_column].min()
            
        price_lines = self.calculate_price_lines()
        result_df = df.copy()
        
        for i, level in enumerate(price_lines):
            result_df[f'degreefactor_{i+1}'] = level
            
        return result_df
