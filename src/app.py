import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from analysis_engine import AnalysisEngine
import pandas as pd
from datetime import datetime

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
    </style>
    """, unsafe_allow_html=True)

# --- JS for Keyboard Shortcuts ---
# Fix: Ensure Ctrl+A / Cmd+A works in selectbox and other inputs
st.components.v1.html(
    """
    <script>
    const doc = window.parent.document;
    doc.addEventListener('keydown', function(event) {
        if ((event.ctrlKey || event.metaKey) && (event.key === 'a' || event.key === 'A')) {
            const activeElement = doc.activeElement;
            if (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA') {
                // Stop Streamlit from intercepting this event
                event.stopImmediatePropagation();
            }
        }
    }, true);
    </script>
    """,
    height=0,
)

# Fetch NSE stock list
@st.cache_data
def get_nse_stocks():
    try:
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        df = pd.read_csv(url)
        # Create a dictionary of { "SYMBOL - NAME": "SYMBOL" }
        stocks = {f"{row['SYMBOL']} - {row['NAME OF COMPANY']}": row['SYMBOL'] for _, row in df.iterrows()}
        return stocks
    except Exception as e:
        st.error(f"Error fetching NSE stock list: {e}")
        return {"RELIANCE - RELIANCE INDUSTRIES LTD": "RELIANCE"}

nse_stocks_dict = get_nse_stocks()
stock_options = sorted(list(nse_stocks_dict.keys()))

# Sidebar
st.sidebar.title("🛠️ Agent Configuration")

# Consolidated stock selection (Ticker and Name in "One Place")
selected_stock_str = st.sidebar.selectbox("Select Stock (Ticker or Name)", 
                                        options=stock_options,
                                        index=stock_options.index("RELIANCE - RELIANCE INDUSTRIES LTD") if "RELIANCE - RELIANCE INDUSTRIES LTD" in stock_options else 0,
                                        help="Search by typing ticker or company name. The list is searchable.")

# Get the symbol from the selected string and add .NS for Yahoo Finance
ticker = f"{nse_stocks_dict[selected_stock_str]}.NS"

timeframe = st.sidebar.selectbox("Timeframe", 
    options=["1m", "5m", "15m", "1h", "4h", "1d", "1wk", "1mo"],
    index=3)

# AI Configuration (Using st.secrets for GitHub safety)
try:
    MODEL_URL = st.secrets["MODEL_URL"]
    MODEL_KEY = st.secrets["MODEL_KEY"]
except:
    MODEL_URL = "https://api.euron.one/api/v1/euri/chat/completions"
    MODEL_KEY = "euri-547dc00208e76ce2d4150524fa1461bf55f8183a73c7419f9f8bd6410a76d743"

st.sidebar.markdown("---")
st.sidebar.subheader("🤖 AI Intelligence")
use_ai = st.sidebar.toggle("Enable AI Reasoning", value=True, help="Use custom LLM for advanced market commentary")
selected_model = st.sidebar.selectbox("Select Model", 
    options=["gpt-5-nano-2025-08-07", "gpt-5-mini-2025-08-07", "gpt-4.1-nano", "gpt-4.1-mini", "gpt-oss-20b", "gpt-oss-120b"])

# Periods for indicators
periods = {
    "1m": "7d", "5m": "30d", "15m": "60d", "1h": "90d", 
    "4h": "max", "1d": "max", "1wk": "max", "1mo": "max"
}

st.title("🚀 Stock Market AI Agent")
st.markdown(f"### Analyzing: {selected_stock_str}")

if ticker:
    try:
        engine = AnalysisEngine(ticker, interval=timeframe, period=periods[timeframe])
        analysis = engine.analyze()
        df = engine.data
        
        # Tabs structure restored to original feel with requested additions
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📊 Agent Analysis", 
            "🤖 AI Insights", 
            "📈 Technical Charts", 
            "🏢 Financials", 
            "🔗 Related Info", 
            "🚀 Agent Recommendations"
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
            
            # List of some liquid NSE tickers for screening
            top_nse_tickers = [
                "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "BHARTIARTL", 
                "INFY", "ITC", "SBIN", "LICI", "HINDUNILVR", 
                "LT", "BAJFINANCE", "HCLTECH", "MARUTI", "SUNPHARMA",
                "ADANIENT", "KOTAKBANK", "TITAN", "AXISBANK", "ONGC"
            ]
            
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
                            st.write("**Technical Basis:**")
                            for r in buy['reasoning']:
                                st.write(f"- {r}")
                            
                with col_sell:
                    st.error("### ❌ Top Avoid/Sell Candidates")
                    if not opps['sells']:
                        st.write("No high-confidence sell setups found.")
                    for sell in opps['sells']:
                        with st.expander(f"🔴 {sell['ticker']} - ₹{sell['price']:.2f} (Conf: {sell['confidence']}%)"):
                            st.write("**Technical Basis:**")
                            for r in sell['reasoning']:
                                st.write(f"- {r}")
            else:
                st.write("Click 'Run Multi-Stock Scanner' to find current opportunities in the market.")

    except Exception as e:
        st.error(f"Error fetching data for {ticker}: {str(e)}")
else:
    st.info("Enter a Ticker Symbol in the sidebar to start analysis.")
