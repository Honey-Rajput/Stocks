from datetime import datetime
import sys
import os
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from db_utils import get_db_manager

def test_connection():
    try:
        db = get_db_manager()
        db.client.admin.command('ping')
        print("✅ MongoDB connection successful!")
        
        # Test saving and retrieving with date_str
        test_data = [{"ticker": "RELIANCE.NS", "price": 2500}]
        db.save_results("swing", test_data)
        print("✅ Test data saved successfully with rolling logic!")
        
        # Test latest
        results, last_updated = db.get_results("swing")
        if results == test_data:
            print(f"✅ Latest data retrieved successfully! ({last_updated})")
            
        # Test historical
        today = datetime.now().strftime("%Y-%m-%d")
        results_hist, last_updated_hist = db.get_results("swing", date_str=today)
        if results_hist == test_data:
            print(f"✅ Historical data for {today} retrieved successfully!")
            
    except Exception as e:
        print(f"❌ Connection/Operation failed: {e}")

if __name__ == "__main__":
    test_connection()
