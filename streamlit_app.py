# streamlit_app.py
"""
MAIN APP (Home/Dashboard lives HERE)

✅ Fixes you asked for:
- Merges the “Home/Dashboard” into streamlit_app.py so your app doesn’t look weird / duplicated.
  → IMPORTANT: delete or rename pages/01_Home.py (otherwise you’ll have two “Home” pages).
- Drivers show abbreviated codes (VER, HAM…) not numbers.
- Event dropdown shows date prefix like: 02-20 Bahrain Grand Prix (so you can distinguish).
- If the event is pre-season testing, sessions display as: Session 1 / Session 2 / Session 3.

Also:
- Creates FastF1 cache folder automatically (fixes NotADirectoryError).
- Stores a shared bundle in st.session_state["bundle"] used by your other pages.
"""

from __future__ import annotations

import os
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

import fastf1


# ----------------------------
# FastF1 cache (critical for Streamlit Cloud)
# ----------------------------
def init_fastf1_cache(cache_dir: str = ".fastf1_cache") -> str:
    p = Path(cache_dir)
    p.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(p))
    return str(p)


# ----------------------------
# Event + session selectors
# ----------------------------
@st.cache_data(show_spinner=False, ttl=24 * 3600)
def get_event_schedule(year: int) -> pd.DataFrame:
    # FastF1 schedule with EventName + EventDate
    sched = fastf1.get_event_schedule(year)
    # Normalize date
    if "EventDate" in sched.columns:
        sched["EventDate"] = pd.to_datetime(sched["EventDate"], errors="coerce")
    return sched


def is_preseason_event(event_name: str) -> bool:
    e = (event_name or "").lower()
    return ("pre-season" in e) or ("preseason" in e) or ("testing" in e) or ("test" in e)


def fmt_event_label(event_row: pd.Series) -> str:
    name = str(event_row.get("EventName", ""))
    d = event_row.get("EventDate", pd.NaT)
    if pd.isna(d):
        return name
    # MM-DD
    return f"{pd.to_datetime(d).strftime('%m-%d')} {name}"


def build_event_options(schedule: pd.DataFrame):
    # returns list of labels + mapping label -> eventName
    opts = []
    mapping = {}
    for _, r in schedule.iterrows():
        label = fmt_event_label(r)
        name = str(r.get("EventName", label))
        opts.append(label)
        mapping[label] = name
    return opts, mapping


# We “probe” for sessions to avoid guessing formats.
# This is fast enough because it's cached, and we stop early.
COMMON_SESSIONS = ["FP1", "FP2", "FP3", "Q", "SQ", "S", "R"]


@st.cache_data(show_spinner=False, ttl=6 * 3600)
def available_sessions(year: int, event_name: str) -> list[str]:
    ok = []
    for s in COMMON_SESSIONS:
        try:
            sess = fastf1.get_session(year, event_name, s)
            # Only keep if it can load metadata (doesn't fully download telemetry)
            _ = sess.event  # triggers minimal fetch
            ok.append(s)
        except Exception:
            continue

    # Pre-season testing is usually not FP/Q/R in a normal way.
    # If nothing found and event looks like testing, offer Session 1/2/3.
    if not ok and is_preseason_event(event_name):
        return ["Session 1", "Session 2", "Session 3"]

    return ok if ok else ["FP1", "FP2", "FP3", "Q", "R"]


def normalize_session_code(event_name: str, ui_choice: str) -> str:
    """
    Convert UI label -> FastF1 session code.
    For testing: map Session 1/2/3 -> FP1/FP2/FP3 (best practical mapping).
    """
    if ui_choice.startswith("Session") and is_preseason_event(event_name):
        if "1" in ui_choice:
            return "FP1"
        if "2" in ui_choice:
            return "FP2"
        if "3" in ui_choice:
            return "FP3"
    return ui_choice


def display_session_label(event_name: str, session_code: str) -> str:
    if is_preseason_event(event_name) and session_code in ["FP1", "FP2", "FP3"]:
        return {"FP1": "Session 1", "FP2": "Session 2", "FP3": "Session 3"}[session_code]
    return session_code


# ----------------------------
# Data loading (cached)
# ----------------------------
@st.cache_data(show_spinner=False, ttl=3 * 3600)
def load_session(year: int, event_name: str, session_code: str):
    s = fastf1.get_session(year, event_name, session_code)
    s.load(telemetry=True, weather=True, messages=False)
    return s


def get_driver_code_map(session) -> dict:
    """
    Try to ensure 'Driver' shows abbreviations like VER, HAM.
    Most of the time FastF1 laps['Driver'] already is the 3-letter code.
    If it looks numeric, map using results (if available).
    """
    mapping = {}
    try:
        res = session.results.copy()
        if "DriverNumber" in res.columns and "Abbreviation" in res.columns:
            for _, r in res.iterrows():
                mapping[str(r["DriverNumber"])] = str(r["Abbreviation"])
    except Exception:
        pass
    return mapping


def normalize_driver_codes(laps: pd.DataFrame, code_map: dict) -> pd.DataFrame:
    df = laps.copy()
    if "Driver" not in df.columns:
        return df
    # If driver values look numeric, map them
    # (Some datasets might have DriverNumber used as Driver)
    df["Driver"] = df["Driver"].astype(str)
    df["Driver"] = df["Driver"].apply(lambda x: code_map.get(x, x))
    return df


# ----------------------------
# Home page helpers (from your 01_Home.py, cleaned)
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

    # Sector markers (only if XY exists)
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
    if "S1" in best.columns: out["S1"] = best["S1"]
    if "S2" in best.columns: out["S2"] = best["S2"]
    if "S3" in best.columns: out["S3"] = best["S3"]
    if "Compound" in best.columns: out["Tire"] = best["Compound"]
    if "TyreLife" in best.columns: out["TyreLife"] = best["TyreLife"]

    # Top speed placeholder (optional compute)
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
# Streamlit page config
# ----------------------------
st.set_page_config(layout="wide", page_title="Formula Performance Dashboard")

# Init cache once
init_fastf1_cache(".fastf1_cache")

# ----------------------------
# Top bar inputs (Season / Event / Session)
# ----------------------------
st.title("Formula Performance Dashboard")

top1, top2, top3 = st.columns([1, 2, 1])

with top1:
    year = st.selectbox("Season", options=list(range(2018, 2027)), index=list(range(2018, 2027)).index(2025) if 2025 in range(2018, 2027) else 0)

schedule = get_event_schedule(int(year))
event_labels, event_map = build_event_options(schedule)

# Default to first non-empty
default_event_label = event_labels[0] if event_labels else ""
with top2:
    event_label = st.selectbox("Event", options=event_labels, index=0)
event_name = event_map.get(event_label, event_label)

sessions = available_sessions(int(year), str(event_name))
# show preseason “Session 1/2/3” in UI if needed
ui_sessions = []
for s in sessions:
    if s.startswith("Session"):
        ui_sessions.append(s)
    else:
        ui_sessions.append(display_session_label(event_name, s))

with top3:
    session_ui = st.selectbox("Session", options=ui_sessions, index=0)

session_code = normalize_session_code(event_name, session_ui)

# Load button (prevents reloading constantly)
load_now = st.button("Load session", use_container_width=True)

# Auto-load first time
if "bundle" not in st.session_state:
    load_now = True

if load_now:
    with st.spinner("Loading session (FastF1)..."):
        session = load_session(int(year), str(event_name), str(session_code))
        laps = session.laps.copy()

        # ensure driver abbreviations
        code_map = get_driver_code_map(session)
        laps = normalize_driver_codes(laps, code_map)

        drivers = sorted([d for d in laps["Driver"].dropna().astype(str).unique().tolist()]) if "Driver" in laps.columns else []
        is_race = (session_code == "R")

        st.session_state["bundle"] = {
            "year": int(year),
            "event": str(event_name),
            "event_label": str(event_label),
            "session_name": str(session_code),  # canonical code for other pages
            "session_label": str(session_ui),   # what user sees (Session 1, etc.)
            "session": session,
            "laps": laps,
            "drivers": drivers,
            "is_race": is_race,
        }

# ----------------------------
# HOME / DASHBOARD (merged)
# ----------------------------
bundle = st.session_state.get("bundle")
if not bundle:
    st.stop()

session = bundle["session"]
laps = bundle["laps"]
drivers = bundle["drivers"]
is_race = bool(bundle.get("is_race", False))

st.caption(f"{bundle['year']} • {bundle['event_label']} • {bundle['session_label']}")

# Track map + conditions
left, right = st.columns([1.2, 1])

with left:
    st.subheader("Track Map")

    laps_valid = laps[laps["LapTime"].notna()].copy()
    if "IsAccurate" in laps_valid.columns:
        laps_valid = laps_valid[laps_valid["IsAccurate"] == True]

    if laps_valid.empty:
        st.warning("No valid laps found for this session.")
        st.stop()

    overall_fast = laps_valid.loc[laps_valid["LapTime"].idxmin()]
    default_driver = str(overall_fast["Driver"])

    map_driver = st.selectbox("Map base driver", options=sorted(drivers), index=sorted(drivers).index(default_driver) if default_driver in drivers else 0)
    map_lap_row = laps_valid[laps_valid["Driver"] == map_driver].sort_values("LapTime").head(1)

    if map_lap_row.empty:
        st.warning("No valid lap for selected driver.")
        st.stop()

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

# Tables: Fastest laps or Race results
if not is_race:
    st.subheader("Fastest Laps (non-race session)")
    fast_tbl = _fastest_laps_table(laps)

    with st.expander("Compute Top Speed from telemetry (optional)", expanded=False):
        if st.button("Compute Top Speed"):
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

st.divider()

st.info(
    "✅ Home/Dashboard is now inside streamlit_app.py.\n\n"
    "If you still have `pages/01_Home.py`, Streamlit will show a duplicate Home page.\n"
    "➡️ Delete it or rename it (e.g., `pages/01_Home_old.py`)."
)
