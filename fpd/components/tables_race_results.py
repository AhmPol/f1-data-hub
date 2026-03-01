# fpd/components/tables_race_results.py
from __future__ import annotations

import streamlit as st
import pandas as pd


def render_race_results_table(session) -> None:
    """
    Race Results table (for Race sessions).

    Columns (planned):
      - Team Logo (later)
      - Driver
      - Total Time
      - Gap
      - Fastest Lap
      - Total Points
      - sort/filter

    This is a best-effort implementation using FastF1 session results.
    Data availability can vary by season/event.
    """
    st.subheader("Race Results")
    st.caption("Driver • Total time • Gap • Fastest lap • Points • sort/filter")

    if session is None:
        st.warning("No session loaded.")
        return

    try:
        results = getattr(session, "results", None)

        if results is None or len(results) == 0:
            st.info("No race results available for this session.")
            return

        df = _build_race_results_df(results)

        # Filters
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
                "Pos": st.column_config.NumberColumn("Pos", format="%d"),
                "Points": st.column_config.NumberColumn("Pts", format="%.0f"),
            },
        )

    except Exception as e:
        st.error(f"Failed to build race results table: {e}")


def _fmt_timedelta(x) -> str:
    if x is None or pd.isna(x):
        return "—"
    try:
        td = pd.to_timedelta(x)
        total_ms = int(td.total_seconds() * 1000)
        hours = total_ms // 3_600_000
        minutes = (total_ms % 3_600_000) // 60_000
        seconds = (total_ms % 60_000) // 1000
        ms = total_ms % 1000
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}.{ms:03d}"
        return f"{minutes}:{seconds:02d}.{ms:03d}"
    except Exception:
        return "—"


def _fmt_gap(x) -> str:
    if x is None or pd.isna(x):
        return "—"
    try:
        # Often stored as seconds float or timedelta-like
        if isinstance(x, (int, float)):
            return f"+{x:.3f}s"
        td = pd.to_timedelta(x)
        return f"+{td.total_seconds():.3f}s"
    except Exception:
        return str(x)


def _build_race_results_df(results: pd.DataFrame) -> pd.DataFrame:
    """
    Build a display-friendly race results DataFrame from session.results.
    """
    r = results.copy()

    # Common columns: Position, Abbreviation, FullName, TeamName, Time, Status, Points, etc.
    # But not all are always present, so we guard everything.
    pos = r["Position"] if "Position" in r.columns else None

    # Prefer driver code (Abbreviation) else short/last name
    if "Abbreviation" in r.columns:
        driver = r["Abbreviation"]
    elif "BroadcastName" in r.columns:
        driver = r["BroadcastName"]
    elif "FullName" in r.columns:
        driver = r["FullName"]
    else:
        driver = pd.Series(["—"] * len(r))

    # Team name
    if "TeamName" in r.columns:
        team = r["TeamName"]
    elif "Team" in r.columns:
        team = r["Team"]
    else:
        team = pd.Series(["—"] * len(r))

    total_time = r["Time"] if "Time" in r.columns else None
    status = r["Status"] if "Status" in r.columns else None
    points = r["Points"] if "Points" in r.columns else None

    # Gap: if there is a Time column, we can compute gap relative to P1 where possible.
    gap = None
    if total_time is not None:
        try:
            t = pd.to_timedelta(total_time, errors="coerce")
            leader_time = t.min()
            gap_sec = (t - leader_time).dt.total_seconds()
            gap = gap_sec.apply(lambda s: "—" if pd.isna(s) or s == 0 else f"+{s:.3f}s")
        except Exception:
            gap = None

    # Fastest lap: not always in results; if missing we show placeholder
    fastest_lap = r["FastestLapTime"] if "FastestLapTime" in r.columns else pd.Series(["—"] * len(r))

    df = pd.DataFrame(
        {
            "Pos": pos if pos is not None else range(1, len(r) + 1),
            "Team": team,
            "Driver": driver,
            "Total Time": total_time.apply(_fmt_timedelta) if total_time is not None else "—",
            "Gap": gap if gap is not None else "—",
            "Fastest Lap": fastest_lap.apply(_fmt_timedelta) if hasattr(fastest_lap, "apply") else fastest_lap,
            "Points": points if points is not None else "—",
            "Status": status if status is not None else "—",
        }
    )

    # Sort by position if possible
    if "Pos" in df.columns:
        df = df.sort_values("Pos", ascending=True)

    return df
