# fpd/components/compare_charts.py
from __future__ import annotations

import streamlit as st
from typing import Iterable


DEFAULT_CHARTS: list[str] = [
    "Speed",
    "Throttle",
    "Brake",
    "Gear",
    "RPM",
    "Delta Time Trace",
    "Gear Map (Selected Drivers)",
    "Track Map (fastest sectors)",
]


def render_compare_stack(
    session,
    mode: str,
    charts: Iterable[str] = DEFAULT_CHARTS,
) -> None:
    """
    Renders the Lap Compare chart stack as vertical rows (one under another),
    with expanders that start OPEN (pre-loaded feel).

    This is UI-only scaffolding.
    The real plotting + telemetry prep should live in fpd/analytics/compare.py
    and return objects/dataframes that you plot here.
    """
    st.subheader("Lap Compare Charts")
    st.caption(
        "Charts are stacked vertically (not side-by-side). Expanders are open by default."
    )

    # Future: This is where you'd show shared controls like:
    # - corner markers toggle
    # - sector shading toggle
    # - click-to-zoom toggle
    _render_compare_options()

    for chart_name in charts:
        with st.expander(chart_name, expanded=True):
            _render_chart_placeholder(chart_name, mode)


def _render_compare_options() -> None:
    c1, c2, c3 = st.columns([1, 1, 1])

    with c1:
        st.toggle("Corner markers", value=True, disabled=True)
    with c2:
        st.toggle("Sector shading", value=True, disabled=True)
    with c3:
        st.toggle("Click corner to zoom", value=False, disabled=True)

    st.caption("These toggles are placeholders for now (wired in later).")


def _render_chart_placeholder(chart_name: str, mode: str) -> None:
    st.info(
        f"Stub: {chart_name} ({mode})\n\n"
        "- Will plot telemetry overlays for selected drivers\n"
        "- Add corner markers + sector shading\n"
        "- Later: click a corner → auto-zoom"
    )
