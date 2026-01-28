import yfinance as yf
import pandas as pd

def test_batch():
    tickers = ["COFORGE", "COALINDIA", "COHANCE"]
    print(f"Downloading without .NS: {tickers}")
    data = yf.download(tickers, period='5d', group_by='ticker', progress=False)
    print("Columns:", data.columns)
    
    tickers_ns = [f"{t}.NS" for t in tickers]
    print(f"\nDownloading with .NS: {tickers_ns}")
    data_ns = yf.download(tickers_ns, period='5d', group_by='ticker', progress_callback=None)
    print("Columns:", data_ns.columns)
    
    if not data_ns.empty and isinstance(data_ns.columns, pd.MultiIndex):
        for t in tickers_ns:
            if t in data_ns.columns.levels[0]:
                df = data_ns[t].dropna()
                if not df.empty:
                    print(f"\n{t} Last Price: {df['Close'].iloc[-1]}")
                else:
                    print(f"\n{t} Data is empty after dropna")
            else:
                print(f"\n{t} not found in columns")

if __name__ == "__main__":
    test_batch()
