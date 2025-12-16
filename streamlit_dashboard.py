cd /workspaces/Amazom-PPC/dashboard

cat > streamlit_dashboard.py << 'EOF'
#!/usr/bin/env python3
"""
Amazon PPC Dashboard (Streamlit)
Uses BigQuery if configured, otherwise falls back to sample data.
"""

import os
from datetime import datetime, timedelta, date
from typing import Dict

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# -----------------------------------------------------------------------------
# PAGE CONFIG
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Amazon PPC Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main { padding: 0rem 1rem; }
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 5px; }
    h1 { color: #ff9900; padding-bottom: 10px; border-bottom: 2px solid #ff9900; }
    h2 { color: #232f3e; margin-top: 20px; }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# DATA HELPERS
# -----------------------------------------------------------------------------
def _normalize_report_date(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure report_date is a plain Python date (fixes datetime vs date comparisons)."""
    if "report_date" in df.columns and not pd.api.types.is_object_dtype(df["report_date"]):
        df = df.copy()
        df["report_date"] = pd.to_datetime(df["report_date"]).dt.date
    return df


@st.cache_data(ttl=300)
def load_data_from_bigquery(project_id: str, dataset_id: str) -> Dict[str, pd.DataFrame]:
    """Load data from BigQuery; on error, raise so we can fall back."""
    from google.cloud import bigquery

    client = bigquery.Client(project=project_id)

    query_budgets = f"""
        SELECT *
        FROM `{project_id}.{dataset_id}.campaign_budgets`
        ORDER BY fetch_timestamp DESC
        LIMIT 1000
    """

    query_campaign_perf = f"""
        SELECT *
        FROM `{project_id}.{dataset_id}.campaign_performance`
        ORDER BY report_date DESC
        LIMIT 50000
    """

    query_keyword_perf = f"""
        SELECT *
        FROM `{project_id}.{dataset_id}.keyword_performance`
        ORDER BY report_date DESC
        LIMIT 50000
    """

    campaign_budgets = client.query(query_budgets).to_dataframe()
    campaign_performance = client.query(query_campaign_perf).to_dataframe()
    keyword_performance = client.query(query_keyword_perf).to_dataframe()

    # Normalize dates so Streamlit date filters work
    campaign_performance = _normalize_report_date(campaign_performance)
    keyword_performance = _normalize_report_date(keyword_performance)

    return {
        "campaign_budgets": campaign_budgets,
        "campaign_performance": campaign_performance,
        "keyword_performance": keyword_performance,
    }


def generate_sample_data() -> Dict[str, pd.DataFrame]:
    """Sample/demo data so the dashboard runs without BigQuery."""
    campaigns = pd.DataFrame(
        {
            "campaign_id": ["123", "456", "789", "101", "102"],
            "campaign_name": [
                "Brand - Exact Match",
                "Generic - Broad Match",
                "Product - Auto",
                "Competitor - Phrase",
                "Category - Broad",
            ],
            "state": ["enabled", "enabled", "enabled", "paused", "enabled"],
            "daily_budget": [50.0, 100.0, 75.0, 30.0, 80.0],
            "targeting_type": ["MANUAL", "MANUAL", "AUTO", "MANUAL", "MANUAL"],
        }
    )

    dates = pd.date_range(end=datetime.now().date(), periods=30)
    campaign_perf_data = []

    for d in dates:
        for _, campaign in campaigns.iterrows():
            base_impressions = 1000 + (hash(campaign["campaign_id"]) % 5000)
            base_clicks = base_impressions * (0.02 + (hash(campaign["campaign_id"]) % 30) / 1000)
            base_cost = base_clicks * (0.5 + (hash(campaign["campaign_id"]) % 20) / 10)
            base_sales = base_cost * (2.5 + (hash(campaign["campaign_id"]) % 30) / 10)

            campaign_perf_data.append(
                {
                    "report_date": d.date(),
                    "campaignId": campaign["campaign_id"],
                    "campaign_name": campaign["campaign_name"],
                    "impressions": int(base_impressions),
                    "clicks": int(base_clicks),
                    "cost": round(base_cost, 2),
                    "attributedSales14d": round(base_sales, 2),
                    "attributedConversions14d": int(base_sales / 50),
                }
            )

    campaign_performance = pd.DataFrame(campaign_perf_data)

    keyword_names = [
        "organic fertilizer",
        "soil amendment",
        "garden soil",
        "compost tea",
        "worm castings",
        "humic acid",
        "kelp meal",
        "fish emulsion",
        "blood meal",
        "bone meal",
    ]
    keywords_data = []

    for d in dates[-7:]:
        for i, keyword in enumerate(keyword_names):
            campaign_id = campaigns.iloc[i % len(campaigns)]["campaign_id"]
            base_impressions = 100 + (hash(keyword) % 500)
            base_clicks = base_impressions * (0.015 + (hash(keyword) % 20) / 1000)
            base_cost = base_clicks * (0.75 + (hash(keyword) % 15) / 10)
            base_sales = base_cost * (2 + (hash(keyword) % 40) / 10)

            keywords_data.append(
                {
                    "report_date": d.date(),
                    "campaignId": campaign_id,
                    "adGroupId": f"ag-{i}",
                    "keywordId": f"kw-{i}",
                    "keywordText": keyword,
                    "matchType": ["EXACT", "PHRASE", "BROAD"][hash(keyword) % 3],
                    "impressions": int(base_impressions),
                    "clicks": int(base_clicks),
                    "cost": round(base_cost, 2),
                    "attributedSales14d": round(base_sales, 2),
                    "attributedConversions14d": int(base_sales / 50),
                }
            )

    keyword_performance = pd.DataFrame(keywords_data)

    campaign_performance = _normalize_report_date(campaign_performance)
    keyword_performance = _normalize_report_date(keyword_performance)

    return {
        "campaign_budgets": campaigns,
        "campaign_performance": campaign_performance,
        "keyword_performance": keyword_performance,
    }


def calculate_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add CTR, CPC, ACOS, ROAS, conversion_rate columns."""
    df = df.copy()

    df["ctr"] = df.apply(
        lambda r: (r["clicks"] / r["impressions"] * 100) if r["impressions"] > 0 else 0, axis=1
    )
    df["cpc"] = df.apply(lambda r: (r["cost"] / r["clicks"]) if r["clicks"] > 0 else 0, axis=1)
    df["acos"] = df.apply(
        lambda r: (r["cost"] / r["attributedSales14d"] * 100) if r["attributedSales14d"] > 0 else 0,
        axis=1,
    )
    df["roas"] = df.apply(
        lambda r: (r["attributedSales14d"] / r["cost"]) if r["cost"] > 0 else 0, axis=1
    )
    df["conversion_rate"] = df.apply(
        lambda r: (r["attributedConversions14d"] / r["clicks"] * 100) if r["clicks"] > 0 else 0,
        axis=1,
    )

    return df


# -----------------------------------------------------------------------------
# VISUALS
# -----------------------------------------------------------------------------
def create_kpi_metrics(df: pd.DataFrame):
    if df.empty:
        st.info("No performance data in selected range.")
        return

    total_impressions = df["impressions"].sum()
    total_clicks = df["clicks"].sum()
    total_cost = df["cost"].sum()
    total_sales = df["attributedSales14d"].sum()
    total_conversions = df["attributedConversions14d"].sum()

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

    daily = (
        df.groupby("report_date")
        .agg(
            {
                "impressions": "sum",
                "clicks": "sum",
                "cost": "sum",
                "attributedSales14d": "sum",
                "attributedConversions14d": "sum",
            }
        )
        .reset_index()
    )
    daily = calculate_metrics(daily)

    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=("Spend & Sales Over Time", "ACOS Trend", "Clicks & Impressions", "ROAS Trend"),
        specs=[[{"secondary_y": False}, {"secondary_y": False}],
               [{"secondary_y": True}, {"secondary_y": False}]],
    )

    fig.add_trace(
        go.Scatter(x=daily["report_date"], y=daily["cost"], name="Spend"),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=daily["report_date"], y=daily["attributedSales14d"], name="Sales"),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(x=daily["report_date"], y=daily["acos"], name="ACOS"),
        row=1,
        col=2,
    )
    fig.add_hline(y=30, line_dash="dash", line_color="orange", annotation_text="Target ACOS", row=1, col=2)

    fig.add_trace(
        go.Scatter(x=daily["report_date"], y=daily["impressions"], name="Impressions"),
        row=2,
        col=1,
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=daily["report_date"], y=daily["clicks"], name="Clicks"),
        row=2,
        col=1,
        secondary_y=True,
    )

    fig.add_trace(
        go.Scatter(x=daily["report_date"], y=daily["roas"], name="ROAS"),
        row=2,
        col=2,
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

    summary = (
        df.groupby("campaign_name")
        .agg(
            {
                "impressions": "sum",
                "clicks": "sum",
                "cost": "sum",
                "attributedSales14d": "sum",
                "attributedConversions14d": "sum",
            }
        )
        .reset_index()
    )

    summary = calculate_metrics(summary)
    summary = summary.sort_values("cost", ascending=True)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=summary["campaign_name"],
            x=summary["cost"],
            name="Spend",
            orientation="h",
        )
    )
    fig.add_trace(
        go.Bar(
            y=summary["campaign_name"],
            x=summary["attributedSales14d"],
            name="Sales",
            orientation="h",
        )
    )

    fig.update_layout(
        title="Campaign Performance Comparison",
        xaxis_title="Amount ($)",
        yaxis_title="Campaign",
        barmode="group",
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Campaign Details")
    display_df = summary[
        [
            "campaign_name",
            "impressions",
            "clicks",
            "cost",
            "attributedSales14d",
            "ctr",
            "cpc",
            "acos",
            "roas",
        ]
    ].copy()

    display_df.columns = [
        "Campaign",
        "Impressions",
        "Clicks",
        "Spend",
        "Sales",
        "CTR (%)",
        "CPC ($)",
        "ACOS (%)",
        "ROAS",
    ]

    display_df["Spend"] = display_df["Spend"].apply(lambda x: f"${x:,.2f}")
    display_df["Sales"] = display_df["Sales"].apply(lambda x: f"${x:,.2f}")
    display_df["CTR (%)"] = display_df["CTR (%)"].apply(lambda x: f"{x:.2f}%")
    display_df["CPC ($)"] = display_df["CPC ($)"].apply(lambda x: f"${x:.2f}")
    display_df["ACOS (%)"] = display_df["ACOS (%)"].apply(lambda x: f"{x:.2f}%")
    display_df["ROAS"] = display_df["ROAS"].apply(lambda x: f"{x:.2f}x")

    st.dataframe(display_df, use_container_width=True, hide_index=True)


def create_keyword_performance(df: pd.DataFrame):
    if df.empty:
        st.info("No keyword performance data available.")
        return

    summary = (
        df.groupby(["keywordText", "matchType"])
        .agg(
            {
                "impressions": "sum",
                "clicks": "sum",
                "cost": "sum",
                "attributedSales14d": "sum",
                "attributedConversions14d": "sum",
            }
        )
        .reset_index()
    )

    summary = calculate_metrics(summary)
    summary = summary.sort_values("cost", ascending=False).head(50)

    col1, col2 = st.columns(2)

    with col1:
        fig = px.bar(
            summary.head(10),
            x="cost",
            y="keywordText",
            color="matchType",
            orientation="h",
            title="Top 10 Keywords by Spend",
            labels={"cost": "Spend ($)", "keywordText": "Keyword"},
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        filtered = summary[summary["acos"] < 200]
        fig = px.scatter(
            filtered,
            x="cost",
            y="acos",
            size="attributedSales14d",
            color="matchType",
            hover_data=["keywordText"],
            title="Keyword ACOS vs Spend",
            labels={"cost": "Spend ($)", "acos": "ACOS (%)"},
        )
        fig.add_hline(y=30, line_dash="dash", line_color="red", annotation_text="Target ACOS")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top Keywords Details")
    display_df = summary[
        [
            "keywordText",
            "matchType",
            "impressions",
            "clicks",
            "cost",
            "attributedSales14d",
            "ctr",
            "cpc",
            "acos",
            "roas",
        ]
    ].copy()

    display_df.columns = [
        "Keyword",
        "Match Type",
        "Impressions",
        "Clicks",
        "Spend",
        "Sales",
        "CTR (%)",
        "CPC ($)",
        "ACOS (%)",
        "ROAS",
    ]

    display_df["Spend"] = display_df["Spend"].apply(lambda x: f"${x:,.2f}")
    display_df["Sales"] = display_df["Sales"].apply(lambda x: f"${x:,.2f}")
    display_df["CTR (%)"] = display_df["CTR (%)"].apply(lambda x: f"{x:.2f}%")
    display_df["CPC ($)"] = display_df["CPC ($)"].apply(lambda x: f"${x:.2f}")
    display_df["ACOS (%)"] = display_df["ACOS (%)"].apply(lambda x: f"{x:.2f}%")
    display_df["ROAS"] = display_df["ROAS"].apply(lambda x: f"{x:.2f}x")

    st.dataframe(display_df, use_container_width=True, hide_index=True)


def create_budget_utilization(campaign_budgets: pd.DataFrame, campaign_performance: pd.DataFrame):
    if campaign_performance.empty or campaign_budgets.empty:
        st.info("No performance/budget data available for budget analysis.")
        return

    latest_budgets = campaign_budgets.copy()

    recent_date = max(campaign_performance["report_date"])
    week_ago = recent_date - timedelta(days=7)

    recent_perf = (
        campaign_performance[campaign_performance["report_date"] > week_ago]
        .groupby("campaignId")
        .agg({"cost": "sum"})
        .reset_index()
    )
    recent_perf["daily_avg_spend"] = recent_perf["cost"] / 7

    budget_analysis = latest_budgets.merge(
        recent_perf,
        left_on="campaign_id",
        right_on="campaignId",
        how="left",
    )

    budget_analysis["daily_avg_spend"] = budget_analysis["daily_avg_spend"].fillna(0)
    budget_analysis["utilization"] = (
        budget_analysis["daily_avg_spend"] / budget_analysis["daily_budget"] * 100
    )

    st.subheader("Budget Utilization (Last 7 Days)")

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=budget_analysis["campaign_name"],
            x=budget_analysis["daily_budget"],
            name="Daily Budget",
            orientation="h",
        )
    )
    fig.add_trace(
        go.Bar(
            y=budget_analysis["campaign_name"],
            x=budget_analysis["daily_avg_spend"],
            name="Avg Daily Spend",
            orientation="h",
        )
    )
    fig.update_layout(
        barmode="overlay",
        xaxis_title="Amount ($)",
        yaxis_title="Campaign",
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Budget Recommendations")

    over_budget = budget_analysis[budget_analysis["utilization"] >= 90]
    under_budget = budget_analysis[budget_analysis["utilization"] < 50]

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


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main():
    st.title("📊 Amazon PPC Performance Dashboard")
    st.markdown("Real-time insights into your Amazon advertising campaigns")

    st.sidebar.title("⚙️ Configuration")

    data_source = st.sidebar.radio("Data Source", ["Sample Data (Demo)", "BigQuery"])

    if data_source == "BigQuery":
        st.sidebar.subheader("BigQuery Settings")
        project_id = st.sidebar.text_input("Project ID", value="")
        dataset_id = st.sidebar.text_input("Dataset ID", value="amazon_ppc")

        if project_id:
            try:
                with st.spinner("Loading data from BigQuery..."):
                    data = load_data_from_bigquery(project_id, dataset_id)
            except Exception as e:
                st.error(
                    f"Error loading data from BigQuery: {e}\n\n"
                    "Falling back to sample/demo data."
                )
                data = generate_sample_data()
        else:
            st.info("Enter a Project ID to load from BigQuery. Using sample data instead.")
            data = generate_sample_data()
    else:
        data = generate_sample_data()

    campaign_budgets = data["campaign_budgets"]
    campaign_performance = data["campaign_performance"]
    keyword_performance = data["keyword_performance"]

    campaign_performance = calculate_metrics(campaign_performance)
    keyword_performance = calculate_metrics(keyword_performance)

    st.sidebar.subheader("📅 Date Range")
    if "report_date" in campaign_performance.columns and not campaign_performance.empty:
        min_date = min(campaign_performance["report_date"])
        max_date = max(campaign_performance["report_date"])

        default_start = max_date - timedelta(days=7)
        if isinstance(default_start, datetime):
            default_start = default_start.date()

        date_range = st.sidebar.date_input(
            "Select Date Range",
            value=(default_start, max_date),
            min_value=min_date,
            max_value=max_date,
        )

        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
            campaign_performance = campaign_performance[
                (campaign_performance["report_date"] >= start_date)
                & (campaign_performance["report_date"] <= end_date)
            ]
            keyword_performance = keyword_performance[
                (keyword_performance["report_date"] >= start_date)
                & (keyword_performance["report_date"] <= end_date)
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

    st.caption("Amazon PPC Dashboard | Powered by Nature's Way Soil Optimizer | v1.0.0")


if __name__ == "__main__":
    main()
EOF
