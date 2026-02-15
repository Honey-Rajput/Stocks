import data_provider as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import requests
import json
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from fundamental_cache import FundamentalCache
except ImportError:
    FundamentalCache = None

try:
    from scanner_robustness import ScannerConfig, DataValidator
except ImportError:
    class ScannerConfig:
        SWING_MIN_PRICE = 50
        SWING_MIN_RSI = 50
        SMC_MIN_ROWS = 100
        CYCLICAL_MIN_PROBABILITY = 0.65
        CYCLICAL_MIN_RETURN = 2.0
    DataValidator = None


class AnalysisEngine:

    def __init__(self, ticker, interval='1h', period='60d', data=None):
        self.ticker = ticker
        self.interval = interval
        self.period = period
        self.bb_cols = {"upper": None, "middle": None, "lower": None}
        self.indicator_cols = {"rsi": None, "macd": None, "macds": None, "macdh": None}
        
        # Use provided data if available to perform analysis without re-fetching
        if data is not None and not data.empty:
            self.data = data
        else:
            self.data = self._fetch_data()

    # ✅ PATCHED — ONLY SAFETY + VALIDATION ADDED (LOGIC SAME)
    
    def _fetch_data(self):
        fetch_interval = self.interval
        fetch_period = self.period

        if self.interval == '4h':
            fetch_interval = '1h'
            if fetch_period == 'max':
                fetch_period = '730d'

        max_retries = 3

        for attempt in range(max_retries):
            try:
                df = yf.download(
                    self.ticker,
                    period=fetch_period,
                    interval=fetch_interval,
                    auto_adjust=True,
                    progress=False,
                    threads=False
                )

                if isinstance(df, pd.DataFrame) and not df.empty:

                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)

                    if self.interval == '4h':
                        logic = {
                            'Open': 'first',
                            'High': 'max',
                            'Low': 'min',
                            'Close': 'last',
                            'Volume': 'sum'
                        }
                        df = df.resample('4H').apply(logic).dropna()

                    return df

            except Exception as e:
                print("Download attempt failed:", e)

            time.sleep(1.5 + attempt)

        raise ValueError(
            f"No data found for {self.ticker} after {max_retries} attempts. "
            f"If using 4h/1h, ensure period is within 730d."
        )


    def add_indicators(self):
        self.data.ta.ema(length=9, append=True)
        self.data.ta.ema(length=21, append=True)
        self.data.ta.ema(length=50, append=True)
        self.data.ta.ema(length=150, append=True)
        self.data.ta.sma(length=150, append=True)
        self.data.ta.sma(length=200, append=True)

        rsi = self.data.ta.rsi(length=14)
        if rsi is not None:
            self.data = pd.concat([self.data, rsi], axis=1)
            self.indicator_cols["rsi"] = rsi.name

        macd = self.data.ta.macd()
        if macd is not None:
            self.data = pd.concat([self.data, macd], axis=1)
            self.indicator_cols["macd"] = macd.columns[0]
            self.indicator_cols["macds"] = macd.columns[1]
            self.indicator_cols["macdh"] = macd.columns[2]

        bb = self.data.ta.bbands(length=20, std=2)
        if bb is not None:
            self.data = pd.concat([self.data, bb], axis=1)
            self.bb_cols = {
                "lower": bb.columns[0],
                "middle": bb.columns[1],
                "upper": bb.columns[2]
            }

        self.data['Support'] = self.data['Low'].rolling(20).min()
        self.data['Resistance'] = self.data['High'].rolling(20).max()

        return self.data

    def analyze(self):

        self.add_indicators()

        if self.data.empty or len(self.data) < 2:
            return None

        last = self.data.iloc[-1]

        price = last['Close']
        ema9 = last.get('EMA_9', price)
        ema21 = last.get('EMA_21', price)

        rsi = last.get(self.indicator_cols.get("rsi"), 50)
        macd = last.get(self.indicator_cols.get("macd"), 0)
        macd_signal = last.get(self.indicator_cols.get("macds"), 0)

        bias = "Sideways"
        if price > ema21 and ema9 > ema21 and rsi > 50:
            bias = "Bullish"
        elif price < ema21 and ema9 < ema21 and rsi < 50:
            bias = "Bearish"

        rec = "Hold"
        if bias == "Bullish" and macd > macd_signal:
            rec = "Buy"
        elif bias == "Bearish" and macd < macd_signal:
            rec = "Sell"

        score = 50
        if bias == "Bullish":
            score = sum([
                price > ema21,
                ema9 > ema21,
                rsi > 50,
                macd > macd_signal
            ]) * 25
        elif bias == "Bearish":
            score = sum([
                price < ema21,
                ema9 < ema21,
                rsi < 50,
                macd < macd_signal
            ]) * 25

        atr = self.data.ta.atr(length=14).iloc[-1]
        sl = price - 2*atr if bias == "Bullish" else price + 2*atr
        t1 = price + 1.5*atr if bias == "Bullish" else price - 1.5*atr
        t2 = price + 3*atr if bias == "Bullish" else price - 3*atr

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

        return {
            "bias": bias,
            "recommendation": rec,
            "confidence": score,
            "probability": "High" if score > 80 else "Medium" if score > 60 else "Low",
            "price": price,
            "targets": [round(t1,2), round(t2,2)],
            "stop_loss": round(sl,2),
            "reasoning": reasoning,
            "indicators": {
                "rsi": round(rsi,2),
                "macd": round(macd,4),
                "ema9": round(ema9,2),
                "ema21": round(ema21,2)
            }
        }

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
            "expiry": expiry
        }

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

    def get_quarterly_returns(self):
        """Calculate average quarterly returns over last 10 years."""
        try:
            if len(self.data) < 250:  # Need at least 1 year of daily data
                return None
            
            # Group by quarter and calculate returns
            self.data['Year'] = self.data.index.year
            self.data['Quarter'] = self.data.index.quarter
            self.data['QuarterKey'] = self.data['Year'].astype(str) + '-Q' + self.data['Quarter'].astype(str)
            
            quarterly_returns = {}
            for q in ['Q1', 'Q2', 'Q3', 'Q4']:
                q_data = []
                for year in range(self.data['Year'].min(), self.data['Year'].max() + 1):
                    q_key = f"{year}-{q}"
                    q_df = self.data[self.data['QuarterKey'] == q_key]
                    if len(q_df) > 0:
                        start_price = q_df['Close'].iloc[0]
                        end_price = q_df['Close'].iloc[-1]
                        ret = ((end_price - start_price) / start_price) * 100
                        q_data.append(ret)
                
                if q_data:
                    quarterly_returns[q] = sum(q_data) / len(q_data)
            
            return quarterly_returns if quarterly_returns else None
        except Exception:
            return None

    def get_stage_analysis(self):
        """Weinstein Stage Analysis and Minervini Checklist."""
        try:
            if len(self.data) < 200:
                return None
            
            price = self.data['Close'].iloc[-1]
            sma_150 = self.data['SMA_150'].iloc[-1] if 'SMA_150' in self.data.columns else None
            sma_200 = self.data['SMA_200'].iloc[-1] if 'SMA_200' in self.data.columns else None
            
            # Weinstein Stage
            stage = "Stage 1 - Basing"
            action = "Wait for breakout"
            rs = "Below average"
            color = "#6b7280"
            
            if sma_150 and sma_200:
                if price > sma_150 and price > sma_200:
                    stage = "Stage 2 - Advancing"
                    action = "Buy on pullbacks"
                    rs = "Above average"
                    color = "#10b981"
                elif price < sma_150 and price < sma_200:
                    stage = "Stage 4 - Declining"
                    action = "Avoid/Short"
                    rs = "Below average"
                    color = "#ef4444"
                else:
                    stage = "Stage 3 - Top"
                    action = "Take profits"
                    rs = "Neutral"
                    color = "#f59e0b"
            
            # Minervini Checklist (simplified)
            minervini = {
                "Price above 150 SMA": price > sma_150 if sma_150 else False,
                "Price above 200 SMA": price > sma_200 if sma_200 else False,
                "150 SMA above 200 SMA": sma_150 > sma_200 if (sma_150 and sma_200) else False,
                "Volume increasing": self.data['Volume'].iloc[-20:].mean() > self.data['Volume'].iloc[-60:-20].mean() if len(self.data) > 60 else False,
                "Price trending up": price > self.data['Close'].iloc[-50] if len(self.data) > 50 else False
            }
            
            # CPR (Central Pivot Range)
            recent_high = self.data['High'].iloc[-20:].max()
            recent_low = self.data['Low'].iloc[-20:].min()
            cpr_high = (recent_high + recent_low + price) / 3
            cpr_low = (recent_high + recent_low) / 2
            cpr_width = ((cpr_high - cpr_low) / price) * 100
            
            return {
                'weinstein': {
                    'stage': stage,
                    'action': action,
                    'rs': rs,
                    'color': color
                },
                'minervini': minervini,
                'cpr': {
                    'width': f"{cpr_width:.2f}%",
                    'type': "Narrow" if cpr_width < 0.5 else "Wide",
                    'range': f"₹{cpr_low:.2f} - ₹{cpr_high:.2f}"
                }
            }
        except Exception:
            return None

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
            url = model_url
            if "/chat/completions" not in url:
                url = f"{url.rstrip('/')}/chat/completions"
            
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            return f"AI Insight Error: {str(e)}"

    @staticmethod
    def get_smart_money_stocks(tickers, max_results=20, max_workers=8, progress_callback=None):
        """Smart Money Concept scanner - Detects institutional activity patterns."""
        from performance_utils import parallel_process_stocks, batch_download_data
        
        # 1. BATCH DOWNLOAD ALL DATA FIRST (Huge speedup)
        # print("Downloading data for Smart Money Scanner...")
        batch_data = batch_download_data(tickers, period='60d', interval='1d')
        
        def process_smc(ticker):
            try:
                full_ticker = f"{ticker}.NS" if not ticker.endswith(".NS") else ticker
                
                # Retrieve from batch data
                df = None
                if ticker in batch_data:
                    df = batch_data[ticker]
                elif full_ticker.replace('.NS', '') in batch_data:
                    df = batch_data[full_ticker.replace('.NS', '')]
                
                if df is None or df.empty or len(df) < ScannerConfig.SMC_MIN_ROWS:
                    return None
                
                if 'Volume' not in df.columns:
                    return None
                
                # Calculate multiple volume metrics
                avg_volume_20 = df['Volume'].iloc[-20:].mean()
                avg_volume_50 = df['Volume'].iloc[-50:].mean()
                current_volume = df['Volume'].iloc[-1]
                prev_volume = df['Volume'].iloc[-2]
                
                # Volume spike calculations
                volume_spike_20 = ((current_volume - avg_volume_20) / avg_volume_20) * 100 if avg_volume_20 > 0 else 0
                volume_surge = ((current_volume - prev_volume) / prev_volume) * 100 if prev_volume > 0 else 0
                
                # Price action
                price = df['Close'].iloc[-1]
                price_change_5d = ((df['Close'].iloc[-1] - df['Close'].iloc[-5]) / df['Close'].iloc[-5]) * 100
                price_change_10d = ((df['Close'].iloc[-1] - df['Close'].iloc[-10]) / df['Close'].iloc[-10]) * 100
                
                # Detect patterns
                signal_type = "Neutral"
                institutional_note = ""
                score = 0
                
                # Pattern 1: Volume Breakout (high volume + price up)
                if volume_spike_20 >= 30 and price_change_5d > 1:
                    signal_type = "Breakout"
                    institutional_note = "Strong volume with upward price momentum"
                    score = min(100, 60 + volume_spike_20/2 + price_change_5d*5)
                
                # Pattern 2: Accumulation (steady high volume, price consolidation)
                elif avg_volume_20 > avg_volume_50 * 1.2 and abs(price_change_5d) < 2:
                    signal_type = "Accumulation"
                    institutional_note = "Consistent high volume with price consolidation"
                    score = min(100, 55 + (avg_volume_20/avg_volume_50 - 1)*50)
                
                # Pattern 3: Absorption (high volume, price not dropping)
                elif volume_spike_20 >= 20 and price_change_5d >= -1:
                    signal_type = "Absorption"
                    institutional_note = "High volume supporting price levels"
                    score = min(100, 50 + volume_spike_20/2)
                
                # Pattern 4: Re-accumulation (volume spike after pullback)
                elif volume_spike_20 >= 25 and price_change_10d < 0 and price_change_5d > 0:
                    signal_type = "Re-accumulation"
                    institutional_note = "Volume surge after pullback, potential reversal"
                    score = min(100, 55 + volume_spike_20/2 + abs(price_change_10d)*2)
                
                # Pattern 5: Volume surge (any significant volume activity)
                elif volume_spike_20 >= 20 or volume_surge >= 50:
                    signal_type = "Volume Surge"
                    institutional_note = "Unusual volume activity detected"
                    score = min(100, 45 + max(volume_spike_20, volume_surge)/2)
                
                # Minimum score threshold
                if score < 50:
                    return None
                
                # Calculate estimated delivery percentage
                delivery_pct = min(100, volume_spike_20 * 0.7)
                
                # Determine signal strength
                if score >= 75:
                    strength = "Strong"
                elif score >= 60:
                    strength = "Moderate"
                else:
                    strength = "Weak"
                
                return {
                    'Stock Symbol': ticker,
                    'Current Price': round(price, 2),
                    'Signal Type (Accumulation / Breakout / Absorption / Re-accumulation)': signal_type,
                    'Volume Spike %': round(volume_spike_20, 1),
                    'Delivery %': round(delivery_pct, 1),
                    'Institutional Activity (Yes/No + short note)': f"Yes - {institutional_note}",
                    'Smart Money Score (0–100)': round(score, 1),
                    'Signal Strength (Weak / Moderate / Strong)': strength
                }
            except Exception as e:
                # print(f"Error processing {ticker}: {e}")
                return None
        
        # Use parallel processing for calculation (CPU bound now, not I/O bound)
        # We can increase workers significantly or just use main thread if list is small, 
        # but parallel is still good for 2000 iterations
        results = parallel_process_stocks(tickers, process_smc, max_workers=20, max_stocks=None, timeout_per_stock=1.0, progress_callback=progress_callback)
        results = sorted(results, key=lambda x: x.get('Smart Money Score (0–100)', 0), reverse=True)
        return results[:max_results]

    @staticmethod
    def get_swing_stocks(tickers, interval='1d', period='60d', max_results=20, max_workers=8, progress_callback=None, min_market_cap=2000000000):
        """Swing Trading Scanner (15-20 days)."""
        from performance_utils import parallel_process_stocks, batch_download_data
        from scanner_robustness import ScannerConfig
        
        # 1. BATCH DOWNLOAD
        batch_data = batch_download_data(tickers, period=period, interval=interval)

        def process_swing(ticker):
            try:
                full_ticker = f"{ticker}.NS" if not ticker.endswith(".NS") else ticker
                
                # Retrieve from batch
                df = None
                if ticker in batch_data:
                    df = batch_data[ticker]
                elif full_ticker.replace('.NS', '') in batch_data:
                    df = batch_data[full_ticker.replace('.NS', '')]
                
                if df is None or df.empty or len(df) < ScannerConfig.SWING_MIN_ROWS:
                    return None
                
                # Add indicators
                df.ta.ema(length=9, append=True)
                df.ta.ema(length=21, append=True)
                rsi = df.ta.rsi(length=14)
                if rsi is not None:
                    df = pd.concat([df, rsi], axis=1)
                    rsi_col = rsi.name
                else:
                    return None
                
                last = df.iloc[-1]
                price = last['Close']
                
                # Filters
                if price < ScannerConfig.SWING_MIN_PRICE:
                    return None
                
                ema9 = last.get('EMA_9', price)
                ema21 = last.get('EMA_21', price)
                rsi_val = last.get(rsi_col, 50)
                
                # Swing criteria
                if not (price > ema21 and ema9 > ema21 and rsi_val > ScannerConfig.SWING_MIN_RSI):
                    return None
                
                # Volume check
                avg_volume = df['Volume'].iloc[-20:].mean()
                current_volume = df['Volume'].iloc[-1]
                volume_spike = ((current_volume - avg_volume) / avg_volume) * 100 if avg_volume > 0 else 0
                
                if volume_spike < ScannerConfig.SWING_MIN_VOLUME_SPIKE:
                    return None
                
                # Calculate targets
                atr = df.ta.atr(length=14).iloc[-1] if len(df) >= 14 else price * 0.02
                target = price + (2 * atr)
                stop_loss = price - (1.5 * atr)
                pct_change = ((target - price) / price) * 100
                
                # Confidence score
                confidence = 50
                confidence += 20 if rsi_val > 60 else 10
                confidence += 15 if volume_spike > 100 else 5
                confidence += 15 if price > ema9 else 0
                
                return {
                    'Stock Symbol': ticker,
                    'Current Price': round(price, 2),
                    'Entry Range': f"₹{price:.2f} - ₹{price * 1.02:.2f}",
                    'Target Price (15–20 day horizon)': round(target, 2),
                    'Stop Loss': round(stop_loss, 2),
                    'Trend Type (Uptrend / Range Breakout)': 'Uptrend',
                    'Technical Reason (short explanation)': f'EMA alignment, RSI {rsi_val:.1f}, Volume surge {volume_spike:.0f}%',
                    'Confidence Score (0–100)': min(100, round(confidence, 1)),
                    'pct_change': round(pct_change, 2)
                }
            except Exception:
                return None
        
        # CPU bound processing now
        results = parallel_process_stocks(tickers, process_swing, max_workers=20, max_stocks=None, timeout_per_stock=1.0, progress_callback=progress_callback)
        results = sorted(results, key=lambda x: x.get('Confidence Score (0–100)', 0), reverse=True)
        return results[:max_results]

    @staticmethod
    def get_long_term_stocks(tickers, max_results=20, max_workers=4, progress_callback=None):
        """Long-term investing scanner based on fundamentals."""
        from performance_utils import parallel_process_stocks
        import data_provider as yf
        
        def process_long_term(ticker):
            try:
                # Add timeout protection
                full_ticker = f"{ticker}.NS" if not ticker.endswith(".NS") else ticker
                t = yf.Ticker(full_ticker)
                
                # Try to get info with timeout protection
                info = None
                try:
                    # Use a simple timeout by checking if info exists quickly
                    info = t.info
                    # If info is empty dict, try fast_info
                    if (not info or len(info) == 0) and hasattr(t, 'fast_info'):
                        fast_info = t.fast_info
                        if fast_info:
                            info = fast_info
                except Exception:
                    # If info fetch fails, try fast_info
                    # If info fetch fails, try fast_info
                    try:
                        if hasattr(t, 'fast_info'):
                            info = t.fast_info
                    except Exception:
                        pass
                
                if not info or len(info) == 0:
                    return None
                
                market_cap = info.get('marketCap', 0) or info.get('market_cap', 0)
                if not market_cap or market_cap < 2000000000:  # Min 200 Cr (more lenient)
                    return None
                
                rev_growth = info.get('revenueGrowth') or info.get('revenue_growth')
                roe = info.get('returnOnEquity') or info.get('roe')
                debt_eq = info.get('debtToEquity') or info.get('debt_to_equity')
                
                # Convert debt_eq if it's a percentage
                if debt_eq and isinstance(debt_eq, (int, float)):
                    if debt_eq > 100:  # Likely a percentage, convert
                        debt_eq = debt_eq / 100
                
                # Scoring system instead of hard filters
                score = 0
                criteria_met = 0
                
                # Revenue growth (0-30 points)
                if rev_growth:
                    if rev_growth >= 0.2:  # 20%+
                        score += 30
                        criteria_met += 1
                    elif rev_growth >= 0.1:  # 10-20%
                        score += 20
                        criteria_met += 1
                    elif rev_growth >= 0.05:  # 5-10%
                        score += 10
                else:
                    score += 5  # Give some points even if data missing
                
                # ROE (0-30 points)
                if roe:
                    if roe >= 0.20:  # 20%+
                        score += 30
                        criteria_met += 1
                    elif roe >= 0.15:  # 15-20%
                        score += 20
                        criteria_met += 1
                    elif roe >= 0.10:  # 10-15%
                        score += 10
                else:
                    score += 5  # Give some points even if data missing
                
                # Debt to Equity (0-20 points) - lower is better
                if debt_eq is not None:
                    if debt_eq <= 0.3:  # Very low debt
                        score += 20
                        criteria_met += 1
                    elif debt_eq <= 0.5:
                        score += 15
                    elif debt_eq <= 1.0:
                        score += 10
                    elif debt_eq <= 2.0:
                        score += 5
                else:
                    score += 10  # Assume reasonable if missing
                
                # Market cap bonus (0-20 points)
                if market_cap >= 10000000000:  # 1000 Cr+
                    score += 20
                elif market_cap >= 5000000000:  # 500 Cr+
                    score += 15
                elif market_cap >= 2000000000:  # 200 Cr+
                    score += 10
                
                # Only return if score is reasonable (at least 40 points) or meets 2+ criteria
                if score < 40 and criteria_met < 2:
                    return None
                
                # Build thesis
                thesis_parts = []
                if rev_growth and rev_growth > 0:
                    thesis_parts.append(f"{round(rev_growth * 100, 1)}% revenue growth")
                if roe and roe > 0:
                    thesis_parts.append(f"{round(roe * 100, 1)}% ROE")
                if debt_eq is not None and debt_eq < 1.0:
                    thesis_parts.append("low debt")
                
                thesis = "Compounder stock with strong moats and fiscal discipline." if thesis_parts else "Fundamentally sound company with growth potential."
                if thesis_parts:
                    thesis = f"Strong fundamentals: {', '.join(thesis_parts)}."
                
                return {
                    'Stock Symbol': ticker,
                    'Sector': info.get('sector', 'N/A'),
                    'Market Cap': f"₹{market_cap/1e7:.2f} Cr",
                    'Revenue Growth %': round(rev_growth * 100, 1) if rev_growth else 'N/A',
                    'Profit Growth %': 'N/A',  # Would need earnings data
                    'ROE %': round(roe * 100, 1) if roe else 'N/A',
                    'Debt to Equity': round(debt_eq, 2) if debt_eq is not None else 'N/A',
                    'Long-Term Thesis (1–2 line summary)': thesis,
                    '_score': score  # For sorting
                }
            except Exception as e:
                # Log error for debugging but don't fail completely
                print(f"[DEBUG] Error in process_long_term for {ticker}: {e}")
                return None
        
        # Use all tickers provided, don't limit artificially
        results = parallel_process_stocks(
            tickers, 
            process_long_term, 
            max_workers=max_workers, 
            max_stocks=None,  # Process all provided tickers
            timeout_per_stock=5.0,  # Reduced timeout to 5 seconds per stock
            progress_callback=progress_callback
        )
        # Sort by score and remove score from output
        results = sorted(results, key=lambda x: x.get('_score', 0), reverse=True)
        for r in results:
            r.pop('_score', None)
        return results[:max_results]

    @staticmethod
    def get_cyclical_stocks_by_quarter(tickers, max_results_per_quarter=15, max_workers=8, progress_callback=None):
        """Cyclical stocks scanner by quarter."""
        from performance_utils import parallel_process_stocks, batch_download_data
        from scanner_robustness import ScannerConfig
        
        # 1. BATCH DOWNLOAD (10 Years is heavy, but batching 300 at a time is still better)
        # print("Downloading 10y data for Cyclical Scanner...")
        batch_data = batch_download_data(tickers, period='10y', interval='1d')
        
        def process_cyclical(ticker):
            try:
                full_ticker = f"{ticker}.NS" if not ticker.endswith(".NS") else ticker
                
                # Retrieve from batch
                df = None
                if ticker in batch_data:
                    df = batch_data[ticker]
                elif full_ticker.replace('.NS', '') in batch_data:
                    df = batch_data[full_ticker.replace('.NS', '')]
                
                if df is None or df.empty or len(df) < ScannerConfig.CYCLICAL_MIN_ROWS:
                    return None
                df['Year'] = df.index.year
                df['Quarter'] = df.index.quarter
                
                quarterly_returns = {'Q1': [], 'Q2': [], 'Q3': [], 'Q4': []}
                
                for year in range(df['Year'].min(), df['Year'].max() + 1):
                    for q in [1, 2, 3, 4]:
                        q_data = df[(df['Year'] == year) & (df['Quarter'] == q)]
                        if len(q_data) > 0:
                            start_price = q_data['Close'].iloc[0]
                            end_price = q_data['Close'].iloc[-1]
                            ret = ((end_price - start_price) / start_price) * 100
                            quarterly_returns[f'Q{q}'].append(ret)
                
                # Find best QUALIFYING quarter
                best_q = None
                best_return = -999
                best_prob = 0
                
                for q, returns in quarterly_returns.items():
                    if not returns:
                        continue
                        
                    avg_ret = sum(returns) / len(returns)
                    pos_years = sum(1 for r in returns if r > 0)
                    probability = pos_years / len(returns)
                    
                    # Check criteria
                    if avg_ret >= ScannerConfig.CYCLICAL_MIN_RETURN and probability >= ScannerConfig.CYCLICAL_MIN_PROBABILITY:
                        # Pick this if it has higher return than current best
                        if avg_ret > best_return:
                            best_return = avg_ret
                            best_q = q
                            best_prob = probability
                
                if best_q is None:
                    return None
                
                return {
                    'Stock Symbol': ticker,
                    'Sector': 'N/A',  # Would need to fetch
                    'Quarter': best_q,
                    'Probabilistic Consistency (%)': round(best_prob * 100, 1),
                    'Historical Median Return (%)': round(best_return, 2),
                    'Score': round(best_prob * 100 + best_return, 1)
                }
            except Exception as e:
                # print(f"Error processing {ticker}: {e}")
                return None
        
        results = parallel_process_stocks(tickers, process_cyclical, max_workers=20, max_stocks=None, timeout_per_stock=1.0, progress_callback=progress_callback)
        
        # Group by quarter
        grouped = {'Q1': [], 'Q2': [], 'Q3': [], 'Q4': []}
        for r in results:
            q = r.get('Quarter')
            if q and q in grouped:
                grouped[q].append(r)
        
        # Sort each quarter by score
        for q in grouped:
            grouped[q] = sorted(grouped[q], key=lambda x: x.get('Score', 0), reverse=True)[:max_results_per_quarter]
        
        return grouped

    @staticmethod
    def get_weinstein_scanner_stocks(tickers, max_workers=8, progress_callback=None):
        """Weinstein Stage Analysis scanner."""
        from performance_utils import parallel_process_stocks, batch_download_data
        from scanner_robustness import ScannerConfig
        
        # 1. BATCH DOWNLOAD
        batch_data = batch_download_data(tickers, period=ScannerConfig.WEINSTEIN_PERIOD, interval='1d')
        
        def process_weinstein(ticker):
            try:
                full_ticker = f"{ticker}.NS" if not ticker.endswith(".NS") else ticker
                
                # Retrieve from batch
                df = None
                if ticker in batch_data:
                    df = batch_data[ticker]
                elif full_ticker.replace('.NS', '') in batch_data:
                    df = batch_data[full_ticker.replace('.NS', '')]
                
                if df is None or df.empty or len(df) < ScannerConfig.WEINSTEIN_MIN_ROWS:
                    return None
                df.ta.sma(length=150, append=True)
                df.ta.sma(length=200, append=True)
                
                last = df.iloc[-1]
                price = last['Close']
                sma_150 = last.get('SMA_150')
                sma_200 = last.get('SMA_200')
                
                if not sma_150 or not sma_200:
                    return None
                
                # Determine stage
                if price > sma_150 and price > sma_200 and sma_150 > sma_200:
                    stage = "Stage 2 - Advancing"
                    rs = "Above average"
                    action = "Buy"
                elif price < sma_150 and price < sma_200:
                    stage = "Stage 4 - Declining"
                    rs = "Below average"
                    action = "Avoid"
                elif price > sma_150 and price > sma_200:
                    stage = "Stage 3 - Top"
                    rs = "Neutral"
                    action = "Take profits"
                else:
                    stage = "Stage 1 - Basing"
                    rs = "Below average"
                    action = "Wait"
                
                return {
                    'Stock Symbol': ticker,
                    'Price': round(price, 2),
                    'RS': rs,
                    'Action': action,
                    '_stage': stage
                }
            except Exception as e:
                # print(f"Error processing {ticker}: {e}")
                return None
        
        results = parallel_process_stocks(tickers, process_weinstein, max_workers=20, max_stocks=None, timeout_per_stock=1.0, progress_callback=progress_callback)
        
        # Group by stage
        grouped = {
            "Stage 1 - Basing": [],
            "Stage 2 - Advancing": [],
            "Stage 3 - Top": [],
            "Stage 4 - Declining": []
        }
        
        for r in results:
            stage = r.pop('_stage', None)
            if stage and stage in grouped:
                grouped[stage].append(r)
        
        return grouped

    def get_news(self):
        try:
            return yf.Ticker(self.ticker).news
        except:
            return []

    def get_financials(self):
        try:
            info = yf.Ticker(self.ticker).info
            if info:
                return {
                    'market_cap': info.get('marketCap', 'N/A'),
                    'pe_ratio': info.get('trailingPE', 'N/A'),
                    'dividend_yield': info.get('dividendYield', 0),
                    'sector': info.get('sector', 'N/A'),
                    'industry': info.get('industry', 'N/A'),
                    'summary': info.get('longBusinessSummary', 'No summary available.'),
                    'calendar': None,  # Would need to fetch separately
                    'earnings': None   # Would need to fetch separately
                }
            return None
        except:
            return None
