
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
EXPORT_DIR = PROJECT_ROOT / "data" / "exports"

st.set_page_config(
    page_title="SmartFleet Analytics",
    page_icon="🚚",
    layout="wide",
)


@st.cache_data
def load_data():
    with open(
        EXPORT_DIR / "analytics_summary.json",
        encoding="utf-8",
    ) as file:
        summary = json.load(file)

    deliveries = pd.read_csv(
        EXPORT_DIR / "delivery_performance.csv"
    )
    daily = pd.read_csv(
        EXPORT_DIR / "daily_performance.csv"
    )
    priority = pd.read_csv(
        EXPORT_DIR / "priority_performance.csv"
    )
    routes = pd.read_csv(
        EXPORT_DIR / "route_performance.csv"
    )

    deliveries["order_date"] = pd.to_datetime(
        deliveries["order_date"]
    )

    daily["date"] = pd.to_datetime(daily["date"])

    return summary, deliveries, daily, priority, routes


st.title("🚚 SmartFleet")
st.caption("Delivery Planning and Logistics Analytics")

try:
    summary, deliveries, daily, priority, routes = load_data()
except Exception as error:
    st.error(f"Unable to load analytics reports: {error}")
    st.info("Run python scripts\\generate_analytics.py first.")
    st.stop()


# Sidebar filters
st.sidebar.header("Dashboard Filters")

date_range = st.sidebar.date_input(
    "Order date range",
    value=(
        deliveries["order_date"].min().date(),
        deliveries["order_date"].max().date(),
    ),
)

priorities = sorted(deliveries["priority"].dropna().unique())

selected_priorities = st.sidebar.multiselect(
    "Priority",
    priorities,
    default=priorities,
)

statuses = sorted(
    deliveries["outcome_status"].dropna().unique()
)

selected_statuses = st.sidebar.multiselect(
    "Delivery outcome",
    statuses,
    default=statuses,
)

filtered = deliveries.copy()

if len(date_range) == 2:
    start_date, end_date = date_range
    filtered = filtered[
        filtered["order_date"].dt.date.between(
            start_date, end_date
        )
    ]

filtered = filtered[
    filtered["priority"].isin(selected_priorities)
    & filtered["outcome_status"].isin(selected_statuses)
]


# KPI metrics
total = len(filtered)

delivered = (
    filtered["outcome_status"] == "DELIVERED"
).sum()

failed = (
    filtered["outcome_status"] == "FAILED"
).sum()

unserved = (
    filtered["outcome_status"] == "UNSERVED"
).sum()

on_time = (
    (filtered["outcome_status"] == "DELIVERED")
    & (filtered["late_minutes"] == 0)
    & filtered["actual_arrival"].notna()
).sum()

success_rate = delivered / total * 100 if total else 0
on_time_rate = on_time / delivered * 100 if delivered else 0


st.subheader("Delivery Overview")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Total Deliveries", f"{total:,}")
c2.metric("Delivered", f"{delivered:,}")
c3.metric("Failed", f"{failed:,}")
c4.metric("Unserved", f"{unserved:,}")

c5, c6 = st.columns(2)

c5.metric("Delivery Success Rate", f"{success_rate:.2f}%")
c6.metric("On-Time Rate", f"{on_time_rate:.2f}%")

st.divider()


# Delivery outcome chart
st.subheader("Delivery Outcome Distribution")

outcome_data = pd.DataFrame({
    "Outcome": ["Delivered", "Failed", "Unserved"],
    "Count": [delivered, failed, unserved],
})

if total:
    fig = px.pie(
        outcome_data,
        names="Outcome",
        values="Count",
        hole=0.45,
    )
    st.plotly_chart(fig, width="stretch")
else:
    st.info("No deliveries match the selected filters.")


# Daily performance
st.subheader("Daily Delivery Performance")

if total:
    daily_filtered = (
        filtered.groupby("order_date")
        .agg(
            delivered=(
                "outcome_status",
                lambda x: (x == "DELIVERED").sum(),
            ),
            failed=(
                "outcome_status",
                lambda x: (x == "FAILED").sum(),
            ),
            unserved=(
                "outcome_status",
                lambda x: (x == "UNSERVED").sum(),
            ),
        )
        .reset_index()
        .sort_values("order_date")
    )

    daily_chart = daily_filtered.melt(
        id_vars="order_date",
        var_name="Outcome",
        value_name="Deliveries",
    )

    fig = px.line(
        daily_chart,
        x="order_date",
        y="Deliveries",
        color="Outcome",
        markers=True,
        title="Daily Delivery Trends",
    )

    st.plotly_chart(fig, width="stretch")


# Priority performance
st.subheader("Priority-wise Performance")

if total:
    priority_filtered = (
        filtered.groupby("priority")
        .agg(
            total_deliveries=("delivery_id", "count"),
            delivered=(
                "outcome_status",
                lambda x: (x == "DELIVERED").sum(),
            ),
            failed=(
                "outcome_status",
                lambda x: (x == "FAILED").sum(),
            ),
            unserved=(
                "outcome_status",
                lambda x: (x == "UNSERVED").sum(),
            ),
        )
        .reset_index()
    )

    priority_filtered["success_rate_percent"] = (
        priority_filtered["delivered"]
        / priority_filtered["total_deliveries"]
        * 100
    ).round(2)

    fig = px.bar(
        priority_filtered,
        x="priority",
        y="success_rate_percent",
        color="priority",
        text="success_rate_percent",
        title="Delivery Success Rate by Priority",
    )

    st.plotly_chart(fig, width="stretch")

    st.dataframe(
        priority_filtered,
        width="stretch",
        hide_index=True,
    )


# Route performance
st.subheader("Route Performance")

r1, r2, r3 = st.columns(3)

r1.metric("Total Routes", len(routes))

r2.metric(
    "Planned Distance",
    f"{routes['planned_distance_km'].sum():,.2f} km",
)

r3.metric(
    "Average Stops per Route",
    f"{routes['total_stops'].mean():.2f}" if len(routes) else "0",
)

st.dataframe(
    routes,
    width="stretch",
    hide_index=True,
)


# Delivery details
st.subheader("Delivery Details")

display_columns = [
    "delivery_id",
    "order_date",
    "priority",
    "outcome_status",
    "late_minutes",
    "on_time",
    "route_id",
]

st.dataframe(
    filtered[display_columns],
    width="stretch",
    hide_index=True,
)

st.download_button(
    "Download Filtered Delivery Report",
    data=filtered.to_csv(index=False).encode("utf-8"),
    file_name="smartfleet_delivery_report.csv",
    mime="text/csv",
)

st.download_button(
    "Download Analytics Summary",
    data=json.dumps(summary, indent=4).encode("utf-8"),
    file_name="analytics_summary.json",
    mime="application/json",
)

st.divider()

st.caption(
    f"SmartFleet Analytics | Generated: {summary['generated_at']}"
)
