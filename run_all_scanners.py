import sys
import os
import time
import requests
import json
from datetime import datetime, timedelta
import pandas as pd

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from analysis_engine import AnalysisEngine
from db_utils import get_db_manager

# API Configuration from User
MODEL_URL = "https://api.euron.one/api/v1/euri/chat/completions"
# Using both keys - we can rotate or use one for specific tasks
API_KEYS = [
    "al-tS3ac_ivQGAGa2M-QHKZkfpUezwEq1-rti5anY5WOej",
    "al-ceMEl8tlv5j89Yak43GTw1H1ujL8Ba-rPGN38CvVcVN"
]

# Deployment Configuration (Update this with your app URL)
APP_URL = "http://localhost:8501" # Or your public .streamlit.app URL

def keep_alive():
    """Pings the app to prevent sleeping on Render/Streamlit Cloud."""
    try:
        if APP_URL:
            requests.get(APP_URL, timeout=10)
            print(f"[{datetime.now()}] Keep-alive ping sent to {APP_URL}")
    except Exception as e:
        print(f"Keep-alive error: {e}")

def run_scanners():
    print(f"[{datetime.now()}] Starting background market scan...")
    db = get_db_manager()
    
    # Use first key by default
    os.environ["MODEL_KEY"] = API_KEYS[0]
    os.environ["MODEL_URL"] = MODEL_URL

    try:
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        df_nse = pd.read_csv(url)
        df_nse = df_nse.drop_duplicates(subset=[' ISIN NUMBER'], keep='first')
        all_tickers = df_nse['SYMBOL'].tolist()
        print(f"Fetched {len(all_tickers)} tickers from NSE.")
    except Exception as e:
        print(f"Error fetching NSE stocks: {e}")
        return

    # NSE Scanner pool
    ticker_pool = all_tickers[:2200] 

    scanners = [
        ("swing", AnalysisEngine.get_swing_stocks),
        ("smc", AnalysisEngine.get_smart_money_stocks),
        ("long_term", AnalysisEngine.get_long_term_stocks),
    ]

    for name, func in scanners:
        print(f"\n--- Running {name.upper()} Scanner ---")
        try:
            results = func(ticker_pool, max_results=50, max_workers=15)
            db.save_results(name, results)
            print(f"Saved {len(results)} {name} results to database.")
        except Exception as e:
            print(f"{name.upper()} Scanner Error: {e}")

    # Special case: Cyclical
    print("\n--- Running CYCLICAL Scanner ---")
    try:
        results = AnalysisEngine.get_cyclical_stocks_by_quarter(ticker_pool, max_results_per_quarter=20, max_workers=10)
        db.save_results("cyclical", results)
        print(f"Saved cyclical results to database.")
    except Exception as e:
        print(f"Cyclical Scanner Error: {e}")

    # Special case: Stage Analysis
    print("\n--- Running STAGE Scanner ---")
    try:
        results = AnalysisEngine.get_weinstein_scanner_stocks(ticker_pool, max_workers=15)
        db.save_results("stage_analysis", results)
        print(f"Saved stage analysis results to database.")
    except Exception as e:
        print(f"Stage Scanner Error: {e}")

    print(f"\n[{datetime.now()}] Background market scan complete!")

    print(f"\n[{datetime.now()}] Background market scan complete!")
    print("Data older than 15 days has been cleaned up.")

def worker_loop():
    """Continuous background worker loop - runs every 1 hour."""
    print("🚀 Background Market Worker Started...")
    print("Schedule: Every 1 hour (24/7, no market hours restriction)")
    
    while True:
        # Run scanners every hour
        run_scanners()
        
        print(f"Waiting 1 hour before next scan...")
        time.sleep(3600)  # 1 hour

if __name__ == "__main__":
    worker_loop()
