# fpd/components/sector_summary.py
from __future__ import annotations

import streamlit as st
import pandas as pd


def render_sector_summary(session) -> None:
    """
    UI-only scaffold for Sector Summary.

    Later, replace stub tables with real outputs from:
      fpd/analytics/corner_sector.py
    """
    st.subheader("Sector Summary")
    st.caption("S1 / S2 / S3 time deltas • who wins each sector and by how much")

    # Basic UI controls (stubs)
    c1, c2 = st.columns([1, 2])
    with c1:
        basis = st.selectbox("Delta basis", ["Fastest lap vs fastest lap", "Selected lap vs selected lap"], index=0)
    with c2:
        st.caption("Later: pick two drivers (or multiple) and compute deltas per sector.")

    st.divider()

    # Stub winner table
    winners_df = pd.DataFrame(
        [
            {"Sector": "S1", "Winner": "VER", "Margin (s)": 0.12},
            {"Sector": "S2", "Winner": "HAM", "Margin (s)": 0.05},
            {"Sector": "S3", "Winner": "LEC", "Margin (s)": 0.08},
        ]
    )
    st.markdown("### Sector Winners (Stub)")
    st.dataframe(winners_df, use_container_width=True, hide_index=True)

    # Stub delta table (example with two drivers)
    deltas_df = pd.DataFrame(
        [
            {"Driver": "VER", "S1 (s)": 30.10, "S2 (s)": 28.90, "S3 (s)": 31.12, "Lap (s)": 90.12},
            {"Driver": "HAM", "S1 (s)": 30.22, "S2 (s)": 28.85, "S3 (s)": 31.20, "Lap (s)": 90.27},
        ]
    )
    st.markdown("### Sector Times (Stub)")
    st.dataframe(deltas_df, use_container_width=True, hide_index=True)

    with st.expander("Planned calculation notes", expanded=False):
        st.markdown(
            """
- Pull **sector times** from lap data (`LapTime`, `Sector1Time`, `Sector2Time`, `Sector3Time`)
- Compute **deltas** relative to a baseline (best lap, selected lap, or a reference driver)
- “Who wins” = lowest sector time among compared drivers, margin = next best − best
"""
        )
