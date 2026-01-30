import os
import json
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, String, DateTime, Text, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.dialects.postgresql import JSONB

load_dotenv()

Base = declarative_base()

class ScannerResult(Base):
    __tablename__ = 'scanner_results'
    
    scanner_type = Column(String(50), primary_key=True)
    data = Column(JSONB) # Using JSONB for flexible storage of list of dicts
    last_updated = Column(DateTime, default=datetime.utcnow)

class PostgresDBManager:
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError("DATABASE_URL not found in environment variables")
        
        # Create engine
        self.engine = create_engine(self.db_url)
        
        # Create tables if they don't exist
        Base.metadata.create_all(self.engine)
        
        self.Session = sessionmaker(bind=self.engine)

    def save_results(self, scanner_type, results):
        """Save scanner results to PostgreSQL and history."""
        from scanner_history import get_history_manager
        # Import sanitizer to ensure JSONB receives valid JSON (no NaN/Inf, numpy types)
        try:
            from json_utils import sanitize_for_json
        except Exception:
            sanitize_for_json = None
        
        session = self.Session()
        try:
            # Check if exists
            existing = session.query(ScannerResult).filter_by(scanner_type=scanner_type).first()
            
            now = datetime.now()
            
            # Sanitize results to avoid NaN/Inf and non-serializable types
            safe_results = sanitize_for_json(results) if sanitize_for_json else results

            if existing:
                existing.data = safe_results
                existing.last_updated = now
            else:
                new_entry = ScannerResult(
                    scanner_type=scanner_type, 
                    data=safe_results, 
                    last_updated=now
                )
                session.add(new_entry)
            
            session.commit()
            print(f"✅ Saved {len(results)} items to DB for {scanner_type}")
            
            # Also save to history (15-day rolling window) using sanitized data
            history_mgr = get_history_manager()
            try:
                history_mgr.save_results_with_history(scanner_type, safe_results)
            except Exception:
                # Fallback to original if history save fails for unexpected reasons
                history_mgr.save_results_with_history(scanner_type, results)
            
        except Exception as e:
            session.rollback()
            print(f"❌ Error saving to DB: {e}")
            raise e
        finally:
            session.close()

    def get_results(self, scanner_type):
        """Retrieve scanner results from PostgreSQL."""
        session = self.Session()
        try:
            result = session.query(ScannerResult).filter_by(scanner_type=scanner_type).first()
            
            if result:
                return result.data, result.last_updated
            return None, None
        except Exception as e:
            print(f"❌ Error reading from DB: {e}")
            return None, None
        finally:
            session.close()

from pathlib import Path

class LocalDBManager:
    """Local file-based storage as fallback."""
    
    def __init__(self):
        self.data_dir = Path("scanner_cache")
        self.data_dir.mkdir(exist_ok=True)
        print("📁 Using Local File Storage (Fallback)")
        
    def save_results(self, scanner_type, results):
        """Save scanner results to local JSON file."""
        file_path = self.data_dir / f"{scanner_type}.json"
        data = {
            "last_updated": datetime.now().isoformat(),
            "results": results
        }
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def get_results(self, scanner_type):
        """Retrieve scanner results from local JSON file."""
        file_path = self.data_dir / f"{scanner_type}.json"
        if not file_path.exists():
            return None, None
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            last_updated = datetime.fromisoformat(data["last_updated"])
            return data["results"], last_updated
        except Exception as e:
            print(f"Error reading {scanner_type}: {e}")
            return None, None

def get_db_manager():
    """Get database manager - tries Postgres first, falls back to local storage."""
    try:
        return PostgresDBManager()
    except Exception as e:
        print(f"⚠️ NeonDB unavailable ({e}), falling back to local storage.")
        return LocalDBManager()

