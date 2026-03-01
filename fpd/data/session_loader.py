# fpd/data/session_loader.py
from __future__ import annotations

import fastf1
import streamlit as st

from fpd.ui.state import has_session_changed, set_loaded_session
from fpd.data.selectors_data import get_testing_number
from fpd.ui.state import StateKeys


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


def load_session(season: int, event_name: str, session_identifier: str | int, test_number: int | None = None):
    """
    Loads a session:
      - Normal events: fastf1.get_session(season, event_name, session_identifier)
      - Testing: fastf1.get_testing_session(season, test_number, session_number)
    """
    try:
        is_testing = "test" in str(event_name).lower()

        if is_testing:
            tn = test_number or st.session_state.get(StateKeys.TEST_NUMBER)
            sn = int(session_identifier)  # 1/2/3

            if not tn:
                st.error("Testing event selected but test_number is missing.")
                return None

            sess = fastf1.get_testing_session(season, int(tn), sn)
        else:
            sess = fastf1.get_session(season, event_name, session_identifier)

        sess.load()
        return sess

    except Exception as e:
        st.error(f"Failed to load session: {e}")
        return None
