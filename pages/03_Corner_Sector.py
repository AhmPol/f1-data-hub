# pages/03_Corner_Sector.py
"""
CORNER & SECTOR BREAKDOWN

Matches your spec:
1) Sector Summary:
   - S1 / S2 / S3 time deltas
   - Who wins each sector and by how much

2) Corner Table (by corner):
   - Entry speed
   - Min speed
   - Exit speed
   - Braking start point (distance proxy)
   - Throttle-on point
   - Time delta in corner segment (vs reference driver)

3) Corner-type grouping:
   - Low-speed / Medium-speed / High-speed corners
   - Shows averages + rankings by groups
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st


# ----------------------------
# Helpers
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

    for col in ["Speed", "Throttle", "Brake", "nGear", "RPM"]:
        if col in tel.columns:
            out[col] = np.interp(grid, d, tel[col].to_numpy(dtype=float))

    # Time interpolation for corner segment time
    if "Time" in tel.columns:
        t = tel["Time"]
        if len(t) > 0 and hasattr(t.iloc[0], "total_seconds"):
            tsec = t.dt.total_seconds().to_numpy(dtype=float)
        else:
            tsec = pd.to_numeric(t, errors="coerce").to_numpy(dtype=float)
        if np.isfinite(tsec).any():
            out["Time_s"] = np.interp(grid, d, tsec)

    return out


def _corner_type(min_speed_kph: float) -> str:
    if not np.isfinite(min_speed_kph):
        return "Unknown"
    if min_speed_kph < 120:
        return "Low"
    if min_speed_kph < 200:
        return "Medium"
    return "High"


def _get_circuit_corners(session) -> pd.DataFrame:
    """
    Prefer official corner distances from FastF1 circuit info.
    Returns columns: Number, Distance (meters).
    """
    try:
        ci = session.get_circuit_info()
        corners = ci.corners.copy()
    except Exception:
        return pd.DataFrame()

    if corners is None or corners.empty:
        return pd.DataFrame()

    keep = [c for c in ["Number", "Distance"] if c in corners.columns]
    if "Number" not in keep or "Distance" not in keep:
        return pd.DataFrame()

    corners = corners[keep].dropna().copy()
    corners["Number"] = corners["Number"].astype(int)
    corners["Distance"] = corners["Distance"].astype(float)
    corners = corners.sort_values("Number")
    return corners


def _valid_laps(laps: pd.DataFrame, drivers: list[str]) -> pd.DataFrame:
    df = laps.copy()
    df = df[df["Driver"].isin(drivers)]
    df = df[df["LapTime"].notna()]
    if "IsAccurate" in df.columns:
        df = df[df["IsAccurate"] == True]
    # keep only laps with sector times if available
    return df


def _fastest_lap_per_driver(laps: pd.DataFrame, drivers: list[str]) -> pd.DataFrame:
    df = _valid_laps(laps, drivers)
    if df.empty:
        return df
    idx = df.groupby("Driver")["LapTime"].idxmin()
    return df.loc[idx].sort_values("LapTime")


def _sector_summary(fastest: pd.DataFrame) -> pd.DataFrame:
    """
    Returns table with LapTime and sector deltas to best sector times.
    """
    if fastest.empty:
        return pd.DataFrame()

    out = fastest.copy()
    # Ensure columns exist
    for c in ["Sector1Time", "Sector2Time", "Sector3Time", "LapTime"]:
        if c not in out.columns:
            out[c] = pd.NaT

    # Convert to seconds for deltas
    out["S1_s"] = out["Sector1Time"].apply(_to_seconds)
    out["S2_s"] = out["Sector2Time"].apply(_to_seconds)
    out["S3_s"] = out["Sector3Time"].apply(_to_seconds)
    out["Lap_s"] = out["LapTime"].apply(_to_seconds)

    # Deltas to best
    for s in ["S1_s", "S2_s", "S3_s"]:
        best = np.nanmin(out[s].to_numpy(dtype=float))
        out[s.replace("_s", "_delta_s")] = out[s] - best

    # Pretty display
    disp = out[["Driver", "Lap_s", "S1_s", "S2_s", "S3_s", "S1_delta_s", "S2_delta_s", "S3_delta_s"]].copy()
    disp = disp.sort_values("Lap_s")
    return disp


def _compute_corner_metrics_for_driver(
    tel_r: pd.DataFrame,
    corners: pd.DataFrame,
    window_m: float = 60.0,
    brake_thresh: float = 0.5,
    throttle_thresh: float = 90.0,
) -> pd.DataFrame:
    """
    For each official corner distance, compute:
    EntrySpeed, MinSpeed, ExitSpeed,
    BrakeStart_m (distance), ThrottleOn_m (distance),
    SegTime_s (segment duration)
    """
    if tel_r.empty or corners.empty:
        return pd.DataFrame()

    if "Distance" not in tel_r.columns or "Speed" not in tel_r.columns:
        return pd.DataFrame()

    d = tel_r["Distance"].to_numpy(dtype=float)
    v = tel_r["Speed"].to_numpy(dtype=float)

    has_brake = "Brake" in tel_r.columns
    has_throttle = "Throttle" in tel_r.columns
    has_time = "Time_s" in tel_r.columns

    rows = []
    for _, cr in corners.iterrows():
        cn = int(cr["Number"])
        cd = float(cr["Distance"])

        m = (d >= cd - window_m) & (d <= cd + window_m)
        if not np.any(m):
            continue

        seg = tel_r.loc[m].copy()
        if seg.empty:
            continue

        # Entry/min/exit
        entry = float(seg["Speed"].iloc[0])
        exitv = float(seg["Speed"].iloc[-1])

        seg_speed = seg["Speed"].to_numpy(dtype=float)
        min_idx_local = int(np.nanargmin(seg_speed))
        min_speed = float(seg_speed[min_idx_local])
        # global distance at min
        d_min = float(seg["Distance"].iloc[min_idx_local])

        # Brake start: first point before min where Brake > thresh
        brake_start = np.nan
        if has_brake:
            pre = seg[seg["Distance"] <= d_min]
            hit = pre[pre["Brake"] > brake_thresh]
            if not hit.empty:
                brake_start = float(hit["Distance"].iloc[0])

        # Throttle-on: first point after min where Throttle > thresh
        throttle_on = np.nan
        if has_throttle:
            post = seg[seg["Distance"] >= d_min]
            hit = post[post["Throttle"] > throttle_thresh]
            if not hit.empty:
                throttle_on = float(hit["Distance"].iloc[0])

        # Segment time
        seg_time = np.nan
        if has_time:
            seg_time = float(seg["Time_s"].iloc[-1] - seg["Time_s"].iloc[0])

        rows.append(
            {
                "Corner": cn,
                "CornerDistance": cd,
                "EntrySpeed": entry,
                "MinSpeed": min_speed,
                "ExitSpeed": exitv,
                "BrakeStart_m": brake_start,
                "ThrottleOn_m": throttle_on,
                "SegTime_s": seg_time,
                "Type": _corner_type(min_speed),
                "SegStart_m": float(seg["Distance"].iloc[0]),
                "SegEnd_m": float(seg["Distance"].iloc[-1]),
            }
        )

    return pd.DataFrame(rows).sort_values("Corner")


def _corner_time_delta_vs_ref(driver_corner: pd.DataFrame, ref_corner: pd.DataFrame) -> pd.Series:
    """
    Compute time delta per corner segment vs reference:
      delta = driver SegTime_s - ref SegTime_s  (positive means slower)
    Requires SegTime_s present.
    """
    if driver_corner.empty or ref_corner.empty:
        return pd.Series(dtype=float)
    if "SegTime_s" not in driver_corner.columns or "SegTime_s" not in ref_corner.columns:
        return pd.Series(dtype=float)

    m = driver_corner.merge(ref_corner[["Corner", "SegTime_s"]], on="Corner", how="left", suffixes=("", "_ref"))
    return (m["SegTime_s"] - m["SegTime_s_ref"]).rename("CornerDelta_s")


def _group_summary(corner_table_all: pd.DataFrame, score_col: str, lower_is_better: bool):
    """
    corner_table_all contains rows for multiple drivers with 'Type' and score_col.
    Returns per-driver averages by corner-type + ranking.
    """
    if corner_table_all.empty or score_col not in corner_table_all.columns:
        return pd.DataFrame()

    grp = (
        corner_table_all.groupby(["Driver", "Type"])[score_col]
        .mean(numeric_only=True)
        .reset_index()
        .pivot(index="Driver", columns="Type", values=score_col)
        .reset_index()
    )

    # Rank each type
    for t in ["Low", "Medium", "High"]:
        if t in grp.columns:
            grp[f"{t}_Rank"] = grp[t].rank(ascending=lower_is_better, method="min")

    return grp


# ----------------------------
# Page
# ----------------------------
st.set_page_config(layout="wide")
st.title("Corner & Sector Breakdown")

if "bundle" not in st.session_state:
    st.error("Session bundle not loaded. Open the main page first.")
    st.stop()

bundle = st.session_state["bundle"]
session = bundle["session"]
laps = bundle["laps"]
drivers_all = sorted(bundle["drivers"])

# Inputs
c1, c2, c3 = st.columns([2, 2, 1])
with c1:
    drivers = st.multiselect("Drivers", drivers_all, default=drivers_all[:2] if len(drivers_all) >= 2 else drivers_all)
with c2:
    reference_driver = st.selectbox("Reference (corner deltas)", options=drivers if drivers else drivers_all)
with c3:
    window_m = st.slider("Corner window (± meters)", 25, 120, 60, 5)

if not drivers:
    st.warning("Select at least one driver.")
    st.stop()

# Fastest lap per driver (for sector summary + corner metrics)
fastest = _fastest_lap_per_driver(laps, drivers)
if fastest.empty:
    st.error("No valid laps found for the selected drivers.")
    st.stop()

# ----------------------------
# Sector Summary
# ----------------------------
st.subheader("Sector Summary (fastest lap per driver)")

sec = _sector_summary(fastest)
if sec.empty:
    st.caption("Sector times not available for this session.")
else:
    # Winner callouts
    def winner(col):
        s = sec[["Driver", col]].dropna()
        if s.empty:
            return "—"
        best_i = s[col].astype(float).idxmin()
        drv = sec.loc[best_i, "Driver"]
        val = sec.loc[best_i, col]
        return f"{drv} ({val:.3f}s)"

    w1 = winner("S1_s")
    w2 = winner("S2_s")
    w3 = winner("S3_s")

    a, b, c = st.columns(3)
    a.metric("S1 Winner", w1)
    b.metric("S2 Winner", w2)
    c.metric("S3 Winner", w3)

    st.dataframe(sec, use_container_width=True)

st.divider()

# ----------------------------
# Corner Table
# ----------------------------
st.subheader("Corner Table (fastest lap telemetry per driver)")

corners = _get_circuit_corners(session)
if corners.empty:
    st.warning("No official circuit corner distances available from FastF1 for this session.")
    st.stop()

# Build corner tables for each driver
corner_tables = {}
corner_tables_all = []

with st.spinner("Computing corner metrics from telemetry..."):
    for drv in drivers:
        lap_row = fastest[fastest["Driver"] == drv]
        if lap_row.empty:
            continue
        lap = lap_row.iloc[0]
        try:
            tel = lap.get_telemetry().copy()
            tel_r = _resample_to_distance(tel, step_m=2.0)
            ct = _compute_corner_metrics_for_driver(tel_r, corners, window_m=float(window_m))
            ct.insert(0, "Driver", drv)
            corner_tables[drv] = ct
            corner_tables_all.append(ct)
        except Exception:
            corner_tables[drv] = pd.DataFrame()

if not corner_tables_all:
    st.error("Could not compute corner tables (telemetry may be missing for this session).")
    st.stop()

corner_all = pd.concat(corner_tables_all, ignore_index=True)

# Add corner delta vs reference
ref_ct = corner_tables.get(reference_driver, pd.DataFrame())
if not ref_ct.empty and "SegTime_s" in ref_ct.columns:
    # Compute deltas per driver and attach
    delta_rows = []
    for drv, ct in corner_tables.items():
        if ct is None or ct.empty:
            continue
        if drv == reference_driver:
            tmp = ct.copy()
            tmp["CornerDelta_s"] = 0.0
        else:
            tmp = ct.copy()
            tmp["CornerDelta_s"] = _corner_time_delta_vs_ref(tmp, ref_ct).to_numpy(dtype=float)
        delta_rows.append(tmp)
    corner_all = pd.concat(delta_rows, ignore_index=True)

# Display corner table (sortable/filterable via Streamlit UI)
display_cols = [
    "Driver",
    "Corner",
    "Type",
    "EntrySpeed",
    "MinSpeed",
    "ExitSpeed",
    "BrakeStart_m",
    "ThrottleOn_m",
    "SegTime_s",
    "CornerDelta_s",
]
display_cols = [c for c in display_cols if c in corner_all.columns]
st.dataframe(corner_all[display_cols].sort_values(["Corner", "Driver"]), use_container_width=True)

st.divider()

# ----------------------------
# Corner-type Grouping: averages + rankings
# ----------------------------
st.subheader("Corner-type Grouping (averages + rankings)")

# 1) Speed-based strength (higher avg MinSpeed is better)
speed_group = _group_summary(corner_all, "MinSpeed", lower_is_better=False)
if not speed_group.empty:
    st.caption("Higher average **MinSpeed** in a corner group = stronger pace in that corner type (proxy).")
    st.dataframe(speed_group, use_container_width=True)

# 2) Time-based performance (lower avg SegTime_s is better)
time_group = _group_summary(corner_all, "SegTime_s", lower_is_better=True)
if not time_group.empty:
    st.caption("Lower average **SegTime_s** in a corner group = faster through that corner type (proxy).")
    st.dataframe(time_group, use_container_width=True)

# 3) Delta-based (vs reference): lower avg CornerDelta_s is better
if "CornerDelta_s" in corner_all.columns:
    delta_group = _group_summary(corner_all, "CornerDelta_s", lower_is_better=True)
    if not delta_group.empty:
        st.caption(f"Average **CornerDelta_s** vs **{reference_driver}** (lower = better).")
        st.dataframe(delta_group, use_container_width=True)

with st.expander("Notes / limitations (for now)", expanded=False):
    st.markdown(
        """
- Corner distances are taken from **FastF1 circuit info**. The window (± meters) controls how wide each corner segment is.
- Braking start and throttle-on are **distance proxies** based on thresholds (`Brake > 0.5`, `Throttle > 90%`).
- Corner time deltas require telemetry time (`Time_s`). If delta columns are blank, that session likely lacks usable telemetry time.
"""
    )
