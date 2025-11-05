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
    """Load data from SQLite database"""
    db_path = os.getenv('DATABASE_PATH', 'data/fund_leaders.db')

    if not os.path.exists(db_path):
        return None, None, None, None

    conn = sqlite3.connect(db_path)

    # Load current leaders (latest per sector)
    current_leaders_query = """
        SELECT
            s.name as sector,
            il.company_symbol as symbol,
            il.company_name as company,
            il.times_held,
            il.total_weight,
            il.avg_weight,
            il.analysis_date,
            il.created_at
        FROM industry_leaders il
        JOIN sectors s ON il.sector_id = s.id
        WHERE il.id IN (
            SELECT MAX(id)
            FROM industry_leaders
            GROUP BY sector_id
        )
        ORDER BY s.name
    """
    current_leaders = pd.read_sql_query(current_leaders_query, conn)

    # Load all historical leaders
    all_leaders_query = """
        SELECT
            s.name as sector,
            il.company_symbol as symbol,
            il.company_name as company,
            il.times_held,
            il.total_weight,
            il.avg_weight,
            il.analysis_date,
            il.created_at
        FROM industry_leaders il
        JOIN sectors s ON il.sector_id = s.id
        ORDER BY il.created_at DESC
    """
    all_leaders = pd.read_sql_query(all_leaders_query, conn)

    # Load analysis runs
    runs_query = """
        SELECT
            run_date,
            sectors_analyzed,
            funds_analyzed,
            leaders_found,
            status,
            notes
        FROM analysis_runs
        ORDER BY run_date DESC
        LIMIT 30
    """
    analysis_runs = pd.read_sql_query(runs_query, conn)

    # Load sectors
    sectors_query = "SELECT name, keywords FROM sectors ORDER BY name"
    sectors = pd.read_sql_query(sectors_query, conn)

    conn.close()

    return current_leaders, all_leaders, analysis_runs, sectors


def detect_changes(all_leaders_df):
    """Detect leadership changes between analysis runs"""
    if all_leaders_df is None or len(all_leaders_df) < 2:
        return pd.DataFrame()

    # Convert dates
    all_leaders_df['date'] = pd.to_datetime(all_leaders_df['analysis_date'], errors='coerce')

    # Get unique dates
    dates = sorted(all_leaders_df['date'].unique(), reverse=True)

    if len(dates) < 2:
        return pd.DataFrame()

    # Compare latest with previous
    latest_date = dates[0]
    previous_date = dates[1]

    latest = all_leaders_df[all_leaders_df['date'] == latest_date]
    previous = all_leaders_df[all_leaders_df['date'] == previous_date]

    changes = []
    for sector in latest['sector'].unique():
        latest_leader = latest[latest['sector'] == sector]['symbol'].iloc[0]
        prev_leaders = previous[previous['sector'] == sector]

        if len(prev_leaders) > 0:
            prev_leader = prev_leaders['symbol'].iloc[0]
            if latest_leader != prev_leader:
                latest_data = latest[latest['sector'] == sector].iloc[0]
                prev_data = prev_leaders.iloc[0]

                changes.append({
                    'sector': sector,
                    'old_symbol': prev_leader,
                    'old_company': prev_data['company'],
                    'new_symbol': latest_leader,
                    'new_company': latest_data['company'],
                    'new_times_held': latest_data['times_held'],
                    'new_avg_weight': latest_data['avg_weight'],
                    'change_date': latest_date.strftime('%Y-%m-%d')
                })

    return pd.DataFrame(changes)


def main():
    # Header
    st.markdown('<div class="main-header">📊 Fund Leader Tracker Dashboard</div>', unsafe_allow_html=True)
    st.markdown("---")

    # Load data
    current_leaders, all_leaders, analysis_runs, sectors = load_data()

    if current_leaders is None or len(current_leaders) == 0:
        st.warning("⚠️ No data available. Please run an analysis first.")
        st.info("Run: `python main.py` to generate data")
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
            label="Recent Changes",
            value=len(changes_df),
            delta="Leadership shifts"
        )

    with col4:
        last_update = current_leaders['analysis_date'].iloc[0] if len(current_leaders) > 0 else "Never"
        st.metric(
            label="Last Analysis",
            value=last_update
        )

    st.markdown("---")

    # Leadership Changes Alert
    if len(changes_df) > 0:
        st.header("🔔 Recent Leadership Changes")
        st.warning(f"⚠️ {len(changes_df)} sector(s) have new leaders!")

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
        st.header("Current Industry Leaders")
        st.caption("Top leader in each sector based on fund holdings analysis")

        # Create display dataframe
        display_df = filtered_leaders.copy()
        display_df['Prevalence'] = (display_df['times_held'] / 5 * 100).round(1).astype(str) + '%'
        display_df['Avg Weight'] = display_df['avg_weight'].round(2).astype(str) + '%'
        display_df = display_df[['sector', 'symbol', 'company', 'times_held', 'Avg Weight', 'Prevalence', 'analysis_date']]
        display_df.columns = ['Sector', 'Symbol', 'Company', 'Times Held', 'Avg Weight', 'Prevalence', 'Analysis Date']

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )

        # Charts
        st.subheader("📊 Visualizations")

        col1, col2 = st.columns(2)

        with col1:
            # Holdings distribution
            fig1 = px.bar(
                filtered_leaders,
                x='sector',
                y='times_held',
                title='Holdings Frequency by Sector',
                labels={'times_held': 'Times Held (out of 5)', 'sector': 'Sector'},
                color='times_held',
                color_continuous_scale='Blues'
            )
            fig1.update_layout(xaxis_tickangle=-45, showlegend=False)
            st.plotly_chart(fig1, use_container_width=True)

        with col2:
            # Average weight
            fig2 = px.bar(
                filtered_leaders,
                x='sector',
                y='avg_weight',
                title='Average Portfolio Weight by Sector',
                labels={'avg_weight': 'Avg Weight (%)', 'sector': 'Sector'},
                color='avg_weight',
                color_continuous_scale='Greens'
            )
            fig2.update_layout(xaxis_tickangle=-45, showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)

        # Top companies
        st.subheader("🏆 Top Companies")
        top_companies = filtered_leaders.nlargest(5, 'avg_weight')[['company', 'symbol', 'sector', 'avg_weight', 'times_held']]

        for idx, row in top_companies.iterrows():
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.markdown(f"**{row['company']}** ({row['symbol']})")
                st.caption(row['sector'])
            with col2:
                st.metric("Avg Weight", f"{row['avg_weight']:.2f}%")
            with col3:
                st.metric("Times Held", f"{row['times_held']}/5")

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
        mutual funds across 10 key sectors. The system tracks which companies are most commonly
        held by institutional investors, providing insights into market sentiment.

        ### 🎯 How It Works

        1. **Data Collection**: Fetches fund holdings data from Alpha Vantage API
        2. **Analysis**: Identifies the top 5 funds per sector based on 3-year performance
        3. **Leader Identification**: Determines which companies appear most frequently in fund portfolios
        4. **Change Detection**: Compares with previous analysis to detect leadership shifts
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


if __name__ == "__main__":
    # Load environment
    from utils import load_env
    load_env()

    main()
