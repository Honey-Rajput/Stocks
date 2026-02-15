"""
Scanner Robustness Utilities
============================
Adds error handling, retry logic, and data validation to all scanners.
"""

import time
import logging
from functools import wraps
import pandas as pd
import numpy as np

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScannerConfig:
    """Configurable thresholds for all scanners."""
    
    # Swing Scanner
    SWING_MIN_PRICE = 50  # Instead of 100
    SWING_MIN_RSI = 50
    SWING_MIN_VOLUME_SPIKE = 50  # %
    SWING_MIN_ROWS = 50
    SWING_MAX_PRICE_FILTER = None  # No upper limit
    
    # SMC Scanner
    SMC_MIN_VOLUME_SPIKE = 30  # % - Reduced from 50 to catch more opportunities
    SMC_MIN_ROWS = 50  # Reduced from 100 to include more stocks
    SMC_SPREAD_RATIO = 0.8
    
    # Cyclical Scanner
    CYCLICAL_MIN_PROBABILITY = 0.60  # Reduced to 60% (6/10 active years)
    CYCLICAL_MIN_RETURN = 2.0  # %
    CYCLICAL_MIN_INSTANCES = 5
    CYCLICAL_MIN_ROWS = 120
    
    # Weinstein Scanner
    WEINSTEIN_MIN_ROWS = 250
    WEINSTEIN_PERIOD = '1y'


def retry_with_backoff(max_retries=3, base_delay=0.5, backoff_factor=2):
    """
    Decorator to retry failed operations with exponential backoff.
    
    Usage:
        @retry_with_backoff(max_retries=3, base_delay=0.5)
        def fetch_data():
            return yf.download(...)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(f"✓ {func.__name__} succeeded on attempt {attempt + 1}")
                    return result
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"⚠️ {func.__name__} failed (attempt {attempt + 1}/{max_retries}): {str(e)[:50]}")
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(f"✗ {func.__name__} failed after {max_retries} attempts: {e}")
            
            return None  # Failed after all retries
        
        return wrapper
    return decorator


class DataValidator:
    """Validates data before processing."""
    
    @staticmethod
    def validate_dataframe(df, min_rows=50, required_cols=None):
        """
        Validate dataframe has sufficient data and columns.
        
        Args:
            df: DataFrame to validate
            min_rows: Minimum required rows
            required_cols: List of required column names
        
        Returns:
            bool: True if valid, False otherwise
        """
        if df is None or df.empty:
            logger.debug("DataFrame is None or empty")
            return False
        
        if len(df) < min_rows:
            logger.debug(f"DataFrame has {len(df)} rows, need {min_rows}")
            return False
        
        if required_cols:
            missing = [col for col in required_cols if col not in df.columns]
            if missing:
                logger.debug(f"Missing columns: {missing}")
                return False
        
        return True
    
    @staticmethod
    def safe_get_value(series, index=-1, default=None):
        """
        Safely get a value from a series, handling NaN/None.
        
        Args:
            series: Pandas Series
            index: Index to retrieve (-1 = last)
            default: Default value if missing/NaN
        
        Returns:
            Value or default
        """
        if series is None or series.empty:
            return default
        
        try:
            value = series.iloc[index]
            if pd.isna(value) or value is None:
                return default
            return value
        except Exception as e:
            logger.debug(f"Error getting value: {e}")
            return default
    
    @staticmethod
    def validate_indicators(df, indicator_cols):
        """
        Check if indicators exist and have valid values.
        
        Args:
            df: DataFrame with indicators
            indicator_cols: Dict of {col_name: min_rows_needed}
        
        Returns:
            dict: {col_name: bool} validity status
        """
        result = {}
        
        for col, min_rows in indicator_cols.items():
            if col not in df.columns:
                result[col] = False
                continue
            
            # Check if column has enough non-NaN values
            valid_count = df[col].notna().sum()
            result[col] = valid_count >= min_rows
        
        return result


class BatchProcessor:
    """Handles batch processing with error recovery."""
    
    @staticmethod
    def process_batch_safe(batch_data, process_func, ticker_names=None):
        """
        Process batch data safely with error handling.
        
        Args:
            batch_data: Dict of {ticker: dataframe}
            process_func: Function to process each (ticker, df)
            ticker_names: Optional list of expected tickers for validation
        
        Returns:
            List of successful results
        """
        results = []
        failed = []
        
        for ticker, df in batch_data.items():
            try:
                if not DataValidator.validate_dataframe(df, min_rows=50):
                    logger.debug(f"Skipping {ticker}: Invalid data")
                    failed.append(ticker)
                    continue
                
                result = process_func(ticker, df)
                if result:
                    results.append(result)
            except Exception as e:
                logger.warning(f"Error processing {ticker}: {e}")
                failed.append(ticker)
        
        if failed:
            logger.info(f"Successfully processed {len(results)}, failed {len(failed)}")
        
        return results


class ScannerHealthCheck:
    """Health check utilities for scanners."""
    
    @staticmethod
    def check_result_quality(results, min_count=5, expected_fields=None):
        """
        Check if scanner results are valid.
        
        Args:
            results: List of result dicts
            min_count: Minimum expected results
            expected_fields: Fields that should be in each result
        
        Returns:
            dict: Health status and recommendations
        """
        status = {
            'valid': True,
            'result_count': len(results),
            'issues': []
        }
        
        if len(results) < min_count:
            status['valid'] = False
            status['issues'].append(f"Low result count: {len(results)} < {min_count}")
        
        if expected_fields and results:
            sample = results[0]
            missing = [f for f in expected_fields if f not in sample]
            if missing:
                status['valid'] = False
                status['issues'].append(f"Missing fields: {missing}")
        
        # Check for duplicate stocks (shouldn't happen)
        if results:
            symbols = [r.get('Stock Symbol', 'N/A') for r in results]
            duplicates = [s for s in set(symbols) if symbols.count(s) > 1]
            if duplicates:
                status['issues'].append(f"Duplicate stocks detected: {duplicates}")
        
        return status
    
    @staticmethod
    def log_scanner_stats(scanner_name, results, duration_sec):
        """Log scanner execution statistics."""
        count = len(results) if results else 0
        rate = count / duration_sec if duration_sec > 0 else 0
        logger.info(f"Scanner {scanner_name}: Found {count} stocks in {duration_sec:.1f}s ({rate:.1f}/sec)")


def safe_batch_download(batch, period, interval, max_retries=2):
    """
    Safely download batch data with retries.
    
    Wraps the performance_utils batch_download_data with error handling.
    """
    from performance_utils import batch_download_data as bd
    
    for attempt in range(max_retries):
        try:
            data = bd(batch, period=period, interval=interval)
            if data and len(data) > 0:
                return data
        except Exception as e:
            logger.warning(f"Batch download attempt {attempt + 1} failed: {str(e)[:50]}")
            if attempt < max_retries - 1:
                time.sleep(1)
    
    logger.error(f"Batch download failed after {max_retries} attempts")
    return {}


# Example usage in scanners:
"""
# In swing scanner:
from scanner_robustness import DataValidator, ScannerConfig, retry_with_backoff

@retry_with_backoff(max_retries=3)
def fetch_swing_data(ticker):
    # ... fetch data
    return df

# In processing:
if not DataValidator.validate_dataframe(df, min_rows=ScannerConfig.SWING_MIN_ROWS):
    return None

price = DataValidator.safe_get_value(df['Close'])
if price < ScannerConfig.SWING_MIN_PRICE:
    return None
"""
