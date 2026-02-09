"""Lightweight replacement for yfinance when yfinance is unavailable or blocked.

Behaviors:
- download() first tries local CSV cache
- if missing → fallback to yfinance (added)
- keeps same return behavior
"""

import os
from pathlib import Path
import pandas as pd
from datetime import datetime

try:
    from fundamental_cache import FundamentalCache
except Exception:
    FundamentalCache = None

# ✅ added fallback provider (no logic change)
try:
    import yfinance as _real_yf
except Exception:
    _real_yf = None


def _local_csv_path(ticker: str) -> Path:
    clean = ticker.replace('.NS', '')
    base = Path('scanner_cache') / 'historical'
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{clean}.csv"


def download(tickers, period=None, interval=None, auto_adjust=True,
             group_by='ticker', progress=False, threads=False, timeout=40):

    single = False
    if isinstance(tickers, str):
        tickers = [tickers]
        single = True

    results = {}

    for t in tickers:
        key = t.replace('.NS', '')
        path = _local_csv_path(t)

        # ✅ cache first (original behavior)
        if path.exists():
            try:
                df = pd.read_csv(path, parse_dates=True, index_col=0)
                results[key] = df
                continue
            except Exception:
                pass

        # ✅ added fallback only when cache missing
        if _real_yf is not None:
            try:
                df = _real_yf.download(
                    t,
                    period=period,
                    interval=interval,
                    auto_adjust=auto_adjust,
                    progress=False,
                    threads=False
                )
                if isinstance(df, pd.DataFrame) and not df.empty:
                    results[key] = df
                    continue
            except Exception:
                pass

        # original fallback
        results[key] = pd.DataFrame()

    if single:
        return results.get(tickers[0].replace('.NS', ''), pd.DataFrame())

    return results


class Ticker:

    def __init__(self, ticker: str):
        self.ticker = ticker.replace('.NS', '')
        self._info = None
        self._fast_info = None

    @property
    def info(self):
        print(f"[DEBUG] Ticker.info called for {self.ticker}")
        if self._info is not None:
            return self._info

        info = {}
        try:
            if FundamentalCache is not None:
                data = FundamentalCache.get_fundamental_data(self.ticker, {})
                if data:
                    info['longBusinessSummary'] = data.get('business_summary') or ''
                    info['sector'] = data.get('sector')
                    info['industry'] = data.get('industry')
                    info['shortName'] = data.get('shortName') or self.ticker
                    info['revenueGrowth'] = data.get('rev_growth')
                    info['returnOnEquity'] = data.get('roe')
                    info['debtToEquity'] = data.get('debt_equity')
                    info['marketCap'] = data.get('market_cap')
        except Exception:
            pass

        # ✅ Fallback to real yfinance if cache is empty OR missing critical data (like marketCap)
        has_critical_data = info.get('marketCap') and info.get('marketCap') > 0
        
        if (not info or not has_critical_data) and _real_yf is not None:
            try:
                print(f"[DEBUG] Fallback to real yfinance for {self.ticker}")
                t = _real_yf.Ticker(f"{self.ticker}.NS")
                real_info = t.info
                print(f"[DEBUG] Got info for {self.ticker}: {list(real_info.keys())[:5] if real_info else 'EMPTY'}")
                
                # Merge real info into cached info (real info takes precedence)
                if real_info:
                    info.update(real_info)
            except Exception as e:
                print(f"[DEBUG] Fallback error for {self.ticker}: {e}")
                pass
        else:
             if _real_yf is None:
                 print(f"[DEBUG] _real_yf is None! Import failed?")

        self._info = info
        return self._info

    @property
    def fast_info(self):
        if self._fast_info is not None:
            return self._fast_info

        fi = {}
        try:
            if FundamentalCache is not None:
                data = FundamentalCache.get_fundamental_data(self.ticker, {})
                if data:
                    fi['market_cap'] = data.get('market_cap')
        except Exception:
            pass

        # ✅ Fallback to real yfinance
        if not fi and _real_yf is not None:
            try:
                t = _real_yf.Ticker(f"{self.ticker}.NS")
                if hasattr(t, 'fast_info'):
                    real_fi = t.fast_info
                    if real_fi:
                        # Convert fast_info object to dict-like if needed or just return it
                        # But analysis_engine expects dict or object access. 
                        # fast_info in yfinance is an object.
                        # Here we return a dict for compatibility with our cache wrapper
                        fi['market_cap'] = real_fi.market_cap
            except Exception:
                pass

        self._fast_info = fi
        return self._fast_info


__all__ = ['download', 'Ticker']
