# fpd/data/session_loader.py
from __future__ import annotations

import fastf1
import streamlit as st

from fpd.ui.state import has_session_changed, set_loaded_session
from fpd.data.selectors_data import get_testing_number


@st.cache_resource(show_spinner=False)
def _load_race_session_cached(season: int, event_name: str, session_identifier: str):
    session = fastf1.get_session(season, event_name, session_identifier)
    session.load()
    return session


@st.cache_resource(show_spinner=False)
def _load_testing_session_cached(season: int, test_number: int, session_identifier: str):
    session = fastf1.get_testing_session(season, test_number, session_identifier)
    session.load()
    return session


def load_session(season: int, event_name: str, session_identifier: str):
    """
    Loads either:
      - race weekend session via fastf1.get_session(year, event, session)
      - testing session via fastf1.get_testing_session(year, test_no, session)

    Uses caching + state tracking.
    """
    if not season or not event_name or not session_identifier:
        return None

    event_name = event_name.strip()
    session_identifier = session_identifier.strip()

    # try race session first (works for normal weekends and sometimes for testing too)
    try:
        session = _load_race_session_cached(season, event_name, session_identifier)

        if has_session_changed(season, event_name, session_identifier):
            set_loaded_session(season, event_name, session_identifier)

        return session
    except Exception:
        pass

    # fallback: if it's testing, use get_testing_session
    test_no = get_testing_number(season, event_name)
    if test_no is None:
        st.error("Could not load session (not found as race or testing event).")
        return None

    try:
        session = _load_testing_session_cached(season, test_no, session_identifier)

        if has_session_changed(season, event_name, session_identifier):
            set_loaded_session(season, event_name, session_identifier)

        return session
    except Exception as e:
        st.error(f"Failed to load testing session: {e}")
        return None
