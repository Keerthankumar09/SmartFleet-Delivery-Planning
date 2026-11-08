import streamlit as st
from src.database.db import get_connection, initialize_database

st.set_page_config(page_title="SmartFleet", page_icon="🚚", layout="wide")
initialize_database()

st.title("🚚 SmartFleet")
st.caption("Delivery planning and logistics analytics")

st.info(
    "Phase 1 scaffold is ready. The database schema and integrity checks are in place. "
    "Synthetic data generation and route planning will be added in the next phases."
)

conn = get_connection()
tables = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
).fetchall()
st.metric("Database tables created", len(tables))
st.write("**Available tables**")
st.dataframe([{"table": row["name"]} for row in tables], use_container_width=True)
conn.close()
