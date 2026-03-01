# fpd/components/topbar_selectors.py
from __future__ import annotations

import streamlit as st

from fpd.core.config import CONFIG
from fpd.data.selectors_data import (
    get_available_seasons,
    get_events_for_season,
    get_sessions_for_event,
    EventItem,
    SessionItem,
)
from fpd.ui.state import StateKeys
from fpd.data.validators import validate_topbar


def render_topbar() -> tuple[int | None, str | None, str | None]:
    """
    Top bar selectors:
      - Season
      - Event (includes Preseason Testing events)
      - Session (shows dd/mm in label)

    Returns:
      (season, event_name, session_identifier)

    Note:
      - event_name is the real EventName used by FastF1
      - session_identifier is what you pass to load_session (e.g., "Q", "R", "Practice 1")
    """
    st.markdown("### Session Selector")

    seasons = get_available_seasons(end=CONFIG.default_season)

    # Persisted defaults
    season_default = st.session_state.get(StateKeys.SEASON) or CONFIG.default_season
    event_default = st.session_state.get(StateKeys.EVENT_NAME) or CONFIG.default_event_name
    session_default = st.session_state.get(StateKeys.SESSION_NAME) or CONFIG.default_session

    c1, c2, c3 = st.columns([1, 2.4, 1.6])

    with c1:
        season = st.selectbox(
            "Season",
            options=seasons,
            index=_safe_index(seasons, season_default),
        )

    # Build event options with dd/mm and testing tag
    events: list[EventItem] = get_events_for_season(season)
    event_labels = [_event_label(e) for e in events]
    event_by_label = {lbl: e for lbl, e in zip(event_labels, events)}

    with c2:
        selected_event_label = st.selectbox(
            "Event",
            options=event_labels if event_labels else ["(no events found)"],
            index=_safe_index(event_labels, _event_label_from_name(events, event_default)),
            disabled=(len(event_labels) == 0),
        )

    selected_event = event_by_label.get(selected_event_label)
    event_name = selected_event.name if selected_event else None

    # Store test_number in session_state if this is a testing event
    if selected_event and selected_event.type == "testing":
        st.session_state[StateKeys.TEST_NUMBER] = getattr(selected_event, "test_number", None)
    else:
        st.session_state[StateKeys.TEST_NUMBER] = None

    # Sessions depend on event
    sessions: list[SessionItem] = get_sessions_for_event(season, event_name) if event_name else []
    session_labels = [s.label for s in sessions]
    session_by_label = {s.label: s for s in sessions}

    with c3:
        selected_session_label = st.selectbox(
            "Session",
            options=session_labels if session_labels else ["(no sessions found)"],
            index=_safe_index(session_labels, _session_label_from_identifier(sessions, session_default)),
            disabled=(len(session_labels) == 0),
        )

    selected_session = session_by_label.get(selected_session_label)
    session_identifier = selected_session.identifier if selected_session else None

    # Save to session_state
    st.session_state[StateKeys.SEASON] = season
    st.session_state[StateKeys.EVENT_NAME] = event_name
    st.session_state[StateKeys.SESSION_NAME] = session_identifier

    # Small inline validation warning if missing
    validate_topbar(season, event_name, session_identifier)

    return season, event_name, session_identifier


def _event_label(e: EventItem) -> str:
    """
    UI label: "Bahrain (28/02)" or "Pre-Season Testing (22/02) [TEST]"
    """
    tag = " [TEST]" if e.type == "testing" else ""
    return f"{e.name} ({e.date_ddmm}){tag}"


def _event_label_from_name(events: list[EventItem], name: str) -> str:
    """
    Find the label that matches a given event name (for default selection).
    """
    name = (name or "").strip()
    for e in events:
        if e.name.strip() == name:
            return _event_label(e)
    # fallback to first event label if present
    return _event_label(events[0]) if events else ""


def _session_label_from_identifier(sessions, identifier) -> str:
    """
    Given a list[SessionItem] and an identifier (str or int),
    return the matching label for the selectbox default.
    """
    identifier_norm = str(identifier).strip()

    for s in sessions:
        if str(s.identifier).strip() == identifier_norm:
            return s.label

    return sessions[0].label if sessions else ""


def _safe_index(options: list, value) -> int:
    """
    Returns index of value in options, else 0.
    """
    try:
        return options.index(value)
    except Exception:
        return 0
