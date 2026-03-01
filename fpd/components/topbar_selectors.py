# fpd/components/topbar_selectors.py
from __future__ import annotations

import streamlit as st

from fpd.core.config import CONFIG
from fpd.data.selectors_data import (
    get_available_seasons,
    get_events_for_season,
    get_sessions_for_event_key,
    EventItem,
    SessionItem,
)
from fpd.ui.state import StateKeys
from fpd.data.validators import validate_topbar


def render_topbar() -> tuple[int | None, str | None, str | int | None]:
    """
    Top bar selectors:
      - Season
      - Event (includes testing events)
      - Session (dd/mm in label)

    Returns:
      (season, event_name, session_identifier)

    Notes:
      - event_name is the FastF1 EventName (not unique across testing, but still needed)
      - session_identifier is:
          * race weekend: "FP1"/"Q"/"R"/etc (string)
          * testing: 1/2/3 (int)
      - We also store:
          * StateKeys.EVENT_KEY (unique schedule row key)
          * StateKeys.TEST_NUMBER (1..N) for testing
    """
    st.markdown("### Session Selector")

    seasons = get_available_seasons(end=CONFIG.default_season)

    # Persisted defaults
    season_default = st.session_state.get(StateKeys.SEASON) or CONFIG.default_season
    event_key_default = st.session_state.get(getattr(StateKeys, "EVENT_KEY", "fpd_event_key"))
    session_default = st.session_state.get(StateKeys.SESSION_NAME) or CONFIG.default_session

    c1, c2, c3 = st.columns([1, 2.4, 1.6])

    # -------------------------
    # Season
    # -------------------------
    with c1:
        season = st.selectbox(
            "Season",
            options=seasons,
            index=_safe_index(seasons, season_default),
        )

    # -------------------------
    # Event (use unique key)
    # -------------------------
    events: list[EventItem] = get_events_for_season(season)
    event_labels = [_event_label(e) for e in events]
    event_by_label = {lbl: e for lbl, e in zip(event_labels, events)}

    # Default event selection:
    # Prefer stored EVENT_KEY, else fall back to CONFIG.default_event_name by name match.
    default_event_label = _event_label_from_key_or_name(
        events=events,
        key=event_key_default,
        name=CONFIG.default_event_name,
    )

    with c2:
        selected_event_label = st.selectbox(
            "Event",
            options=event_labels if event_labels else ["(no events found)"],
            index=_safe_index(event_labels, default_event_label),
            disabled=(len(event_labels) == 0),
        )

    selected_event = event_by_label.get(selected_event_label)
    event_name = selected_event.name if selected_event else None
    event_key = selected_event.key if selected_event else None

    # Store event key (unique)
    if hasattr(StateKeys, "EVENT_KEY"):
        st.session_state[StateKeys.EVENT_KEY] = event_key
    else:
        st.session_state["fpd_event_key"] = event_key  # fallback if you didn't add EVENT_KEY yet

    # Store test_number (1..N for testing)
    if selected_event and selected_event.type == "testing":
        if hasattr(StateKeys, "TEST_NUMBER"):
            st.session_state[StateKeys.TEST_NUMBER] = getattr(selected_event, "test_number", None)
        else:
            st.session_state["fpd_test_number"] = getattr(selected_event, "test_number", None)
    else:
        if hasattr(StateKeys, "TEST_NUMBER"):
            st.session_state[StateKeys.TEST_NUMBER] = None
        else:
            st.session_state["fpd_test_number"] = None

    # -------------------------
    # Sessions (by event_key!)
    # -------------------------
    sessions: list[SessionItem] = []
    if season is not None and event_key is not None:
        sessions = get_sessions_for_event_key(season, int(event_key))

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

    # Save to session_state (so pages can use it)
    st.session_state[StateKeys.SEASON] = season
    st.session_state[StateKeys.EVENT_NAME] = event_name
    st.session_state[StateKeys.SESSION_NAME] = session_identifier

    # Inline validation warning
    validate_topbar(season, event_name, session_identifier)

    return season, event_name, session_identifier


def _event_label(e: EventItem) -> str:
    """
    UI label example:
      - "Bahrain (28/02)"
      - "Pre-Season Testing (13/02) [TEST #1]"
      - "Pre-Season Testing (20/02) [TEST #2]"
    """
    if e.type == "testing":
        tn = e.test_number if e.test_number is not None else "?"
        return f"{e.name} ({e.date_ddmm}) [TEST #{tn}]"
    return f"{e.name} ({e.date_ddmm})"


def _event_label_from_key_or_name(events: list[EventItem], key, name: str) -> str:
    """
    Pick default event label:
      1) If key matches an event.key, use that
      2) Else if name matches event.name, use first match
      3) Else use first event
    """
    # 1) key match
    if key is not None:
        try:
            k = int(key)
            for e in events:
                if int(e.key) == k:
                    return _event_label(e)
        except Exception:
            pass

    # 2) name match
    n = (name or "").strip()
    if n:
        for e in events:
            if e.name.strip() == n:
                return _event_label(e)

    # 3) fallback
    return _event_label(events[0]) if events else ""


def _session_label_from_identifier(sessions: list[SessionItem], identifier) -> str:
    """
    identifier may be str (FP1/Q/R) or int (testing 1/2/3).
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
