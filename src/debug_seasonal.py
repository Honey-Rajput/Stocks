
import sys
import os
import pandas as pd
import time

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analysis_engine import AnalysisEngine
from scanner_robustness import ScannerConfig

def debug_q3_scanner():
    print("--- Debugging Q3 Seasonal Scanner ---")
    
    # Test with a few major stocks that might have seasonality
    tickers = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "TATAMOTORS", "ITC", "LT", "BHARTIARTL"]
    # Add .NS
    tickers = [t + ".NS" for t in tickers]
    
    print(f"Testing with {len(tickers)} tickers: {tickers}")
    print(f"Config: Min Prob={ScannerConfig.CYCLICAL_MIN_PROBABILITY}, Min Return={ScannerConfig.CYCLICAL_MIN_RETURN}%")
    
    # try:
    #     # Run the scanner
    #     start_time = time.time()
    #     results = AnalysisEngine.get_cyclical_stocks_by_quarter(
    #         tickers, 
    #         max_results_per_quarter=10, 
    #         max_workers=5
    #     )
    #     elapsed = time.time() - start_time
        
    #     print(f"\nScanner completed in {elapsed:.2f}s")
        
    #     if not results:
    #         print("Results is None or empty.")
    #         return

    #     for q, stocks in results.items():
    #         print(f"\n{q} Results ({len(stocks)} stocks):")
    #         for s in stocks:
    #             print(f"  - {s['Stock Symbol']}: Score={s['Score']}, Prob={s['Probabilistic Consistency (%)']}%, Median Ret={s['Historical Median Return (%)']}%")
                
        # Deep dive into one stock to see raw data calculation
    print("\n--- Deep Dive into RELIANCE.NS calculations ---")
    debug_single_stock("RELIANCE.NS")
            
    # except Exception as e:
    #     print(f"Error running scanner: {e}")
    #     import traceback
    #     traceback.print_exc()

def debug_single_stock(ticker):
    from performance_utils import batch_download_data
    
    with open("debug_output.txt", "w") as f:
        f.write(f"--- Deep Dive into {ticker} ---\n")
        
        # print(f"Downloading 10y data for {ticker}...")
        batch = batch_download_data([ticker], period='10y', interval='1d')
        clean_ticker = ticker.replace('.NS', '')
        df = batch.get(clean_ticker)
        
        if df is None:
            df = batch.get(ticker)
        
        if df is None or df.empty:
            f.write(f"No data found for {ticker} (clean: {clean_ticker}). Keys in batch: {list(batch.keys())}\n")
            return
            
        df['Year'] = df.index.year
        df['Quarter'] = df.index.quarter
        
        quarterly_returns = {'Q1': [], 'Q2': [], 'Q3': [], 'Q4': []}
        
        f.write("\nCalculated Returns per Quarter:\n")
        for year in range(df['Year'].min(), df['Year'].max() + 1):
            for q in [1, 2, 3, 4]:
                q_data = df[(df['Year'] == year) & (df['Quarter'] == q)]
                if len(q_data) > 0:
                    start_price = q_data['Close'].iloc[0]
                    end_price = q_data['Close'].iloc[-1]
                    ret = ((end_price - start_price) / start_price) * 100
                    quarterly_returns[f'Q{q}'].append(ret)
                    # f.write(f"  {year} Q{q}: {ret:.2f}%\n")
        
        f.write(f"\nSummary for {ticker}:\n")
        for q, returns in quarterly_returns.items():
            if not returns:
                f.write(f"  {q}: No data\n")
                continue
                
            avg_ret = sum(returns) / len(returns)
            pos_years = sum(1 for r in returns if r > 0)
            prob = pos_years / len(returns)
            
            f.write(f"  {q}: Avg Ret={avg_ret:.2f}%, Probability={prob:.2f} ({pos_years}/{len(returns)})\n")
        
        is_best = False
        # Simple check if this would be selected
        # (Note: Logic in analysis_engine picks the MAX avg_return quarter)

if __name__ == "__main__":
    debug_q3_scanner()
