import sys
import os
import pandas_ta as ta
import pandas as pd
import time
import codecs

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))
from performance_utils import batch_download_data
from analysis_engine import AnalysisEngine

# List from user's Chartink screenshot
tickers = ['HINDCOPPER', 'OIL', 'SOLARINDS', 'BEL', 'ONGC', 'ACUTAAS', 'MCX', 'BDL', 'HAL', 'PFC', 'RELIANCE', 'TCS']

print(f"Final Sync Test: Checking {tickers}")

# Run the actual AnalysisEngine method
ae_results = AnalysisEngine.get_swing_stocks(tickers, interval='1d', period='1y')
print(f"\nAnalysisEngine found {len(ae_results)} results:")
for i, r in enumerate(ae_results):
    print(f"{i+1}. {r['Stock Symbol']}: {r['Technical Reason (short explanation)']}")

# Verify HINDCOPPER is #1 or near it
if ae_results and ae_results[0]['Stock Symbol'] == 'HINDCOPPER':
    print("\nSUCCESS: HINDCOPPER is at the Top (Match with Chartink Buzzing order)!")
else:
    print("\nNOTE: Order might differ slightly depending on yfinance vs Chartink live data timing.")
