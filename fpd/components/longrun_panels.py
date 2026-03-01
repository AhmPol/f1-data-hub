# fpd/components/longrun_panels.py
from __future__ import annotations

import streamlit as st
import pandas as pd


def render_longrun_tools(session) -> dict:
    """
    UI controls for Long Runs & Tire Degradation.

    Returns a small dict of user selections so the page can pass it into analytics later.
    """
    st.subheader("Tools")
    st.caption("Auto-detect stints (or manual lap range), then compare lap time trends.")

    c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1])

    with c1:
        mode = st.radio("Stint mode", ["Auto-detect stints", "Manual lap range"], horizontal=False)

    with c2:
        min_laps = st.number_input("Min laps per stint", min_value=3, max_value=30, value=6, step=1)

    with c3:
        smooth = st.checkbox("Smooth lap time curve", value=True, disabled=True)

    with c4:
        include_inlaps = st.checkbox("Include in/out laps", value=False, disabled=True)

    st.divider()

    if mode == "Manual lap range":
        a, b, c = st.columns([1, 1, 2])
        with a:
            lap_start = st.number_input("Lap start", min_value=1, value=1, step=1)
        with b:
            lap_end = st.number_input("Lap end", min_value=1, value=10, step=1)
        with c:
            st.caption("Later: you’ll pick drivers and each driver can have their own range.")
    else:
        lap_start, lap_end = None, None

    return {
        "mode": mode,
        "min_laps": int(min_laps),
        "lap_start": int(lap_start) if lap_start is not None else None,
        "lap_end": int(lap_end) if lap_end is not None else None,
    }


def render_longrun_outputs(session, settings: dict | None = None) -> None:
    """
    Output panels for long runs.

    This file stays UI-only.
    Real computations go into fpd/analytics/long_runs.py and return DataFrames.
    """
    st.subheader("Outputs")
    st.caption("Lap time vs lap number • degradation slope • consistency • rankings • pace drop-off")

    # Placeholders for the plots (you will replace with Plotly charts later)
    st.info("Stub: Plot lap time vs lap number (per driver) here.")
    st.info("Stub: Plot degradation slope comparisons here.")

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Best degradation (Stub)")
        deg_df = pd.DataFrame(
            [
                {"Rank": 1, "Driver": "VER", "Slope (s/lap)": 0.04},
                {"Rank": 2, "Driver": "HAM", "Slope (s/lap)": 0.06},
                {"Rank": 3, "Driver": "LEC", "Slope (s/lap)": 0.07},
            ]
        )
        st.dataframe(deg_df, use_container_width=True, hide_index=True)

    with c2:
        st.markdown("### Best consistency (Stub)")
        cons_df = pd.DataFrame(
            [
                {"Rank": 1, "Driver": "HAM", "Std Dev (s)": 0.18},
                {"Rank": 2, "Driver": "VER", "Std Dev (s)": 0.22},
                {"Rank": 3, "Driver": "LEC", "Std Dev (s)": 0.25},
            ]
        )
        st.dataframe(cons_df, use_container_width=True, hide_index=True)

    st.divider()

    st.markdown("### Stint-to-stint pace drop-off (Stub)")
    drop_df = pd.DataFrame(
        [
            {"Driver": "VER", "Stint 1 Avg": 91.2, "Stint 2 Avg": 92.0, "Drop-off (s)": 0.8},
            {"Driver": "HAM", "Stint 1 Avg": 91.6, "Stint 2 Avg": 92.6, "Drop-off (s)": 1.0},
        ]
    )
    st.dataframe(drop_df, use_container_width=True, hide_index=True)

    with st.expander("Planned calculation notes", expanded=False):
        st.markdown(
            """
- **Auto-detect stints**: group consecutive laps with the same compound (and no long pit gaps)
- **Degradation slope**: linear regression of lap time vs lap number within a stint
- **Consistency**: standard deviation of lap times within stint (optionally excluding in/out laps)
- **Pace drop-off**: difference between average lap times of consecutive stints
"""
        )
