import sys
import os
import pandas_ta as ta
import pandas as pd
import yfinance as yf

tickers = ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'INFY.NS', 'BHARTIARTL.NS', 'SBIN.NS', 'ITC.NS', 'SUNPHARMA.NS', 'TATAMOTORS.NS']

print(f"Diagnostics: Checking {len(tickers)} stocks...")

data = yf.download(tickers, period='1y', interval='1d', group_by='ticker', auto_adjust=True, progress=False)

hits = []
for t in tickers:
    try:
        df = data[t].dropna(subset=['Close'])
        if len(df) < 100:
            print(f"{t}: FAIL (Short data: {len(df)})")
            continue
            
        price = df['Close'].iloc[-1]
        ema20 = ta.ema(df['Close'], 20).iloc[-1]
        vol_sma = df['Volume'].rolling(20).mean().iloc[-1]
        rsi = ta.rsi(df['Close'], 14).iloc[-1]
        
        # Original Logic: price > max of Highs of previous 40 bars (excluding current)
        max40 = df['High'].rolling(40).max().shift(1).iloc[-1]
        
        c1 = price >= 100
        c2 = price > ema20
        c3 = df['Volume'].iloc[-1] > vol_sma
        c4 = rsi > 50
        c5 = price > max40
        
        if all([c1, c2, c3, c4, c5]):
            print(f"{t}: PASS | P={price:.1f}, M40={max40:.1f}, RSI={rsi:.1f}")
            hits.append(t)
        else:
            reasons = []
            if not c1: reasons.append("P<100")
            if not c2: reasons.append(f"P({price:.1f})<=E20({ema20:.1f})")
            if not c3: reasons.append("V<=VSMA")
            if not c4: reasons.append(f"RSI({rsi:.1f})<=50")
            if not c5: reasons.append(f"P({price:.1f})<=M40({max40:.1f})")
            print(f"{t}: FAIL ({', '.join(reasons)})")

    except Exception as e:
        print(f"{t}: error {e}")

print(f"\nHits: {hits}")
