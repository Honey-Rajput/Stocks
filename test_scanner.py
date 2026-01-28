"""
Quick test to verify scanner functionality
"""
import sys
sys.path.insert(0, 'src')

from analysis_engine import AnalysisEngine

# Test with a small set of tickers
test_tickers = ['RELIANCE', 'TCS', 'INFY', 'HDFC', 'ICICIBANK']

print("Testing Smart Money Scanner...")
try:
    results = AnalysisEngine.get_smart_money_stocks(test_tickers, max_results=5, max_workers=3)
    print(f"✅ Scanner works! Found {len(results)} results")
    if results:
        print(f"First result: {results[0]}")
except Exception as e:
    print(f"❌ Scanner failed: {e}")
    import traceback
    traceback.print_exc()
