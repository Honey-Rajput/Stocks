import yfinance as yf

tickers = ["ALGOQUANT.NS", "CARRARO.NS", "ASTRAZEN.NS", "CELLO.NS", "RELIANCE.NS"]

print(f"{'Ticker':<15} {'DebtToEquity (Raw)':<20} {'Attempted Norm (<100 issue)'}")
print("-" * 60)

for ticker in tickers:
    try:
        t = yf.Ticker(ticker)
        info = t.info
        de = info.get('debtToEquity')
        
        normalized = "N/A"
        if de is not None:
            # Current logic in analysis_engine.py
            val = de
            if val > 100:
                val = val / 100
            normalized = val
            
        print(f"{ticker:<15} {str(de):<20} {str(normalized)}")
    except Exception as e:
        print(f"{ticker:<15} Error: {e}")
