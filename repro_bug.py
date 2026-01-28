import yfinance as yf
from concurrent.futures import ThreadPoolExecutor
import time

def check(ticker):
    print(f"Starting {ticker}")
    df = yf.download(ticker, period='1d', auto_adjust=True)
    price = df['Close'].iloc[-1]
    print(f"Finished {ticker}: {price}")
    return (ticker, price)

with ThreadPoolExecutor(max_workers=2) as executor:
    # Use ticker symbols that share ISIN or are problematic
    futures = [executor.submit(check, t) for t in ["ALIVUS.NS", "ALKEM.NS"]]
    results = [f.result() for f in futures]

print("\nResults:")
for t, p in results:
    print(f"{t}: {p}")
