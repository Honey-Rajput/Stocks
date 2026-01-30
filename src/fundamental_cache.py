"""
Fundamental Data Cache Manager
===============================
Manages caching and fallback retrieval of fundamental stock data.
Solves the issue of yFinance returning incomplete data for Indian stocks.
"""

import json
import csv
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import requests

class FundamentalCache:
    """Caches fundamental data and provides fallback mechanisms."""
    
    def __init__(self, cache_dir="scanner_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "fundamentals_cache.json"
        self.load_cache()
    
    def load_cache(self):
        """Load existing cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    self.cache = json.load(f)
            except:
                self.cache = {}
        else:
            self.cache = {}
    
    def save_cache(self):
        """Save cache to disk."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2, default=str)
        except Exception as e:
            print(f"⚠️ Could not save cache: {e}")
    
    def is_cache_valid(self, ticker, hours=24):
        """Check if cached data is still valid."""
        if ticker not in self.cache:
            return False
        
        cached_time = self.cache[ticker].get('timestamp')
        if not cached_time:
            return False
        
        try:
            cached_dt = datetime.fromisoformat(cached_time)
            return (datetime.now() - cached_dt).total_seconds() < (hours * 3600)
        except:
            return False
    
    def get_cached(self, ticker):
        """Get cached fundamental data for a ticker."""
        if ticker in self.cache and self.is_cache_valid(ticker):
            return self.cache[ticker].get('data')
        return None
    
    def cache_data(self, ticker, data):
        """Store fundamental data in cache."""
        self.cache[ticker] = {
            'data': data,
            'timestamp': datetime.now().isoformat()
        }
        self.save_cache()
    
    @staticmethod
    def fetch_from_screener(ticker):
        """Fetch fundamental data from screener.in API (unofficial but reliable)."""
        try:
            url = f"https://www.screener.in/api/company/{ticker}/consolidated/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
            }
            
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                
                # Extract relevant metrics
                quarters = data.get('quarters', [])
                if quarters:
                    latest = quarters[0]
                    
                    return {
                        'revenue_growth': latest.get('revenue_growth'),
                        'roe': latest.get('roe'),
                        'debt_to_equity': latest.get('debt_to_equity'),
                        'eps': latest.get('eps'),
                        'source': 'screener.in'
                    }
        except Exception as e:
            pass
        
        return None
    
    @staticmethod
    def fetch_from_bseindia(ticker):
        """Fetch from BSE India data."""
        try:
            # This would require web scraping or API access
            # Placeholder for potential future implementation
            pass
        except:
            pass
        
        return None
    
    @staticmethod
    def enhance_yfinance_data(yf_info, ticker):
        """
        Enhance incomplete yFinance data with alternative sources.
        
        Returns dict with:
        - rev_growth, roe, debt_equity (all numeric or None)
        - source indicator
        """
        result = {
            'rev_growth': None,
            'roe': None,
            'debt_equity': None,
            'source': 'yfinance'
        }
        
        # Try to get from yFinance first
        rev_growth = yf_info.get('revenueGrowth')
        if rev_growth:
            result['rev_growth'] = float(rev_growth)
        
        roe = yf_info.get('returnOnEquity')
        if roe:
            result['roe'] = float(roe)
        
        debt_eq = yf_info.get('debtToEquity')
        if debt_eq:
            result['debt_equity'] = float(debt_eq) / 100 if float(debt_eq) > 1 else float(debt_eq)
        
        # If we got all data from yFinance, return early
        if result['rev_growth'] and result['roe'] and result['debt_equity']:
            return result
        
        # Otherwise try Screener.in as fallback
        screener_data = FundamentalCache.fetch_from_screener(ticker)
        if screener_data:
            if not result['rev_growth']:
                result['rev_growth'] = screener_data.get('revenue_growth')
            if not result['roe']:
                result['roe'] = screener_data.get('roe')
            if not result['debt_equity']:
                result['debt_equity'] = screener_data.get('debt_to_equity')
            result['source'] = 'hybrid (yfinance + screener.in)'
        
        return result
    
    @staticmethod
    def build_fundamental_index():
        """
        Build a fundamental metrics index for all NSE stocks.
        Run this periodically to populate the cache.
        """
        print("🔄 Building fundamental index... (This may take time)")
        
        try:
            # Try to fetch NSE list
            url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
            df_nse = pd.read_csv(url)
            symbols = df_nse['SYMBOL'].unique()[:500]  # Sample first 500 for speed
            
            cache = FundamentalCache()
            successful = 0
            
            for idx, ticker in enumerate(symbols):
                if idx % 50 == 0:
                    print(f"  Processing {idx}/{len(symbols)}...")
                
                data = FundamentalCache.fetch_from_screener(ticker)
                if data:
                    cache.cache_data(ticker, data)
                    successful += 1
            
            print(f"✅ Cached fundamental data for {successful} stocks")
            
        except Exception as e:
            print(f"❌ Error building index: {e}")
    
    @staticmethod
    def get_fundamental_data(ticker, yf_info):
        """
        Get complete fundamental data for a ticker.
        Uses cache first, then tries multiple sources.
        """
        cache = FundamentalCache()
        
        # Check cache first
        cached = cache.get_cached(ticker)
        if cached:
            return cached
        
        # Try to enhance yFinance data with alternatives
        data = FundamentalCache.enhance_yfinance_data(yf_info, ticker)
        
        # Cache the result
        cache.cache_data(ticker, data)
        
        return data


def test_fundamental_fetching():
    """Test the fundamental data fetching."""
    print("Testing fundamental data fetching...")
    
    test_tickers = ['INFY', 'RELIANCE', 'TCS', 'HDFC', 'LT']
    
    for ticker in test_tickers:
        print(f"\n{ticker}:")
        
        # Get from screener
        data = FundamentalCache.fetch_from_screener(ticker)
        if data:
            print(f"  ✓ Screener: Rev Growth={data.get('revenue_growth')}, ROE={data.get('roe')}, D/E={data.get('debt_to_equity')}")
        else:
            print(f"  ✗ Screener: No data")


if __name__ == "__main__":
    test_fundamental_fetching()
