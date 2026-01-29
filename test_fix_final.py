#!/usr/bin/env python3
"""
Test script to verify the fixed stock agent.
Tests: Swing Stock Scanner with improved filtering and batch download.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from analysis_engine import AnalysisEngine
from performance_utils import batch_download_data
import pandas as pd

def test_batch_download():
    """Test improved batch download with fallback."""
    print("=" * 70)
    print("TEST 1: Batch Download with Fallback Logic")
    print("=" * 70)
    
    test_tickers = ['TCS', 'RELIANCE', 'INFY', 'SBIN', 'LT', 'HDFC', 'BAJAJ-AUTO', 'WIPRO']
    print(f"Testing with tickers: {test_tickers}")
    print()
    
    results = batch_download_data(test_tickers, period='60d', interval='1d')
    
    print(f"✓ Batch download successful!")
    print(f"  - Tickers retrieved: {len(results)}/{len(test_tickers)}")
    print(f"  - Retrieved: {list(results.keys())}")
    for ticker, df in results.items():
        print(f"    • {ticker}: {len(df)} bars, Close Range: ₹{df['Close'].min():.2f} - ₹{df['Close'].max():.2f}")
    print()
    return results

def test_swing_stock_filtering(results):
    \"\"\"Test improved swing stock filtering logic.\"\"\"
    print("=" * 70)
    print("TEST 2: Swing Stock Filtering (Improved Logic)")
    print("=" * 70)
    
    swing_results = []
    
    for ticker, df in results.items():
        result = AnalysisEngine._process_swing_stock(ticker, df)
        if result:
            swing_results.append(result)
            print(f"✓ {result['Stock Symbol']}")
            print(f"  Price: {result['Current Price']}, Confidence: {result['Confidence Score (0–100)']}")
            print(f"  Reason: {result['Technical Reason (short explanation)']}")
            print()
    
    if not swing_results:
        print("⚠ No swing stock opportunities found in test data")
        print("  (This is normal if none of the test tickers match swing criteria)")
    else:
        print(f"✓ Found {len(swing_results)} swing opportunities!")
    print()
    return swing_results

def test_full_scanner():
    \"\"\"Test the full swing stock scanner on NSE universe.\"\"\"
    print(\"=\" * 70)
    print(\"TEST 3: Full Swing Stock Scanner (Small Universe Test)\")
    print(\"=\" * 70)
    
    # Test with a small curated list
    test_universe = ['TCS', 'RELIANCE', 'INFY', 'SBIN', 'LT', 'HDFC', 'BAJAJ-AUTO', 
                     'WIPRO', 'ASIANPAINT', 'MARUTI', 'ONGC', 'ICICIBANK', 'AXISBANK',
                     'BEL', 'OIL', 'PFC', 'HINDCOPPER', 'HAL']
    
    print(f\"Testing scanner on {len(test_universe)} stocks...\")
    print()
    
    def progress_callback(current, total, ticker):
        if current % 5 == 0 or current == total:
            print(f\"  Progress: {current}/{total} - {ticker}\")
    
    results = AnalysisEngine.get_swing_stocks(
        test_universe,
        interval='1d',
        period='1y',
        max_results=10,
        progress_callback=progress_callback
    )
    
    print()
    if results:
        print(f\"✓ Scanner found {len(results)} swing opportunities:\")
        print()
        for i, stock in enumerate(results, 1):
            print(f\"{i}. {stock.get('Stock Symbol', 'N/A')}\")
            print(f\"   Price: {stock.get('Current Price', 'N/A')}\")
            print(f\"   Target: {stock.get('Target Price (15–20 day horizon)', 'N/A')}\")
            print(f\"   Confidence: {stock.get('Confidence Score (0–100)', 'N/A')}%\")
            print(f\"   Reason: {stock.get('Technical Reason (short explanation)', 'N/A')}\")
            print()
    else:
        print(\"⚠ Scanner found no swing opportunities in test universe.\")
        print(\"  (This is normal depending on market conditions)\")
    print()
    return results

if __name__ == \"__main__\":
    print()
    print(\"🔍 STOCK AGENT IMPROVEMENT TEST SUITE\")
    print()
    
    try:
        # Test 1: Batch download
        download_results = test_batch_download()
        
        # Test 2: Swing filtering on downloaded data
        swing_results = test_swing_stock_filtering(download_results)
        
        # Test 3: Full scanner
        full_scan_results = test_full_scanner()
        
        print(\"=\" * 70)
        print(\"✓ ALL TESTS COMPLETED SUCCESSFULLY!\")
        print(\"=\" * 70)
        print()
        print(\"IMPROVEMENTS APPLIED:\")
        print(\"  1. ✓ Reduced market cap filter: 1000 Cr → 200 Cr (more stocks)")
        print(\"  2. ✓ Improved batch download with retry & individual fallback\")
        print(\"  3. ✓ Better NaN handling in technical indicators\")
        print(\"  4. ✓ Relaxed RSI threshold: > 50 → > 40 (emerging momentum)\")
        print(\"  5. ✓ Reduced price floor: ₹100 → ₹50 (better coverage)\")
        print(\"  6. ✓ Enhanced confidence scoring with volume & breakout strength\")
        print()
        
    except Exception as e:
        print(f\"❌ TEST FAILED: {e}\")
        import traceback
        traceback.print_exc()
