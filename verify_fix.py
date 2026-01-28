import pandas as pd
import yfinance as yf
from src.analysis_engine import AnalysisEngine

def verify_deduplication():
    print("Verifying ticker deduplication...")
    # Mocking the CSV read logic from app.py
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    df = pd.read_csv(url)
    original_count = len(df)
    
    # Apply the same logic as in app.py
    df_dedup = df.drop_duplicates(subset=[' ISIN NUMBER'], keep='first')
    new_count = len(df_dedup)
    
    print(f"Original: {original_count}, Deduplicated: {new_count}")
    
    # Check if ALKEM exists and ALIVUS is gone (if it was a duplicate)
    alkem_in = "ALKEM" in df_dedup['SYMBOL'].values
    alivus_in = "ALIVUS" in df_dedup['SYMBOL'].values
    
    print(f"ALKEM in list: {alkem_in}")
    print(f"ALIVUS in list: {alivus_in}")
    
    if alivus_in:
        alkem_isin = df[df['SYMBOL'] == 'ALKEM'][' ISIN NUMBER'].iloc[0]
        alivus_isin = df[df['SYMBOL'] == 'ALIVUS'][' ISIN NUMBER'].iloc[0]
        print(f"ALKEM ISIN: {alkem_isin}")
        print(f"ALIVUS ISIN: {alivus_isin}")
        if alkem_isin == alivus_isin:
            print("ERROR: ALIVUS and ALKEM share ISIN but both are in the list!")
        else:
            print("INFO: ALIVUS and ALKEM have different ISINs (strange, but possible if they are different companies).")

def verify_fetch():
    print("\nVerifying data fetch for ALKEM...")
    engine = AnalysisEngine("ALKEM.NS")
    # This calls _fetch_data internally
    df = engine.data
    price = df['Close'].iloc[-1]
    print(f"ALKEM Price: {price}")
    if 900 < price < 1000:
        print("ERROR: Still getting ALIVUS price for ALKEM!")
    elif price > 5000:
        print("SUCCESS: Getting correct ALKEM price.")
    else:
        print(f"WARNING: Unexpected price {price}")

if __name__ == "__main__":
    verify_deduplication()
    verify_fetch()
