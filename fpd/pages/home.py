# fpd/pages/home.py
from __future__ import annotations

import streamlit as st

from fpd.components.topbar_selectors import render_topbar
from fpd.components.track_map_panel import render_track_map_panel
from fpd.components.tables_fastest_laps import render_fastest_laps_table
from fpd.components.tables_race_results import render_race_results_table
from fpd.components.charts_leaderboards import render_leaderboards
from fpd.components.cards_summary import render_summary_cards

from fpd.data.session_loader import load_session
from fpd.data.validators import validate_topbar


def render() -> None:
    """
    Home / Dashboard page.

    Layout:
      - Top selector bar
      - Track map (left)
      - Fastest laps OR Race results (right)
      - Leaderboards
      - Summary cards
    """

    st.header("Home / Dashboard")

    # -------------------------
    # Top selectors
    # -------------------------
    season, event_name, session_identifier = render_topbar()

    if not validate_topbar(season, event_name, session_identifier):
        st.stop()

    # -------------------------
    # Load session
    # -------------------------
    with st.spinner("Loading session data..."):
        session = load_session(season, event_name, session_identifier)

    if session is None:
        st.stop()

    # -------------------------
    # Main layout (top half)
    # -------------------------
    left, right = st.columns([1.3, 1])

    with left:
        render_track_map_panel(session)

    with right:
        if str(session_identifier).upper() in ["R", "RACE"]:
            render_race_results_table(session)
        else:
            render_fastest_laps_table(session)

    # -------------------------
    # Leaderboards
    # -------------------------
    st.divider()

    is_race = str(session_identifier).upper() in ["R", "RACE"]
    render_leaderboards(session, is_race=is_race)

    # -------------------------
    # Summary Cards
    # -------------------------
    st.divider()
    render_summary_cards(session)
