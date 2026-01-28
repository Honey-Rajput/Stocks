import time
import pandas as pd
from src.analysis_engine import AnalysisEngine

def benchmark_swing_scanner():
    print("Benchmarking Swing Trading Scanner...")
    # Mock ticker pool
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    df = pd.read_csv(url)
    tickers = df['SYMBOL'].head(200).tolist()
    
    start_time = time.time()
    results1 = AnalysisEngine.get_swing_stocks(tickers, max_results=10)
    end_time = time.time()
    
    print(f"Scan 1 took {end_time - start_time:.2f} seconds.")
    print(f"Found {len(results1)} results.")
    
    start_time = time.time()
    results2 = AnalysisEngine.get_swing_stocks(tickers, max_results=10)
    end_time = time.time()
    
    print(f"Scan 2 took {end_time - start_time:.2f} seconds.")
    
    # Verify stability
    match = results1 == results2
    print(f"Results match exactly: {match}")
    if not match:
        print("Mismatched result symbols:")
        s1 = [r['Stock Symbol'] for r in results1]
        s2 = [r['Stock Symbol'] for r in results2]
        print(f"List 1: {s1}")
        print(f"List 2: {s2}")

if __name__ == "__main__":
    benchmark_swing_scanner()
