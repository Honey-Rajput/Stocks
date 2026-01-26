import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import requests
import json
import time

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
        # Using auto_adjust=True for cleaner technical analysis data
        # Implement retry logic to handle transient yfinance failures
        max_retries = 3
        for attempt in range(max_retries):
            try:
                df = yf.download(self.ticker, period=self.period, interval=self.interval, auto_adjust=True)
                if not df.empty:
                    # Handle recent yfinance versions returning MultiIndex even for single ticker
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    return df
            except Exception:
                pass
            
            if attempt < max_retries - 1:
                time.sleep(1) # Wait 1 second before retrying
                
        raise ValueError(f"No data found for {self.ticker} after {max_retries} attempts")

    def add_indicators(self):
        # EMAs
        self.data.ta.ema(length=9, append=True)
        self.data.ta.ema(length=21, append=True)
        self.data.ta.ema(length=50, append=True)
        self.data.ta.ema(length=200, append=True)
        
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
    def get_market_opportunities(ticker_list, interval='1d'):
        opportunities = {"buys": [], "sells": []}
        
        # Limit to first 20 for performance during screening
        for ticker in list(ticker_list)[:25]:
            try:
                # Add .NS if not present
                full_ticker = ticker if ticker.endswith(".NS") else f"{ticker}.NS"
                engine = AnalysisEngine(full_ticker, interval=interval, period='60d')
                analysis = engine.analyze()
                
                if analysis['confidence'] >= 70:
                    stock_data = {
                        "ticker": ticker,
                        "price": analysis['price'],
                        "confidence": analysis['confidence'],
                        "bias": analysis['bias']
                    }
                    if analysis['bias'] == "Bullish":
                        opportunities["buys"].append(stock_data)
                    elif analysis['bias'] == "Bearish":
                        opportunities["sells"].append(stock_data)
            except Exception:
                continue
                
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
