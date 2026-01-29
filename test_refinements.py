import sys
import os
import pandas as pd
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from analysis_engine import AnalysisEngine
from performance_utils import filter_by_market_cap

def test_refinements():
    # Test 1: Market Cap Filtering
    test_tickers = ["RELIANCE", "TCS", "IDEA", "SUZLON", "ZOMATO"] # Mix of large and historically smaller/mid
    print(f"Testing market cap filter on: {test_tickers}")
    filtered = filter_by_market_cap(test_tickers, min_market_cap=10000000000)
    print(f"Filtered (Above 1000 Cr): {filtered}")
    
    # Test 2: Cyclical Scanner on a subset
    print("\nTesting Refined Cyclical Scanner (subset)...")
    cyclical_results = AnalysisEngine.get_cyclical_stocks_by_quarter(test_tickers[:3])
    for q, results in cyclical_results.items():
        if results:
            print(f"Found {len(results)} stocks for {q}")
            for r in results:
                print(f" - {r['Stock Symbol']}: Consistency {r.get('Probabilistic Consistency (%)')}, Median {r.get('Historical Median Return (%)')}")

if __name__ == "__main__":
    test_refinements()
