import streamlit as st
from engine.data import init_fastf1_cache, list_events_for_year, list_sessions_for_event
import os

st.set_page_config(page_title="F1 Telemetry Dashboard", layout="wide")

cache_path = os.path.join(os.getcwd(), ".fastf1_cache")
init_fastf1_cache(cache_path)
st.title("F1 Telemetry Dashboard")


with st.sidebar:
    st.header("Session Inputs")

    year = st.selectbox("Season", options=list(range(2018, 2027)), index=7)  # default 2025-ish
    events = list_events_for_year(year)
    event_name = st.selectbox("Event", options=events)

    sessions = list_sessions_for_event(year, event_name)
    session_name = st.selectbox("Session", options=sessions)

    st.divider()
    st.caption("Use the left sidebar on each page for driver/lap choices.")

st.info(
    "Use the pages (left sidebar / multipage) to open Home, Lap Compare, Corner/Sector, and Long Runs."
)

