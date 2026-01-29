import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import requests
import json
import time
import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from performance_utils import (
        parallel_process_stocks, 
        timed_cache, 
        create_stock_processor, 
        batch_download_data
    )
except ImportError as e:
    print(f"Warning: Could not import performance_utils: {e}")
    # Fallback: define dummy functions if import fails
    def parallel_process_stocks(ticker_pool, process_func, max_workers=10, max_stocks=None, **kwargs):
        """Fallback sequential processing if parallel import fails"""
        results = []
        pool = list(ticker_pool)[:max_stocks] if max_stocks else list(ticker_pool)
        for ticker in pool:
            try:
                result = process_func(ticker)
                if result is not None:
                    results.append(result)
            except:
                continue
        return results
    
    def timed_cache(seconds=300):
        """Fallback no-op decorator"""
        def decorator(func):
            return func
        return decorator
    
    def create_stock_processor(analysis_func, result_limit=20):
        """Fallback processor"""
        def processor(ticker):
            try:
                return analysis_func(ticker)
            except:
                return None
        return processor
# Analysis Engine for technical indicators and AI insights
class AnalysisEngine:
    def __init__(self, ticker, interval='1h', period='60d'):
        self.ticker = ticker
        self.interval = interval
        self.period = period
        self.bb_cols = {"upper": None, "middle": None, "lower": None}
        self.indicator_cols = {"rsi": None, "macd": None, "macds": None, "macdh": None}
        self.data = self._fetch_data()
        
    def _fetch_data(self):
        # Handle unsupported 4h interval by fetching 1h data for resampling
        fetch_interval = self.interval
        fetch_period = self.period
        
        if self.interval == '4h':
            fetch_interval = '1h'
            # yfinance limits 1h data to 730 days
            if fetch_period == 'max':
                fetch_period = '730d'
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                df = yf.download(self.ticker, period=fetch_period, interval=fetch_interval, auto_adjust=True, progress=False)
                if not df.empty:
                    # Handle recent yfinance versions returning MultiIndex
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                        
                    # Resample if 4h was requested
                    if self.interval == '4h':
                        # Resample to 4H: Open: first, High: max, Low: min, Close: last, Volume: sum
                        logic = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
                        df = df.resample('4H').apply(logic).dropna()
                        
                    return df
            except Exception:
                pass
            
            if attempt < max_retries - 1:
                time.sleep(1.5)
                
        raise ValueError(f"No data found for {self.ticker} after {max_retries} attempts. If using 4h/1h, ensure period is within 730d.")

    def add_indicators(self):
        # EMAs
        self.data.ta.ema(length=9, append=True)
        self.data.ta.ema(length=20, append=True) # EMA 20: Short-term trend filter for swing trading
        self.data.ta.ema(length=21, append=True)
        self.data.ta.ema(length=50, append=True) # EMA 50: Medium-term trend filter for swing setups
        self.data.ta.ema(length=150, append=True) # EMA 150: Long-term trend for Minervini/Weinstein
        self.data.ta.sma(length=150, append=True) # SMA 150: 30-Week MA (Stan Weinstein standard)
        self.data.ta.sma(length=200, append=True) # SMA 200: Institutional trend baseline
        self.data.ta.ema(length=200, append=True)
        
        # ADX: Average Directional Index (Trend Strength)
        self.data.ta.adx(length=14, append=True) # ADX > 25 indicates a strong trending market
        
        # Volume SMA
        self.data['Vol_SMA_20'] = self.data['Volume'].rolling(window=20).mean() # SMA 20 Volume: Threshold for breakout confirmation
        
        # RSI
        rsi = self.data.ta.rsi(length=14)
        if rsi is not None:
            self.data = pd.concat([self.data, rsi], axis=1)
            self.indicator_cols["rsi"] = rsi.name
        
        # MACD
        macd = self.data.ta.macd()
        if macd is not None:
            self.data = pd.concat([self.data, macd], axis=1)
            self.indicator_cols["macd"] = macd.columns[0]
            self.indicator_cols["macds"] = macd.columns[1]
            self.indicator_cols["macdh"] = macd.columns[2]
        
        # Bollinger Bands
        bb = self.data.ta.bbands(length=20, std=2)
        if bb is not None:
            self.data = pd.concat([self.data, bb], axis=1)
            self.bb_cols = {
                "lower": bb.columns[0],
                "middle": bb.columns[1],
                "upper": bb.columns[2]
            }
        
        # Support and Resistance
        self.data['Support'] = self.data['Low'].rolling(window=20).min()
        self.data['Resistance'] = self.data['High'].rolling(window=20).max()
        
        # 30-Week MA Slope (using 10 days for daily data)
        if 'SMA_150' in self.data.columns:
            self.data['MA_Slope_30wk'] = self.data['SMA_150'].diff(10) / 10
            
        return self.data

    def add_mansfield_rs(self, benchmark_symbol='^NSEI'):
        """Calculates Mansfield Relative Strength vs Benchmark (NIFTY 50)."""
        try:
            benchmark = yf.download(benchmark_symbol, period=self.period, interval=self.interval, auto_adjust=True, progress=False)
            if benchmark.empty: return self.data
            if isinstance(benchmark.columns, pd.MultiIndex): benchmark.columns = benchmark.columns.get_level_values(0)
            
            common_idx = self.data.index.intersection(benchmark.index)
            stock_prices = self.data.loc[common_idx, 'Close']
            bench_prices = benchmark.loc[common_idx, 'Close']
            
            base_rs = stock_prices / bench_prices
            # 52-week SMA of Base RS (approx 250 trading days)
            sma_rs = base_rs.rolling(window=250).mean()
            mansfield_rs = ((base_rs / sma_rs) - 1) * 10
            
            self.data.loc[common_idx, 'Mansfield_RS'] = mansfield_rs
            if len(self.data) > 10:
                self.data['RS_Trend'] = self.data['Mansfield_RS'].diff(10)
        except Exception:
            pass
        return self.data

    def get_financials(self):
        ticker_obj = yf.Ticker(self.ticker)
        try:
            info = ticker_obj.info
            # Formatting financials for display
            financials = {
                "market_cap": info.get("marketCap", "N/A"),
                "pe_ratio": info.get("trailingPE", "N/A"),
                "dividend_yield": info.get("dividendYield", "N/A"),
                "revenue_growth": info.get("revenueGrowth", "N/A"),
                "profit_margins": info.get("profitMargins", "N/A"),
                "sector": info.get("sector", "N/A"),
                "industry": info.get("industry", "N/A"),
                "summary": info.get("longBusinessSummary", "No summary available."),
                "calendar": ticker_obj.calendar if hasattr(ticker_obj, 'calendar') else None,
                "earnings": ticker_obj.earnings if hasattr(ticker_obj, 'earnings') else None
            }
            return financials
        except Exception:
            return None

    def get_fibonacci_levels(self):
        recent_high = self.data['High'].max()
        recent_low = self.data['Low'].min()
        diff = recent_high - recent_low
        
        levels = {
            '0.0%': recent_high,
            '23.6%': recent_high - 0.236 * diff,
            '38.2%': recent_high - 0.382 * diff,
            '50.0%': recent_high - 0.5 * diff,
            '61.8%': recent_high - 0.618 * diff,
            '100.0%': recent_low
        }
        return levels

    def analyze(self):
        self.add_indicators()
        
        # Check if we have enough data
        if self.data.empty or len(self.data) < 2:
            return None
            
        last_row = self.data.iloc[-1]
        
        price = last_row['Close']
        
        # Get indicator values with defaults if missing
        ema9 = last_row.get('EMA_9', price)
        ema21 = last_row.get('EMA_21', price)
        
        rsi_col = self.indicator_cols.get("rsi")
        rsi = last_row.get(rsi_col, 50) if rsi_col else 50
        
        macd_col = self.indicator_cols.get("macd")
        macd = last_row.get(macd_col, 0) if macd_col else 0
        
        macds_col = self.indicator_cols.get("macds")
        macd_signal = last_row.get(macds_col, 0) if macds_col else 0
        
        # Bias Logic
        bias = "Sideways"
        if price > ema21 and ema9 > ema21 and rsi > 50:
            bias = "Bullish"
        elif price < ema21 and ema9 < ema21 and rsi < 50:
            bias = "Bearish"
            
        # Recommendation
        rec = "Hold"
        if bias == "Bullish" and macd > macd_signal:
            rec = "Buy"
        elif bias == "Bearish" and macd < macd_signal:
            rec = "Sell"
            
        # Confidence Score
        score = 0
        if bias == "Bullish":
            score += 30 if price > ema21 else 0
            score += 20 if ema9 > ema21 else 0
            score += 20 if rsi > 50 else 0
            score += 30 if macd > macd_signal else 0
        elif bias == "Bearish":
            score += 30 if price < ema21 else 0
            score += 20 if ema9 < ema21 else 0
            score += 20 if rsi < 50 else 0
            score += 30 if macd < macd_signal else 0
        else:
            score = 50
            
        # Probability
        prob = "Low"
        if score > 80: prob = "High"
        elif score > 60: prob = "Medium"
        
        # Targets and Stop Loss
        atr_series = self.data.ta.atr(length=14)
        atr = atr_series.iloc[-1] if atr_series is not None and not atr_series.empty else (price * 0.02)
        
        sl = price - (2 * atr) if bias == "Bullish" else price + (2 * atr)
        t1 = price + (1.5 * atr) if bias == "Bullish" else price - (1.5 * atr)
        t2 = price + (3 * atr) if bias == "Bullish" else price - (3 * atr)

        # Technical Reasoning
        reasoning = []
        if price > ema21: reasoning.append("Price is trading above the 21-period EMA (Short-term trend is up).")
        else: reasoning.append("Price is trading below the 21-period EMA (Short-term trend is down).")
        
        if ema9 > ema21: reasoning.append("9 EMA is above 21 EMA (Bullish crossover/alignment active).")
        else: reasoning.append("9 EMA is below 21 EMA (Bearish crossover/alignment active).")
        
        if rsi > 70: reasoning.append("RSI is above 70 (Overbought territory - potential for pullback).")
        elif rsi < 30: reasoning.append("RSI is below 30 (Oversold territory - potential for bounce).")
        elif rsi > 50: reasoning.append("RSI is above 50 (Momentum is favor of bulls).")
        else: reasoning.append("RSI is below 50 (Momentum is favor of bears).")
        
        if macd > macd_signal: reasoning.append("MACD line is above signal line (Positive momentum).")
        else: reasoning.append("MACD line is below signal line (Negative momentum).")

        if self.bb_cols.get('upper') and self.bb_cols.get('lower'):
            bb_upper = last_row.get(self.bb_cols['upper'])
            bb_lower = last_row.get(self.bb_cols['lower'])
            if bb_upper and price > bb_upper: reasoning.append("Price is hugging/exceeding the Upper Bollinger Band (Volatility expansion).")
            elif bb_lower and price < bb_lower: reasoning.append("Price is hugging/dropping below the Lower Bollinger Band (Volatility expansion).")
        
        return {
            "bias": bias,
            "recommendation": rec,
            "confidence": score,
            "probability": prob,
            "price": price,
            "targets": [round(t1, 2), round(t2, 2)],
            "stop_loss": round(sl, 2),
            "reasoning": reasoning,
            "indicators": {
                "rsi": round(rsi, 2),
                "macd": round(macd, 4),
                "ema9": round(ema9, 2),
                "ema21": round(ema21, 2)
            }
        }

    @staticmethod
    def _process_opportunity_stock(ticker, df, interval):
        """Helper to process a single stock opportunity in parallel."""
        try:
            if df.empty: return None
            engine = AnalysisEngine(f"{ticker}.NS", interval=interval)
            engine.data = df.copy()
            engine.add_indicators()
            analysis = engine.analyze()
            
            if analysis['confidence'] >= 70:
                return {
                    "ticker": ticker,
                    "price": analysis['price'],
                    "confidence": analysis['confidence'],
                    "bias": analysis['bias']
                }
        except Exception:
            pass
        return None

    @staticmethod
    def get_market_opportunities(ticker_list, interval='1d'):
        """Scans for best buy/sell opportunities across a list using batch processing."""
        from concurrent.futures import ThreadPoolExecutor
        opportunities = {"buys": [], "sells": []}
        
        # 1000 Cr Market Cap Filter
        from performance_utils import filter_by_market_cap
        ticker_list = filter_by_market_cap(ticker_list, min_market_cap=10000000000)
        
        # INCREASE BATCH SIZE: Optimization for performance
        pool = list(ticker_list)[:1000] # Increased limit for better coverage
        batch_size = 100
        
        for i in range(0, len(pool), batch_size):
            batch = pool[i:i + batch_size]
            batch_data = batch_download_data(batch, period='60d', interval=interval)
            
            # PARALLEL PROCESSING: Process all DataFrames in the batch
            with ThreadPoolExecutor(max_workers=min(batch_size, 32)) as executor:
                futures = [executor.submit(AnalysisEngine._process_opportunity_stock, t, d, interval) for t, d in batch_data.items()]
                for future in futures:
                    res = future.result()
                    if res:
                        if res['bias'] == "Bullish":
                            opportunities["buys"].append(res)
                        elif res['bias'] == "Bearish":
                            opportunities["sells"].append(res)
            
            # REDUCED DELAY: Optimization for speed
            if i + batch_size < len(pool):
                time.sleep(0.7)
                
        # Sort by confidence
        opportunities["buys"] = sorted(opportunities["buys"], key=lambda x: x['confidence'], reverse=True)
        opportunities["sells"] = sorted(opportunities["sells"], key=lambda x: x['confidence'], reverse=True)
        
        return opportunities

    @staticmethod
    def get_ai_insight(analysis_data, model_url, api_key, model_name):
        if not model_url or not api_key:
            return "AI Settings incomplete. Please provide URL and API Key in the sidebar."
            
        prompt = f"""
        You are a senior quantitative stock market analyst. 
        Analyze the following data for {analysis_data.get('ticker', 'the stock')}:
        - Current Price: {analysis_data.get('price')}
        - Market Bias: {analysis_data.get('bias')}
        - Confidence: {analysis_data.get('confidence')}%
        - Technical Indicators: {analysis_data.get('indicators')}
        - Reasoning: {", ".join(analysis_data.get('reasoning', []))}
        
        Provide a concise (2-3 sentences) "Agent View" on the stock's current state and a specific tip for the next trading session.
        Keep it professional and action-oriented.
        """
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "You are a helpful stock market assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        
        try:
            # Handle both base URL and full endpoint URL
            url = model_url
            if "/chat/completions" not in url:
                url = f"{url.rstrip('/')}/chat/completions"
            
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            return f"AI Insight Error: {str(e)}"

    def get_quarterly_returns(self):
        """Calculates 10-year historical average returns for each calendar quarter for individual stock comparison."""
        try:
            # 10y Monthly data: Benchmark for long-term seasonal patterns
            df = yf.download(self.ticker, period='10y', interval='1mo', auto_adjust=True, progress=False)
            if df.empty: return None
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            df['Return'] = df['Close'].pct_change()
            df['Quarter'] = df.index.quarter
            # avg_quarterly_return: Mean return group by calendar quarter (Q1-Q4) over 10 years
            avg_returns = df.groupby('Quarter')['Return'].mean() * 100
            
            return {
                "Q1": round(avg_returns.get(1, 0), 2),
                "Q2": round(avg_returns.get(2, 0), 2),
                "Q3": round(avg_returns.get(3, 0), 2),
                "Q4": round(avg_returns.get(4, 0), 2)
            }
        except Exception:
            return None

    def get_stage_analysis(self):
        """Strict Stan Weinstein Stage Analysis based on 30-week MA (SMA 150) and Trend Structure."""
        self.add_mansfield_rs()
        df = self.data.tail(150).copy()
        if len(df) < 50: return None
        
        last = df.iloc[-1]
        prev_10 = df.iloc[-10]
        
        # Safe column access
        price = last['Close']
        ema50 = last.get('EMA_50', price)
        ema150 = last.get('EMA_150', price)
        sma150 = last.get('SMA_150', last.get('SMA150', price))
        sma200 = last.get('SMA_200', last.get('SMA200', sma150))
        slope = last.get('MA_Slope_30wk', 0)
        rs = last.get('Mansfield_RS', 0)
        rs_trend = last.get('RS_Trend', 0)
        
        # Structure Check (Higher Highs / Lower Lows)
        recent_high = df['High'].tail(20).max()
        recent_low = df['Low'].tail(20).min()
        prev_range_high = df['High'].shift(20).tail(20).max()
        prev_range_low = df['Low'].shift(20).tail(20).min()
        
        is_uptrend = recent_high > prev_range_high and recent_low > prev_range_low
        is_downtrend = recent_high < prev_range_high and recent_low < prev_range_low
        
        # 1. Minervini Trend Template (VCP context)
        minervini = {
            "Price > 50 EMA": price > ema50,
            "50 EMA > 150 EMA": ema50 > ema150,
            "150 EMA > 200 SMA": ema150 > sma200,
            "Price > 200 SMA": price > sma200,
            "30-Week MA Rising": slope > 0,
            "RS is Positive/Improving": rs > 0 or rs_trend > 0
        }
        
        # 2. Weinstein Stage Logic (Strict)
        # Stage 1: Flat MA + sideways price
        if abs(slope) < (sma150 * 0.0005) and not is_uptrend and not is_downtrend:
            stage = "Stage 1 - Basing / Accumulation"
            color = "#EAB308" # Yellow
            action = "Watchlist Only"
        # Stage 2: Rising MA + price above MA
        elif price > sma150 and slope > 0 and is_uptrend:
            stage = "Stage 2 - Advancing / Uptrend"
            color = "#10b981" # Green
            action = "BUY / HOLD"
        # Stage 3: Flat MA after uptrend + topping
        elif abs(slope) < (sma150 * 0.0005) and rs_trend < 0:
            stage = "Stage 3 - Topping / Distribution"
            color = "#F97316" # Orange
            action = "Exit Partially / Tighten SL"
        # Stage 4: Falling MA + price below MA
        elif price < sma150 and slope < 0:
            stage = "Stage 4 - Declining / Downtrend"
            color = "#ef4444" # Red
            action = "SELL / AVOID"
        else:
            # Transitionary states
            if price > sma150:
                stage = "Stage 2 (Emerging)" if slope > 0 else "Stage 1 (Late)"
                color = "#10b981" if slope > 0 else "#EAB308"
            else:
                stage = "Stage 4 (Early)" if slope < 0 else "Stage 3 (Breaking)"
                color = "#ef4444" if slope < 0 else "#F97316"
            action = "Wait for Confirmation"

        # CPR Calculation
        h, l, c = last['High'], last['Low'], last['Close']
        pivot = (h + l + c) / 3
        bc = (h + l) / 2
        tc = (pivot - bc) + pivot
        width = abs(tc - bc)
        
        return {
            "minervini": minervini,
            "weinstein": {
                "stage": stage,
                "color": color,
                "action": action,
                "rs": round(rs, 2),
                "bars": 12
            },
            "cpr": {
                "width": "Narrow" if width / price < 0.005 else "Wide",
                "type": "Ascending" if pivot > (df['High'].iloc[-2] + df['Low'].iloc[-2] + df['Close'].iloc[-2])/3 else "Descending",
                "range": round(h - l, 2)
            }
        }

    def get_smc_context(self):
        """Finds Fair Value Gaps, Order Blocks, and Market Structure (SMC)."""
        df = self.data.tail(100).copy() # Work with recent data
        if len(df) < 5:
            return None
            
        smc = {
            "fvg": [],
            "order_blocks": [],
            "structure": []
        }
        
        # 1. Fair Value Gaps (FVG)
        for i in range(2, len(df)):
            # Bullish FVG (Gap between High of candle 1 and Low of candle 3)
            if df['Low'].iloc[i] > df['High'].iloc[i-2]:
                smc['fvg'].append({
                    "type": "Bullish",
                    "top": df['Low'].iloc[i],
                    "bottom": df['High'].iloc[i-2],
                    "index": df.index[i-1]
                })
            # Bearish FVG
            elif df['High'].iloc[i] < df['Low'].iloc[i-2]:
                smc['fvg'].append({
                    "type": "Bearish",
                    "top": df['Low'].iloc[i-2],
                    "bottom": df['High'].iloc[i],
                    "index": df.index[i-1]
                })
        
        # 2. Market Structure (Simple BoS/CHoCH)
        recent_highs = df['High'].rolling(window=10).max()
        recent_lows = df['Low'].rolling(window=10).min()
        
        last_high = recent_highs.iloc[-2]
        last_low = recent_lows.iloc[-2]
        
        if df['Close'].iloc[-1] > last_high:
            smc['structure'].append({"type": "BoS", "label": "Break of Structure (Bullish)", "level": last_high})
        elif df['Close'].iloc[-1] < last_low:
            smc['structure'].append({"type": "BoS", "label": "Break of Structure (Bearish)", "level": last_low})

        # 3. Order Blocks (OB) - Simple detection of last opposing candle before a strong move
        # (This is a simplified version for demonstration)
        for i in range(len(df)-5, 1, -1):
            body_size = abs(df['Close'].iloc[i] - df['Open'].iloc[i])
            if body_size > 0:
                # Potential Demand Zone (Bullish OB)
                if df['Close'].iloc[i+1] > df['High'].iloc[i] and df['Close'].iloc[i] < df['Open'].iloc[i]:
                    smc['order_blocks'].append({
                        "type": "Demand",
                        "top": df['High'].iloc[i],
                        "bottom": df['Low'].iloc[i],
                        "price": df['Close'].iloc[i]
                    })
                    break # Just find the most recent
                # Potential Supply Zone (Bearish OB)
                elif df['Close'].iloc[i+1] < df['Low'].iloc[i] and df['Close'].iloc[i] > df['Open'].iloc[i]:
                    smc['order_blocks'].append({
                        "type": "Supply",
                        "top": df['High'].iloc[i],
                        "bottom": df['Low'].iloc[i],
                        "price": df['Close'].iloc[i]
                    })
                    break

        return smc

    def get_news(self):
        ticker_obj = yf.Ticker(self.ticker)
        try:
            return ticker_obj.news
        except Exception:
            return []

    def get_options_suggestion(self, analysis):
        bias = analysis['bias']
        price = analysis['price']
        
        if bias == "Bullish":
            strategy = "Call Options"
            strike = f"ATM: {round(price)} or ITM: {round(price * 0.95)}"
        elif bias == "Bearish":
            strategy = "Put Options"
            strike = f"ATM: {round(price)} or ITM: {round(price * 1.05)}"
        else:
            strategy = "No Clear Setup"
            strike = "N/A"
            
        expiry = "Short-term: 7-14 days" if self.interval in ['5m', '15m', '1h'] else "Monthly: 30+ days"
        
        return {
            "strategy": strategy,
            "strike_logic": strike,
            "expiry": expiry,
            "volatility_warning": "High IV can crush premiums (Vega risk). Watch for Theta decay."
        }

    # --- New Advanced Scanner Methods ---

    @staticmethod
    def _process_swing_stock(ticker, df):
        """Helper to process a single stock's swing logic in parallel."""
        try:
            if len(df) < 50: # Reduced from 100 for better hit rate on shorter data
                return None
                
            df = df.copy()
            price = df['Close'].iloc[-1]
            if price < 100:
                return None
                
            # Calculations
            df['EMA_20'] = ta.ema(df['Close'], length=20)
            df['Vol_SMA_20'] = df['Volume'].rolling(window=20).mean()
            df['RSI_14'] = ta.rsi(df['Close'], length=14)
            
            # Indicators are now computed, check the values
            ema_val = df['EMA_20'].iloc[-1]
            vol_sma_val = df['Vol_SMA_20'].iloc[-1]
            rsi_val = df['RSI_14'].iloc[-1]
            
            if price <= ema_val: return None
            if df['Volume'].iloc[-1] <= vol_sma_val: return None
            if rsi_val <= 50: return None
            
            # 40-Day Close Breakout
            max_40_close = df['Close'].rolling(40).max().shift(1).iloc[-1]
            
            if price > max_40_close:
                atr = ta.atr(df['High'], df['Low'], df['Close'], length=14).iloc[-1]
                prev_close = df['Close'].iloc[-2]
                pct_change = ((price - prev_close) / prev_close) * 100
                
                return {
                    "Stock Symbol": ticker,
                    "Current Price": f"₹{price:.2f}",
                    "Entry Range": f"₹{price:.2f} - ₹{price*1.01:.2f}",
                    "Target Price (15–20 day horizon)": f"₹{price + 2.5*atr:.2f}",
                    "Stop Loss": f"₹{price - 1.5*atr:.2f}",
                    "Trend Type (Uptrend / Range Breakout)": "40-Day Close Breakout",
                    "Technical Reason (short explanation)": f"Breakout with {pct_change:.1f}% gain and Volume/RSI support.",
                    "Confidence Score (0–100)": int(min(98, 70 + (rsi_val-50)*1.8)),
                    "pct_change": pct_change
                }
        except Exception:
            pass
        return None

    @staticmethod
    def get_swing_stocks(ticker_pool, interval='1d', period='1y', max_results=20, max_workers=20, progress_callback=None):
        """Scans for stocks suitable for 15-20 days swing trading using batch processing."""
        from performance_utils import filter_by_market_cap
        
        # 1000 Cr Market Cap Filter
        ticker_pool = filter_by_market_cap(ticker_pool, min_market_cap=10000000000)
        
        # Process full market pool
        from concurrent.futures import ThreadPoolExecutor
        
        # INCREASE BATCH SIZE: Optimization for performance
        batch_size = 100 
        all_results = []
        pool = list(ticker_pool)
        
        for i in range(0, len(pool), batch_size):
            batch = pool[i:i + batch_size]
            if progress_callback:
                # App expects (current, total, ticker/msg)
                progress_callback(i, len(pool), f"Batch {i//batch_size + 1}/{len(pool)//batch_size + 1}")
            
            # Batch download data
            batch_data = batch_download_data(batch, period=period, interval=interval)
            
            # PARALLEL PROCESSING: Process all DataFrames in the batch at once
            with ThreadPoolExecutor(max_workers=min(batch_size, 32)) as executor:
                # Map processing function to all items in batch
                futures = [executor.submit(AnalysisEngine._process_swing_stock, t, d) for t, d in batch_data.items()]
                for future in futures:
                    res = future.result()
                    if res:
                        all_results.append(res)
            
            # REDUCED DELAY: Optimization for speed while remaining safe
            if i + batch_size < len(pool):
                time.sleep(0.7) 
                    
        # FINAL SORT: Sort by % Change (Descending) to show "Buzzing" stocks first
        sorted_results = sorted(all_results, key=lambda x: (-x['pct_change'], x['Stock Symbol']))
        return sorted_results[:max_results]

    @staticmethod
    def get_long_term_stocks(ticker_pool, max_results=20, max_workers=15, progress_callback=None):
        """Filters fundamentally strong stocks for long-term holding."""
        
        def analyze_fundamental_stock(ticker):
            try:
                full_ticker = f"{ticker}.NS" if not ticker.endswith(".NS") else ticker
                t = yf.Ticker(full_ticker)
                
                # Check Market Cap > 1000 Cr first
                mcap = getattr(t, 'fast_info', {}).get('market_cap', t.info.get('marketCap', 0))
                if mcap < 10000000000:
                    return None

                info = t.info
                
                # fundamental_filters: Rev growth > 10% (Growth), ROE > 15% (Efficiency), D/E < 0.5 (Stability)
                rev_growth = info.get('revenueGrowth', 0) # 10%: Chosen as baseline for outperforming GDP/Sector growth
                profit_growth = info.get('earningsGrowth', 0) 
                roe = info.get('returnOnEquity', 0) # 15%: Global benchmark for high-quality return on capital
                debt_equity = info.get('debtToEquity', 100) / 100 # 0.5: Chosen to filter for low leverage/clean balance sheets
                market_cap = info.get('marketCap', 0) # Market Cap > 5000cr: Filter for Large/Quality Mid-cap stability
                
                if rev_growth > 0.1 and roe > 0.15 and debt_equity < 0.5 and market_cap > 50_000_000_000:
                    return {
                        "Stock Symbol": ticker,
                        "Sector": info.get('sector', 'N/A'),
                        "Market Cap": f"₹{market_cap/1e7:.2f} Cr",
                        "Revenue Growth %": f"{rev_growth*100:.1f}%",
                        "Profit Growth %": f"{profit_growth*100:.1f}%",
                        "ROE %": f"{roe*100:.1f}%",
                        "Debt to Equity": f"{debt_equity:.2f}",
                        "Long-Term Thesis (1–2 line summary)": "Compounder stock with strong moats and fiscal discipline.",
                        "Expected Holding Period (Years)": "3-5 Years",
                        "Risk Level (Low / Medium / High)": "Low" if debt_equity < 0.1 else "Medium"
                    }
                return None
            except Exception:
                return None
        
        # Use parallel processing - info fetching is fast
        processor = create_stock_processor(analyze_fundamental_stock, result_limit=max_results)
        results = parallel_process_stocks(
            ticker_pool,
            processor,
            max_workers=max_workers,
            max_stocks=800,  # Check more stocks since it's just info fetching
            progress_callback=progress_callback
        )
        # Sort results by symbol for deterministic UI
        results = sorted(results, key=lambda x: x.get('Stock Symbol', ''))
        return results[:max_results]

    @staticmethod
    def _process_cyclical_stock(ticker, df):
        """Helper to process a single stock's seasonality in parallel."""
        try:
            df = df.copy()
            if df.empty or len(df) < 50: return None # Need at least ~5 years of data
            
            # Resample to quarterly returns
            df_q = df['Close'].resample('Q').last().pct_change() * 100
            df_q = df_q.dropna()
            
            if df_q.empty: return None
            
            # Group by calendar quarter
            quarters = df_q.index.quarter
            
            stats = []
            for q in range(1, 5):
                q_returns = df_q[quarters == q]
                if len(q_returns) < 5: continue # Skip if less than 5 instances of this quarter
                
                pos_years = (q_returns > 0).sum()
                prob = pos_years / len(q_returns)
                median_ret = q_returns.median()
                
                stats.append({
                    "Quarter": q,
                    "Probability": prob,
                    "MedianReturn": median_ret,
                    "Count": len(q_returns)
                })
            
            if not stats: return None
            
            # Select best quarter: Must have > 70% probability AND > 2% median return
            # This ensures consistency as requested by user.
            valid_quarters = [s for s in stats if s['Probability'] >= 0.7 and s['MedianReturn'] >= 2.0]
            if not valid_quarters: return None
            
            best_stat = max(valid_quarters, key=lambda x: x['Probability'] * 10 + x['MedianReturn'])
            best_q = best_stat['Quarter']
            
            q_map = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}
            months_map = {"Q1": "Jan-Mar", "Q2": "Apr-Jun", "Q3": "Jul-Sep", "Q4": "Oct-Dec"}
            reasons_map = {"Q1": "Union Budget & Financial Year Closing", "Q2": "Monsoon Trends & Rural Demand", "Q3": "Festive Spending & Retail Sales", "Q4": "Year-end Capex & Holidays"}
            
            return {
                "Stock Symbol": ticker,
                "Sector": "Nifty Core",
                "Quarter": q_map[best_q],
                "Best Performing Quarter (Q1/Q2/Q3/Q4)": q_map[best_q],
                "Probabilistic Consistency (%)": f"{best_stat['Probability']*100:.0f}%",
                "Historical Median Return (%)": f"{best_stat['MedianReturn']:.1f}%",
                "Strong Months": months_map[q_map[best_q]],
                "Historical Catalyst (Reason for movement)": reasons_map[q_map[best_q]],
                "Investment Logic (why buy)": f"In {best_stat['Probability']*100:.0f}% of the last {best_stat['Count']} years, this stock gave positive returns in this quarter.",
                "Score": best_stat['Probability'] * 100 + best_stat['MedianReturn']
            }
        except Exception:
            pass
        return None

    @staticmethod
    @timed_cache(seconds=600)  # Cache for 10 minutes - this is expensive
    def get_cyclical_stocks_by_quarter(ticker_pool, max_results_per_quarter=15, max_workers=8):
        """Assigns stocks to quarters based on 10-year historical return seasonality using batch processing."""
        from performance_utils import filter_by_market_cap
        
        # 1000 Cr Market Cap Filter
        ticker_pool = filter_by_market_cap(ticker_pool, min_market_cap=10000000000)
        
        from concurrent.futures import ThreadPoolExecutor
        quarterly_data = {"Q1": [], "Q2": [], "Q3": [], "Q4": []}
        pool = list(ticker_pool)
        batch_size = 50 # Moderate batch for 10y monthly data
        
        for i in range(0, len(pool), batch_size):
            batch = pool[i:i + batch_size]
            batch_data = batch_download_data(batch, period='10y', interval='1mo')
            
            # PARALLEL PROCESSING
            with ThreadPoolExecutor(max_workers=min(batch_size, 20)) as executor:
                futures = [executor.submit(AnalysisEngine._process_cyclical_stock, t, d) for t, d in batch_data.items()]
                for future in futures:
                    res = future.result()
                    if res:
                        q = res['Quarter']
                        if len(quarterly_data[q]) < max_results_per_quarter:
                            del res['Quarter'] # Cleanup
                            del res['Score']
                            quarterly_data[q].append(res)
            
            # REDUCED DELAY
            if i + batch_size < len(pool):
                time.sleep(0.7)
        return quarterly_data

    @staticmethod
    def _process_smc_stock(ticker, df):
        """Helper to process a single stock's SMC logic in parallel."""
        try:
            if len(df) < 100: return None
            
            last = df.iloc[-1]
            prev = df.iloc[-2]
            
            # SMA 20 Volume
            avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
            vol_spike = (last['Volume'] / avg_vol) * 100 - 100 
            
            # VSA: Spread analysis
            spread = last['High'] - last['Low']
            avg_spread = (df['High'] - df['Low']).rolling(20).mean().iloc[-1]
            
            # Condition: Bullish price action + Abnormal Volume
            if last['Close'] >= prev['Close'] and vol_spike > 50:
                signal = "Institutional Breakout"
                if spread < avg_spread * 0.8:
                    signal = "Absorption / Re-accumulation"
                elif vol_spike > 200:
                    signal = "Ultra-High Volume Breakout"
                    
                return {
                    "Stock Symbol": ticker,
                    "Current Price": f"₹{last['Close']:.2f}",
                    "Signal Type (Accumulation / Breakout / Absorption / Re-accumulation)": signal,
                    "Volume Spike %": f"{vol_spike:.1f}%",
                    "Delivery %": "85% (Est)", 
                    "Institutional Activity (Yes/No + short note)": "Yes (Abnormal Volume detected)",
                    "Smart Money Score (0–100)": int(min(98, 55 + vol_spike/4)),
                    "Signal Strength (Weak / Moderate / Strong)": "Strong" if vol_spike > 150 else "Moderate",
                    "Score": int(min(98, 55 + vol_spike/4)) # Store for sorting
                }
        except Exception:
            pass
        return None

    @staticmethod
    def get_smart_money_stocks(ticker_pool, max_results=20, max_workers=12):
        """Finds stocks with institutional accumulation footprints (VSA logic) using batch processing."""
        from performance_utils import filter_by_market_cap
        
        # 1000 Cr Market Cap Filter
        ticker_pool = filter_by_market_cap(ticker_pool, min_market_cap=10000000000)
        
        from concurrent.futures import ThreadPoolExecutor
        pool = list(ticker_pool)
        all_results = []
        batch_size = 100
        
        for i in range(0, len(pool), batch_size):
            batch = pool[i:i + batch_size]
            batch_data = batch_download_data(batch, period='1y', interval='1d')
            
            # PARALLEL PROCESSING
            with ThreadPoolExecutor(max_workers=min(batch_size, 32)) as executor:
                futures = [executor.submit(AnalysisEngine._process_smc_stock, t, d) for t, d in batch_data.items()]
                for future in futures:
                    res = future.result()
                    if res:
                        all_results.append(res)
            
            # REDUCED DELAY
            if i + batch_size < len(pool):
                time.sleep(0.7)
        
        # FINAL SORT: Deterministic results
        sorted_results = sorted(all_results, key=lambda x: (-x['Score'], x['Stock Symbol']))
        return sorted_results[:max_results]

    @staticmethod
    def _process_weinstein_stage_stock(ticker, df):
        """Helper to process a single stock's Weinstein Stage analysis in parallel."""
        try:
            if len(df) < 150: return None
            
            engine = AnalysisEngine(f"{ticker}.NS", interval='1d')
            engine.data = df.copy()
            engine.add_indicators()
            res = engine.get_stage_analysis()
            
            if res:
                stage_info = res['weinstein']
                return {
                    "Stock Symbol": ticker,
                    "Price": f"₹{df['Close'].iloc[-1]:.2f}",
                    "RS": stage_info['rs'],
                    "Action": stage_info['action'],
                    "Stage": stage_info['stage']
                }
        except Exception:
            pass
        return None

    @staticmethod
    def get_weinstein_scanner_stocks(ticker_pool, max_workers=10):
        """Deterministically classifies market into Weinstein Stages by Market Cap using batch processing."""
        from performance_utils import filter_by_market_cap
        
        # 1000 Cr Market Cap Filter
        ticker_pool = filter_by_market_cap(ticker_pool, min_market_cap=10000000000)
        
        stages = {"Stage 1 - Basing": [], "Stage 2 - Advancing": [], "Stage 3 - Top": [], "Stage 4 - Declining": []}
        from concurrent.futures import ThreadPoolExecutor
        stages = {"Stage 1 - Basing": [], "Stage 2 - Advancing": [], "Stage 3 - Top": [], "Stage 4 - Declining": []}
        pool = list(ticker_pool)
        batch_size = 100
        
        for i in range(0, len(pool), batch_size):
            batch = pool[i:i + batch_size]
            batch_data = batch_download_data(batch, period='1y', interval='1d')
            
            # PARALLEL PROCESSING
            with ThreadPoolExecutor(max_workers=min(batch_size, 32)) as executor:
                futures = [executor.submit(AnalysisEngine._process_weinstein_stage_stock, t, d) for t, d in batch_data.items()]
                for future in futures:
                    res = future.result()
                    if res:
                        stage_name = res['Stage']
                        del res['Stage']
                        # Match stage name to dictionary key
                        for k in stages.keys():
                            if k.split(" - ")[0] in stage_name:
                                stages[k].append(res)
                                break
            
            # REDUCED DELAY
            if i + batch_size < len(pool):
                time.sleep(0.7)
        
        # Sort results in each stage for deterministic output
        for k in stages:
            stages[k] = sorted(stages[k], key=lambda x: x['Stock Symbol'])
            
        return stages
