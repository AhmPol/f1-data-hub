# fpd/components/corner_table.py
from __future__ import annotations

import streamlit as st
import pandas as pd


def render_corner_table(session) -> None:
    """
    UI-only scaffold for the Corner Table.

    Later, you’ll replace the stub DataFrame with real output from:
      fpd/analytics/corner_sector.py
    """
    st.subheader("Corner Table")
    st.caption(
        "Per-corner metrics: entry/min/exit speed • braking start proxy • throttle-on point • time delta • "
        "plus grouped low/medium/high-speed corner averages & rankings."
    )

    # Filters (UI stubs)
    f1, f2, f3 = st.columns([1, 1, 1])
    with f1:
        group = st.selectbox(
            "Corner group",
            ["All", "Low-speed", "Medium-speed", "High-speed"],
            index=0,
        )
    with f2:
        show_rankings = st.checkbox("Show group rankings", value=True)
    with f3:
        show_raw = st.checkbox("Show raw corner rows", value=True)

    st.divider()

    if show_rankings:
        st.markdown("### Group Averages & Rankings (Stub)")
        group_df = pd.DataFrame(
            [
                {"Group": "Low-speed", "Avg Entry": 155, "Avg Min": 82, "Avg Exit": 143, "Rank": "—"},
                {"Group": "Medium-speed", "Avg Entry": 210, "Avg Min": 145, "Avg Exit": 205, "Rank": "—"},
                {"Group": "High-speed", "Avg Entry": 265, "Avg Min": 210, "Avg Exit": 260, "Rank": "—"},
            ]
        )
        st.dataframe(group_df, use_container_width=True, hide_index=True)

    if show_raw:
        st.markdown("### Per-Corner Metrics (Stub)")
        corners_df = pd.DataFrame(
            [
                {
                    "Corner": 1,
                    "Type": "Low-speed",
                    "EntrySpeed": 160,
                    "MinSpeed": 78,
                    "ExitSpeed": 145,
                    "BrakeStart(m)": 120,
                    "ThrottleOn(m)": 165,
                    "CornerDelta(s)": 0.00,
                },
                {
                    "Corner": 2,
                    "Type": "Medium-speed",
                    "EntrySpeed": 215,
                    "MinSpeed": 150,
                    "ExitSpeed": 210,
                    "BrakeStart(m)": 80,
                    "ThrottleOn(m)": 130,
                    "CornerDelta(s)": 0.00,
                },
            ]
        )

        if group != "All":
            corners_df = corners_df[corners_df["Type"] == group]

        st.dataframe(corners_df, use_container_width=True, hide_index=True)

    with st.expander("Planned calculation notes", expanded=False):
        st.markdown(
            """
- **Entry / Min / Exit speed**: derived from speed trace in the corner segment  
- **Braking start point**: distance-to-brake onset proxy (first strong decel / brake application)  
- **Throttle-on point**: distance where throttle rises above threshold after apex  
- **Corner delta**: time difference between drivers within the same corner segment  
- **Groups**: classify corners by min speed (thresholds you define per track)
"""
        )
