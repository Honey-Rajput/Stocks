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
    Download data for multiple tickers in batches to improve performance.
    Chunked to 500 tickers to respect API limits and memory.
    """
    import data_provider as yf
    import pandas as pd
    import yfinance as real_yf
    import time

    # Ensure deterministic processing
    tickers = sorted(list(set(tickers)))
    formatted_tickers = [f"{t}.NS" if not t.endswith(".NS") else t for t in tickers]
    
    if not formatted_tickers:
        return {}
        
    results = {}
    
    # Chunk tickers into batches
    # Use smaller batches for long periods to avoid timeouts/errors
    if 'y' in period or 'max' in period:
        chunk_size = 50  # Smaller chunks for heavy data (10y)
    else:
        chunk_size = 300 # Larger chunks for short data
        
    chunks = [formatted_tickers[i:i + chunk_size] for i in range(0, len(formatted_tickers), chunk_size)]
    
    for i, chunk in enumerate(chunks):
        try:
            print(f"Downloading batch {i+1}/{len(chunks)} ({len(chunk)} stocks)...")
            data = real_yf.download(
                chunk,
                period=period,
                interval=interval,
                auto_adjust=True,
                group_by='ticker',
                progress=False,
                threads=True, 
                timeout=60
            )
            
            # Debug: Print data structure
            # print(f"Batch {i+1} downloaded. Data shape: {data.shape}, Columns: {data.columns}")
            
            # Handle multi-ticker data structure
            if isinstance(data, pd.DataFrame) and isinstance(data.columns, pd.MultiIndex):
                # Iterate through level 0 (Tickers)
                for ticker in data.columns.levels[0]:
                    try:
                        ticker_df = data[ticker].dropna(how='all')
                        # Check for sufficient data
                        if not ticker_df.empty and len(ticker_df) >= 20: 
                            clean_name = str(ticker).replace(".NS", "")
                            results[clean_name] = ticker_df
                            # print(f"Cached {clean_name} ({len(ticker_df)} rows)")
                    except Exception as e:
                        print(f"Error accessing ticker {ticker}: {e}")
                        continue
            
            # Handle single ticker returned as standard DataFrame
            elif isinstance(data, pd.DataFrame) and not data.empty:
                # If explicit single ticker requested, we're good
                if len(chunk) == 1:
                    clean_name = chunk[0].replace(".NS", "")
                    results[clean_name] = data
                else:
                    # Ambiguous case: Asked for N > 1, got 1 DataFrame.
                    # This implies valid data for unknown ticker (or all merged? unlikely with group_by='ticker').
                    # Fallback to serial download for this chunk to be safe.
                    print(f"Warning: Batch {i+1} returned ambiguous/single-index DataFrame. Falling back to serial download.")
                    raise ValueError("Ambiguous batch result")

        except Exception as e:
            # Fallback: Serial download for this chunk
            # print(f"Batch {i+1} falling back to serial: {e}")
            for t in chunk:
                try:
                    clean = t.replace('.NS', '')
                    # Skip if already cached/handled (though in this function we start fresh)
                    df = real_yf.download(
                        [t],
                        period=period,
                        interval=interval,
                        auto_adjust=True,
                        progress=False,
                        threads=False,
                        timeout=10
                    )
                    if not df.empty:
                        results[clean] = df
                except Exception:
                    continue
        
        # Small sleep
        if len(chunks) > 1:
            time.sleep(1.0)
            
    return results
