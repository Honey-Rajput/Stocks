import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from analysis_engine import AnalysisEngine
import pandas as pd
from datetime import datetime
import time
from db_utils import get_db_manager

# Page config
st.set_page_config(page_title="Stock Market AI Agent", layout="wide", page_icon="📈")

# Custom CSS for "Premium" look
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    .stMetric {
        background: rgba(255, 255, 255, 0.05);
        padding: 15px;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .status-card {
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 15px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .bullish { background-color: rgba(16, 185, 129, 0.1); border-left: 5px solid #10b981; }
    .bearish { background-color: rgba(239, 68, 68, 0.1); border-left: 5px solid #ef4444; }
    .sideways { background-color: rgba(107, 114, 128, 0.1); border-left: 5px solid #6b7280; }
    
    /* Wrap tab text */
    button[data-baseweb="tab"] p {
        white-space: normal !important;
        text-align: center !important;
        line-height: 1.2 !important;
        font-size: 14px !important;
    }
    button[data-baseweb="tab"] {
        height: auto !important;
        min-height: 40px !important;
        padding-top: 5px !important;
        padding-bottom: 5px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- App Configuration ---
# UI and analysis settings for the Stock Market AI Agent.

# Fetch NSE stock list
@st.cache_data
def get_nse_stocks():
    try:
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        df = pd.read_csv(url)
        df = df.drop_duplicates(subset=[' ISIN NUMBER'], keep='first')
        stocks = {f"{row['SYMBOL']} - {row['NAME OF COMPANY']}": row['SYMBOL'] for _, row in df.iterrows()}
        return stocks
    except Exception as e:
        st.error(f"Error fetching NSE stock list: {e}")
        return {"RELIANCE - RELIANCE INDUSTRIES LTD": "RELIANCE"}

def add_tradingview_column(results):
    """Transforms the Stock Symbol column into a TradingView URL for clickable rows."""
    if not results: return results
    # Work on a copy to avoid side effects if reused
    processed = []
    for res in results:
        new_res = res.copy()
        # Standardize key
        key = 'Stock Symbol' if 'Stock Symbol' in new_res else ('ticker' if 'ticker' in new_res else None)
        if not key: 
            processed.append(new_res)
            continue
            
        symbol = new_res.get(key)
        if symbol:
            # If already a URL, don't double wrap
            if "tradingview.com" in str(symbol):
                new_res['Stock Symbol'] = symbol
            else:
                clean_symbol = str(symbol).replace(".NS", "")
                new_res['Stock Symbol'] = f"https://www.tradingview.com/chart/?symbol=NSE:{clean_symbol}"
            
            # Remove old key if it was 'ticker'
            if key == 'ticker':
                new_res.pop('ticker', None)
        processed.append(new_res)
    return processed

nse_stocks_dict = get_nse_stocks()
stock_options = sorted(list(nse_stocks_dict.keys()))

# Sidebar
st.sidebar.title("🛠️ Agent")

# Consolidated stock selection (Ticker and Name in "One Place")
selected_stock_str = st.sidebar.selectbox("Select Stock (Ticker or Name)", 
                                        options=stock_options,
                                        index=stock_options.index("RELIANCE - RELIANCE INDUSTRIES LTD") if "RELIANCE - RELIANCE INDUSTRIES LTD" in stock_options else 0,
                                        help="Search by typing ticker or company name. The list is searchable.")

# Get the symbol from the selected string and add .NS for Yahoo Finance
ticker = f"{nse_stocks_dict[selected_stock_str]}.NS"

timeframe = st.sidebar.selectbox("Timeframe", 
    options=["1m", "5m", "15m", "1h", "4h", "1d", "1wk", "1mo"],
    index=5) # Default to 1d

# AI Configuration (Using st.secrets for GitHub safety)
try:
    MODEL_URL = st.secrets["MODEL_URL"]
    MODEL_KEY = st.secrets["MODEL_KEY"]
except:
    MODEL_URL = "https://api.euron.one/api/v1/euri/chat/completions"
    MODEL_KEY = "euri-547dc00208e76ce2d4150524fa1461bf55f8183a73c7419f9f8bd6410a76d743"

# Default AI settings (hidden from UI)
use_ai = True
selected_model = "gpt-5-nano-2025-08-07"

# Scanner Performance Configuration (hidden from UI)
max_workers = 4  # Reduced from 10 to prevent rate limiting
max_scan_stocks = 500 # Reduced from 2200 to Nifty 500 size to prevent API 401/Crumb errors

# The nse_stocks_dict variable already contains the full live NSE list from EQUITY_L.csv
# We will use this dynamically for all scanners.


# Periods for indicators (Capped at yfinance limits for stability)
periods = {
    "1m": "7d", "5m": "30d", "15m": "60d", "1h": "730d", 
    "4h": "730d", "1d": "max", "1wk": "max", "1mo": "max"
}

st.title("🚀 Stock Market AI Agent")
# Add TradingView link for the selected stock
clean_header_ticker = ticker.replace(".NS", "")
st.markdown(f"### Analyzing: {selected_stock_str} | [View Chart 📈](https://www.tradingview.com/chart/?symbol=NSE:{clean_header_ticker})")

if ticker:
    try:
        engine = AnalysisEngine(ticker, interval=timeframe, period=periods[timeframe])
        analysis = engine.analyze()
        df = engine.data
        
        # Tabs structure consolidated to fix blank tab issues
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11 = st.tabs([
            "📊 Agent Analysis", 
            "🤖 AI Insights", 
            "📈 Technical Charts", 
            "🏢 Financials", 
            "🔗 Related Info", 
            "🚀 Agent Recommendations",
            "💹 Smart Money Concept",
            "🎯 Swing Trading (15–20 Days)",
            "⏳ Long Term Investing",
            "🗓️ Cyclical Stocks by Quarter",
            "📌 Stage Analysis"
        ])
        
        with tab1:
            # Header Metrics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Current Price", f"₹{analysis['price']:.2f}")
            col2.metric("Market Bias", analysis['bias'])
            col3.metric("Confidence", f"{analysis['confidence']}%")
            col4.metric("Probability", analysis['probability'])
            
            # Recommendations Card
            bias_class = analysis['bias'].lower()
            st.markdown(f"""
                <div class="status-card {bias_class}">
                    <h3>Trade Recommendation: {analysis['recommendation']}</h3>
                    <p><b>Entry Zone:</b> ₹{analysis['price']:.2f} - ₹{analysis['price']*1.01:.2f}</p>
                    <p><b>Targets:</b> T1: ₹{analysis['targets'][0]} | T2: ₹{analysis['targets'][1]}</p>
                    <p><b>Stop Loss:</b> ₹{analysis['stop_loss']}</p>
                </div>
            """, unsafe_allow_html=True)

            # --- Chart Rendering ---
            st.subheader(f"📈 {selected_stock_str} Price Action")
            
            if df.empty or len(df) < 5:
                st.warning("Insufficient data for this timeframe. Try a larger period.")
            else:
                try:
                    # Explicitly defined plot heights and subplots
                    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                                       vertical_spacing=0.05, 
                                       subplot_titles=('Price', 'RSI', 'MACD'),
                                       row_heights=[0.6, 0.2, 0.2])

                    # Price
                    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
                    
                    if 'EMA_9' in df.columns:
                        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_9'], line=dict(color='cyan', width=1), name='EMA 9'), row=1, col=1)
                    if 'EMA_21' in df.columns:
                        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_21'], line=dict(color='orange', width=1), name='EMA 21'), row=1, col=1)

                    # RSI
                    if engine.indicator_cols['rsi'] in df.columns:
                        fig.add_trace(go.Scatter(x=df.index, y=df[engine.indicator_cols['rsi']], line=dict(color='purple'), name='RSI'), row=2, col=1)
                        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

                    # MACD
                    ic = engine.indicator_cols
                    if ic['macd'] in df.columns:
                        fig.add_trace(go.Bar(x=df.index, y=df[ic['macdh']], name='Hist'), row=3, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df[ic['macd']], line=dict(color='blue'), name='MACD'), row=3, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df[ic['macds']], line=dict(color='yellow'), name='Signal'), row=3, col=1)

                    fig.update_layout(height=900, template='plotly_dark', showlegend=False, xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Chart Render Failed: {e}")
                    st.line_chart(df['Close'])

            # Options & Risk panel
            c1, c2 = st.columns(2)
            with c1:
                st.write("### 🧪 Options Strategy")
                opt = engine.get_options_suggestion(analysis)
                st.write(f"**Strategy:** {opt['strategy']}")
                st.write(f"**Strike:** {opt['strike_logic']}")
                st.write(f"**Expiry:** {opt['expiry']}")
            with c2:
                st.write("### 🛡️ Risk Management")
                st.write(f"**Stop Loss:** ₹{analysis['stop_loss']}")
                st.write(f"**Risk Ratio:** 1:2.0")

            # Technical Expansion
            with st.expander("📐 Technical Deep Dive"):
                fib = engine.get_fibonacci_levels()
                st.write("#### Fibonacci Levels")
                f_cols = st.columns(len(fib))
                for i, (l, v) in enumerate(fib.items()):
                    f_cols[i].metric(l, f"₹{v:.2f}")

        with tab2:
            st.subheader("🤖 AI Driven Analysis & Outlook")
            
            # Moved technical reasoning here to keep Tab 1 original
            with st.expander("🔍 Technical Basis (Why this bias?)"):
                for r in analysis['reasoning']:
                    st.write(f"- {r}")
                    
            if use_ai:
                analysis['ticker'] = ticker
                if st.button("🧠 Generate AI Insight"):
                    with st.spinner(f"Agent {selected_model} is thinking..."):
                        insight = AnalysisEngine.get_ai_insight(analysis, MODEL_URL, MODEL_KEY, selected_model)
                        st.info(insight)
                else:
                    st.write("Click the button above to generate AI analysis for this stock.")
            else:
                st.warning("Please enable AI Reasoning in the sidebar to see AI Insights.")

        with tab3:
            st.subheader("Raw Data & Indicators")
            st.dataframe(df.tail(100))

        with tab4:
            st.subheader("Company Financials & Earnings")
            fin = engine.get_financials()
            if fin:
                c1, c2, c3 = st.columns(3)
                c1.metric("Market Cap", f"₹{fin['market_cap']:,}" if isinstance(fin['market_cap'], (int, float)) else fin['market_cap'])
                c2.metric("P/E Ratio", fin['pe_ratio'])
                c3.metric("Div. Yield", f"{fin['dividend_yield']*100:.2f}%" if isinstance(fin['dividend_yield'], (int, float)) else fin['dividend_yield'])
                
                st.markdown(f"**Sector:** {fin['sector']} | **Industry:** {fin['industry']}")
                
                # Earnings & Results Section
                st.write("### 📅 Results & Earnings")
                
                st.write("**Upcoming Calendar**")
                if fin['calendar'] is not None:
                    st.dataframe(fin['calendar'], use_container_width=True)
                else:
                    st.write("No upcoming calendar events.")
                
                st.write("**Historical Earnings (Yearly)**")
                if fin['earnings'] is not None:
                    st.dataframe(fin['earnings'], use_container_width=True)
                else:
                    st.write("Historical earnings data not available.")

                st.info(f"**Business Summary:**\n\n{fin['summary']}")

                # Seasonality Section for Individual Stock
                st.write("### 🗓️ Historical Seasonality (10-Year Average)")
                q_returns = engine.get_quarterly_returns()
                if q_returns:
                    q_df = pd.DataFrame({
                        "Quarter": list(q_returns.keys()),
                        "Avg Return %": list(q_returns.values())
                    })
                    
                    # Rationale explanation
                    best_q = max(q_returns, key=q_returns.get)
                    st.write(f"This chart compares the average performance of **{ticker}** across all 4 quarters. "
                             f"We highlight **{best_q}** because it has the highest historical average return of **{q_returns[best_q]}%** over the last decade.")
                    
                    # Bar Chart
                    st.bar_chart(q_df.set_index("Quarter"))
                else:
                    st.write("Seasonality data not available.")
            else:
                st.warning("Financial data not available for this ticker.")

        with tab5:
            st.subheader("🔗 Related Stock Information")
            try:
                news = engine.get_news()
                if news:
                    for item in news:
                        # Handle new yfinance news structure
                        content = item.get('content', {})
                        title = content.get('title', item.get('title', 'Market Update'))
                        link = content.get('canonicalUrl', {}).get('url', item.get('link', '#'))
                        publisher = content.get('provider', {}).get('displayName', item.get('publisher', 'Financial News'))
                        
                        # Handle timestamps if available
                        pub_time = content.get('pubDate', item.get('pubDate'))
                        date_str = ""
                        if pub_time:
                            try:
                                # yfinance often uses ISO format strings now, or timestamps
                                if isinstance(pub_time, (int, float)):
                                    date_str = datetime.fromtimestamp(pub_time).strftime('%Y-%m-%d %H:%M')
                                else:
                                    date_str = str(pub_time)[:16] # Use string slice for common ISO formats
                            except:
                                date_str = str(pub_time)

                        with st.container():
                            st.markdown(f"#### [{title}]({link})")
                            st.write(f"📅 **Published:** {date_str} | **Source:** {publisher}")
                            st.markdown("---")
                else:
                    st.write("No recent news found for this ticker.")
            except Exception as e:
                st.warning(f"Related information unavailable: {e}")

        with tab6:
            st.subheader("🚀 High-Confidence Market Opportunities")
            st.info("The agent is currently screening the Top NSE stocks for immediate opportunities based on technical alignment.")
            
            if st.button("🔍 Run Multi-Stock Scanner"):
                opps = {"buys": [], "sells": []}
                progress_container = st.empty()
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                with st.container():
                    for i, ticker in enumerate(top_nse_tickers):
                        status_text.text(f"Scanning {ticker} ({i+1}/{len(top_nse_tickers)})...")
                        progress_bar.progress((i + 1) / len(top_nse_tickers))
                        
                        try:
                            full_ticker = f"{ticker}.NS"
                            # Use a smaller period for scanning to speed up
                            scan_engine = AnalysisEngine(full_ticker, interval=timeframe, period='60d')
                            scan_res = scan_engine.analyze()
                            
                            if scan_res and scan_res['confidence'] >= 70:
                                stock_data = {
                                    "ticker": ticker,
                                    "price": scan_res['price'],
                                    "confidence": scan_res['confidence'],
                                    "bias": scan_res['bias'],
                                    "reasoning": scan_res['reasoning']
                                }
                                if scan_res['bias'] == "Bullish":
                                    opps["buys"].append(stock_data)
                                elif scan_res['bias'] == "Bearish":
                                    opps["sells"].append(stock_data)
                        except Exception as e:
                            continue
                
                status_text.success(f"Scan Complete! Found {len(opps['buys'])} Buy and {len(opps['sells'])} Sell opportunities.")
                
                # Sort by confidence
                opps["buys"] = sorted(opps["buys"], key=lambda x: x['confidence'], reverse=True)
                opps["sells"] = sorted(opps["sells"], key=lambda x: x['confidence'], reverse=True)
                
                # AI Global Summary
                if use_ai and (opps['buys'] or opps['sells']):
                    st.markdown("---")
                    if st.button("🤖 Ask AI for Global Synthesis"):
                        st.subheader("🤖 Agent Global Market View")
                        with st.spinner("AI is synthesizing scanner results..."):
                            summary_data = {
                                "top_buys": [b['ticker'] for b in opps['buys'][:3]],
                                "top_sells": [s['ticker'] for s in opps['sells'][:3]],
                                "market_context": f"Scanned {len(top_nse_tickers)} stocks at {timeframe} interval."
                            }
                            global_insight = AnalysisEngine.get_ai_insight(summary_data, MODEL_URL, MODEL_KEY, selected_model)
                            st.info(global_insight)
                    st.markdown("---")
                
                col_buy, col_sell = st.columns(2)
                
                with col_buy:
                    st.success("### ✅ Top Buy Candidates")
                    if not opps['buys']:
                        st.write("No high-confidence buy setups found.")
                    for buy in opps['buys']:
                        with st.expander(f"🟢 {buy['ticker']} - ₹{buy['price']:.2f} (Conf: {buy['confidence']}%)"):
                            st.markdown(f"[**Open TradingView Chart 📈**](https://www.tradingview.com/chart/?symbol=NSE:{buy['ticker']})")
                            st.write("**Technical Basis:**")
                            for r in buy['reasoning']:
                                st.write(f"- {r}")
                            
                with col_sell:
                    st.error("### ❌ Top Avoid/Sell Candidates")
                    if not opps['sells']:
                        st.write("No high-confidence sell setups found.")
                    for sell in opps['sells']:
                        with st.expander(f"🔴 {sell['ticker']} - ₹{sell['price']:.2f} (Conf: {sell['confidence']}%)"):
                            st.markdown(f"[**Open TradingView Chart 📈**](https://www.tradingview.com/chart/?symbol=NSE:{sell['ticker']})")
                            st.write("**Technical Basis:**")
                            for r in sell['reasoning']:
                                st.write(f"- {r}")
            else:
                st.write("Click 'Run Multi-Stock Scanner' to find current opportunities in the market.")

        with tab7:
            st.subheader("💹 Smart Money Concept & Institutional Tracker")
            st.info("Detecting institutional accumulation and large volume absorption across the market.")
            
            # 1. Load and Display Cached Results (Immediate)
            db = get_db_manager()
            cached_results, last_updated = db.get_results("smc")
            
            if cached_results:
                st.success(f"✅ Loaded {len(cached_results)} stocks from Database (Last Updated: {last_updated.strftime('%H:%M %d %b')})")
                display_df = pd.DataFrame(add_tradingview_column(cached_results))
                st.dataframe(display_df, 
                             column_config={
                                 "Stock Symbol": st.column_config.LinkColumn("Stock Symbol", display_text="symbol=NSE:(.*)"),
                                 "Score": None,
                                 "pct_change": None
                             },
                             use_container_width=True)
            else:
                st.info("💡 Data is being prepared. Check back soon or run a manual scan.")

            # 2. Manual Scan Option
            if st.button("🛰️ Run Smart Money Scanner"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                start_time = time.time()
                
                with st.spinner("Monitoring institutional footprints across NSE..."):
                    try:
                        all_tickers = list(nse_stocks_dict.values())[:max_scan_stocks]
                        sm_stocks = AnalysisEngine.get_smart_money_stocks(
                            all_tickers,
                            max_results=20,
                            max_workers=max_workers
                        )
                        
                        elapsed = time.time() - start_time
                        if sm_stocks:
                            status_text.success(f"✅ Found {len(sm_stocks)} stocks with institutional footprints in {elapsed:.1f}s")
                            sm_stocks = add_tradingview_column(sm_stocks)
                            st.dataframe(pd.DataFrame(sm_stocks), 
                                         column_config={
                                             "Stock Symbol": st.column_config.LinkColumn("Stock Symbol", display_text="symbol=NSE:(.*)"),
                                             "Score": None,
                                             "pct_change": None
                                         },
                                         use_container_width=True)
                            # Save to DB if scanned manually
                            db.save_results("smc", sm_stocks)
                        else:
                            status_text.warning("No significant institutional activity detected.")
                    except Exception as e:
                        st.error(f"Scanner error: {str(e)}")

        with tab8:
            st.subheader("🎯 Swing Trading Scanner (15–20 Days)")
            st.info("Scanning for stocks with EMA alignment, RSI momentum, and Volume surge.")
            
            # 1. Load and Display Cached Results (Immediate)
            db = get_db_manager()
            cached_results, last_updated = db.get_results("swing")
            
            if cached_results:
                st.success(f"✅ Loaded {len(cached_results)} setups from Database (Last Updated: {last_updated.strftime('%H:%M %d %b')})")
                display_df = pd.DataFrame(add_tradingview_column(cached_results))
                st.dataframe(display_df, 
                             column_config={
                                 "Stock Symbol": st.column_config.LinkColumn("Stock Symbol", display_text="symbol=NSE:(.*)"),
                                 "pct_change": None,
                                 "Score": None
                             },
                             use_container_width=True)
            else:
                st.info("💡 Data is being prepared. Check back soon or run a manual scan.")

            # 2. Manual Scan Option
            if st.button("🔍 Run Swing Scanner"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                start_time = time.time()
                
                with st.spinner("Analyzing NSE market trends for high-quality Swing setups..."):
                    try:
                        all_tickers = list(nse_stocks_dict.values())[:max_scan_stocks]
                        
                        # Progress callback
                        def update_progress(current, total, ticker):
                            progress = current / total
                            progress_bar.progress(progress)
                            elapsed = time.time() - start_time
                            rate = current / elapsed if elapsed > 0 else 0
                            eta = (total - current) / rate if rate > 0 else 0
                            status_text.text(f"Scanned {current}/{total} stocks ({rate:.1f} stocks/sec) - ETA: {eta:.0f}s - Last: {ticker}")
                        
                        swing_stocks = AnalysisEngine.get_swing_stocks(
                            all_tickers, 
                            interval=timeframe,
                            period=periods[timeframe],
                            max_results=20, 
                            max_workers=max_workers,
                            progress_callback=update_progress
                        )
                        
                        elapsed = time.time() - start_time
                        status_text.success(f"✅ Scan complete in {elapsed:.1f}s! Found {len(swing_stocks)} high-quality swing candidates.")
                        
                        if swing_stocks:
                            swing_stocks = add_tradingview_column(swing_stocks)
                            st.dataframe(pd.DataFrame(swing_stocks), 
                                         column_config={
                                             "Stock Symbol": st.column_config.LinkColumn("Stock Symbol", display_text="symbol=NSE:(.*)"),
                                             "pct_change": None,
                                             "Score": None
                                         },
                                         use_container_width=True)
                            # Save to DB if scanned manually
                            db.save_results("swing", swing_stocks)
                        else:
                            st.warning("No high-quality bullish swing setups found at the moment.")
                    except Exception as e:
                        st.error(f"Scanner error: {str(e)}")

        with tab9:
            st.subheader("⏳ Long Term Investing")
            st.info("Filtering for stocks with high growth, ROE, and low debt (Fundamental Strength).")
            
            # 1. Load and Display Cached Results (Immediate)
            db = get_db_manager()
            cached_results, last_updated = db.get_results("long_term")
            
            if cached_results:
                st.success(f"✅ Loaded {len(cached_results)} companies from Database (Last Updated: {last_updated.strftime('%H:%M %d %b')})")
                display_df = pd.DataFrame(add_tradingview_column(cached_results))
                st.dataframe(display_df, 
                             column_config={
                                 "Stock Symbol": st.column_config.LinkColumn("Stock Symbol", display_text="symbol=NSE:(.*)")
                             },
                             use_container_width=True)
            else:
                st.info("💡 Data is being prepared. Check back soon or run a manual scan.")

            # 2. Manual Scan Option
            if st.button("📈 Run Long-Term Scanner", key="long_term_scanner"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                start_time = time.time()
                
                with st.spinner("Evaluating NSE company fundamentals (this may take a moment)..."):
                    try:
                        all_tickers = list(nse_stocks_dict.values())[:max_scan_stocks]
                        lt_stocks = AnalysisEngine.get_long_term_stocks(
                            all_tickers,
                            max_results=20,
                            max_workers=max_workers
                        )
                        
                        elapsed = time.time() - start_time
                        if lt_stocks:
                            status_text.success(f"✅ Found {len(lt_stocks)} fundamentally strong companies in {elapsed:.1f}s")
                            lt_stocks = add_tradingview_column(lt_stocks)
                            st.dataframe(pd.DataFrame(lt_stocks), 
                                         column_config={
                                             "Stock Symbol": st.column_config.LinkColumn("Stock Symbol", display_text="symbol=NSE:(.*)")
                                         },
                                         use_container_width=True)
                            # Save to DB if scanned manually
                            db.save_results("long_term", lt_stocks)
                        else:
                            status_text.warning("No stocks met the strict fundamental criteria.")
                    except Exception as e:
                        st.error(f"Scanner error: {str(e)}")

        with tab10:
            st.subheader("🗓️ Cyclical Stocks by Quarter")
            st.info("Stocks categorized by their historically best-performing quarter (10yr backtest).")
            
            # 1. Load and Display Cached Results (Immediate)
            db = get_db_manager()
            cached_results, last_updated = db.get_results("cyclical")
            
            if cached_results:
                st.success(f"✅ Loaded seasonal patterns from Database (Last Updated: {last_updated.strftime('%H:%M %d %b')})")
                cyclical_groups = cached_results
            else:
                st.info("💡 Seasonal data is being prepared. Run manual scan for instant calculation.")
                cyclical_groups = None

            # 2. Manual Scan Option
            if st.button("🗓️ Run Cyclical Scanner"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                start_time = time.time()
                
                with st.spinner("Calculating 10-year seasonal return probabilities for NSE stocks..."):
                    try:
                        st.info("Scanning for seasonal patterns (this may take a minute)...")
                        all_tickers = list(nse_stocks_dict.values())[:max_scan_stocks]
                        cyclical_groups = AnalysisEngine.get_cyclical_stocks_by_quarter(
                            all_tickers,
                            max_results_per_quarter=15,
                            max_workers=8  # Lower workers for data-heavy operation
                        )
                        # Save to DB if scanned manually
                        db.save_results("cyclical", cyclical_groups)
                        
                        elapsed = time.time() - start_time
                        total_found = sum(len(v) for v in cyclical_groups.values())
                        status_text.success(f"✅ Analyzed seasonal patterns in {elapsed:.1f}s. Found {total_found} historical outperformers.")
                        
                        sub_q1, sub_q2, sub_q3, sub_q4 = st.tabs(["Q1 Stocks", "Q2 Stocks", "Q3 Stocks", "Q4 Stocks"])
                        
                        with sub_q1:
                            if cyclical_groups["Q1"]:
                                q1 = add_tradingview_column(cyclical_groups["Q1"])
                                st.dataframe(pd.DataFrame(q1), 
                                             column_config={"Stock Symbol": st.column_config.LinkColumn("Stock Symbol", display_text="NSE:(.*)")},
                                             use_container_width=True)
                            else: st.info("No significant Q1 outperformers found in this sample.")
                        with sub_q2:
                            if cyclical_groups["Q2"]:
                                q2 = add_tradingview_column(cyclical_groups["Q2"])
                                st.dataframe(pd.DataFrame(q2), 
                                             column_config={"Stock Symbol": st.column_config.LinkColumn("Stock Symbol", display_text="NSE:(.*)")},
                                             use_container_width=True)
                            else: st.info("No significant Q2 outperformers found in this sample.")
                        with sub_q3:
                            if cyclical_groups["Q3"]:
                                q3 = add_tradingview_column(cyclical_groups["Q3"])
                                st.dataframe(pd.DataFrame(q3), 
                                             column_config={"Stock Symbol": st.column_config.LinkColumn("Stock Symbol", display_text="NSE:(.*)")},
                                             use_container_width=True)
                            else: st.info("No significant Q3 outperformers found in this sample.")
                        with sub_q4:
                            if cyclical_groups["Q4"]:
                                q4 = add_tradingview_column(cyclical_groups["Q4"])
                                st.dataframe(pd.DataFrame(q4), 
                                             column_config={"Stock Symbol": st.column_config.LinkColumn("Stock Symbol", display_text="NSE:(.*)")},
                                             use_container_width=True)
                            else: st.info("No significant Q4 outperformers found in this sample.")
                    except Exception as e:
                        st.error(f"Scanner error: {str(e)}")

        with tab11:
            st.subheader("📌 Weinstein Stages & Minervini Checklist")
            st.info("Institutional Stage Analysis following global standards.")
            
            # 1. Individual Analysis
            st.markdown("### 🔍 Individual Stock Audit")
            stage_data = engine.get_stage_analysis()
            if stage_data:
                col1, col2 = st.columns([1, 1])
                with col1:
                    st.markdown("""<div style="background-color: #1e2130; color: white; padding: 10px; border-radius: 5px; font-weight: bold; margin-bottom: 15px;">📋 Mark Minervini Template</div>""", unsafe_allow_html=True)
                    for criteria, met in stage_data['minervini'].items():
                        icon = "✅" if met else "❌"; color = "#10b981" if met else "#ef4444"
                        st.markdown(f"<p style='margin:0; font-size:16px;'>{icon} <span style='color:{color}'>{criteria}</span></p>", unsafe_allow_html=True)
                with col2:
                    st.markdown(f"""<div style="background-color: #1e2130; color: white; padding: 10px; border-radius: 5px; font-weight: bold; margin-bottom: 15px;">📌 Stan Weinstein Stage Analysis</div><div style="background-color: {stage_data['weinstein']['color']}; color: white; padding: 8px 15px; font-size: 18px; font-weight: bold; border-left: 5px solid white;">Current Stage: {stage_data['weinstein']['stage']}</div><div style="background-color: #d1d5db33; padding: 5px 15px; margin-bottom: 10px; font-size: 14px;"><b>Action:</b> {stage_data['weinstein']['action']}</div><div style="background-color: #d1d5db33; padding: 5px 15px; margin-bottom: 20px; font-size: 14px;"><b>Mansfield RS:</b> {stage_data['weinstein']['rs']}</div>""", unsafe_allow_html=True)
                    st.markdown("""<table style="width:100%; border-collapse: collapse; border: 1px solid #374151; font-family: sans-serif;"><tr style="border: 1px solid #374151; background: #1e2130;"><td style="padding: 10px; font-weight: bold; color: white;">Metrics</td><td style="padding: 10px; font-weight: bold; color: white;">Value</td></tr><tr style="border: 1px solid #374151;"><td style="padding: 10px; font-weight: bold;">CPR Width</td><td style="padding: 10px;">"""+stage_data['cpr']['width']+"""</td></tr><tr style="border: 1px solid #374151;"><td style="padding: 10px; font-weight: bold;">CPR Type</td><td style="padding: 10px;">"""+stage_data['cpr']['type']+"""</td></tr><tr style="border: 1px solid #374151;"><td style="padding: 10px; font-weight: bold;">IB (Range)</td><td style="padding: 10px; color: #ef4444;">"""+str(stage_data['cpr']['range'])+"""</td></tr></table>""", unsafe_allow_html=True)
            else:
                st.warning("Insufficient data for Stage Analysis.")

            st.markdown("---")
            
            # 2. Market-wide Scanner
            st.markdown("### 🛰️ Weinstein Market-wide Scanner")
            st.write("Scan the entire market to find stocks currently in specific stages.")
            
            # 1. Load and Display Cached Results (Immediate)
            db = get_db_manager()
            cached_results, last_updated = db.get_results("stage_analysis")
            
            if cached_results:
                st.success(f"✅ Loaded Market Stages from Database (Last Updated: {last_updated.strftime('%H:%M %d %b')})")
                stage_results = cached_results
            else:
                st.info("💡 Market stage data is being prepared.")
                stage_results = None

            # 2. Manual Scan Option
            if st.button("🚀 Run Stage Scanner"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                start_time = time.time()
                
                with st.spinner("Classifying market into Weinstein Stages (1-4)..."):
                    try:
                        st.info("Running market-wide stage classification...")
                        all_tickers = list(nse_stocks_dict.values())[:max_scan_stocks]
                        stage_results = AnalysisEngine.get_weinstein_scanner_stocks(
                            all_tickers,
                            max_workers=max_workers
                        )
                        db.save_results("stage_analysis", stage_results)
                        
                        elapsed = time.time() - start_time
                        total_found = sum(len(v) for v in stage_results.values())
                        status_text.success(f"✅ Stage classification complete in {elapsed:.1f}s. Found {total_found} stocks.")
                        
                        s_tabs = st.tabs(["🏗️ Stage 1", "🚀 Stage 2", "📉 Stage 3", "💀 Stage 4"])
                        
                        with s_tabs[0]:
                            if stage_results["Stage 1 - Basing"]:
                                s1 = add_tradingview_column(stage_results["Stage 1 - Basing"])
                                st.dataframe(pd.DataFrame(s1), 
                                             column_config={"Stock Symbol": st.column_config.LinkColumn("Stock Symbol", display_text="NSE:(.*)")},
                                             use_container_width=True)
                            else: st.info("No stocks currently in the basing stage.")
                        with s_tabs[1]:
                            if stage_results["Stage 2 - Advancing"]:
                                s2 = add_tradingview_column(stage_results["Stage 2 - Advancing"])
                                st.dataframe(pd.DataFrame(s2), 
                                             column_config={"Stock Symbol": st.column_config.LinkColumn("Stock Symbol", display_text="NSE:(.*)")},
                                             use_container_width=True)
                            else: st.info("No stocks currently in the advancing stage.")
                        with s_tabs[2]:
                            if stage_results["Stage 3 - Top"]:
                                s3 = add_tradingview_column(stage_results["Stage 3 - Top"])
                                st.dataframe(pd.DataFrame(s3), 
                                             column_config={"Stock Symbol": st.column_config.LinkColumn("Stock Symbol", display_text="NSE:(.*)")},
                                             use_container_width=True)
                            else: st.info("No stocks currently in the top/distribution stage.")
                        with s_tabs[3]:
                            if stage_results["Stage 4 - Declining"]:
                                s4 = add_tradingview_column(stage_results["Stage 4 - Declining"])
                                st.dataframe(pd.DataFrame(s4), 
                                             column_config={"Stock Symbol": st.column_config.LinkColumn("Stock Symbol", display_text="NSE:(.*)")},
                                             use_container_width=True)
                            else: st.info("No stocks currently in the declining stage.")
                    except Exception as e:
                        st.error(f"Scanner error: {str(e)}")

    except Exception as e:
        st.error(f"Error fetching data for {ticker}: {str(e)}")
else:
    st.info("Enter a Ticker Symbol in the sidebar to start analysis.")
