# fpd/pages/long_runs.py
from __future__ import annotations

import streamlit as st

from fpd.components.topbar_selectors import render_topbar
from fpd.components.longrun_panels import render_longrun_tools, render_longrun_outputs

from fpd.data.session_loader import load_session
from fpd.data.validators import validate_topbar


def render() -> None:
    """
    Long Runs & Tire Degradation page.

    Layout:
      - Top selector bar
      - Tools panel (stint detection / lap range)
      - Outputs panel (deg rankings, consistency, drop-off)
    """

    st.header("Long Runs & Tire Degradation")

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
    # Tools
    # -------------------------
    settings = render_longrun_tools(session)

    # -------------------------
    # Outputs
    # -------------------------
    st.divider()
    render_longrun_outputs(session, settings=settings)
