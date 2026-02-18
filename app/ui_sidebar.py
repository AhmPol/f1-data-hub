import streamlit as st
import fastf1
import pandas as pd
from .utils import detect_testing

def sidebar_controls():
    st.sidebar.header("Control Center")

    years = list(range(2018, 2027))
    year = st.sidebar.selectbox("Year", years, index=len(years) - 1)

    if st.sidebar.button("Load Event List"):
        schedule = fastf1.get_event_schedule(year)
        schedule = schedule[["RoundNumber", "EventName", "EventDate", "EventFormat"]].copy()

        def _date_str(d):
            try:
                return pd.to_datetime(d).date().isoformat()
            except Exception:
                return str(d)

        schedule["EventDateStr"] = schedule["EventDate"].apply(_date_str)
        schedule["DisplayName"] = (
            schedule["EventName"].astype(str)
            + " — "
            + schedule["EventDateStr"].astype(str)
            + " (" + schedule["EventFormat"].astype(str) + ")"
        )

        schedule["RoundSort"] = pd.to_numeric(schedule["RoundNumber"], errors="coerce")
        schedule = schedule.sort_values(["EventDate", "RoundSort"], na_position="last").reset_index(drop=True)
        st.session_state["races"] = schedule

    if "races" not in st.session_state:
        st.info("Load the event list from the sidebar to start.")
        st.stop()

    schedule = st.session_state["races"]
    gp_label = st.sidebar.selectbox("Grand Prix / Event", schedule["DisplayName"].tolist())
    selected_event = schedule.loc[schedule["DisplayName"] == gp_label].iloc[0]
    is_testing = detect_testing(selected_event)

    if is_testing:
        testing_session_label = st.sidebar.selectbox("Testing Session", ["Session 1", "Session 2", "Session 3"])
        testing_session_number = int(testing_session_label.split()[-1])
        session_type = None
    else:
        session_type = st.sidebar.selectbox("Session", ["FP1", "FP2", "FP3", "Q", "R"])
        testing_session_number = None

    st.sidebar.divider()
    st.sidebar.subheader("Compare")
    compare_mode = st.sidebar.toggle("Enable Compare Tab (2 drivers)", value=False)

    return year, schedule, gp_label, selected_event, is_testing, session_type, testing_session_number, compare_mode
