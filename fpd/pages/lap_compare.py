# fpd/pages/lap_compare.py
from __future__ import annotations

import streamlit as st

from fpd.components.topbar_selectors import render_topbar
from fpd.components.compare_charts import render_compare_stack

from fpd.data.session_loader import load_session
from fpd.data.validators import validate_topbar, validate_driver_selection


def render() -> None:
    """
    Lap Compare page.

    Requirements:
      - Mode: Current Session or All Time
      - Charts stacked vertically (handled by render_compare_stack)

    Note:
      - This is the UI scaffold. Real telemetry overlays will be wired in later using
        fpd/analytics/compare.py
    """
    st.header("Lap Compare")

    mode_ui = st.radio("Mode", ["Current Session", "All Time"], horizontal=True)
    mode = "current" if mode_ui == "Current Session" else "all_time"

    if mode == "current":
        season, event_name, session_identifier = render_topbar()
        if not validate_topbar(season, event_name, session_identifier):
            st.stop()

        with st.spinner("Loading session data..."):
            session = load_session(season, event_name, session_identifier)

        if session is None:
            st.stop()

        # Driver selection (best-effort list from session.laps)
        driver_codes = []
        try:
            if session.laps is not None and len(session.laps) > 0:
                driver_codes = sorted(session.laps["Driver"].dropna().unique().tolist())
        except Exception:
            driver_codes = []

        st.subheader("Selectors")
        c1, c2 = st.columns([2, 1])

        with c1:
            selected_drivers = st.multiselect(
                "Drivers",
                options=driver_codes,
                default=driver_codes[:2] if len(driver_codes) >= 2 else driver_codes[:1],
                max_selections=4,
            )
        with c2:
            st.selectbox("Lap number", options=["Fastest (default)"], index=0, disabled=True)

        if not validate_driver_selection(selected_drivers):
            st.stop()

        st.divider()
        render_compare_stack(session=session, mode="current")

    else:
        st.info(
            "All Time mode scaffold:\n\n"
            "- Select Year + Drivers + fastest lap\n"
            "- Add another year with a '+' button\n\n"
            "We’ll implement this after current-session compare is fully working."
        )

        # Still show chart stack placeholders in all_time mode
        st.divider()
        render_compare_stack(session=None, mode="all_time")
