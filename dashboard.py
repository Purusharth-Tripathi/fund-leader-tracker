"""
Fund Leader Tracker - Interactive Dashboard
Web-based dashboard for visualizing planner analysis results
"""
import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os
import sqlite3

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

    # Discover which tables are present so we degrade gracefully on older schemas
    existing_tables = set(
        pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table'", conn
        )['name'].tolist()
    )

    def safe_query(sql, fallback_cols):
        try:
            return pd.read_sql_query(sql, conn)
        except Exception:
            return pd.DataFrame(columns=fallback_cols)

    # Latest planner state per sector
    if 'sector_strategy_state' in existing_tables:
        current_state = safe_query("""
            SELECT sector_name AS sector, review_date, active_symbol AS symbol, active_name AS company,
                   active_kind, status, data_status, last_action, last_action_reason,
                   evidence_json, sector_freshness_json
            FROM sector_strategy_state
            WHERE id IN (SELECT MAX(id) FROM sector_strategy_state GROUP BY sector_name)
            ORDER BY sector_name
        """, ['sector', 'review_date', 'symbol', 'company', 'active_kind',
              'status', 'data_status', 'last_action', 'last_action_reason',
              'evidence_json', 'sector_freshness_json'])
    else:
        current_state = pd.DataFrame(columns=[
            'sector', 'review_date', 'symbol', 'company', 'active_kind',
            'status', 'data_status', 'last_action', 'last_action_reason',
            'evidence_json', 'sector_freshness_json',
        ])

    # Planner run history
    if 'strategy_runs' in existing_tables:
        strategy_runs = safe_query("""
            SELECT review_date, run_timestamp, summary_json, portfolio_json,
                   report_text_path, report_json_path
            FROM strategy_runs
            ORDER BY run_timestamp DESC
            LIMIT 30
        """, ['review_date', 'run_timestamp', 'summary_json',
              'portfolio_json', 'report_text_path', 'report_json_path'])
    else:
        strategy_runs = pd.DataFrame(columns=[
            'review_date', 'run_timestamp', 'summary_json',
            'portfolio_json', 'report_text_path', 'report_json_path',
        ])

    # Sector definitions
    if 'sectors' in existing_tables:
        sectors = safe_query("SELECT name, keywords FROM sectors ORDER BY name",
                             ['name', 'keywords'])
    else:
        sectors = pd.DataFrame(columns=['name', 'keywords'])

    # Tracked funds
    if 'tracked_funds' in existing_tables:
        funds = safe_query("""
            SELECT sector_name AS sector, fund_symbol, fund_name, rank_in_sector
            FROM tracked_funds
            ORDER BY sector_name, rank_in_sector
        """, ['sector', 'fund_symbol', 'fund_name', 'rank_in_sector'])
    else:
        funds = pd.DataFrame(columns=['sector', 'fund_symbol', 'fund_name', 'rank_in_sector'])

    # Candidate leaders derived from evidence_json -> leaders_considered
    candidate_rows = []
    for _, row in current_state.iterrows():
        try:
            evidence = json.loads(row['evidence_json']) if row['evidence_json'] else {}
            for leader in (evidence.get('leaders_considered') or []):
                candidate_rows.append({
                    'sector': row['sector'],
                    'review_date': row['review_date'],
                    'symbol': leader.get('symbol'),
                    'company': leader.get('name'),
                    'times_held': leader.get('times_held'),
                    'avg_weight': leader.get('avg_weight'),
                    'prevalence': leader.get('prevalence'),
                    'sector_status': row['status'],
                    'active_symbol': row['symbol'],
                })
        except Exception:
            pass
    candidates = pd.DataFrame(candidate_rows)

    conn.close()
    return current_state, candidates, strategy_runs, sectors, funds, db_path


def get_pending_sectors(current_state_df):
    if current_state_df is None or len(current_state_df) == 0:
        return pd.DataFrame()
    return current_state_df[current_state_df['status'] == 'pending_confirmation'][
        ['sector', 'symbol', 'company', 'status']
    ].copy()


def main():
    # Header
    st.markdown('<div class="main-header">📊 Fund Leader Tracker Dashboard</div>', unsafe_allow_html=True)
    st.markdown("---")

    # Load data
    current_state, candidates, strategy_runs, sectors, funds, db_path = load_data()

    if current_state is None:
        st.warning("⚠️ Database not found. Please run a planner review first.")
        st.info(f"Expected DB path: {db_path}")
        return

    if len(current_state) == 0:
        st.warning("⚠️ No planner data yet. The `sector_strategy_state` table is empty or missing.")
        st.info(
            f"DB path: {db_path}\n\n"
            "Run a planner review (`python run_analysis.py`) to populate the planner tables."
        )
        return

    # Sidebar
    st.sidebar.header("⚙️ Dashboard Controls")

    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    # Sector filter
    st.sidebar.subheader("🏢 Sector Filter")
    all_sectors = sorted(current_state['sector'].unique())
    selected_sectors = st.sidebar.multiselect(
        "Select sectors",
        options=all_sectors,
        default=all_sectors
    )

    # Filter state to selected sectors
    filtered_state = current_state[current_state['sector'].isin(selected_sectors)]

    # ── Overview Metrics ──────────────────────────────────────────────────────
    st.header("📈 Overview")
    col1, col2, col3, col4 = st.columns(4)

    pending_df = get_pending_sectors(filtered_state)

    with col1:
        st.metric("Total Sectors", len(filtered_state))

    with col2:
        st.metric("Pending Confirmation", len(pending_df))

    with col3:
        last_review = filtered_state['review_date'].max() if len(filtered_state) > 0 else "Never"
        st.metric("Last Review Date", last_review)

    with col4:
        total_runs = len(strategy_runs) if strategy_runs is not None else 0
        st.metric("Planner Runs (last 30)", total_runs)

    st.markdown("---")

    # ── Pending Confirmation Alert ────────────────────────────────────────────
    if len(pending_df) > 0:
        st.header("🔔 Pending Confirmation")
        st.warning(f"⚠️ {len(pending_df)} sector(s) have candidates pending confirmation")
        for _, row in pending_df.iterrows():
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown(f"**{row['sector']}**")
            with col2:
                st.markdown(
                    f"Candidate: <span class='change-positive'>{row['symbol']}</span> ({row['company']})",
                    unsafe_allow_html=True
                )
        st.markdown("---")

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Current State", "📊 Charts", "📜 Run History", "ℹ️ About"])

    # ── Tab 1: Current Sector Strategy State ─────────────────────────────────
    with tab1:
        st.header("Current Sector Strategy State")
        st.caption("Latest planner state per sector: active instrument, status, data freshness, and review date")

        display_df = filtered_state[
            ['sector', 'symbol', 'company', 'active_kind', 'status', 'data_status', 'review_date']
        ].copy()
        display_df.columns = ['Sector', 'Active Symbol', 'Active Name', 'Kind', 'Status', 'Data Status', 'Review Date']
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # ── Candidate Leaders by Sector ───────────────────────────────────────
        st.subheader("Candidate Leaders by Sector")
        filtered_candidates = (
            candidates[candidates['sector'].isin(selected_sectors)]
            if candidates is not None and len(candidates) > 0
            else pd.DataFrame()
        )
        if len(filtered_candidates) > 0:
            cand_display = filtered_candidates[
                ['sector', 'symbol', 'company', 'times_held', 'avg_weight', 'prevalence', 'sector_status']
            ].copy()
            cand_display.columns = [
                'Sector', 'Candidate Symbol', 'Candidate Name',
                'Times Held', 'Avg Weight', 'Prevalence', 'Sector Status'
            ]
            st.dataframe(cand_display, use_container_width=True, hide_index=True)
        else:
            st.info("No candidate leaders available yet for the selected sectors.")

        # ── Tracked Funds by Sector ───────────────────────────────────────────
        st.subheader("📁 Funds Tracked by Sector")
        if funds is not None and len(funds) > 0:
            filtered_funds = funds[funds['sector'].isin(selected_sectors)]
            for sector in selected_sectors:
                sector_funds = filtered_funds[filtered_funds['sector'] == sector]
                if len(sector_funds) > 0:
                    with st.expander(f"**{sector}** ({len(sector_funds)} funds)", expanded=False):
                        fund_cols = st.columns(min(5, len(sector_funds)))
                        for i, (_, fund) in enumerate(sector_funds.iterrows()):
                            with fund_cols[i % 5]:
                                st.markdown(f"**{fund['fund_symbol']}**")
                                if fund['fund_name'] and fund['fund_name'] != fund['fund_symbol']:
                                    st.caption(str(fund['fund_name'])[:30])
        else:
            st.info("No fund data available")

    # ── Tab 2: Planner Charts ─────────────────────────────────────────────────
    with tab2:
        st.header("Planner Overview Charts")

        col1, col2 = st.columns(2)

        with col1:
            status_counts = filtered_state['status'].value_counts().reset_index()
            status_counts.columns = ['status', 'count']
            fig1 = px.bar(
                status_counts, x='status', y='count',
                title='Sector Status Counts', color='status'
            )
            st.plotly_chart(fig1, use_container_width=True)

        with col2:
            freshness_counts = filtered_state['data_status'].value_counts().reset_index()
            freshness_counts.columns = ['data_status', 'count']
            fig2 = px.bar(
                freshness_counts, x='data_status', y='count',
                title='Data Status Counts', color='data_status'
            )
            st.plotly_chart(fig2, use_container_width=True)

        # Top candidate leaders by avg_weight
        if len(filtered_candidates) > 0 and 'avg_weight' in filtered_candidates.columns:
            st.subheader("🏆 Top Candidate Leaders by Avg Weight")
            top_candidates = (
                filtered_candidates
                .dropna(subset=['avg_weight'])
                .sort_values('avg_weight', ascending=False)
                .head(10)
            )
            if len(top_candidates) > 0:
                fig3 = px.bar(
                    top_candidates, x='symbol', y='avg_weight',
                    color='sector', text='company',
                    title='Top Candidates by Average Weight',
                    labels={'avg_weight': 'Avg Weight (%)', 'symbol': 'Symbol'}
                )
                st.plotly_chart(fig3, use_container_width=True)

    # ── Tab 3: Planner Run History ────────────────────────────────────────────
    with tab3:
        st.header("Planner Run History")

        if strategy_runs is not None and len(strategy_runs) > 0:
            st.subheader("Recent Strategy Runs")

            runs_display = strategy_runs[
                ['review_date', 'run_timestamp', 'summary_json']
            ].copy()
            runs_display.columns = ['Review Date', 'Run Timestamp', 'Summary']
            st.dataframe(runs_display, use_container_width=True, hide_index=True)

            # Runs-per-date bar chart
            if len(strategy_runs) > 1:
                runs_df = strategy_runs.copy()
                runs_df['date'] = pd.to_datetime(runs_df['review_date'], errors='coerce')
                runs_df = runs_df.dropna(subset=['date'])
                runs_per_date = runs_df.groupby('date').size().reset_index(name='runs')
                fig = px.bar(
                    runs_per_date, x='date', y='runs',
                    title='Planner Runs by Review Date',
                    labels={'date': 'Date', 'runs': 'Runs'}
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No planner run history available")

        # Candidate history (all sectors, filtered)
        if candidates is not None and len(candidates) > 0:
            st.subheader("Candidate Leader Log")
            cand_log = candidates[candidates['sector'].isin(selected_sectors)][
                ['review_date', 'sector', 'symbol', 'company', 'times_held', 'avg_weight', 'prevalence']
            ].copy()
            cand_log.columns = [
                'Review Date', 'Sector', 'Symbol', 'Company',
                'Times Held', 'Avg Weight (%)', 'Prevalence'
            ]
            if 'Avg Weight (%)' in cand_log.columns:
                cand_log['Avg Weight (%)'] = pd.to_numeric(
                    cand_log['Avg Weight (%)'], errors='coerce'
                ).round(2)
            st.dataframe(cand_log, use_container_width=True, hide_index=True)

            csv = cand_log.to_csv(index=False)
            st.download_button(
                label="📥 Download Candidate Data (CSV)",
                data=csv,
                file_name=f"fund_leaders_candidates_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

    # ── Tab 4: About ──────────────────────────────────────────────────────────
    with tab4:
        st.header("About Fund Leader Tracker")

        st.markdown("""
        ### 📊 What is Fund Leader Tracker?

        Fund Leader Tracker identifies sector leaders by analysing the holdings of top-performing
        sector ETFs. The planner model maintains a per-sector strategy state — tracking the active
        symbol, its confirmation status, and data freshness — so the portfolio always reflects the
        most evidence-backed choice rather than a snapshot vote.

        ### 🎯 How It Works

        1. **Data Collection**: Fetches ETF holdings from Alpha Vantage (with FMP fallback)
        2. **Sector Review**: Each of the 9 sectors is reviewed on a staggered cadence to respect
           API rate limits
        3. **Candidate Evaluation**: Leaders are ranked by prevalence and weight across the curated
           fund universe; the top candidate is compared against the current active holding
        4. **Planner State**: Changes require a `pending_confirmation` step before the active
           symbol is updated, preventing noise-driven churn
        5. **Run History**: Every review cycle is logged in `strategy_runs` for full auditability

        ### 📈 Status Values

        - **confirmed** – active symbol has been validated and is held
        - **pending_confirmation** – a new candidate has been identified; awaiting next review to confirm
        - **fallback** – no strong candidate; holding a broad-market fallback
        - **no_data** – insufficient holdings data to make a determination

        ### 🏢 Sectors Covered
        """)

        if sectors is not None and len(sectors) > 0:
            for _, sector in sectors.iterrows():
                with st.expander(f"**{sector['name']}**"):
                    st.write(f"Keywords: {sector['keywords']}")

        st.markdown("""
        ### 🔄 Automation

        The planner can be scheduled via Windows Task Scheduler to run daily, automatically:
        - Refreshing ETF holdings (cache-aware, to minimise API calls)
        - Advancing sector planner state
        - Sending email alerts when an active symbol changes
        - Updating this dashboard

        ### 📧 Email Alerts

        Alerts are sent only when the active symbol for a sector changes, keeping notifications
        meaningful and low-volume.

        ---

        **Last Updated**: {0}

        **Primary Data Source**: Alpha Vantage API
        """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    # Footer
    st.markdown("---")
    st.caption("Fund Leader Tracker Dashboard | Data updates daily | Powered by Streamlit & Alpha Vantage")


from utils import load_env
load_env()

if __name__ == "__main__":
    main()
