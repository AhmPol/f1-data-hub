import streamlit as st
import pandas as pd
from engine.data import load_session, get_drivers, get_laps_df
from engine.prep import fastest_laps_by_driver
from engine.prep import get_lap_telemetry_distance, resample_to_distance
from engine.performance import session_summary_indices, normalize_indices_across_drivers

st.title("Home")

# Pull shared inputs from sidebar (Streamlit multipage keeps sidebar from app.py)
# We read them from st.session_state if you want, but easiest: re-use app sidebar via st.sidebar is fine.
with st.sidebar:
    st.subheader("Home Options")

# We need year/event/session from the main sidebar created in app.py
# Streamlit multipage: those widgets exist in app.py, but values aren't automatically stored.
# So we re-create the same keys here to make sure we can read them:
year = st.sidebar.selectbox("Season", options=list(range(2018, 2027)), index=7, key="home_year")
event_name = st.sidebar.text_input("Event (exact name)", value="Bahrain Grand Prix", key="home_event")
session_name = st.sidebar.selectbox("Session", options=["FP1","FP2","FP3","Q","S","SQ","R"], index=3, key="home_session")

session = load_session(year, event_name, session_name)
laps = get_laps_df(session)

drivers = get_drivers(session)
selected = st.multiselect("Drivers", options=drivers, default=drivers[:6])

fast = fastest_laps_by_driver(laps, selected)

st.subheader("Fastest laps (selected drivers)")
show_cols = ["Driver", "Team", "LapNumber", "LapTime", "Sector1Time", "Sector2Time", "Sector3Time", "Compound", "TyreLife"]
show_cols = [c for c in show_cols if c in fast.columns]
st.dataframe(fast[show_cols], use_container_width=True)

st.subheader("Session Summary Cards (simple indices)")

raw = []
for drv in selected:
    lap_row = fast[fast["Driver"] == drv]
    if lap_row.empty:
        continue
    lap = lap_row.iloc[0]
    tel = get_lap_telemetry_distance(lap)
    telr = resample_to_distance(tel, step_m=2.0)
    ind = session_summary_indices(telr)
    raw.append({"Driver": drv, **ind})

scores = normalize_indices_across_drivers(raw)

if scores.empty:
    st.warning("No indices computed (try different drivers/session).")
else:
    st.dataframe(scores, use_container_width=True)