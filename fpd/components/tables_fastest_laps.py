# fpd/components/tables_fastest_laps.py
from __future__ import annotations

import streamlit as st
import pandas as pd


def render_fastest_laps_table(session) -> None:
    """
    Fastest laps table for non-race sessions.

    Columns (planned):
      - Team Logo (later)
      - Driver
      - Time (lap time)
      - Lap #
      - S1 / S2 / S3
      - Tire
      - Top Speed

    This is a working implementation using FastF1 laps data, with safe fallbacks.
    """
    st.subheader("Fastest Laps")
    st.caption("Driver • Lap time • S1/S2/S3 • Tire • Top speed • sort/filter")

    if session is None:
        st.warning("No session loaded.")
        return

    try:
        laps = session.laps
        if laps is None or len(laps) == 0:
            st.info("No laps available for this session.")
            return

        df = _build_fastest_laps_df(laps)

        # Simple filters
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            teams = sorted([t for t in df["Team"].dropna().unique().tolist() if t])
            team_filter = st.multiselect("Filter teams", teams, default=[])
        with c2:
            drivers = sorted([d for d in df["Driver"].dropna().unique().tolist() if d])
            driver_filter = st.multiselect("Filter drivers", drivers, default=[])
        with c3:
            st.caption("Tip: click column headers to sort in the table.")

        if team_filter:
            df = df[df["Team"].isin(team_filter)]
        if driver_filter:
            df = df[df["Driver"].isin(driver_filter)]

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "LapTime": st.column_config.TextColumn("Lap Time"),
                "S1": st.column_config.TextColumn("S1"),
                "S2": st.column_config.TextColumn("S2"),
                "S3": st.column_config.TextColumn("S3"),
                "TopSpeed": st.column_config.NumberColumn("Top Speed", help="km/h", format="%.0f"),
            },
        )

    except Exception as e:
        st.error(f"Failed to build fastest laps table: {e}")


def _fmt_timedelta(x) -> str:
    """
    Format pandas/py timedelta to mm:ss.mmm
    """
    if x is None or pd.isna(x):
        return "—"
    try:
        td = pd.to_timedelta(x)
        total_ms = int(td.total_seconds() * 1000)
        minutes = total_ms // 60000
        seconds = (total_ms % 60000) // 1000
        ms = total_ms % 1000
        return f"{minutes}:{seconds:02d}.{ms:03d}"
    except Exception:
        return "—"


def _build_fastest_laps_df(laps) -> pd.DataFrame:
    """
    Takes session.laps (FastF1 Laps) and returns a dataframe of each driver's fastest lap.
    """
    # FastF1 helper: fastest lap per driver
    fastest = laps.pick_fastest()

    # Some sessions return multiple rows per driver depending on data state,
    # so we group by Driver and keep the best LapTime.
    base = fastest.copy()

    # Ensure LapTime exists
    if "LapTime" not in base.columns:
        raise ValueError("LapTime not found in laps data.")

    base = base.sort_values("LapTime").groupby("Driver", as_index=False).first()

    # Top speed: best effort from telemetry (may be missing for some sessions)
    top_speeds = {}
    for _, row in base.iterrows():
        drv = row.get("Driver")
        try:
            tel = row.get_telemetry()
            if tel is not None and "Speed" in tel.columns and len(tel["Speed"]) > 0:
                top_speeds[drv] = float(pd.to_numeric(tel["Speed"], errors="coerce").max())
            else:
                top_speeds[drv] = None
        except Exception:
            top_speeds[drv] = None

    df = pd.DataFrame(
        {
            "Team": base.get("Team"),
            "Driver": base.get("Driver"),
            "Lap #": base.get("LapNumber"),
            "LapTime": base.get("LapTime").apply(_fmt_timedelta),
            "S1": base.get("Sector1Time").apply(_fmt_timedelta) if "Sector1Time" in base.columns else "—",
            "S2": base.get("Sector2Time").apply(_fmt_timedelta) if "Sector2Time" in base.columns else "—",
            "S3": base.get("Sector3Time").apply(_fmt_timedelta) if "Sector3Time" in base.columns else "—",
            "Tire": base.get("Compound") if "Compound" in base.columns else None,
            "TopSpeed": [top_speeds.get(d) for d in base.get("Driver")],
        }
    )

    # Order by lap time (already string formatted, so sort using original LapTime)
    # We'll keep the grouped base ordering; df inherits it.
    return df
