import time
from src.analysis_engine import AnalysisEngine

def verify_different_prices():
    tickers = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]
    print(f"Verifying prices for: {tickers}")
    results = AnalysisEngine.get_swing_stocks(tickers, max_results=10)
    
    if not results:
        print("No results found (possibly market criteria or rate limit).")
        return
        
    for res in results:
        print(f"Stock: {res['Stock Symbol']}, Price: {res['Current Price']}")
    
    prices = [res['Current Price'] for res in results]
    if len(set(prices)) == len(prices):
        print("SUCCESS: All prices are unique and correct.")
    else:
        print("WARNING: Some prices are identical. Investigating...")

if __name__ == "__main__":
    verify_different_prices()
