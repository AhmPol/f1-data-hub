# pages/01_Home.py
"""
HOME / DASHBOARD

Uses the shared session bundle created in streamlit_app.py + app_state.py:
    bundle = st.session_state["bundle"]

Implements:
- Top map panel (track outline + turn numbers + sector boundaries + corner labels + temperature)
- Fastest laps table (non-race) OR race results table (race)
- Leaderboards (fastest drivers/teams) (+ simple race gap chart if race)
- Session summary cards (winners for straight-line / traction / cornering / braking / tire deg)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go


# ----------------------------
# Helpers (keep in-page for now)
# ----------------------------
def _to_seconds(td):
    if td is None or pd.isna(td):
        return np.nan
    # pandas Timedelta
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
        # FastF1 telemetry objects support add_distance(); DataFrame usually doesn't
        try:
            tel = tel.add_distance()
        except Exception:
            pass
    return tel


def _resample_to_distance(tel: pd.DataFrame, step_m: float = 2.0) -> pd.DataFrame:
    tel = tel.copy()
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

    # Time interpolation for sector boundaries mapping
    if "Time" in tel.columns:
        t = tel["Time"]
        if hasattr(t.iloc[0], "total_seconds"):
            tsec = t.dt.total_seconds().to_numpy(dtype=float)
        else:
            # fallback (may be already numeric)
            tsec = pd.to_numeric(t, errors="coerce").to_numpy(dtype=float)
        out["Time_s"] = np.interp(grid, d, tsec)

    return out


def _sector_end_distances(lap, tel_r: pd.DataFrame):
    """
    Use Sector1Time / Sector2Time to approximate where S1 ends and S2 ends.
    We map cumulative sector times onto Time_s to get distance.
    """
    s1 = getattr(lap, "Sector1Time", None)
    s2 = getattr(lap, "Sector2Time", None)

    s1s = _to_seconds(s1)
    s2s = _to_seconds(s2)

    if "Time_s" not in tel_r.columns or np.isnan(s1s) or np.isnan(s2s):
        return None, None

    t = tel_r["Time_s"].to_numpy(dtype=float)
    d = tel_r["Distance"].to_numpy(dtype=float)

    # cumulative times from lap start
    t1 = s1s
    t2 = s1s + s2s

    d1 = float(np.interp(t1, t, d))
    d2 = float(np.interp(t2, t, d))
    return d1, d2


def _corner_class(min_speed_kph: float) -> str:
    if not np.isfinite(min_speed_kph):
        return "?"
    if min_speed_kph < 120:
        return "Slow"
    if min_speed_kph < 200:
        return "Medium"
    return "High"


def _compute_braking_efficiency(tel_r: pd.DataFrame) -> float:
    if "Brake" not in tel_r.columns or "Speed" not in tel_r.columns:
        return np.nan
    br = tel_r[tel_r["Brake"] > 0.5]
    if len(br) < 10:
        return np.nan
    dv = np.diff(br["Speed"].to_numpy(dtype=float))
    dd = np.diff(br["Distance"].to_numpy(dtype=float))
    with np.errstate(divide="ignore", invalid="ignore"):
        decel = -dv / dd  # kph per meter (proxy)
    return float(np.nanmean(decel))


def _compute_low_speed_traction(tel_r: pd.DataFrame) -> float:
    if "Speed" not in tel_r.columns or "Throttle" not in tel_r.columns:
        return np.nan
    low = tel_r[tel_r["Speed"] < 140]
    if len(low) < 20:
        return np.nan
    return float(np.nanmean(low["Throttle"].to_numpy(dtype=float)))


def _compute_corner_strengths(corners_df: pd.DataFrame):
    """
    corners_df contains per-corner MinSpeed and Type.
    Strength proxy: higher average MinSpeed within each type.
    """
    if corners_df is None or corners_df.empty:
        return np.nan, np.nan, np.nan
    out = {}
    for t in ["Slow", "Medium", "High"]:
        sub = corners_df[corners_df["Type"] == t]
        out[t] = float(np.nanmean(sub["MinSpeed"])) if not sub.empty else np.nan
    return out.get("Slow", np.nan), out.get("Medium", np.nan), out.get("High", np.nan)


def _detect_corners_from_circuit_info(session, tel_r: pd.DataFrame, window_m: float = 35.0) -> pd.DataFrame:
    """
    Preferred: use official circuit corner distances from FastF1 circuit info.
    For each corner, compute min speed around its distance window and classify Slow/Medium/High.
    """
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
        except Exception:
            continue
        cd = float(row.get("Distance"))
        m = (d >= cd - window_m) & (d <= cd + window_m)
        if not np.any(m):
            continue
        min_v = float(np.nanmin(v[m]))
        rows.append(
            {
                "Corner": cn,
                "CornerDistance": cd,
                "MinSpeed": min_v,
                "Type": _corner_class(min_v),
            }
        )
    df = pd.DataFrame(rows).sort_values("Corner")
    return df


def _track_map_figure(
    tel_r: pd.DataFrame,
    corners_df: pd.DataFrame,
    d_s1: float | None,
    d_s2: float | None,
):
    fig = go.Figure()

    if "X" in tel_r.columns and "Y" in tel_r.columns:
        fig.add_trace(
            go.Scatter(
                x=tel_r["X"],
                y=tel_r["Y"],
                mode="lines",
                name="Track",
                hoverinfo="skip",
            )
        )
    else:
        # fallback to distance-speed if XY missing
        fig.add_trace(
            go.Scatter(
                x=tel_r["Distance"],
                y=tel_r["Speed"] if "Speed" in tel_r.columns else tel_r["Distance"] * 0,
                mode="lines",
                name="Track (fallback)",
            )
        )

    # Sector boundaries (approx): mark points where Distance == d_s1/d_s2
    if d_s1 is not None and np.isfinite(d_s1) and "Distance" in tel_r.columns:
        idx = int(np.argmin(np.abs(tel_r["Distance"].to_numpy(dtype=float) - d_s1)))
        if "X" in tel_r.columns and "Y" in tel_r.columns:
            fig.add_trace(
                go.Scatter(
                    x=[tel_r["X"].iloc[idx]],
                    y=[tel_r["Y"].iloc[idx]],
                    mode="markers+text",
                    text=["S1 end"],
                    textposition="top center",
                    name="S1 end",
                )
            )

    if d_s2 is not None and np.isfinite(d_s2) and "Distance" in tel_r.columns:
        idx = int(np.argmin(np.abs(tel_r["Distance"].to_numpy(dtype=float) - d_s2)))
        if "X" in tel_r.columns and "Y" in tel_r.columns:
            fig.add_trace(
                go.Scatter(
                    x=[tel_r["X"].iloc[idx]],
                    y=[tel_r["Y"].iloc[idx]],
                    mode="markers+text",
                    text=["S2 end"],
                    textposition="top center",
                    name="S2 end",
                )
            )

    # Turn numbers + Slow/Medium/High labels
    if corners_df is not None and not corners_df.empty and "X" in tel_r.columns and "Y" in tel_r.columns:
        # Map corner distance -> nearest XY from telemetry
        d = tel_r["Distance"].to_numpy(dtype=float)
        xs = tel_r["X"].to_numpy(dtype=float)
        ys = tel_r["Y"].to_numpy(dtype=float)

        cx, cy, labels = [], [], []
        for _, r in corners_df.iterrows():
            cd = float(r["CornerDistance"])
            idx = int(np.argmin(np.abs(d - cd)))
            cx.append(xs[idx])
            cy.append(ys[idx])
            labels.append(f"T{int(r['Corner'])} ({r['Type'][0]})")  # S/M/H initial

        fig.add_trace(
            go.Scatter(
                x=cx,
                y=cy,
                mode="markers+text",
                text=labels,
                textposition="top center",
                name="Turns",
            )
        )

    fig.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=30, b=10),
        showlegend=False,
    )
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    return fig


def _fastest_laps_table(laps: pd.DataFrame) -> pd.DataFrame:
    """
    Per driver fastest lap. Includes S1/S2/S3, tire, and placeholder top speed.
    """
    df = laps.copy()
    df = df[df["LapTime"].notna()]
    if "IsAccurate" in df.columns:
        df = df[df["IsAccurate"] == True]

    idx = df.groupby("Driver")["LapTime"].idxmin()
    best = df.loc[idx].copy().sort_values("LapTime")

    cols = ["Team", "Driver", "LapTime", "Sector1Time", "Sector2Time", "Sector3Time", "Compound", "TyreLife"]
    cols = [c for c in cols if c in best.columns]
    best = best[cols].copy()

    # nice formatting columns
    if "LapTime" in best.columns:
        best["LapTimeStr"] = best["LapTime"].apply(_lap_time_str)
    if "Sector1Time" in best.columns:
        best["S1"] = best["Sector1Time"].apply(_lap_time_str)
    if "Sector2Time" in best.columns:
        best["S2"] = best["Sector2Time"].apply(_lap_time_str)
    if "Sector3Time" in best.columns:
        best["S3"] = best["Sector3Time"].apply(_lap_time_str)

    # reorder display
    display = pd.DataFrame()
    if "Team" in best.columns: display["Team"] = best["Team"]
    display["Driver"] = best["Driver"]
    if "LapTimeStr" in best.columns: display["Lap Time"] = best["LapTimeStr"]
    if "S1" in best.columns: display["S1"] = best["S1"]
    if "S2" in best.columns: display["S2"] = best["S2"]
    if "S3" in best.columns: display["S3"] = best["S3"]
    if "Compound" in best.columns: display["Tire"] = best["Compound"]
    if "TyreLife" in best.columns: display["TyreLife"] = best["TyreLife"]

    # Top speed will be computed per driver later (telemetry); keep placeholder here
    display["Top Speed (kph)"] = np.nan

    return display


def _race_results_table(session) -> pd.DataFrame:
    """
    Uses session.results if available (FastF1 provides it for races).
    """
    try:
        res = session.results.copy()
    except Exception:
        return pd.DataFrame()

    # columns vary; keep essentials
    cols = []
    for c in ["TeamName", "Abbreviation", "FullName", "Position", "Time", "Status", "Points", "GridPosition"]:
        if c in res.columns:
            cols.append(c)
    out = res[cols].copy()

    # normalize names
    if "Abbreviation" in out.columns:
        out.rename(columns={"Abbreviation": "Driver"}, inplace=True)
    if "TeamName" in out.columns:
        out.rename(columns={"TeamName": "Team"}, inplace=True)

    # time string
    if "Time" in out.columns:
        out["Total Time"] = out["Time"].astype(str)

    # create gap vs winner if possible (Time might be timedelta-like strings)
    # Keep simple: show Total Time and Points.
    keep = []
    for c in ["Position", "Team", "Driver", "Total Time", "Status", "Points", "GridPosition"]:
        if c in out.columns:
            keep.append(c)
    return out[keep].sort_values("Position") if "Position" in out.columns else out[keep]


def _bar_fastest_drivers(fast_tbl: pd.DataFrame):
    if fast_tbl.empty or "Lap Time" not in fast_tbl.columns:
        return None

    # parse Lap Time string back to seconds
    def parse_laptime(s):
        try:
            m, rest = s.split(":")
            return float(m) * 60 + float(rest)
        except Exception:
            return np.nan

    d = fast_tbl.copy()
    d["Lap_s"] = d["Lap Time"].apply(parse_laptime)
    d = d.sort_values("Lap_s")

    fig = go.Figure(
        go.Bar(
            x=d["Driver"],
            y=d["Lap_s"],
            name="Fastest lap (s)",
        )
    )
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10), title="Fastest Drivers (Fastest Lap)")
    fig.update_yaxes(title="Seconds")
    return fig


def _bar_fastest_teams(laps: pd.DataFrame):
    df = laps.copy()
    df = df[df["LapTime"].notna()]
    if "IsAccurate" in df.columns:
        df = df[df["IsAccurate"] == True]
    if "Team" not in df.columns:
        return None

    df["Lap_s"] = df["LapTime"].dt.total_seconds()
    team_best = df.groupby("Team")["Lap_s"].min().reset_index().sort_values("Lap_s")

    fig = go.Figure(go.Bar(x=team_best["Team"], y=team_best["Lap_s"], name="Team best (s)"))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10), title="Fastest Teams (Best Lap)")
    fig.update_yaxes(title="Seconds")
    return fig


def _simple_deg_scores(laps: pd.DataFrame) -> pd.DataFrame:
    """
    Rough tire degradation resistance:
    For each driver, take a stint-like continuous segment with same Compound
    (largest TyreLife span), fit slope seconds/lap (lower = better).
    """
    df = laps.copy()
    df = df[df["LapTime"].notna()]
    if "IsAccurate" in df.columns:
        df = df[df["IsAccurate"] == True]
    if "TyreLife" not in df.columns or "Compound" not in df.columns:
        return pd.DataFrame()

    df["Lap_s"] = df["LapTime"].dt.total_seconds()

    rows = []
    for drv, sub in df.groupby("Driver"):
        sub = sub.sort_values("LapNumber")
        # pick compound with most rows as crude stint proxy
        comp = sub["Compound"].value_counts().idxmax()
        stint = sub[sub["Compound"] == comp].copy()
        # require enough laps
        if len(stint) < 6:
            continue
        x = stint["LapNumber"].to_numpy(dtype=float)
        y = stint["Lap_s"].to_numpy(dtype=float)
        slope = np.polyfit(x, y, 1)[0]  # s/lap
        rows.append({"Driver": drv, "Deg_s_per_lap": float(slope), "Compound": comp, "N": int(len(stint))})

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values("Deg_s_per_lap")


# ----------------------------
# Page
# ----------------------------
st.set_page_config(layout="wide")

if "bundle" not in st.session_state:
    st.error("Session bundle not loaded. Go to the main page (streamlit_app.py) first.")
    st.stop()

bundle = st.session_state["bundle"]
session = bundle["session"]
laps = bundle["laps"]
drivers = bundle["drivers"]
is_race = bool(bundle.get("is_race", False))

st.title("Home / Dashboard")

# ----------------------------
# Track Map Panel (fastest lap as base)
# ----------------------------
left, right = st.columns([1.2, 1])

with left:
    st.subheader("Track Map")

    # Choose a driver for the map base (default: fastest overall in session)
    laps_valid = laps[laps["LapTime"].notna()].copy()
    if "IsAccurate" in laps_valid.columns:
        laps_valid = laps_valid[laps_valid["IsAccurate"] == True]

    if laps_valid.empty:
        st.warning("No valid laps found for this session.")
        st.stop()

    overall_fast = laps_valid.loc[laps_valid["LapTime"].idxmin()]
    default_driver = overall_fast["Driver"]

    map_driver = st.selectbox("Map base driver", options=sorted(drivers), index=sorted(drivers).index(default_driver))
    map_lap_row = laps_valid[laps_valid["Driver"] == map_driver].sort_values("LapTime").head(1)
    if map_lap_row.empty:
        st.warning("No valid lap for selected driver.")
        st.stop()

    map_lap = map_lap_row.iloc[0]
    tel = map_lap.get_telemetry().copy()
    tel = _ensure_distance(tel)
    tel_r = _resample_to_distance(tel, step_m=2.0)

    # Sector boundaries (approx)
    d_s1, d_s2 = _sector_end_distances(map_lap, tel_r)

    # Corners using official circuit info
    corners_df = _detect_corners_from_circuit_info(session, tel_r)

    fig_map = _track_map_figure(tel_r, corners_df, d_s1, d_s2)
    st.plotly_chart(fig_map, use_container_width=True)

with right:
    st.subheader("Conditions")
    # Temperature (best-effort)
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
            f"Corner types (from min speed near official turn distances): "
            f"Slow={counts.get('Slow',0)} • Medium={counts.get('Medium',0)} • High={counts.get('High',0)}"
        )
    else:
        st.caption("Corner labels unavailable (circuit info / XY missing for this session).")


st.divider()

# ----------------------------
# Fastest Laps (non-race) OR Race Results (race)
# ----------------------------
if not is_race:
    st.subheader("Fastest Laps (non-race session)")

    fast_tbl = _fastest_laps_table(laps)

    # Compute Top Speed per driver from their fastest lap telemetry (best-effort)
    # (This can be a bit slow; keep it optional)
    with st.expander("Compute Top Speed from telemetry (may take a bit)", expanded=False):
        if st.button("Compute Top Speed", use_container_width=False):
            tops = {}
            laps_valid = laps[laps["LapTime"].notna()].copy()
            if "IsAccurate" in laps_valid.columns:
                laps_valid = laps_valid[laps_valid["IsAccurate"] == True]
            # fastest lap per driver
            idx = laps_valid.groupby("Driver")["LapTime"].idxmin()
            best = laps_valid.loc[idx].copy()

            for _, r in best.iterrows():
                drv = r["Driver"]
                try:
                    tel = r.get_telemetry().copy()
                    tel = _ensure_distance(tel)
                    tel_r2 = _resample_to_distance(tel, step_m=4.0)
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

# ----------------------------
# Leaderboards (Graphs)
# ----------------------------
st.subheader("Leaderboards")

if not is_race:
    # use fastest laps table for driver leaderboard
    fast_tbl = _fastest_laps_table(laps)
    fig_drv = _bar_fastest_drivers(fast_tbl)
    fig_team = _bar_fastest_teams(laps)

    c1, c2 = st.columns(2)
    with c1:
        if fig_drv:
            st.plotly_chart(fig_drv, use_container_width=True)
        else:
            st.caption("Driver leaderboard unavailable.")
    with c2:
        if fig_team:
            st.plotly_chart(fig_team, use_container_width=True)
        else:
            st.caption("Team leaderboard unavailable.")

else:
    # race chart: simple final points bar (or positions)
    race_tbl = _race_results_table(session)
    if race_tbl.empty or "Points" not in race_tbl.columns:
        st.caption("Race chart unavailable (no race results/points).")
    else:
        d = race_tbl.copy()
        # ensure Driver exists
        if "Driver" in d.columns:
            fig = go.Figure(go.Bar(x=d["Driver"], y=d["Points"], name="Points"))
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10), title="Race Chart: Points")
            st.plotly_chart(fig, use_container_width=True)

st.divider()

# ----------------------------
# Session Summary Cards (winners)
# ----------------------------
st.subheader("Session Summary Cards (winners)")

# Use fastest lap telemetry per driver (subset to keep performance reasonable)
# Let user choose how many drivers to evaluate
max_drivers = min(12, len(drivers))
n_eval = st.slider("Drivers to evaluate (fastest-lap telemetry)", 2, max_drivers, value=min(8, max_drivers))

# pick fastest drivers by LapTime to evaluate
laps_valid = laps[laps["LapTime"].notna()].copy()
if "IsAccurate" in laps_valid.columns:
    laps_valid = laps_valid[laps_valid["IsAccurate"] == True]

best_idx = laps_valid.groupby("Driver")["LapTime"].idxmin()
best = laps_valid.loc[best_idx].copy()
best = best.sort_values("LapTime").head(n_eval)

rows = []
for _, r in best.iterrows():
    drv = r["Driver"]
    try:
        tel = r.get_telemetry().copy()
        tel = _ensure_distance(tel)
        tel_r = _resample_to_distance(tel, step_m=3.0)

        top_speed = float(np.nanmax(tel_r["Speed"])) if "Speed" in tel_r.columns else np.nan
        braking = _compute_braking_efficiency(tel_r)
        traction = _compute_low_speed_traction(tel_r)

        corners_df = _detect_corners_from_circuit_info(session, tel_r)
        slow_cs, med_cs, high_cs = _compute_corner_strengths(corners_df)

        rows.append(
            {
                "Driver": drv,
                "TopSpeed": top_speed,
                "Braking": braking,
                "LowSpeedTraction": traction,
                "SlowCornerStrength": slow_cs,
                "MedCornerStrength": med_cs,
                "HighCornerStrength": high_cs,
            }
        )
    except Exception:
        rows.append(
            {
                "Driver": drv,
                "TopSpeed": np.nan,
                "Braking": np.nan,
                "LowSpeedTraction": np.nan,
                "SlowCornerStrength": np.nan,
                "MedCornerStrength": np.nan,
                "HighCornerStrength": np.nan,
            }
        )

scores = pd.DataFrame(rows)
deg_tbl = _simple_deg_scores(laps)

# pick winners
def pick_winner(df, col, higher_is_better=True):
    if df.empty or col not in df.columns:
        return None, np.nan
    s = pd.to_numeric(df[col], errors="coerce")
    if s.isna().all():
        return None, np.nan
    idx = s.idxmax() if higher_is_better else s.idxmin()
    return str(df.loc[idx, "Driver"]), float(s.loc[idx])

w_straight, v_straight = pick_winner(scores, "TopSpeed", True)
w_brake, v_brake = pick_winner(scores, "Braking", True)
w_trac, v_trac = pick_winner(scores, "LowSpeedTraction", True)
w_med, v_med = pick_winner(scores, "MedCornerStrength", True)
w_high, v_high = pick_winner(scores, "HighCornerStrength", True)

# Tire deg: lower slope is better
w_deg, v_deg = (None, np.nan)
if not deg_tbl.empty:
    w_deg = str(deg_tbl.iloc[0]["Driver"])
    v_deg = float(deg_tbl.iloc[0]["Deg_s_per_lap"])

c1, c2, c3 = st.columns(3)
c1.metric("Top straight-line speed", f"{w_straight or '—'}", f"{v_straight:.1f} kph" if np.isfinite(v_straight) else "")
c2.metric("Best low-speed traction", f"{w_trac or '—'}", f"{v_trac:.1f} avg throttle" if np.isfinite(v_trac) else "")
c3.metric("Best braking efficiency", f"{w_brake or '—'}", f"{v_brake:.4f} kph/m" if np.isfinite(v_brake) else "")

c4, c5, c6 = st.columns(3)
c4.metric("Best medium-speed corner strength", f"{w_med or '—'}", f"{v_med:.1f} kph" if np.isfinite(v_med) else "")
c5.metric("Best high-speed corner strength", f"{w_high or '—'}", f"{v_high:.1f} kph" if np.isfinite(v_high) else "")
c6.metric("Tire Degradation Resistance", f"{w_deg or '—'}", f"{v_deg:.3f} s/lap" if np.isfinite(v_deg) else "")

with st.expander("Show raw metrics table (debug)", expanded=False):
    st.dataframe(scores, use_container_width=True)
    if not deg_tbl.empty:
        st.caption("Degradation (lower slope = better):")
        st.dataframe(deg_tbl, use_container_width=True)
