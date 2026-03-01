# fpd/pages/corner_sector_breakdown.py
from __future__ import annotations

import streamlit as st

from fpd.components.topbar_selectors import render_topbar
from fpd.components.sector_summary import render_sector_summary
from fpd.components.corner_table import render_corner_table

from fpd.data.session_loader import load_session
from fpd.data.validators import validate_topbar


def render() -> None:
    """
    Corner & Sector Breakdown page.

    Layout:
      - Top selector bar
      - Sector Summary (S1/S2/S3 deltas + winners)
      - Corner Table (entry/min/exit/brake/throttle/time per corner)
    """

    st.header("Corner & Sector Breakdown")

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
    # Sector Summary
    # -------------------------
    render_sector_summary(session)

    # -------------------------
    # Corner Table
    # -------------------------
    st.divider()
    render_corner_table(session)
