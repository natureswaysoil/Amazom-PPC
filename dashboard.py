"""
Amazon PPC Streamlit Dashboard
==============================

A Streamlit dashboard for viewing campaign performance data from BigQuery.
Includes proper datetime handling for pandas 2.x compatibility.
"""

import os
import logging
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account

# Import centralized credential loading
from gcp_credentials import load_credentials

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = os.getenv('GCP_PROJECT_ID') or os.getenv('GOOGLE_CLOUD_PROJECT', 'amazon-ppc-474902')
DATASET_ID = os.getenv('BIGQUERY_DATASET', 'amazon_ppc')


def get_bigquery_client():
    """
    Initialize BigQuery client with credentials.
    
    Returns:
        bigquery.Client or None: The initialized client or None if failed.
    """
    try:
        credentials = load_credentials()
        if credentials:
            logger.info("Using service account credentials for BigQuery")
            client = bigquery.Client(project=PROJECT_ID, credentials=credentials)
        else:
            logger.info("Using Application Default Credentials for BigQuery")
            client = bigquery.Client(project=PROJECT_ID)
        logger.info(f"BigQuery client initialized successfully for project {PROJECT_ID}")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize BigQuery client: {e}")
        return None


def load_campaign_performance(client: bigquery.Client) -> pd.DataFrame:
    """
    Load campaign performance data from BigQuery.
    
    Args:
        client: BigQuery client instance.
        
    Returns:
        DataFrame with campaign performance data.
    """
    query = f"""
    SELECT
        campaign_id,
        campaign_name,
        report_date,
        impressions,
        clicks,
        spend,
        sales,
        acos,
        conversions
    FROM `{PROJECT_ID}.{DATASET_ID}.campaign_details`
    ORDER BY report_date DESC
    """
    
    campaign_performance = client.query(query).to_dataframe()
    
    # ensure report_date is a pandas datetime64 dtype
    campaign_performance['report_date'] = pd.to_datetime(campaign_performance['report_date'])
    
    return campaign_performance


def main():
    """Main Streamlit dashboard application."""
    st.set_page_config(
        page_title="Amazon PPC Dashboard",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("📊 Amazon PPC Campaign Performance Dashboard")
    
    # Initialize BigQuery client
    client = get_bigquery_client()
    if not client:
        st.error("Failed to connect to BigQuery. Please check your credentials.")
        return
    
    # Load campaign performance data
    try:
        campaign_performance = load_campaign_performance(client)
    except Exception as e:
        st.error(f"Failed to load campaign data: {e}")
        return
    
    if campaign_performance.empty:
        st.warning("No campaign performance data available.")
        return
    
    # Sidebar filters
    st.sidebar.header("Filters")
    
    # Date range filter
    min_date = campaign_performance['report_date'].min().date()
    max_date = campaign_performance['report_date'].max().date()
    
    # Default to last 30 days or available range
    default_start = max(min_date, max_date - timedelta(days=30))
    
    start_date = st.sidebar.date_input(
        "Start Date",
        value=default_start,
        min_value=min_date,
        max_value=max_date
    )
    
    end_date = st.sidebar.date_input(
        "End Date",
        value=max_date,
        min_value=min_date,
        max_value=max_date
    )
    
    # If start_date/end_date come from Streamlit they are datetime.date objects;
    # convert to pandas Timestamp for valid comparison with datetime64[ns] columns
    if start_date is not None:
        start_date = pd.to_datetime(start_date)
    if end_date is not None:
        end_date = pd.to_datetime(end_date)
    
    # Filter data by date range
    if start_date is not None and end_date is not None:
        mask = (
            (campaign_performance['report_date'] >= start_date) &
            (campaign_performance['report_date'] <= end_date)
        )
        campaign_performance = campaign_performance[mask]
    
    # Campaign filter
    campaigns = ['All'] + sorted(campaign_performance['campaign_name'].unique().tolist())
    selected_campaign = st.sidebar.selectbox("Campaign", campaigns)
    
    if selected_campaign != 'All':
        campaign_performance = campaign_performance[
            campaign_performance['campaign_name'] == selected_campaign
        ]
    
    # Display metrics
    st.header("Key Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_spend = campaign_performance['spend'].sum()
        st.metric("Total Spend", f"${total_spend:,.2f}")
    
    with col2:
        total_sales = campaign_performance['sales'].sum()
        st.metric("Total Sales", f"${total_sales:,.2f}")
    
    with col3:
        total_clicks = campaign_performance['clicks'].sum()
        st.metric("Total Clicks", f"{total_clicks:,}")
    
    with col4:
        avg_acos = campaign_performance['acos'].mean() if not campaign_performance.empty else 0
        st.metric("Avg ACOS", f"{avg_acos:.2f}%")
    
    # Display data table
    st.header("Campaign Performance Data")
    st.dataframe(
        campaign_performance,
        use_container_width=True,
        hide_index=True
    )
    
    # Performance chart
    if not campaign_performance.empty:
        st.header("Performance Over Time")
        
        daily_performance = campaign_performance.groupby('report_date').agg({
            'spend': 'sum',
            'sales': 'sum',
            'clicks': 'sum',
            'impressions': 'sum'
        }).reset_index()
        
        st.line_chart(
            daily_performance.set_index('report_date')[['spend', 'sales']],
            use_container_width=True
        )


if __name__ == "__main__":
    main()
