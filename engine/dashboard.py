# dashboard.py
"""
Dashboard (Home) page logic extracted so it can be reused.

Usage:
- In streamlit_app.py (or pages/01_Home.py) do:
    from dashboard import render_dashboard
    render_dashboard(st.session_state["bundle"])

This file DOES NOT touch FastF1 cache. That should be done once in streamlit_app.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ----------------------------
# Basic helpers
# ----------------------------
def _to_seconds(td):
    if td is None or pd.isna(td):
        return np.nan
    if hasattr(td, "total_seconds"):
        return float(td.total_seconds())
    try:
        return float(pd.to_timedelta(td).total_seconds())
    except Exception:
        return np.nan


def _lap_time_str(td) -> str:
    if td is None or pd.isna(td):
        return ""
    try:
        total_ms = int(pd.to_timedelta(td).total_seconds() * 1000)
        m = total_ms // 60000
        s = (total_ms % 60000) / 1000
        return f"{m}:{s:06.3f}"
    except Exception:
        return str(td)


def _ensure_distance(tel: pd.DataFrame) -> pd.DataFrame:
    tel = tel.copy()
    if "Distance" not in tel.columns:
        try:
            tel = tel.add_distance()
        except Exception:
            pass
    return tel


def _resample_to_distance(tel: pd.DataFrame, step_m: float = 2.0) -> pd.DataFrame:
    tel = _ensure_distance(tel)
    tel = tel[tel["Distance"].notna()].sort_values("Distance")
    if tel.empty:
        return tel

    d = tel["Distance"].to_numpy(dtype=float)
    dmin, dmax = float(np.nanmin(d)), float(np.nanmax(d))
    grid = np.arange(dmin, dmax, step_m)

    out = pd.DataFrame({"Distance": grid})
    for col in ["Speed", "Throttle", "Brake", "nGear", "RPM", "X", "Y"]:
        if col in tel.columns:
            out[col] = np.interp(grid, d, tel[col].to_numpy(dtype=float))

    # Time interpolation for mapping sector boundaries
    if "Time" in tel.columns:
        t = tel["Time"]
        if len(t) and hasattr(t.iloc[0], "total_seconds"):
            tsec = t.dt.total_seconds().to_numpy(dtype=float)
        else:
            tsec = pd.to_numeric(t, errors="coerce").to_numpy(dtype=float)
        if np.isfinite(tsec).any():
            out["Time_s"] = np.interp(grid, d, tsec)

    return out


def _sector_end_distances(lap, tel_r: pd.DataFrame):
    s1s = _to_seconds(getattr(lap, "Sector1Time", None))
    s2s = _to_seconds(getattr(lap, "Sector2Time", None))
    if "Time_s" not in tel_r.columns or not np.isfinite(s1s) or not np.isfinite(s2s):
        return None, None

    t = tel_r["Time_s"].to_numpy(dtype=float)
    d = tel_r["Distance"].to_numpy(dtype=float)
    d1 = float(np.interp(s1s, t, d))
    d2 = float(np.interp(s1s + s2s, t, d))
    return d1, d2


def _corner_class(min_speed_kph: float) -> str:
    if not np.isfinite(min_speed_kph):
        return "?"
    if min_speed_kph < 120:
        return "Slow"
    if min_speed_kph < 200:
        return "Medium"
    return "High"


def _detect_corners_from_circuit_info(session, tel_r: pd.DataFrame, window_m: float = 35.0) -> pd.DataFrame:
    try:
        ci = session.get_circuit_info()
        corners = ci.corners.copy()
    except Exception:
        return pd.DataFrame()

    if corners is None or corners.empty or "Distance" not in corners.columns:
        return pd.DataFrame()
    if "Speed" not in tel_r.columns or "Distance" not in tel_r.columns:
        return pd.DataFrame()

    d = tel_r["Distance"].to_numpy(dtype=float)
    v = tel_r["Speed"].to_numpy(dtype=float)

    rows = []
    for _, row in corners.iterrows():
        try:
            cn = int(row.get("Number"))
            cd = float(row.get("Distance"))
        except Exception:
            continue
        m = (d >= cd - window_m) & (d <= cd + window_m)
        if not np.any(m):
            continue
        min_v = float(np.nanmin(v[m]))
        rows.append({"Corner": cn, "CornerDistance": cd, "MinSpeed": min_v, "Type": _corner_class(min_v)})

    return pd.DataFrame(rows).sort_values("Corner")


def _track_map_figure(tel_r: pd.DataFrame, corners_df: pd.DataFrame, d_s1: float | None, d_s2: float | None):
    fig = go.Figure()

    if "X" in tel_r.columns and "Y" in tel_r.columns:
        fig.add_trace(go.Scatter(x=tel_r["X"], y=tel_r["Y"], mode="lines", hoverinfo="skip"))
    else:
        fig.add_trace(go.Scatter(x=tel_r["Distance"], y=tel_r.get("Speed", tel_r["Distance"] * 0), mode="lines"))

    # Sector markers (XY only)
    if "X" in tel_r.columns and "Y" in tel_r.columns and "Distance" in tel_r.columns:
        if d_s1 is not None and np.isfinite(d_s1):
            idx = int(np.argmin(np.abs(tel_r["Distance"].to_numpy(dtype=float) - d_s1)))
            fig.add_trace(go.Scatter(x=[tel_r["X"].iloc[idx]], y=[tel_r["Y"].iloc[idx]], mode="markers+text",
                                     text=["S1"], textposition="top center"))
        if d_s2 is not None and np.isfinite(d_s2):
            idx = int(np.argmin(np.abs(tel_r["Distance"].to_numpy(dtype=float) - d_s2)))
            fig.add_trace(go.Scatter(x=[tel_r["X"].iloc[idx]], y=[tel_r["Y"].iloc[idx]], mode="markers+text",
                                     text=["S2"], textposition="top center"))

    # Turn labels
    if corners_df is not None and not corners_df.empty and "X" in tel_r.columns and "Y" in tel_r.columns:
        d = tel_r["Distance"].to_numpy(dtype=float)
        xs = tel_r["X"].to_numpy(dtype=float)
        ys = tel_r["Y"].to_numpy(dtype=float)

        cx, cy, labels = [], [], []
        for _, r in corners_df.iterrows():
            cd = float(r["CornerDistance"])
            idx = int(np.argmin(np.abs(d - cd)))
            cx.append(xs[idx])
            cy.append(ys[idx])
            labels.append(f"T{int(r['Corner'])} ({r['Type'][0]})")

        fig.add_trace(go.Scatter(x=cx, y=cy, mode="markers+text", text=labels, textposition="top center"))

    fig.update_layout(height=520, margin=dict(l=10, r=10, t=20, b=10), showlegend=False)
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    return fig


# ----------------------------
# Tables & charts
# ----------------------------
def _fastest_laps_table(laps: pd.DataFrame) -> pd.DataFrame:
    df = laps.copy()
    df = df[df["LapTime"].notna()]
    if "IsAccurate" in df.columns:
        df = df[df["IsAccurate"] == True]
    if df.empty:
        return pd.DataFrame()

    idx = df.groupby("Driver")["LapTime"].idxmin()
    best = df.loc[idx].copy().sort_values("LapTime")

    best["Lap Time"] = best["LapTime"].apply(_lap_time_str)
    if "Sector1Time" in best.columns:
        best["S1"] = best["Sector1Time"].apply(_lap_time_str)
    if "Sector2Time" in best.columns:
        best["S2"] = best["Sector2Time"].apply(_lap_time_str)
    if "Sector3Time" in best.columns:
        best["S3"] = best["Sector3Time"].apply(_lap_time_str)

    out = pd.DataFrame()
    if "Team" in best.columns:
        out["Team"] = best["Team"]
    out["Driver"] = best["Driver"]
    out["Lap Time"] = best["Lap Time"]
    if "S1" in best.columns:
        out["S1"] = best["S1"]
    if "S2" in best.columns:
        out["S2"] = best["S2"]
    if "S3" in best.columns:
        out["S3"] = best["S3"]
    if "Compound" in best.columns:
        out["Tire"] = best["Compound"]
    if "TyreLife" in best.columns:
        out["TyreLife"] = best["TyreLife"]

    out["Top Speed (kph)"] = np.nan
    return out


def _race_results_table(session) -> pd.DataFrame:
    try:
        res = session.results.copy()
    except Exception:
        return pd.DataFrame()

    cols = []
    for c in ["Position", "TeamName", "Abbreviation", "Time", "Status", "Points", "GridPosition"]:
        if c in res.columns:
            cols.append(c)

    out = res[cols].copy()
    if "TeamName" in out.columns:
        out.rename(columns={"TeamName": "Team"}, inplace=True)
    if "Abbreviation" in out.columns:
        out.rename(columns={"Abbreviation": "Driver"}, inplace=True)
    if "Time" in out.columns:
        out["Total Time"] = out["Time"].astype(str)

    keep = [c for c in ["Position", "Team", "Driver", "Total Time", "Status", "Points", "GridPosition"] if c in out.columns]
    if "Position" in out.columns:
        out = out.sort_values("Position")
    return out[keep]


def _bar_fastest_drivers(fast_tbl: pd.DataFrame):
    if fast_tbl.empty or "Lap Time" not in fast_tbl.columns:
        return None

    def parse_laptime(s):
        try:
            m, rest = s.split(":")
            return float(m) * 60 + float(rest)
        except Exception:
            return np.nan

    d = fast_tbl.copy()
    d["Lap_s"] = d["Lap Time"].apply(parse_laptime)
    d = d.sort_values("Lap_s")

    fig = go.Figure(go.Bar(x=d["Driver"], y=d["Lap_s"]))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10), title="Fastest Drivers (Fastest Lap)")
    fig.update_yaxes(title="Seconds")
    return fig


def _bar_fastest_teams(laps: pd.DataFrame):
    df = laps.copy()
    df = df[df["LapTime"].notna()]
    if "IsAccurate" in df.columns:
        df = df[df["IsAccurate"] == True]
    if "Team" not in df.columns or df.empty:
        return None

    df["Lap_s"] = df["LapTime"].dt.total_seconds()
    team_best = df.groupby("Team")["Lap_s"].min().reset_index().sort_values("Lap_s")

    fig = go.Figure(go.Bar(x=team_best["Team"], y=team_best["Lap_s"]))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10), title="Fastest Teams (Best Lap)")
    fig.update_yaxes(title="Seconds")
    return fig


# ----------------------------
# Public renderer
# ----------------------------
def render_dashboard(bundle: dict):
    """
    Render the Home/Dashboard using an already-loaded bundle.
    bundle keys expected:
      - year, event_label, session_label
      - session, laps, drivers, is_race
    """
    session = bundle["session"]
    laps = bundle["laps"]
    drivers = bundle["drivers"]
    is_race = bool(bundle.get("is_race", False))

    st.caption(f"{bundle.get('year')} • {bundle.get('event_label')} • {bundle.get('session_label')}")

    # Track map + conditions
    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("Track Map")

        laps_valid = laps[laps["LapTime"].notna()].copy()
        if "IsAccurate" in laps_valid.columns:
            laps_valid = laps_valid[laps_valid["IsAccurate"] == True]

        if laps_valid.empty:
            st.warning("No valid laps found for this session.")
            return

        overall_fast = laps_valid.loc[laps_valid["LapTime"].idxmin()]
        default_driver = str(overall_fast["Driver"])

        map_driver = st.selectbox(
            "Map base driver",
            options=sorted(drivers),
            index=sorted(drivers).index(default_driver) if default_driver in drivers else 0,
            key="dash_map_driver",
        )
        map_lap_row = laps_valid[laps_valid["Driver"] == map_driver].sort_values("LapTime").head(1)
        if map_lap_row.empty:
            st.warning("No valid lap for selected driver.")
            return

        map_lap = map_lap_row.iloc[0]
        tel_r = _resample_to_distance(map_lap.get_telemetry().copy(), step_m=2.0)
        d_s1, d_s2 = _sector_end_distances(map_lap, tel_r)
        corners_df = _detect_corners_from_circuit_info(session, tel_r)

        st.plotly_chart(_track_map_figure(tel_r, corners_df, d_s1, d_s2), use_container_width=True)

    with right:
        st.subheader("Conditions")
        air_temp = track_temp = np.nan
        try:
            w = session.weather_data
            if w is not None and not w.empty:
                air_temp = float(np.nanmean(w["AirTemp"])) if "AirTemp" in w.columns else np.nan
                track_temp = float(np.nanmean(w["TrackTemp"])) if "TrackTemp" in w.columns else np.nan
        except Exception:
            pass

        c1, c2 = st.columns(2)
        c1.metric("Air Temp (°C)", f"{air_temp:.1f}" if np.isfinite(air_temp) else "—")
        c2.metric("Track Temp (°C)", f"{track_temp:.1f}" if np.isfinite(track_temp) else "—")

        if corners_df is not None and not corners_df.empty:
            counts = corners_df["Type"].value_counts().to_dict()
            st.caption(
                f"Corner types: Slow={counts.get('Slow',0)} • Medium={counts.get('Medium',0)} • High={counts.get('High',0)}"
            )
        else:
            st.caption("Corner labels unavailable for this session.")

    st.divider()

    # Tables
    if not is_race:
        st.subheader("Fastest Laps (non-race session)")
        fast_tbl = _fastest_laps_table(laps)

        with st.expander("Compute Top Speed from telemetry (optional)", expanded=False):
            if st.button("Compute Top Speed", key="dash_compute_topspeed"):
                tops = {}
                laps_valid = laps[laps["LapTime"].notna()].copy()
                if "IsAccurate" in laps_valid.columns:
                    laps_valid = laps_valid[laps_valid["IsAccurate"] == True]
                idx = laps_valid.groupby("Driver")["LapTime"].idxmin()
                best = laps_valid.loc[idx].copy()

                for _, r in best.iterrows():
                    drv = str(r["Driver"])
                    try:
                        tel_r2 = _resample_to_distance(r.get_telemetry().copy(), step_m=4.0)
                        tops[drv] = float(np.nanmax(tel_r2["Speed"])) if "Speed" in tel_r2.columns else np.nan
                    except Exception:
                        tops[drv] = np.nan

                fast_tbl["Top Speed (kph)"] = fast_tbl["Driver"].map(tops)

        st.dataframe(fast_tbl, use_container_width=True)

    else:
        st.subheader("Race Results (race session)")
        race_tbl = _race_results_table(session)
        if race_tbl.empty:
            st.warning("Race results not available for this session via FastF1.")
        else:
            st.dataframe(race_tbl, use_container_width=True)

    st.divider()

    # Leaderboards
    st.subheader("Leaderboards")
    if not is_race:
        fig_drv = _bar_fastest_drivers(_fastest_laps_table(laps))
        fig_team = _bar_fastest_teams(laps)

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(fig_drv, use_container_width=True) if fig_drv else st.caption("Driver leaderboard unavailable.")
        with c2:
            st.plotly_chart(fig_team, use_container_width=True) if fig_team else st.caption("Team leaderboard unavailable.")
    else:
        race_tbl = _race_results_table(session)
        if not race_tbl.empty and "Points" in race_tbl.columns:
            fig = go.Figure(go.Bar(x=race_tbl["Driver"], y=race_tbl["Points"]))
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10), title="Race Chart: Points")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("Race chart unavailable.")
