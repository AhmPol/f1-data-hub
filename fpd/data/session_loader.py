# fpd/data/session_loader.py
from __future__ import annotations

import fastf1
import streamlit as st

from fpd.ui.state import StateKeys


def load_session(season: int, event_name: str, session_identifier, test_number: int | None = None):
    """
    Loads:
      - Race weekends: fastf1.get_session(season, event_name, session_identifier)
      - Testing:       fastf1.get_testing_session(season, test_number, session_number)

    session_identifier:
      - race: str like "FP1", "Q", "R", etc.
      - testing: int 1/2/3 (or string convertible)
    """
    try:
        is_testing = _is_testing_event_name(event_name)

        if is_testing:
            # Prefer explicit argument, else read from state
            tn = test_number
            if tn is None:
                tn = st.session_state.get(getattr(StateKeys, "TEST_NUMBER", "fpd_test_number"))

            if tn is None:
                st.error("Testing event selected but test_number is missing.")
                return None

            sn = _to_testing_session_number(session_identifier)  # 1/2/3
            sess = fastf1.get_testing_session(int(season), int(tn), int(sn))
        else:
            sess = fastf1.get_session(int(season), str(event_name), session_identifier)

        sess.load()
        return sess

    except Exception as e:
        st.error(f"Failed to load session: {e}")
        return None


def _is_testing_event_name(event_name: str) -> bool:
    s = str(event_name).lower()
    return ("test" in s) or ("testing" in s) or ("pre-season" in s) or ("preseason" in s)


def _to_testing_session_number(x) -> int:
    """
    Accept 2, "2", "Practice 2", "Session 2" -> 2
    """
    s = str(x).strip().lower()
    if s.isdigit():
        n = int(s)
        if n in (1, 2, 3):
            return n
    for n in (1, 2, 3):
        if f"practice {n}" in s or f"session {n}" in s:
            return n
    raise ValueError(f"Invalid testing session identifier: {x}")
