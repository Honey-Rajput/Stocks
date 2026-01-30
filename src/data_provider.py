"""Lightweight replacement for yfinance when yfinance is unavailable or blocked.

Behaviors:
- `download(tickers, period, interval, ...)` will try to load CSV files from
  `scanner_cache/historical/{TICKER}.csv` (without .NS). If not present, returns
  an empty pandas.DataFrame.
- `Ticker` class exposes `.info` and `.fast_info` maps populated from
  `FundamentalCache` (screener.in + local cache). This provides `market_cap`,
  `longBusinessSummary` and basic fundamentals used by the app.

This avoids external HTTP calls to Yahoo and prevents HTTP 401 noise.
"""
import os
from pathlib import Path
import pandas as pd
from datetime import datetime

try:
    from fundamental_cache import FundamentalCache
except Exception:
    FundamentalCache = None


def _local_csv_path(ticker: str) -> Path:
    # Accept ticker with or without .NS
    clean = ticker.replace('.NS', '')
    base = Path('scanner_cache') / 'historical'
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{clean}.csv"


def download(tickers, period=None, interval=None, auto_adjust=True, group_by='ticker', progress=False, threads=False, timeout=40):
    """Mimic yfinance.download interface minimally using local CSVs.

    If multiple tickers are requested, returns a dict-like mapping where keys
    are ticker symbols (without .NS) and values are DataFrames. For single
    ticker calls, returns a DataFrame.
    """
    # Normalize input
    single = False
    if isinstance(tickers, str):
        tickers = [tickers]
        single = True

    results = {}
    for t in tickers:
        path = _local_csv_path(t)
        if path.exists():
            try:
                df = pd.read_csv(path, parse_dates=True, index_col=0)
                results[t.replace('.NS', '')] = df
            except Exception:
                # On parse error, skip
                continue
        else:
            # No local data; return empty placeholder
            results[t.replace('.NS', '')] = pd.DataFrame()

    if single:
        return results.get(tickers[0].replace('.NS', ''), pd.DataFrame())

    # If yfinance-like MultiIndex expected, return a dict; callers handle DataFrame types
    return results


class Ticker:
    """Minimal Ticker replacement exposing `.info` and `.fast_info`.

    `.info` contains keys commonly used by the app. If `FundamentalCache` is
    available, we populate fields from it; otherwise `.info` will be empty.
    """
    def __init__(self, ticker: str):
        self.ticker = ticker.replace('.NS', '')
        self._info = None
        self._fast_info = None

    @property
    def info(self):
        if self._info is not None:
            return self._info

        info = {}
        # Try to populate from FundamentalCache if available
        try:
            if FundamentalCache is not None:
                data = FundamentalCache.get_fundamental_data(self.ticker, {})
                if data:
                    # Map known fields
                    info['longBusinessSummary'] = data.get('business_summary') or ''
                    info['sector'] = data.get('sector')
                    info['industry'] = data.get('industry')
                    info['shortName'] = data.get('shortName') or self.ticker
                    # Some numeric fundamentals
                    info['revenueGrowth'] = data.get('rev_growth')
                    info['returnOnEquity'] = data.get('roe')
                    info['debtToEquity'] = data.get('debt_equity')
                    # Market cap if present
                    info['marketCap'] = data.get('market_cap')
        except Exception:
            pass

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
                fi['market_cap'] = data.get('market_cap') if data else None
        except Exception:
            fi['market_cap'] = None

        self._fast_info = fi
        return self._fast_info


def __all__():
    return ['download', 'Ticker']
