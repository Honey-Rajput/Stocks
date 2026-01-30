"""
Scanner History Manager with 15-Day Rolling Window
====================================================
Ensures:
1. Consistent results (same stocks when run 5-10 min apart)
2. 15-day rolling history (auto-delete old data)
3. No time-based filtering (run anytime)
4. History tracking for UI review
"""

import os
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import create_engine, Column, String, DateTime, Text, Integer, Index
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.dialects.postgresql import JSONB
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

class ScannerResultHistory(Base):
    """Stores scanner results with 15-day rolling window."""
    __tablename__ = 'scanner_result_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    scanner_type = Column(String(50), nullable=False)  # swing, smc, long_term, cyclical, stage_analysis
    timestamp = Column(DateTime, nullable=False, index=True)  # Exact time of scan
    result_hash = Column(String(64), nullable=False)  # Hash to detect changes
    data = Column(JSONB, nullable=False)  # Full result data
    stock_count = Column(Integer, nullable=False)  # Number of stocks found
    
    # Composite index for efficient queries
    __table_args__ = (
        Index('idx_scanner_timestamp', 'scanner_type', 'timestamp'),
    )


class ScannerHistoryManager:
    """Manages 15-day rolling history with consistency tracking."""
    
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        self.use_db = bool(self.db_url)
        
        if self.use_db:
            self.engine = create_engine(self.db_url)
            Base.metadata.create_all(self.engine)
            self.Session = sessionmaker(bind=self.engine)
        else:
            self.cache_dir = Path("scanner_cache")
            self.cache_dir.mkdir(exist_ok=True)
            self.history_file = self.cache_dir / "history.json"
            self._load_local_history()
    
    def _load_local_history(self):
        """Load history from local JSON."""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    self.local_history = json.load(f)
            except:
                self.local_history = {}
        else:
            self.local_history = {}
    
    def _save_local_history(self):
        """Save history to local JSON."""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.local_history, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving history: {e}")
    
    @staticmethod
    def _hash_results(results):
        """Create hash of results to detect changes."""
        try:
            # Sort to ensure consistent hashing
            # Sanitize to avoid NaN/Inf and non-serializable types
            try:
                from json_utils import sanitize_for_json
                safe = sanitize_for_json(results)
            except Exception:
                safe = results

            if isinstance(safe, list):
                data_str = json.dumps([r.get('Stock Symbol', '') for r in safe], sort_keys=True)
            else:
                data_str = json.dumps(safe, sort_keys=True, default=str)
            return hashlib.sha256(data_str.encode()).hexdigest()
        except:
            return "unknown"
    
    def save_results_with_history(self, scanner_type, results):
        """Save results and maintain 15-day history."""
        timestamp = datetime.now()
        result_hash = self._hash_results(results)
        stock_count = len(results) if isinstance(results, list) else 0
        
        if self.use_db:
            self._save_to_db(scanner_type, timestamp, result_hash, results, stock_count)
        else:
            self._save_to_local(scanner_type, timestamp, result_hash, results, stock_count)
        
        # Cleanup old data (older than 15 days)
        self._cleanup_old_data(scanner_type)
        
        return {
            'timestamp': timestamp,
            'hash': result_hash,
            'count': stock_count,
            'status': 'saved'
        }
    
    def _save_to_db(self, scanner_type, timestamp, result_hash, results, stock_count):
        """Save to PostgreSQL."""
        session = self.Session()
        try:
            # Sanitize data before saving to JSONB
            try:
                from json_utils import sanitize_for_json
                data_safe = sanitize_for_json(results)
            except Exception:
                data_safe = results

            entry = ScannerResultHistory(
                scanner_type=scanner_type,
                timestamp=timestamp,
                result_hash=result_hash,
                data=data_safe,
                stock_count=stock_count
            )
            session.add(entry)
            session.commit()
            print(f"✅ Saved {scanner_type} history: {stock_count} stocks at {timestamp}")
        except Exception as e:
            session.rollback()
            print(f"❌ Error saving history: {e}")
        finally:
            session.close()
    
    def _save_to_local(self, scanner_type, timestamp, result_hash, results, stock_count):
        """Save to local JSON."""
        if scanner_type not in self.local_history:
            self.local_history[scanner_type] = []
        
        entry = {
            'timestamp': timestamp.isoformat(),
            'hash': result_hash,
            'count': stock_count,
            'stocks': [r.get('Stock Symbol', 'N/A') if isinstance(r, dict) else str(r) for r in results] if isinstance(results, list) else []
        }
        
        self.local_history[scanner_type].append(entry)
        self._save_local_history()
        print(f"✅ Saved {scanner_type} history: {stock_count} stocks at {timestamp}")
    
    def get_history(self, scanner_type, days=15):
        """Get scan history for last N days."""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        if self.use_db:
            return self._get_history_from_db(scanner_type, cutoff_date)
        else:
            return self._get_history_from_local(scanner_type, cutoff_date)
    
    def _get_history_from_db(self, scanner_type, cutoff_date):
        """Get history from PostgreSQL."""
        session = self.Session()
        try:
            results = session.query(ScannerResultHistory).filter(
                ScannerResultHistory.scanner_type == scanner_type,
                ScannerResultHistory.timestamp >= cutoff_date
            ).order_by(ScannerResultHistory.timestamp.desc()).all()
            
            history = []
            for r in results:
                history.append({
                    'timestamp': r.timestamp,
                    'hash': r.result_hash,
                    'count': r.stock_count,
                    'stocks': [s.get('Stock Symbol', 'N/A') for s in r.data] if isinstance(r.data, list) else []
                })
            
            return history
        except Exception as e:
            print(f"Error retrieving history: {e}")
            return []
        finally:
            session.close()
    
    def _get_history_from_local(self, scanner_type, cutoff_date):
        """Get history from local JSON."""
        if scanner_type not in self.local_history:
            return []
        
        history = []
        for entry in self.local_history[scanner_type]:
            try:
                ts = datetime.fromisoformat(entry['timestamp'])
                if ts >= cutoff_date:
                    history.append(entry)
            except:
                pass
        
        return sorted(history, key=lambda x: x['timestamp'], reverse=True)
    
    def _cleanup_old_data(self, scanner_type):
        """Remove data older than 15 days."""
        cutoff_date = datetime.now() - timedelta(days=15)
        
        if self.use_db:
            self._cleanup_db(scanner_type, cutoff_date)
        else:
            self._cleanup_local(scanner_type, cutoff_date)
    
    def _cleanup_db(self, scanner_type, cutoff_date):
        """Delete old data from PostgreSQL."""
        session = self.Session()
        try:
            deleted = session.query(ScannerResultHistory).filter(
                ScannerResultHistory.scanner_type == scanner_type,
                ScannerResultHistory.timestamp < cutoff_date
            ).delete()
            session.commit()
            if deleted > 0:
                print(f"🗑️ Deleted {deleted} old {scanner_type} records (older than 15 days)")
        except Exception as e:
            session.rollback()
            print(f"Error cleaning up: {e}")
        finally:
            session.close()
    
    def _cleanup_local(self, scanner_type, cutoff_date):
        """Delete old data from local JSON."""
        if scanner_type not in self.local_history:
            return
        
        initial_count = len(self.local_history[scanner_type])
        
        self.local_history[scanner_type] = [
            entry for entry in self.local_history[scanner_type]
            if datetime.fromisoformat(entry['timestamp']) >= cutoff_date
        ]
        
        deleted = initial_count - len(self.local_history[scanner_type])
        if deleted > 0:
            self._save_local_history()
            print(f"🗑️ Deleted {deleted} old {scanner_type} records (older than 15 days)")
    
    def detect_change(self, scanner_type):
        """Check if results changed from last scan."""
        history = self.get_history(scanner_type, days=1)
        
        if len(history) < 2:
            return None  # No previous scan today
        
        current_hash = history[0]['hash']
        previous_hash = history[1]['hash']
        
        changed = current_hash != previous_hash
        current_count = history[0]['count']
        previous_count = history[1]['count']
        
        return {
            'changed': changed,
            'current_count': current_count,
            'previous_count': previous_count,
            'difference': current_count - previous_count
        }
    
    def get_statistics(self, scanner_type, days=15):
        """Get statistics about scan history."""
        history = self.get_history(scanner_type, days=days)
        
        if not history:
            return None
        
        counts = [h['count'] for h in history]
        hashes = [h['hash'] for h in history]
        unique_hashes = len(set(hashes))
        
        return {
            'total_scans': len(history),
            'average_count': sum(counts) / len(counts),
            'min_count': min(counts),
            'max_count': max(counts),
            'unique_results': unique_hashes,
            'date_range_days': days,
            'first_scan': history[-1]['timestamp'] if history else None,
            'last_scan': history[0]['timestamp'] if history else None
        }


# Global manager instance
_history_manager = None

def get_history_manager():
    """Get singleton history manager."""
    global _history_manager
    if _history_manager is None:
        _history_manager = ScannerHistoryManager()
    return _history_manager
