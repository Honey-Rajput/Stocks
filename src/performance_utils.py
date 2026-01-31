"""
Performance utilities for parallel stock scanning and caching.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache, wraps
import time
from typing import List, Callable, Any, Dict
import threading

# Thread-safe cache for stock data with TTL
_cache_lock = threading.Lock()
_stock_data_cache = {}
_cache_ttl = 300  # 5 minutes

def timed_cache(seconds: int = 300):
    """Decorator that caches function results with a time-to-live."""
    def decorator(func):
        cache = {}
        cache_times = {}
        lock = threading.Lock()
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from args
            key = str(args) + str(sorted(kwargs.items()))
            
            with lock:
                # Check if cached and not expired
                if key in cache:
                    if time.time() - cache_times[key] < seconds:
                        return cache[key]
                    else:
                        # Expired, remove from cache
                        del cache[key]
                        del cache_times[key]
            
            # Call function and cache result
            result = func(*args, **kwargs)
            
            with lock:
                cache[key] = result
                cache_times[key] = time.time()
            
            return result
        
        # Add cache clearing method
        def clear_cache():
            with lock:
                cache.clear()
                cache_times.clear()
        
        wrapper.clear_cache = clear_cache
        return wrapper
    
    return decorator


def parallel_process_stocks(
    ticker_pool: List[str],
    process_func: Callable,
    max_workers: int = 10,
    max_stocks: int = None,
    timeout_per_stock: float = 30.0,
    progress_callback: Callable = None
) -> List[Any]:
    """
    Process stocks in parallel using ThreadPoolExecutor.
    
    Args:
        ticker_pool: List of stock tickers to process
        process_func: Function that takes a ticker and returns result or None
        max_workers: Maximum number of concurrent threads
        max_stocks: Maximum number of stocks to process (None = all)
        timeout_per_stock: Timeout for each stock processing
        progress_callback: Optional callback(current, total, ticker) for progress updates
    
    Returns:
        List of successful results (None results are filtered out)
    """
    results = []
    pool = list(ticker_pool)[:max_stocks] if max_stocks else list(ticker_pool)
    total = len(pool)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_ticker = {
            executor.submit(process_func, ticker): ticker 
            for ticker in pool
        }
        
        # Process completed tasks
        completed = 0
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            completed += 1
            
            try:
                result = future.result(timeout=timeout_per_stock)
                if result is not None:
                    results.append(result)
                
                # Progress callback
                if progress_callback:
                    progress_callback(completed, total, ticker)
                    
            except Exception as e:
                # Skip failed stocks silently
                if progress_callback:
                    progress_callback(completed, total, ticker)
                continue
    
    return results


def batch_process_stocks(
    ticker_pool: List[str],
    process_func: Callable,
    batch_size: int = 50,
    max_workers: int = 10,
    progress_callback: Callable = None
) -> List[Any]:
    """
    Process stocks in batches with parallel processing.
    
    Args:
        ticker_pool: List of stock tickers
        process_func: Function to process each ticker
        batch_size: Number of stocks per batch
        max_workers: Concurrent workers per batch
        progress_callback: Progress callback function
    
    Returns:
        Combined results from all batches
    """
    all_results = []
    pool = list(ticker_pool)
    total_stocks = len(pool)
    
    for i in range(0, len(pool), batch_size):
        batch = pool[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(pool) + batch_size - 1) // batch_size
        
        # Process batch in parallel
        batch_results = parallel_process_stocks(
            batch,
            process_func,
            max_workers=max_workers,
            progress_callback=lambda curr, tot, ticker: progress_callback(
                i + curr, total_stocks, ticker
            ) if progress_callback else None
        )
        
        all_results.extend(batch_results)
    
    return all_results


def create_stock_processor(analysis_func: Callable, result_limit: int = 20):
    """
    Factory function to create a stock processor with result limiting.
    
    Args:
        analysis_func: Function that analyzes a ticker and returns dict or None
        result_limit: Maximum number of results to collect
    
    Returns:
        Processor function suitable for parallel_process_stocks
    """
    results_lock = threading.Lock()
    results_count = [0]  # Use list to allow modification in closure
    
    def processor(ticker: str):
        # Early exit if we have enough results
        with results_lock:
            if results_count[0] >= result_limit:
                return None
        
        try:
            result = analysis_func(ticker)
            
            if result is not None:
                with results_lock:
                    if results_count[0] < result_limit:
                        results_count[0] += 1
                        return result
            
            return None
            
        except Exception:
            return None
    
    return processor


def filter_by_market_cap(ticker_pool: List[str], min_market_cap: float = 10000000000) -> List[str]:
    """
    Pre-filter tickers by market cap to reduce processing time.
    Standardized to 1000 Crore (10 Billion) if not specified.
    
    Args:
        ticker_pool: List of tickers
        min_market_cap: Minimum market cap in rupees (Default: 1000 Cr)
    
    Returns:
        Filtered list of tickers
    """
    import data_provider as yf
    
    def check_mcap(ticker):
        try:
            full_ticker = f"{ticker}.NS" if not ticker.endswith(".NS") else ticker
            # Use fast_info if available in newer yfinance, else info
            t = yf.Ticker(full_ticker)
            mcap = getattr(t, 'fast_info', {}).get('market_cap', t.info.get('marketCap', 0))
            if mcap >= min_market_cap:
                return ticker
        except:
            pass
        return None
    
    return parallel_process_stocks(
        ticker_pool,
        check_mcap,
        max_workers=20,
        timeout_per_stock=5.0
    )

def is_market_cap_ok(ticker: str, min_market_cap: float = 10000000000) -> bool:
    """Check if single stock meets market cap requirement (Default 1000 Cr)."""
    import data_provider as yf
    try:
        full_ticker = f"{ticker}.NS" if not ticker.endswith(".NS") else ticker
        t = yf.Ticker(full_ticker)
        mcap = getattr(t, 'fast_info', {}).get('market_cap', t.info.get('marketCap', 0))
        return mcap >= min_market_cap
    except:
        return False
def batch_download_data(tickers: List[str], period: str = '60d', interval: str = '1d') -> Dict[str, Any]:
    """
    Download data for multiple tickers in a single batch to improve performance.
    Includes retry logic and individual ticker fallback for robustness.
    """
    import data_provider as yf
    import pandas as pd
    import time
    
    # Ensure deterministic processing by sorting tickers
    tickers = sorted(list(set(tickers)))
    # Ensure all tickers have .NS suffix for NSE
    formatted_tickers = [f"{t}.NS" if not t.endswith(".NS") else t for t in tickers]
    
    if not formatted_tickers:
        return {}
        
    results = {}
    
    # Try using yfinance directly for batch download first
    try:
        import yfinance as real_yf
        # Try batch download with yfinance directly
        data = real_yf.download(
            formatted_tickers,
            period=period,
            interval=interval,
            auto_adjust=True,
            group_by='ticker',
            progress=False,
            threads=False,
            timeout=40
        )
        
        # Handle yfinance batch download response
        if isinstance(data, dict):
            for ticker_symbol, ticker_df in data.items():
                try:
                    if isinstance(ticker_df, pd.DataFrame) and not ticker_df.empty:
                        # Handle MultiIndex columns
                        if isinstance(ticker_df.columns, pd.MultiIndex):
                            ticker_df.columns = ticker_df.columns.get_level_values(0)
                        ticker_df = ticker_df.dropna(subset=['Close'])
                        if not ticker_df.empty and len(ticker_df) >= 20:
                            clean_name = str(ticker_symbol).replace(".NS", "")
                            results[clean_name] = ticker_df
                except Exception:
                    continue
        elif isinstance(data, pd.DataFrame) and not data.empty:
            # Single ticker case or all tickers in one DataFrame
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            data = data.dropna(subset=['Close'])
            if not data.empty and len(data) >= 20:
                # If only one ticker was requested
                if len(formatted_tickers) == 1:
                    clean_name = formatted_tickers[0].replace(".NS", "")
                    results[clean_name] = data
                else:
                    # Multiple tickers but returned as single DataFrame
                    # This shouldn't happen with group_by='ticker' but handle it
                    for ticker in formatted_tickers:
                        clean_name = ticker.replace(".NS", "")
                        results[clean_name] = data
        
        # If batch download worked, return results
        if results:
            return results
    except Exception as e:
        # Batch download failed, fall through to individual downloads
        pass
    
    # Fallback: Download tickers individually using data_provider (which checks cache first)
    for ticker in formatted_tickers:
        try:
            df = yf.download(
                ticker,
                period=period,
                interval=interval,
                auto_adjust=True,
                progress=False,
                timeout=20
            )
            
            # data_provider returns DataFrame for single ticker
            if isinstance(df, pd.DataFrame) and not df.empty:
                # Handle MultiIndex columns
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df = df.dropna(subset=['Close'])
                if not df.empty and len(df) >= 20:
                    clean_name = ticker.replace(".NS", "")
                    results[clean_name] = df
            elif isinstance(df, dict):
                # If it returns a dict, get the first value
                for key, val in df.items():
                    if isinstance(val, pd.DataFrame) and not val.empty:
                        if isinstance(val.columns, pd.MultiIndex):
                            val.columns = val.columns.get_level_values(0)
                        val = val.dropna(subset=['Close'])
                        if not val.empty and len(val) >= 20:
                            clean_name = key.replace(".NS", "")
                            results[clean_name] = val
                        break
                    
        except Exception:
            # Skip this ticker and continue
            pass
    
    return results
