# fpd/components/charts_leaderboards.py
from __future__ import annotations

import streamlit as st
import pandas as pd


def render_leaderboards(session, is_race: bool) -> None:
    """
    Leaderboards container.

    - If race: show a "race chart" placeholder (position over laps) + fastest driver/team charts
    - If not race: fastest driver/team charts

    This module stays UI-only.
    Real calculations should live in fpd/analytics/* and return DataFrames.
    """
    st.subheader("Leaderboards")

    if is_race:
        _race_chart_placeholder(session)
        st.divider()

    c1, c2 = st.columns(2)
    with c1:
        _fastest_drivers_placeholder(session)
    with c2:
        _fastest_teams_placeholder(session)


def _race_chart_placeholder(session) -> None:
    st.markdown("### Race Chart")
    st.caption("Race chart (position over laps) — shown only for Race sessions.")
    st.info("Stub: implement position-over-laps chart here (Plotly).")


def _fastest_drivers_placeholder(session) -> None:
    st.markdown("### Fastest Drivers")
    st.caption("Fastest lap ranking by driver (best lap time).")
    df = pd.DataFrame(
        [
            {"Driver": "VER", "LapTime": "1:30.123"},
            {"Driver": "HAM", "LapTime": "1:30.456"},
            {"Driver": "LEC", "LapTime": "1:30.700"},
        ]
    )
    st.dataframe(df, use_container_width=True, hide_index=True)


def _fastest_teams_placeholder(session) -> None:
    st.markdown("### Fastest Teams")
    st.caption("Fastest lap ranking by team (best driver lap).")
    df = pd.DataFrame(
        [
            {"Team": "Red Bull", "BestLap": "1:30.123"},
            {"Team": "Mercedes", "BestLap": "1:30.456"},
            {"Team": "Ferrari", "BestLap": "1:30.700"},
        ]
    )
    st.dataframe(df, use_container_width=True, hide_index=True)
