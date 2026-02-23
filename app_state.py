# app_state.py
"""
Shared app state for the Formula Performance Dashboard.

What this file does:
- Renders ONE shared "Top Bar" (Season / Event / Session + Reload)
- Loads the selected FastF1 session ONCE
- Stores a reusable "bundle" in st.session_state so all pages can reuse it:
    bundle = st.session_state["bundle"]

Bundle contents:
- session: FastF1 session object (loaded with telemetry + weather)
- laps: pandas DataFrame of laps
- drivers: list of driver codes available
- is_race: True if session is Race ("R")
- year, event, session_name: selected identifiers
"""

from __future__ import annotations

import streamlit as st
from engine.data import list_events_for_year, list_sessions_for_event, load_session, get_laps_df, get_drivers


def _default_year_index() -> int:
    years = list(range(2018, 2027))
    # Prefer 2025 if present, otherwise last
    return years.index(2025) if 2025 in years else len(years) - 1


def top_bar_inputs():
    """
    Renders a top bar with Season / Event / Session selectors + Reload button.

    Returns:
        (year, event_name, session_name, reload_now)
    """
    c1, c2, c3, c4 = st.columns([1, 2.4, 1.2, 1])

    with c1:
        years = list(range(2018, 2027))
        year = st.selectbox("Season", years, index=_default_year_index(), key="top_year")

    with c2:
        # Preload events for the year
        events = list_events_for_year(year)
        if not events:
            st.error("No events found for this season. Try another year.")
            event_name = None
        else:
            # Prefer something stable as a default
            default_event = events[0]
            event_name = st.selectbox("Event", events, index=events.index(default_event), key="top_event")

    with c3:
        session_name = None
        if event_name:
            sessions = list_sessions_for_event(year, event_name)
            if not sessions:
                st.error("No sessions found for this event.")
            else:
                # Prefer Qualifying if exists, else Race, else first available
                preferred = "Q" if "Q" in sessions else ("R" if "R" in sessions else sessions[0])
                session_name = st.selectbox("Session", sessions, index=sessions.index(preferred), key="top_session")

    with c4:
        reload_now = st.button("Reload", use_container_width=True)

    return year, event_name, session_name, reload_now


def get_session_bundle(year: int, event_name: str, session_name: str, reload_now: bool = False):
    """
    Loads and stores a session bundle in st.session_state.

    Rules:
    - If selection changes (bundle_key differs) -> reload
    - If reload_now is True -> reload
    - Otherwise reuse cached bundle

    Returns:
        bundle dict
    """
    if not (year and event_name and session_name):
        st.stop()

    key = f"{year}|{event_name}|{session_name}"

    # Build or reuse bundle
    if reload_now or st.session_state.get("bundle_key") != key or "bundle" not in st.session_state:
        with st.spinner("Loading session data (FastF1)..."):
            session = load_session(year, event_name, session_name)
            laps = get_laps_df(session)
            drivers = get_drivers(session)

        # Basic detection: Race session is "R"
        is_race = (session_name == "R")

        st.session_state["bundle_key"] = key
        st.session_state["bundle"] = {
            "session": session,
            "laps": laps,
            "drivers": drivers,
            "is_race": is_race,
            "year": year,
            "event": event_name,
            "session_name": session_name,
        }

    return st.session_state["bundle"]
