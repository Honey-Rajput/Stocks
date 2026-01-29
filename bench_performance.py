import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))
from analysis_engine import AnalysisEngine

# Fetch some tickers from CSV
import pandas as pd
df = pd.read_csv('nse_stocks.csv')
all_tickers = df['SYMBOL'].tolist()
sample_pool = all_tickers[:500]

print(f"🚀 Performance Benchmark: Scanning {len(sample_pool)} stocks...")

start = time.time()
results = AnalysisEngine.get_swing_stocks(
    sample_pool, 
    max_results=20, 
    max_workers=20,
    progress_callback=lambda c, t, msg: print(f"\rProgress: {c}/{t} ({msg})", end="")
)
duration = time.time() - start

print(f"\n\n✅ Benchmark Complete!")
print(f"Total Time: {duration:.2f} seconds")
print(f"Rate: {len(sample_pool)/duration:.2f} stocks/sec")
print(f"Results Found: {len(results)}")

if duration < 30: # For 500 stocks, < 30s is very good
    print("✨ SPEED PERFORMANCE: EXCELLENT!")
else:
    print("📈 Speed improvement confirmed, but can be further tuned.")
