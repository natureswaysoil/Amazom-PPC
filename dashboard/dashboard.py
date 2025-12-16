#!/usr/bin/env python3
"""
Amazon PPC Dashboard
====================

Interactive dashboard for visualizing Amazon PPC campaign performance data.
Uses data exported from the optimizer_core.py script to BigQuery or local files.

Author: Nature's Way Soil
Version: 1.0.1
License: MIT

Usage:
  streamlit run dashboard.py
"""

import os
from datetime import datetime, timedelta, date
from typing import Dict

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Page configuration
st.set_page_config(
    page_title="Amazon PPC Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main {
        padding: 0rem 1rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
    }
    h1 {
        color: #ff9900;
        padding-bottom: 10px;
        border-bottom: 2px solid #ff9900;
    }
    h2 {
        color: #232f3e;
        margin-top: 20px;
    }
    .css-1d391kg {
        padding-top: 1rem;
    }
    </style>
""", unsafe_allow_html=True)


# ============================================================================
# DATA LOADING FUNCTIONS
# ============================================================================

@st.cache_data(ttl=300)
def load_data_from_bigquery(project_id: str, dataset_id: str) -> Dict[str, pd.DataFrame]:
    """Load data from BigQuery tables"""
    try:
        from google.cloud import bigquery

        client = bigquery.Client(project=project_id)

        # Query campaign budgets
        query_budgets = f"""
        SELECT *
        FROM `{project_id}.{dataset_id}.campaign_budgets`
        ORDER BY fetch_timestamp DESC
        LIMIT 1000
        """

        # Query campaign performance
        query_campaign_perf = f"""
        SELECT *
        FROM `{project_id}.{dataset_id}.campaign_performance`
        WHERE report_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
        ORDER BY report_date DESC
        """

        # Query keyword performance
        query_keyword_perf = f"""
        SELECT *
        FROM `{project_id}.{dataset_id}.keyword_performance`
        WHERE report_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
        ORDER BY report_date DESC
        """

        campaign_budgets = client.query(query_budgets).to_dataframe()
        campaign_performance = client.query(query_campaign_perf).to_dataframe()
        keyword_performance = client.query(query_keyword_perf).to_dataframe()

        # Normalize report_date columns to pandas datetime64[ns]
        for df in (campaign_performance, keyword_performance):
            if "report_date" in df.columns:
                df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce")

        return {
            'campaign_budgets': campaign_budgets,
            'campaign_performance': campaign_performance,
            'keyword_performance': keyword_performance
        }

    except ImportError:
        st.error(
            "Error loading data from BigQuery: missing dependency.\n\n"
            "Make sure your Python environment has:\n\n"
            "    google-cloud-bigquery>=3.11.0\n"
            "    db-dtypes>=1.2.0\n\n"
            "Update requirements-dashboard.txt and reinstall."
        )
        return generate_sample_data()
    except Exception as e:
        st.error(f"Error loading data from BigQuery: {e}")
        return generate_sample_data()


def generate_sample_data() -> Dict[str, pd.DataFrame]:
    """Generate sample data for demonstration purposes"""

    # Sample campaign data
    campaigns = pd.DataFrame({
        'campaign_id': ['123', '456', '789', '101', '102'],
        'campaign_name': [
            'Brand - Exact Match',
            'Generic - Broad Match',
            'Product - Auto',
            'Competitor - Phrase',
            'Category - Broad'
        ],
        'state': ['enabled', 'enabled', 'enabled', 'paused', 'enabled'],
        'daily_budget': [50.0, 100.0, 75.0, 30.0, 80.0],
        'targeting_type': ['MANUAL', 'MANUAL', 'AUTO', 'MANUAL', 'MANUAL'],
    })

    # Generate 30 days of performance data
    dates = pd.date_range(end=datetime.now().date(), periods=30)
    campaign_perf_data = []

    for date_val in dates:
        for _, campaign in campaigns.iterrows():
            base_impressions = 1000 + (hash(campaign['campaign_id']) % 5000)
            base_clicks = base_impressions * (0.02 + (hash(campaign['campaign_id']) % 30) / 1000)
            base_cost = base_clicks * (0.5 + (hash(campaign['campaign_id']) % 20) / 10)
            base_sales = base_cost * (2.5 + (hash(campaign['campaign_id']) % 30) / 10)

            campaign_perf_data.append({
                'report_date': date_val,
                'campaignId': campaign['campaign_id'],
                'campaign_name': campaign['campaign_name'],
                'impressions': int(base_impressions * (0.8 + (hash(str(date_val)) % 40) / 100)),
                'clicks': int(base_clicks * (0.8 + (hash(str(date_val)) % 40) / 100)),
                'cost': round(base_cost * (0.8 + (hash(str(date_val)) % 40) / 100), 2),
                'attributedSales14d': round(base_sales * (0.8 + (hash(str(date_val)) % 40) / 100), 2),
                'attributedConversions14d': int(base_sales / 50),
            })

    campaign_performance = pd.DataFrame(campaign_perf_data)

    # Generate keyword performance data
    keywords_data = []
    keyword_names = [
        'organic fertilizer', 'soil amendment', 'garden soil',
        'compost tea', 'worm castings', 'humic acid',
        'kelp meal', 'fish emulsion', 'blood meal', 'bone meal'
    ]

    for date_val in dates[-7:]:  # Last 7 days
        for i, keyword in enumerate(keyword_names):
            campaign_id = campaigns.iloc[i % len(campaigns)]['campaign_id']
            base_impressions = 100 + (hash(keyword) % 500)
            base_clicks = base_impressions * (0.015 + (hash(keyword) % 20) / 1000)
            base_cost = base_clicks * (0.75 + (hash(keyword) % 15) / 10)
            base_sales = base_cost * (2 + (hash(keyword) % 40) / 10)

            keywords_data.append({
                'report_date': date_val,
                'campaignId': campaign_id,
                'adGroupId': f'ag-{i}',
                'keywordId': f'kw-{i}',
                'keywordText': keyword,
                'matchType': ['EXACT', 'PHRASE', 'BROAD'][hash(keyword) % 3],
                'impressions': int(base_impressions * (0.8 + (hash(str(date_val) + keyword) % 40) / 100)),
                'clicks': int(base_clicks * (0.8 + (hash(str(date_val) + keyword) % 40) / 100)),
                'cost': round(base_cost * (0.8 + (hash(str(date_val) + keyword) % 40) / 100), 2),
                'attributedSales14d': round(base_sales * (0.8 + (hash(str(date_val) + keyword) % 40) / 100), 2),
                'attributedConversions14d': int(base_sales / 50),
            })

    keyword_performance = pd.DataFrame(keywords_data)

    # Ensure report_date is datetime64[ns] for both
    campaign_performance['report_date'] = pd.to_datetime(campaign_performance['report_date'], errors='coerce')
    keyword_performance['report_date'] = pd.to_datetime(keyword_performance['report_date'], errors='coerce')

    return {
        'campaign_budgets': campaigns,
        'campaign_performance': campaign_performance,
        'keyword_performance': keyword_performance
    }


def calculate_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate derived metrics (CTR, CPC, ACOS, ROAS)"""
    df = df.copy()

    df['ctr'] = df.apply(
        lambda row: (row['clicks'] / row['impressions'] * 100) if row['impressions'] > 0 else 0,
        axis=1
    )
    df['cpc'] = df.apply(
        lambda row: (row['cost'] / row['clicks']) if row['clicks'] > 0 else 0,
        axis=1
    )
    df['acos'] = df.apply(
        lambda row: (row['cost'] / row['attributedSales14d'] * 100) if row['attributedSales14d'] > 0 else 0,
        axis=1
    )
    df['roas'] = df.apply(
        lambda row: (row['attributedSales14d'] / row['cost']) if row['cost'] > 0 else 0,
        axis=1
    )
    df['conversion_rate'] = df.apply(
        lambda row: (row['attributedConversions14d'] / row['clicks'] * 100) if row['clicks'] > 0 else 0,
        axis=1
    )

    return df


# ============================================================================
# VISUALIZATION FUNCTIONS
# ============================================================================

def create_kpi_metrics(df: pd.DataFrame):
    total_impressions = df['impressions'].sum()
    total_clicks = df['clicks'].sum()
    total_cost = df['cost'].sum()
    total_sales = df['attributedSales14d'].sum()
    total_conversions = df['attributedConversions14d'].sum()

    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    avg_cpc = (total_cost / total_clicks) if total_clicks > 0 else 0
    overall_acos = (total_cost / total_sales * 100) if total_sales > 0 else 0
    overall_roas = (total_sales / total_cost) if total_cost > 0 else 0

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total Spend", f"${total_cost:,.2f}")
        st.metric("Total Sales", f"${total_sales:,.2f}")

    with col2:
        st.metric("Impressions", f"{total_impressions:,}")
        st.metric("Clicks", f"{total_clicks:,}")

    with col3:
        st.metric("CTR", f"{avg_ctr:.2f}%")
        st.metric("CPC", f"${avg_cpc:.2f}")

    with col4:
        st.metric("ACOS", f"{overall_acos:.2f}%")
        acos_color = "🟢" if overall_acos < 30 else "🟡" if overall_acos < 50 else "🔴"
        st.caption(f"{acos_color} Target: 30%")

    with col5:
        st.metric("ROAS", f"{overall_roas:.2f}x")
        st.metric("Conversions", f"{total_conversions:,}")


def create_performance_trend_chart(df: pd.DataFrame):
    if df.empty:
        st.info("No performance data for selected range.")
        return

    daily_metrics = df.groupby('report_date').agg({
        'impressions': 'sum',
        'clicks': 'sum',
        'cost': 'sum',
        'attributedSales14d': 'sum',
    }).reset_index()

    daily_metrics = calculate_metrics(daily_metrics)

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Spend & Sales Over Time', 'ACOS Trend',
                       'Clicks & Impressions', 'ROAS Trend'),
        specs=[[{"secondary_y": False}, {"secondary_y": False}],
               [{"secondary_y": True}, {"secondary_y": False}]]
    )

    fig.add_trace(
        go.Scatter(x=daily_metrics['report_date'], y=daily_metrics['cost'],
                   name='Spend', line=dict(color='#ff6b6b')),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=daily_metrics['report_date'], y=daily_metrics['attributedSales14d'],
                   name='Sales', line=dict(color='#51cf66')),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(x=daily_metrics['report_date'], y=daily_metrics['acos'],
                   name='ACOS', line=dict(color='#748ffc')),
        row=1, col=2
    )
    fig.add_hline(y=30, line_dash="dash", line_color="orange",
                  annotation_text="Target ACOS", row=1, col=2)

    fig.add_trace(
        go.Scatter(x=daily_metrics['report_date'], y=daily_metrics['impressions'],
                   name='Impressions', line=dict(color='#4dabf7')),
        row=2, col=1, secondary_y=False
    )
    fig.add_trace(
        go.Scatter(x=daily_metrics['report_date'], y=daily_metrics['clicks'],
                   name='Clicks', line=dict(color='#ff9900')),
        row=2, col=1, secondary_y=True
    )

    fig.add_trace(
        go.Scatter(x=daily_metrics['report_date'], y=daily_metrics['roas'],
                   name='ROAS', line=dict(color='#20c997')),
        row=2, col=2
    )

    fig.update_layout(height=600, showlegend=True, title_text="Performance Trends")
    fig.update_xaxes(title_text="Date")
    fig.update_yaxes(title_text="Amount ($)", row=1, col=1)
    fig.update_yaxes(title_text="ACOS (%)", row=1, col=2)
    fig.update_yaxes(title_text="Impressions", row=2, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Clicks", row=2, col=1, secondary_y=True)
    fig.update_yaxes(title_text="ROAS", row=2, col=2)

    st.plotly_chart(fig, use_container_width=True)


def create_campaign_comparison(df: pd.DataFrame):
    if df.empty:
        st.info("No campaign data for selected range.")
        return

    campaign_summary = df.groupby('campaign_name').agg({
        'impressions': 'sum',
        'clicks': 'sum',
        'cost': 'sum',
        'attributedSales14d': 'sum',
        'attributedConversions14d': 'sum'
    }).reset_index()

    campaign_summary = calculate_metrics(campaign_summary)
    campaign_summary = campaign_summary.sort_values('cost', ascending=True)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=campaign_summary['campaign_name'],
        x=campaign_summary['cost'],
        name='Spend',
        orientation='h',
        marker=dict(color='#ff6b6b')
    ))

    fig.add_trace(go.Bar(
        y=campaign_summary['campaign_name'],
        x=campaign_summary['attributedSales14d'],
        name='Sales',
        orientation='h',
        marker=dict(color='#51cf66')
    ))

    fig.update_layout(
        title="Campaign Performance Comparison",
        xaxis_title="Amount ($)",
        yaxis_title="Campaign",
        barmode='group',
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Campaign Details")
    display_df = campaign_summary[[
        'campaign_name', 'impressions', 'clicks', 'cost',
        'attributedSales14d', 'ctr', 'cpc', 'acos', 'roas'
    ]].copy()

    display_df.columns = [
        'Campaign', 'Impressions', 'Clicks', 'Spend',
        'Sales', 'CTR (%)', 'CPC ($)', 'ACOS (%)', 'ROAS'
    ]

    display_df['Spend'] = display_df['Spend'].apply(lambda x: f"${x:,.2f}")
    display_df['Sales'] = display_df['Sales'].apply(lambda x: f"${x:,.2f}")
    display_df['CTR (%)'] = display_df['CTR (%)'].apply(lambda x: f"{x:.2f}%")
    display_df['CPC ($)'] = display_df['CPC ($)'].apply(lambda x: f"${x:.2f}")
    display_df['ACOS (%)'] = display_df['ACOS (%)'].apply(lambda x: f"{x:.2f}%")
    display_df['ROAS'] = display_df['ROAS'].apply(lambda x: f"{x:.2f}x")

    st.dataframe(display_df, use_container_width=True, hide_index=True)


def create_keyword_performance(df: pd.DataFrame):
    if df.empty:
        st.info("No keyword performance data available")
        return

    keyword_summary = df.groupby(['keywordText', 'matchType']).agg({
        'impressions': 'sum',
        'clicks': 'sum',
        'cost': 'sum',
        'attributedSales14d': 'sum',
        'attributedConversions14d': 'sum'
    }).reset_index()

    keyword_summary = calculate_metrics(keyword_summary)
    keyword_summary = keyword_summary.sort_values('cost', ascending=False).head(20)

    col1, col2 = st.columns(2)

    with col1:
        fig = px.bar(
            keyword_summary.head(10),
            x='cost',
            y='keywordText',
            color='matchType',
            orientation='h',
            title='Top 10 Keywords by Spend',
            labels={'cost': 'Spend ($)', 'keywordText': 'Keyword'},
            color_discrete_map={'EXACT': '#20c997', 'PHRASE': '#4dabf7', 'BROAD': '#ff9900'}
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        keyword_summary_filtered = keyword_summary[keyword_summary['acos'] < 200]
        fig = px.scatter(
            keyword_summary_filtered,
            x='cost',
            y='acos',
            size='attributedSales14d',
            color='matchType',
            hover_data=['keywordText'],
            title='Keyword ACOS vs Spend',
            labels={'cost': 'Spend ($)', 'acos': 'ACOS (%)'},
            color_discrete_map={'EXACT': '#20c997', 'PHRASE': '#4dabf7', 'BROAD': '#ff9900'}
        )
        fig.add_hline(y=30, line_dash="dash", line_color="red", annotation_text="Target ACOS")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top Keywords Details")
    display_df = keyword_summary[[
        'keywordText', 'matchType', 'impressions', 'clicks',
        'cost', 'attributedSales14d', 'ctr', 'cpc', 'acos', 'roas'
    ]].copy()

    display_df.columns = [
        'Keyword', 'Match Type', 'Impressions', 'Clicks',
        'Spend', 'Sales', 'CTR (%)', 'CPC ($)', 'ACOS (%)', 'ROAS'
    ]

    display_df['Spend'] = display_df['Spend'].apply(lambda x: f"${x:,.2f}")
    display_df['Sales'] = display_df['Sales'].apply(lambda x: f"${x:,.2f}")
    display_df['CTR (%)'] = display_df['CTR (%)'].apply(lambda x: f"{x:.2f}%")
    display_df['CPC ($)'] = display_df['CPC ($)'].apply(lambda x: f"${x:.2f}")
    display_df['ACOS (%)'] = display_df['ACOS (%)'].apply(lambda x: f"{x:.2f}%")
    display_df['ROAS'] = display_df['ROAS'].apply(lambda x: f"{x:.2f}x")

    st.dataframe(display_df, use_container_width=True, hide_index=True)


def create_budget_utilization(campaign_budgets: pd.DataFrame, campaign_performance: pd.DataFrame):
    if campaign_performance.empty:
        st.info("No performance data available for budget analysis.")
        return

    latest_budgets = campaign_budgets.copy()

    recent_date = campaign_performance['report_date'].max()
    week_ago = recent_date - timedelta(days=7)
    recent_performance = campaign_performance[
        campaign_performance['report_date'] > week_ago
    ].groupby('campaignId').agg({
        'cost': 'sum'
    }).reset_index()
    recent_performance['daily_avg_spend'] = recent_performance['cost'] / 7

    budget_analysis = latest_budgets.merge(
        recent_performance,
        left_on='campaign_id',
        right_on='campaignId',
        how='left'
    )
    budget_analysis['daily_avg_spend'] = budget_analysis['daily_avg_spend'].fillna(0)
    budget_analysis['utilization'] = (
        budget_analysis['daily_avg_spend'] / budget_analysis['daily_budget'] * 100
    )

    st.subheader("Budget Utilization (Last 7 Days)")

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=budget_analysis['campaign_name'],
        x=budget_analysis['daily_budget'],
        name='Daily Budget',
        orientation='h',
        marker=dict(color='lightblue')
    ))

    fig.add_trace(go.Bar(
        y=budget_analysis['campaign_name'],
        x=budget_analysis['daily_avg_spend'],
        name='Avg Daily Spend',
        orientation='h',
        marker=dict(color='#ff9900')
    ))

    fig.update_layout(
        barmode='overlay',
        xaxis_title="Amount ($)",
        yaxis_title="Campaign",
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Budget Recommendations")

    over_budget = budget_analysis[budget_analysis['utilization'] >= 90]
    under_budget = budget_analysis[budget_analysis['utilization'] < 50]

    col1, col2 = st.columns(2)

    with col1:
        if not over_budget.empty:
            st.warning("⚠️ Campaigns Near/Over Budget")
            for _, row in over_budget.iterrows():
                st.write(f"- **{row['campaign_name']}**: {row['utilization']:.1f}% utilized")
        else:
            st.success("✅ No campaigns over budget")

    with col2:
        if not under_budget.empty:
            st.info("💡 Campaigns Under-Utilizing Budget")
            for _, row in under_budget.iterrows():
                st.write(f"- **{row['campaign_name']}**: {row['utilization']:.1f}% utilized")
        else:
            st.success("✅ All campaigns utilizing budget well")


# ============================================================================
# MAIN DASHBOARD
# ============================================================================

def main():
    st.title("📊 Amazon PPC Performance Dashboard")
    st.markdown("Real-time insights into your Amazon advertising campaigns")

    st.sidebar.title("⚙️ Configuration")

    data_source = st.sidebar.radio(
        "Data Source",
        ["Sample Data (Demo)", "BigQuery"]
    )

    if data_source == "BigQuery":
        st.sidebar.subheader("BigQuery Settings")
        default_project = os.getenv("GCP_PROJECT_ID", "")
        project_id = st.sidebar.text_input("Project ID", value=default_project)
        dataset_id = st.sidebar.text_input("Dataset ID", value="amazon_ads_data")

        if project_id:
            with st.spinner("Loading data from BigQuery..."):
                data = load_data_from_bigquery(project_id, dataset_id)
        else:
            st.warning("Please enter BigQuery Project ID in the sidebar; using sample data instead.")
            data = generate_sample_data()
    else:
        data = generate_sample_data()

    campaign_budgets = data['campaign_budgets']
    campaign_performance = data['campaign_performance']
    keyword_performance = data['keyword_performance']

    for df in (campaign_performance, keyword_performance):
        if "report_date" in df.columns:
            df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce")

    campaign_performance = calculate_metrics(campaign_performance)
    keyword_performance = calculate_metrics(keyword_performance)

    st.sidebar.subheader("📅 Date Range")
    if 'report_date' in campaign_performance.columns and not campaign_performance.empty:
        min_ts = campaign_performance['report_date'].min()
        max_ts = campaign_performance['report_date'].max()

        if pd.isna(min_ts) or pd.isna(max_ts):
            today = date.today()
            min_date_val = today - timedelta(days=30)
            max_date_val = today
        else:
            min_date_val = min_ts.date()
            max_date_val = max_ts.date()

        default_start = max_date_val - timedelta(days=7)
        if default_start < min_date_val:
            default_start = min_date_val

        date_range = st.sidebar.date_input(
            "Select Date Range",
            value=(default_start, max_date_val),
            min_value=min_date_val,
            max_value=max_date_val
        )

        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date_input, end_date_input = date_range
            start_ts = pd.to_datetime(start_date_input)
            end_ts = pd.to_datetime(end_date_input)

            campaign_performance = campaign_performance[
                (campaign_performance['report_date'] >= start_ts) &
                (campaign_performance['report_date'] <= end_ts)
            ]
            keyword_performance = keyword_performance[
                (keyword_performance['report_date'] >= start_ts) &
                (keyword_performance['report_date'] <= end_ts)
            ]

    st.sidebar.markdown("---")
    st.sidebar.caption(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    st.header("📈 Key Performance Indicators")
    create_kpi_metrics(campaign_performance)

    st.markdown("---")

    st.header("📊 Performance Trends")
    create_performance_trend_chart(campaign_performance)

    st.markdown("---")

    st.header("🎯 Campaign Performance")
    create_campaign_comparison(campaign_performance)

    st.markdown("---")

    st.header("💰 Budget Management")
    create_budget_utilization(campaign_budgets, campaign_performance)

    st.markdown("---")

    st.header("🔑 Keyword Performance")
    create_keyword_performance(keyword_performance)

    st.markdown("---")
    st.caption("Amazon PPC Dashboard | Powered by Nature's Way Soil Optimizer | v1.0.1")


if __name__ == "__main__":
    main()
