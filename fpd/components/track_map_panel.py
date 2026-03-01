# fpd/components/track_map_panel.py
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px


def render_track_map_panel(session) -> None:
    """
    Track Map Panel (UI + basic working map).

    Shows:
      - Track outline (from fastest lap telemetry X/Y)
      - Sector boundaries (placeholder for now)
      - Turn numbers / corner labels (placeholder for now)
      - Temperature (best-effort from session.weather_data if available)

    Notes:
      - FastF1 track XY comes from telemetry with add_distance().
      - True corner numbers/sector shading will be implemented later in analytics.
    """
    st.subheader("Track Map")
    _render_temperature_row(session)

    if session is None:
        st.warning("No session loaded.")
        return

    telemetry_df = _get_reference_telemetry_xy(session)
    if telemetry_df is None or telemetry_df.empty:
        st.info("Track map data not available for this session.")
        return

    fig = px.line(
        telemetry_df,
        x="X",
        y="Y",
        title=None,
    )
    fig.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title=None,
        yaxis_title=None,
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False, scaleanchor="x", scaleratio=1),
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "Planned: turn numbers, corner labels (slow/medium/high), and sector boundaries shading."
    )


def _get_reference_telemetry_xy(session) -> pd.DataFrame | None:
    """
    Build a reference track outline from a single lap:
      - Prefer fastest lap if available
      - Fallback to first available lap

    Returns dataframe with columns: X, Y, Distance.
    """
    try:
        laps = session.laps
        if laps is None or len(laps) == 0:
            return None

        # pick fastest lap where possible
        try:
            lap = laps.pick_fastest()
            # pick_fastest may return a Laps object; get first row if needed
            if hasattr(lap, "iloc"):
                lap = lap.iloc[0]
        except Exception:
            lap = laps.iloc[0]

        tel = lap.get_telemetry()
        if tel is None or len(tel) == 0:
            return None

        # Ensure distance and xy exist
        if "Distance" not in tel.columns:
            tel = tel.add_distance()

        if "X" not in tel.columns or "Y" not in tel.columns:
            # Some sessions may not include positional data
            return None

        out = tel[["X", "Y", "Distance"]].copy()
        out = out.dropna(subset=["X", "Y"])
        return out

    except Exception:
        return None


def _render_temperature_row(session) -> None:
    """
    Best-effort temperature display.
    FastF1 weather_data availability varies.
    """
    c1, c2, c3 = st.columns([1, 1, 2])

    air = track = humidity = None
    try:
        w = getattr(session, "weather_data", None)
        if w is not None and len(w) > 0:
            # take median-ish values (weather can vary)
            air = _safe_num(w.get("AirTemp"))
            track = _safe_num(w.get("TrackTemp"))
            humidity = _safe_num(w.get("Humidity"))
    except Exception:
        pass

    with c1:
        st.metric("Air Temp", f"{air:.1f}°C" if air is not None else "—")
    with c2:
        st.metric("Track Temp", f"{track:.1f}°C" if track is not None else "—")
    with c3:
        st.metric("Humidity", f"{humidity:.0f}%" if humidity is not None else "—")


def _safe_num(series_or_value) -> float | None:
    try:
        if hasattr(series_or_value, "median"):
            v = float(pd.to_numeric(series_or_value, errors="coerce").median())
            return None if pd.isna(v) else v
        v = float(series_or_value)
        return None if pd.isna(v) else v
    except Exception:
        return None
