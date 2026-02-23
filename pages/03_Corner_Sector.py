import streamlit as st
from engine.data import load_session, get_drivers, get_laps_df
from engine.prep import fastest_laps_by_driver, get_lap_telemetry_distance, resample_to_distance
from engine.corners import detect_corners_from_speed, compute_corner_table, sector_summary

st.title("Corner & Sector Breakdown")

year = st.sidebar.selectbox("Season", options=list(range(2018, 2027)), index=7, key="cs_year")
event_name = st.sidebar.text_input("Event (exact name)", value="Bahrain Grand Prix", key="cs_event")
session_name = st.sidebar.selectbox("Session", options=["FP1","FP2","FP3","Q","S","SQ","R"], index=3, key="cs_session")

session = load_session(year, event_name, session_name)
laps = get_laps_df(session)

drivers = get_drivers(session)
selected = st.multiselect("Drivers", options=drivers, default=drivers[:2])

st.subheader("Sector Summary (fastest lap per driver)")
sec = sector_summary(laps, selected)
st.dataframe(sec, use_container_width=True)

st.divider()
st.subheader("Corner Table (auto-detected from speed minima)")

fast = fastest_laps_by_driver(laps, selected)

driver_for_corners = st.selectbox("Use driver for corner detection", options=selected, index=0)
lap_row = fast[fast["Driver"] == driver_for_corners]
if lap_row.empty:
    st.warning("No fastest lap found for that driver.")
    st.stop()

lap = lap_row.iloc[0]
tel = get_lap_telemetry_distance(lap)
telr = resample_to_distance(tel, step_m=2.0)

with st.expander("Corner detection settings", expanded=False):
    min_sep = st.slider("Min separation (m)", 100, 600, 250, 10)
    prominence = st.slider("Min prominence (kph drop)", 10, 60, 20, 1)
    window = st.slider("Window half-size (m)", 60, 250, 120, 10)

corners = detect_corners_from_speed(
    telr,
    min_separation_m=float(min_sep),
    min_prominence_kph=float(prominence),
    window_m=float(window),
)

corner_df = compute_corner_table(telr, corners)

if corner_df.empty:
    st.warning("No corners detected. Try reducing prominence or separation.")
else:
    st.dataframe(corner_df, use_container_width=True)

    st.subheader("Corner-type averages")
    avg = corner_df.groupby("Type")[["EntrySpeed","MinSpeed","ExitSpeed","SegTime_s"]].mean(numeric_only=True).reset_index()
    st.dataframe(avg, use_container_width=True)