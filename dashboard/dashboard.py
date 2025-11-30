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
        st.met
