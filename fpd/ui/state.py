# fpd/ui/state.py
from __future__ import annotations

import streamlit as st


class StateKeys:
    # Session selection
    SEASON = "season"
    EVENT_NAME = "event_name"
    SESSION_NAME = "session_name"
    TEST_NUMBER = "fpd_test_number"

    # Cached session identity (so we can reload only when needed)
    LOADED_SESSION_KEY = "loaded_session_key"

    # Lap compare selections (extend later)
    COMPARE_MODE = "compare_mode"
    COMPARE_DRIVERS = "compare_drivers"
    COMPARE_LAPS = "compare_laps"
    COMPARE_YEARS = "compare_years"


DEFAULTS: dict[str, object] = {
    StateKeys.SEASON: 2026,
    StateKeys.EVENT_NAME: "Bahrain",
    StateKeys.SESSION_NAME: "R",
    StateKeys.LOADED_SESSION_KEY: None,
    StateKeys.COMPARE_MODE: "Current Session",
    StateKeys.COMPARE_DRIVERS: [],
    StateKeys.COMPARE_LAPS: [],
    StateKeys.COMPARE_YEARS: [],
}


def init_state() -> None:
    """
    Initialize session_state keys once.
    """
    st.session_state.setdefault(StateKeys.SEASON, None)
    st.session_state.setdefault(StateKeys.EVENT_NAME, None)
    st.session_state.setdefault(StateKeys.SESSION_NAME, None)
    st.session_state.setdefault(StateKeys.TEST_NUMBER, None)


def make_session_key(season: int, event_name: str, session_name: str) -> str:
    """
    A stable identifier for the currently loaded session.
    """
    return f"{season}::{event_name.strip()}::{session_name.strip()}"


def has_session_changed(season: int, event_name: str, session_name: str) -> bool:
    """
    Returns True if the selection differs from what's loaded.
    """
    current = make_session_key(season, event_name, session_name)
    loaded = st.session_state.get(StateKeys.LOADED_SESSION_KEY)
    return loaded != current


def set_loaded_session(season: int, event_name: str, session_name: str) -> None:
    st.session_state[StateKeys.LOADED_SESSION_KEY] = make_session_key(
        season, event_name, session_name
    )
