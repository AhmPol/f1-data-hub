# engine/data.py
import os
import fastf1
import streamlit as st

def init_fastf1_cache(path: str = ".fastf1_cache"):
    """
    FastF1 requires the cache directory to exist.
    On Streamlit Cloud, we must create it inside the app working directory.
    """
    os.makedirs(path, exist_ok=True)
    fastf1.Cache.enable_cache(path)

@st.cache_data(show_spinner=False)
def get_event_schedule(year: int):
    return fastf1.get_event_schedule(year)

@st.cache_data(show_spinner=False)
def list_events_for_year(year: int):
    sched = get_event_schedule(year)
    return sched["EventName"].dropna().tolist()

@st.cache_data(show_spinner=False)
def list_sessions_for_event(year: int, event_name: str):
    ev = fastf1.get_event(year, event_name)
    # This is better than my earlier one: it queries the event itself
    # and returns sessions that exist for that event.
    sessions = []
    for s in ["FP1", "FP2", "FP3", "Q", "SQ", "S", "R"]:
        try:
            _ = ev.get_session(s)
            sessions.append(s)
        except Exception:
            pass
    return sessions if sessions else ["R"]

@st.cache_data(show_spinner=True)
def load_session(year: int, event_name: str, session_name: str):
    session = fastf1.get_session(year, event_name, session_name)
    session.load(telemetry=True, weather=True, messages=False)
    return session

def get_drivers(session):
    return sorted(session.drivers)

def get_laps_df(session):
    return session.laps.copy()
