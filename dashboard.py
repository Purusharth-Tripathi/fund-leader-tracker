"""
Fund Leader Tracker - Interactive Dashboard
Web-based dashboard for visualizing fund analysis results
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import sqlite3
from pathlib import Path

# Page configuration
st.set_page_config(
    page_title="Fund Leader Tracker Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .change-positive {
        color: #28a745;
        font-weight: bold;
    }
    .change-negative {
        color: #dc3545;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_data():
    """Load planner data from SQLite database."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_db = os.path.join(script_dir, 'data', 'fund_leaders.db')
    db_path = os.getenv('DATABASE_PATH', default_db)

    if not os.path.exists(db_path):
        return None, None, None, None, None, None

    conn = sqlite3.connect(db_path)

    current_state_query = """
        SELECT sector_name as sector, review_date, active_symbol as symbol, active_name as company,
               active_kind, status, data_status, last_action, last_action_reason, evidence_json, sector_freshness_json
        FROM sector_strategy_state
        WHERE id IN (SELECT MAX(id) FROM sector_strategy_state GROUP BY sector_name)
        ORDER BY sector_name
    """
    current_state = pd.read_sql_query(current_state_query, conn)

    strategy_runs_query = """
        SELECT review_date, run_timestamp, summary_json, portfolio_json, report_text_path, report_json_path
        FROM strategy_runs
        ORDER BY run_timestamp DESC
        LIMIT 30
    """
    strategy_runs = pd.read_sql_query(strategy_runs_query, conn)

    sectors_query = "SELECT name, keywords FROM sectors ORDER BY name"
    sectors = pd.read_sql_query(sectors_query, conn)

    funds_query = """
        SELECT sector_name as sector, fund_symbol, fund_name, rank_in_sector
        FROM tracked_funds
        ORDER BY sector_name, rank_in_sector
    """
    funds = pd.read_sql_query(funds_query, conn)

    # Planner candidates view derived from evidence_json
    candidate_rows = []
    for _, row in current_state.iterrows():
        try:
            evidence = __import__('json').loads(row['evidence_json']) if row['evidence_json'] else {}
            for leader in (evidence.get('leaders_considered') or []):
                candidate_rows.append({
                    'sector': row['sector'],
                    'review_date': row['review_date'],
                    'symbol': leader.get('symbol'),
                    'company': leader.get('name'),
                    'times_held': leader.get('times_held'),
                    'avg_weight': leader.get('avg_weight'),
                    'prevalence': leader.get('prevalence'),
                    'status': row['status'],
                    'active_symbol': row['symbol'],
                })
        except Exception:
            pass
    candidates = pd.DataFrame(candidate_rows)

    conn.close()
    return current_state, candidates, strategy_runs, sectors, funds, db_path


def detect_changes(current_state_df):
    if current_state_df is None or len(current_state_df) == 0:
        return pd.DataFrame()
    return current_state_df[current_state_df['status'].isin(['pending_confirmation'])][['sector','symbol','company','status']].copy()


def main():
    # Header
    st.markdown('<div class="main-header">📊 Fund Leader Tracker Dashboard</div>', unsafe_allow_html=True)
    st.markdown("---")

    # Load data
    current_leaders, all_leaders, analysis_runs, sectors, funds, db_path = load_data()

    if current_leaders is None or len(current_leaders) == 0:
        st.warning("⚠️ No data available. Please run an analysis first.")
        st.info(f"DB path: {db_path}\nRun planner review to generate data.")
        return

    # Sidebar
    st.sidebar.header("⚙️ Dashboard Controls")

    # Refresh button
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    # Date filter
    st.sidebar.subheader("📅 Date Range")
    if all_leaders is not None and len(all_leaders) > 0:
        all_leaders['date'] = pd.to_datetime(all_leaders['analysis_date'], errors='coerce')
        all_leaders = all_leaders.dropna(subset=['date'])  # Remove rows with invalid dates
        min_date = all_leaders['date'].min().date()
        max_date = all_leaders['date'].max().date()

        date_range = st.sidebar.date_input(
            "Select date range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )

    # Sector filter
    st.sidebar.subheader("🏢 Sector Filter")
    selected_sectors = st.sidebar.multiselect(
        "Select sectors",
        options=current_leaders['sector'].unique(),
        default=current_leaders['sector'].unique()
    )

    # Filter data
    filtered_leaders = current_leaders[current_leaders['sector'].isin(selected_sectors)]

    # Overview Metrics
    st.header("📈 Overview")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total Sectors",
            value=len(filtered_leaders),
            delta=None
        )

    with col2:
        latest_run = analysis_runs.iloc[0] if len(analysis_runs) > 0 else None
        funds_analyzed = latest_run['funds_analyzed'] if latest_run is not None else 0
        st.metric(
            label="Funds Analyzed",
            value=funds_analyzed
        )

    with col3:
        # Detect recent changes
        changes_df = detect_changes(all_leaders)
        st.metric(
            label="Pending Sectors",
            value=len(changes_df),
            delta="Need confirmation"
        )

    with col4:
        last_update = current_leaders['analysis_date'].max() if len(current_leaders) > 0 else "Never"
        st.metric(
            label="Last Analysis",
            value=last_update
        )

    st.markdown("---")

    # Leadership Changes Alert
    if len(changes_df) > 0:
        st.header("🔔 Pending Confirmation")
        st.warning(f"⚠️ {len(changes_df)} sector(s) have candidate leaders pending confirmation")

        for _, change in changes_df.iterrows():
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown(f"**{change['sector']}**")
            with col2:
                st.markdown(
                    f"<span class='change-negative'>{change['old_symbol']}</span> "
                    f"({change['old_company']}) → "
                    f"<span class='change-positive'>{change['new_symbol']}</span> "
                    f"({change['new_company']})",
                    unsafe_allow_html=True
                )
        st.markdown("---")

    # Main Content Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Current Leaders", "📈 Trends", "📜 History", "ℹ️ About"])

    with tab1:
        st.header("Current Sector Strategy State")
        st.caption("Planner state by sector: active instrument, status, data freshness, and candidate leaders")

        display_df = filtered_leaders[['sector','symbol','company','active_kind','status','data_status','review_date']].copy()
        display_df.columns = ['Sector', 'Active Symbol', 'Active Name', 'Kind', 'Status', 'Data Status', 'Review Date']
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        st.subheader("Candidate Leaders by Sector")
        candidate_df = all_leaders[all_leaders['sector'].isin(selected_sectors)] if all_leaders is not None and len(all_leaders) > 0 else pd.DataFrame()
        if len(candidate_df) > 0:
            cand = candidate_df[['sector','symbol','company','times_held','avg_weight','prevalence','status']].copy()
            cand.columns = ['Sector','Candidate Symbol','Candidate Name','Times Held','Avg Weight','Prevalence','Sector Status']
            st.dataframe(cand, use_container_width=True, hide_index=True)
        else:
            st.info('No candidate leaders available yet for the selected sectors.')

        # Charts
        st.subheader("📊 Planner Overview")

        col1, col2 = st.columns(2)

        with col1:
            # Holdings distribution
            status_counts = filtered_leaders['status'].value_counts().reset_index()
            status_counts.columns=['status','count']
            fig1 = px.bar(status_counts, x='status', y='count', title='Sector Status Counts', color='status')
            st.plotly_chart(fig1, use_container_width=True)

        with col2:
            # Average weight
            freshness_counts = filtered_leaders['data_status'].value_counts().reset_index()
            freshness_counts.columns=['data_status','count']
            fig2 = px.bar(freshness_counts, x='data_status', y='count', title='Data Status Counts', color='data_status')
            st.plotly_chart(fig2, use_container_width=True)

        # Top companies
        st.subheader("🏆 Top Candidate Leaders")
        top_companies = all_leaders.sort_values('avg_weight', ascending=False).head(5) if all_leaders is not None and len(all_leaders) > 0 else pd.DataFrame()

        for idx, row in top_companies.iterrows():
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.markdown(f"**{row['company']}** ({row['symbol']})")
                st.caption(row['sector'])
            with col2:
                st.metric("Avg Weight", f"{row['avg_weight']:.2f}%")
            with col3:
                st.metric("Times Held", f"{row['times_held']}/5")

        # Funds analyzed per sector
        st.subheader("📁 Funds Analyzed by Sector")
        st.caption("The 5 ETFs/funds analyzed for each sector")

        if funds is not None and len(funds) > 0:
            # Filter funds based on selected sectors
            filtered_funds = funds[funds['sector'].isin(selected_sectors)]

            # Group by sector and display
            for sector in selected_sectors:
                sector_funds = filtered_funds[filtered_funds['sector'] == sector]
                if len(sector_funds) > 0:
                    with st.expander(f"**{sector}** ({len(sector_funds)} funds)", expanded=False):
                        # Create columns for fund display
                        fund_cols = st.columns(min(5, len(sector_funds)))
                        for i, (_, fund) in enumerate(sector_funds.iterrows()):
                            with fund_cols[i % 5]:
                                st.markdown(f"**{fund['fund_symbol']}**")
                                if fund['fund_name'] and fund['fund_name'] != fund['fund_symbol']:
                                    st.caption(fund['fund_name'][:30])
        else:
            st.info("No fund data available")

    with tab2:
        st.header("Historical Trends")

        if all_leaders is not None and len(all_leaders) > 1:
            # Prepare trend data
            trend_data = all_leaders.copy()
            trend_data['date'] = pd.to_datetime(trend_data['analysis_date'], errors='coerce')
            trend_data = trend_data.dropna(subset=['date'])  # Remove rows with invalid dates

            # Filter by selected sectors
            trend_data = trend_data[trend_data['sector'].isin(selected_sectors)]

            # Sector selector for trend
            selected_trend_sector = st.selectbox(
                "Select sector to view trend",
                options=sorted(selected_sectors)
            )

            sector_trend = trend_data[trend_data['sector'] == selected_trend_sector].sort_values('date')

            if len(sector_trend) > 0:
                # Leadership timeline
                fig = go.Figure()

                for symbol in sector_trend['symbol'].unique():
                    symbol_data = sector_trend[sector_trend['symbol'] == symbol]
                    fig.add_trace(go.Scatter(
                        x=symbol_data['date'],
                        y=symbol_data['avg_weight'],
                        mode='lines+markers',
                        name=symbol,
                        text=symbol_data['company'],
                        hovertemplate='<b>%{text}</b><br>Date: %{x}<br>Weight: %{y:.2f}%<extra></extra>'
                    ))

                fig.update_layout(
                    title=f'Leadership Trend: {selected_trend_sector}',
                    xaxis_title='Date',
                    yaxis_title='Average Weight (%)',
                    hovermode='x unified',
                    height=500
                )

                st.plotly_chart(fig, use_container_width=True)

                # Leadership changes table for this sector
                st.subheader(f"Leadership History: {selected_trend_sector}")
                history_display = sector_trend[['date', 'symbol', 'company', 'times_held', 'avg_weight']].copy()
                history_display['date'] = history_display['date'].dt.strftime('%Y-%m-%d')
                history_display.columns = ['Date', 'Symbol', 'Company', 'Times Held', 'Avg Weight (%)']
                st.dataframe(history_display, use_container_width=True, hide_index=True)
            else:
                st.info("No historical data available for this sector")
        else:
            st.info("Run multiple analyses to see trends over time")

    with tab3:
        st.header("Analysis History")

        if analysis_runs is not None and len(analysis_runs) > 0:
            st.subheader("Recent Analysis Runs")

            runs_display = analysis_runs.copy()
            runs_display.columns = ['Date', 'Sectors', 'Funds', 'Leaders', 'Status', 'Notes']

            st.dataframe(
                runs_display,
                use_container_width=True,
                hide_index=True
            )

            # Analysis frequency chart
            if len(analysis_runs) > 1:
                runs_df = analysis_runs.copy()
                runs_df['date'] = pd.to_datetime(runs_df['run_date'], errors='coerce')
                runs_df = runs_df.dropna(subset=['date'])  # Remove any rows where date parsing failed
                runs_df = runs_df.sort_values('date')

                fig = px.line(
                    runs_df,
                    x='date',
                    y='leaders_found',
                    title='Leaders Found Over Time',
                    labels={'leaders_found': 'Leaders Identified', 'date': 'Date'},
                    markers=True
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No analysis history available")

        # All historical leaders
        if all_leaders is not None and len(all_leaders) > 0:
            st.subheader("Complete Leadership History")

            # Apply date filter if available
            if 'date_range' in locals() and len(date_range) == 2:
                filtered_history = all_leaders[
                    (all_leaders['date'].dt.date >= date_range[0]) &
                    (all_leaders['date'].dt.date <= date_range[1]) &
                    (all_leaders['sector'].isin(selected_sectors))
                ]
            else:
                filtered_history = all_leaders[all_leaders['sector'].isin(selected_sectors)]

            history_display = filtered_history[['analysis_date', 'sector', 'symbol', 'company', 'times_held', 'avg_weight']].copy()
            history_display['avg_weight'] = history_display['avg_weight'].round(2)
            history_display.columns = ['Date', 'Sector', 'Symbol', 'Company', 'Times Held', 'Avg Weight (%)']

            st.dataframe(
                history_display,
                use_container_width=True,
                hide_index=True
            )

            # Download button
            csv = history_display.to_csv(index=False)
            st.download_button(
                label="📥 Download Historical Data (CSV)",
                data=csv,
                file_name=f"fund_leaders_history_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

    with tab4:
        st.header("About Fund Leader Tracker")

        st.markdown("""
        ### 📊 What is Fund Leader Tracker?

        Fund Leader Tracker identifies industry leaders by analyzing the holdings of top-performing
        sector ETFs across the current planner universe. The system tracks which companies are most commonly
        held by institutional investors, providing insights into market sentiment.

        ### 🎯 How It Works

        1. **Data Collection**: Fetches fund holdings data from Alpha Vantage API
        2. **Analysis**: Reviews the curated 5 ETF universe per sector using planner state and cache-aware holdings refresh
        3. **Leader Identification**: Determines which companies appear most frequently in fund portfolios
        4. **Planner State**: Tracks pending confirmations, fallbacks, and freshness by sector
        5. **Alerts**: Sends email notifications when sector leaders change

        ### 📈 Metrics Explained

        - **Times Held**: How many of the top 5 funds hold this stock (out of 5)
        - **Average Weight**: Average portfolio percentage across holding funds
        - **Prevalence**: Percentage of analyzed funds that hold this stock

        ### 🏢 Sectors Covered
        """)

        if sectors is not None:
            for _, sector in sectors.iterrows():
                with st.expander(f"**{sector['name']}**"):
                    st.write(f"Keywords: {sector['keywords']}")

        st.markdown("""
        ### 🔄 Daily Automation

        The system can be scheduled to run daily via Windows Task Scheduler, automatically:
        - Analyzing fund holdings
        - Detecting leadership changes
        - Sending email alerts
        - Updating the dashboard

        ### 📧 Email Alerts

        Configured to send alerts only when leadership changes are detected, reducing noise
        while keeping you informed of significant market shifts.

        ---

        **Last Updated**: {0}

        **Data Source**: Alpha Vantage API
        """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    # Footer
    st.markdown("---")
    st.caption("Fund Leader Tracker Dashboard | Data updates daily | Powered by Streamlit & Alpha Vantage")


from utils import load_env
load_env()

if __name__ == "__main__":
    main()
