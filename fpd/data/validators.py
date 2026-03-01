# fpd/data/validators.py
from __future__ import annotations

import streamlit as st
from typing import Sequence


def validate_season(season: int | None) -> bool:
    if season is None:
        st.warning("Please select a season.")
        return False
    return True


def validate_event(event_name: str | None) -> bool:
    if not event_name or not event_name.strip():
        st.warning("Please select an event.")
        return False
    return True


def validate_session(session_identifier: str | int | None) -> bool:
    """
    Accepts session identifiers as str (FP1/Q/R) or int (testing 1/2/3).
    """
    if session_identifier is None:
        st.warning("Please select a session.")
        return False

    # Convert to string safely
    s = str(session_identifier).strip()
    if not s:
        st.warning("Please select a session.")
        return False

    return True

def validate_topbar(
    season: int | None,
    event_name: str | None,
    session_identifier: str | None,
) -> bool:
    """
    Validates all topbar selections together.
    """
    return (
        validate_season(season)
        and validate_event(event_name)
        and validate_session(session_identifier)
    )


def validate_driver_selection(drivers: Sequence[str] | None) -> bool:
    if not drivers:
        st.warning("Please select at least one driver.")
        return False
    return True


def validate_lap_selection(laps: Sequence[int] | None) -> bool:
    if not laps:
        st.warning("Please select at least one lap.")
        return False
    return True
