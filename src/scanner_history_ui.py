"""
15-Day History UI Component for Streamlit
===========================================
Displays scanner result history and changes over time.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from scanner_history import get_history_manager

def show_scanner_history_ui(scanner_name):
    """Display 15-day history for a scanner."""
    st.subheader(f"📊 {scanner_name.upper()} - 15 Day History")
    
    history_mgr = get_history_manager()
    history = history_mgr.get_history(scanner_name, days=15)
    
    if not history:
        st.info("No historical data available yet. Check back after first scan.")
        return
    
    # Get statistics
    stats = history_mgr.get_statistics(scanner_name, days=15)
    
    # Display stats in columns
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Scans", stats['total_scans'])
    with col2:
        st.metric("Average Count", f"{stats['average_count']:.0f}")
    with col3:
        st.metric("Min/Max", f"{stats['min_count']}/{stats['max_count']}")
    with col4:
        st.metric("Unique Results", stats['unique_results'])
    
    # Create visualization data
    df_history = pd.DataFrame([
        {
            'Timestamp': h['timestamp'],
            'Stock Count': h['count'],
            'Hash': h['hash'][:8]
        }
        for h in history
    ])
    
    df_history['Timestamp'] = pd.to_datetime(df_history['Timestamp'])
    df_history = df_history.sort_values('Timestamp')
    
    # Chart: Stock count over time
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_history['Timestamp'],
        y=df_history['Stock Count'],
        mode='lines+markers',
        name='Stock Count',
        line=dict(color='#10b981', width=2),
        marker=dict(size=8)
    ))
    
    fig.update_layout(
        title='Stock Count Over 15 Days',
        xaxis_title='Date/Time',
        yaxis_title='Number of Stocks',
        hovermode='x unified',
        height=400,
        template='plotly_dark'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Table: Detailed history
    st.write("### Detailed Scan History")
    
    display_df = pd.DataFrame([
        {
            'Timestamp': h['timestamp'],
            'Stock Count': h['count'],
            'Result Hash': h['hash'][:12],
            'Stocks': ', '.join(h['stocks'][:5]) + ('...' if len(h['stocks']) > 5 else '')
        }
        for h in history
    ])
    
    display_df['Timestamp'] = pd.to_datetime(display_df['Timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # Detection: Changes from previous scan
    change_info = history_mgr.detect_change(scanner_name)
    if change_info:
        st.write("### Latest Change Detection")
        if change_info['changed']:
            st.warning(f"⚠️ Results changed!")
            st.info(f"Previous: {change_info['previous_count']} stocks → Current: {change_info['current_count']} stocks (Δ {change_info['difference']:+d})")
        else:
            st.success(f"✅ Results consistent")
            st.info(f"Same results: {change_info['current_count']} stocks")


def show_all_scanners_history():
    """Display history for all scanners in tabs."""
    history_mgr = get_history_manager()
    
    scanners = [
        ('swing', 'Swing Trading'),
        ('smc', 'Smart Money'),
        ('long_term', 'Long-Term'),
        ('cyclical', 'Cyclical'),
        ('stage_analysis', 'Weinstein Stage')
    ]
    
    tabs = st.tabs([s[1] for s in scanners])
    
    for tab, (scanner_key, scanner_label) in zip(tabs, scanners):
        with tab:
            show_scanner_history_ui(scanner_key)


def compare_scanners_across_time():
    """Compare all scanners across time."""
    st.subheader("🔄 Compare All Scanners")
    
    history_mgr = get_history_manager()
    
    scanners = ['swing', 'smc', 'long_term', 'cyclical', 'stage_analysis']
    
    # Get data for all scanners
    all_data = []
    for scanner in scanners:
        history = history_mgr.get_history(scanner, days=15)
        for h in history:
            all_data.append({
                'Scanner': scanner.upper(),
                'Timestamp': h['timestamp'],
                'Count': h['count']
            })
    
    if not all_data:
        st.info("No historical data available yet.")
        return
    
    df = pd.DataFrame(all_data)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    
    # Multi-line chart
    fig = go.Figure()
    
    colors = {
        'SWING': '#10b981',
        'SMC': '#3b82f6',
        'LONG_TERM': '#f59e0b',
        'CYCLICAL': '#8b5cf6',
        'STAGE_ANALYSIS': '#ef4444'
    }
    
    for scanner in scanners:
        scanner_data = df[df['Scanner'] == scanner.upper()].sort_values('Timestamp')
        fig.add_trace(go.Scatter(
            x=scanner_data['Timestamp'],
            y=scanner_data['Count'],
            mode='lines+markers',
            name=scanner.upper(),
            line=dict(color=colors.get(scanner.upper(), '#gray'), width=2),
            marker=dict(size=6)
        ))
    
    fig.update_layout(
        title='All Scanners - Stock Count Comparison',
        xaxis_title='Date/Time',
        yaxis_title='Number of Stocks',
        hovermode='x unified',
        height=500,
        template='plotly_dark'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # --- Common Stocks (Confluence) ---
    st.markdown("### 🏆 Confluence Candidates (Stocks in multiple scanners)")
    st.info("Showing stocks that appear in the **latest** scan of multiple strategies.")
    
    # 1. Get latest results for each scanner
    latest_holdings = {}
    for scanner in scanners:
        # Get history sorted by timestamp (desc)
        history = history_mgr.get_history(scanner, days=5) # 5 days enough to get latest
        if history:
            # Sort by timestamp desc to get absolute latest
            latest = sorted(history, key=lambda x: x['timestamp'], reverse=True)[0]
            # stocks is a list of strings
            latest_holdings[scanner] = set(latest['stocks'])
            
    # 2. Find intersections
    all_tickers = set()
    for stocks in latest_holdings.values():
        all_tickers.update(stocks)
        
    confluence_data = []
    for ticker in all_tickers:
        found_in = []
        for scanner, stocks in latest_holdings.items():
            if ticker in stocks:
                found_in.append(scanner.upper().replace('_', ' '))
        
        if len(found_in) > 1:
            confluence_data.append({
                "Stock Symbol": ticker,
                "Confluence Count": len(found_in),
                "Strategies": ", ".join(found_in)
            })
            
    # 3. Display
    if confluence_data:
        # Sort by count desc
        confluence_data.sort(key=lambda x: x['Confluence Count'], reverse=True)
        
        df_confluence = pd.DataFrame(confluence_data)
        st.dataframe(
            df_confluence,
            column_config={
                "Stock Symbol": st.column_config.TextColumn("Stock", help="Stock found in multiple strategies"),
                "Confluence Count": st.column_config.ProgressColumn("Strength", format="%d", min_value=0, max_value=len(scanners)),
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.warning("No common stocks found across the latest scans.")


# Usage in main app:
"""
In app.py, add a new tab:

with tab_history:
    st.write("### 15-Day Scanner History & Analysis")
    history_view = st.radio("View:", ["Individual Scanner", "Compare All"])
    
    if history_view == "Individual Scanner":
        show_all_scanners_history()
    else:
        compare_scanners_across_time()
"""
