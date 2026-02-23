# app_state.py
import streamlit as st
from engine.data import list_events_for_year, list_sessions_for_event, load_session, get_laps_df, get_drivers

def top_bar_inputs():
    """One shared selector for the entire app."""
    c1, c2, c3, c4 = st.columns([1, 2, 1, 1])

    with c1:
        year = st.selectbox("Season", list(range(2018, 2027)), index=7, key="year")

    with c2:
        events = list_events_for_year(year)
        event = st.selectbox("Event", events, key="event")

    with c3:
        sessions = list_sessions_for_event(year, event)
        session_name = st.selectbox("Session", sessions, key="session")

    with c4:
        reload_now = st.button("Reload session", use_container_width=True)

    return year, event, session_name, reload_now

def get_session_bundle(year, event, session_name, reload_now=False):
    """
    Loads once, stores in session_state.
    Bundle contains: session, laps_df, drivers, is_race
    """
    key = f"{year}|{event}|{session_name}"

    if reload_now or st.session_state.get("bundle_key") != key:
        session = load_session(year, event, session_name)
        laps = get_laps_df(session)
        drivers = get_drivers(session)

        # race detection (simple + reliable)
        is_race = session_name == "R"

        st.session_state["bundle_key"] = key
        st.session_state["bundle"] = {
            "session": session,
            "laps": laps,
            "drivers": drivers,
            "is_race": is_race,
            "year": year,
            "event": event,
            "session_name": session_name,
        }

    return st.session_state["bundle"]
