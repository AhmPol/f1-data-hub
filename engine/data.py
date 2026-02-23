import fastf1
import pandas as pd
import streamlit as st

def init_fastf1_cache(path: str):
    fastf1.Cache.enable_cache(path)

@st.cache_data(show_spinner=False)
def list_events_for_year(year: int):
    sched = fastf1.get_event_schedule(year)
    # Some years include testing; filter only races
    if "EventName" in sched.columns:
        return sched["EventName"].dropna().tolist()
    return []

@st.cache_data(show_spinner=False)
def list_sessions_for_event(year: int, event_name: str):
    ev = fastf1.get_event(year, event_name)
    # Common set; FastF1 can vary by era
    possible = ["FP1", "FP2", "FP3", "SQ", "S", "Q", "R"]
    available = []
    for s in possible:
        try:
            _ = ev.get_session(s)
            available.append(s)
        except Exception:
            pass
    # Also include Sprint Qualifying naming for some years if needed:
    # but above usually covers.
    return available if available else ["R"]

@st.cache_data(show_spinner=True)
def load_session(year: int, event_name: str, session_name: str):
    """Loads session and returns FastF1 session object."""
    session = fastf1.get_session(year, event_name, session_name)
    session.load(telemetry=True, weather=True, messages=False)
    return session

def get_drivers(session):
    """Return list of driver codes available (e.g., VER, HAM)."""
    try:
        return sorted(session.drivers)
    except Exception:
        return []

def get_laps_df(session):
    """Return laps dataframe (cached via session load)."""
    laps = session.laps
    return laps.copy()

def pick_team_color(session, driver_code: str):
    """Best-effort team color; safe fallback."""
    try:
        drv = session.get_driver(driver_code)
        return getattr(drv, "TeamColor", None)
    except Exception:
        return None