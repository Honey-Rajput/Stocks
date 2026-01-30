#!/usr/bin/env python3
"""
Setup script to build fundamental data cache.
Run this once to populate the scanner cache with fundamental metrics.

Usage:
    python setup_cache.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from fundamental_cache import FundamentalCache
import pandas as pd

def main():
    print("=" * 60)
    print("SETTING UP FUNDAMENTAL DATA CACHE")
    print("=" * 60)
    
    try:
        # Fetch NSE stock list
        print("\n📥 Fetching NSE stock list...")
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        df_nse = pd.read_csv(url)
        symbols = df_nse['SYMBOL'].unique()
        
        print(f"✅ Found {len(symbols)} NSE stocks")
        
        # Build cache for top stocks (large cap focus)
        print("\n🔄 Building fundamental cache...")
        print("   (This may take 10-20 minutes for comprehensive coverage)")
        
        cache = FundamentalCache()
        successful = 0
        failed = 0
        
        # Sample large-cap stocks (first 300 are typically large-caps)
        sample_symbols = symbols[:300]
        
        for idx, ticker in enumerate(sample_symbols, 1):
            if idx % 25 == 0:
                print(f"   [{idx}/{len(sample_symbols)}] Processed {successful} successful, {failed} failed")
            
            try:
                # Try to fetch from Screener.in
                data = FundamentalCache.fetch_from_screener(ticker)
                if data:
                    cache.cache_data(ticker, data)
                    successful += 1
                else:
                    failed += 1
            except:
                failed += 1
        
        print("\n" + "=" * 60)
        print(f"✅ CACHE BUILD COMPLETE")
        print("=" * 60)
        print(f"✓ Cached data for: {successful} stocks")
        print(f"✗ Failed to cache: {failed} stocks")
        print(f"📁 Cache location: scanner_cache/fundamentals_cache.json")
        print("\n💡 Next steps:")
        print("   1. Run the app: streamlit run src/app.py")
        print("   2. Go to 'Long Term Investing' tab")
        print("   3. Click 'Run Long-Term Scanner' button")
        print("\nℹ️  Cache will auto-refresh for stocks with data older than 24 hours")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nTroubleshooting:")
        print("- Check internet connection")
        print("- Verify NSE website is accessible")
        print("- Try again in a few minutes")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
