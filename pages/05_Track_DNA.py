# pages/05_Track_DNA.py
"""
TRACK DNA

Implements your spec (best-effort with FastF1 data):

Track profile:
- Corner speed distribution (histogram of min speeds near official corner distances)
- Counts: low / medium / high-speed corners
- Straights length (approx from high-speed segments on distance-speed telemetry)
- Braking zone count + intensity (proxy from decel)

Track fingerprint vector (numeric signature you can store per track):
- pct_low_corners
- pct_med_corners
- pct_high_corners
- avg_braking_intensity (proxy)
- straight_dominance_score
- traction_demand_score
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go


# ----------------------------
# Helpers
# ----------------------------
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

    # Time in seconds (optional)
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
    Official corner list from FastF1 circuit info.
    Needs Number + Distance.
    """
    try:
        ci = session.get_circuit_info()
        corners = ci.corners.copy()
    except Exception:
        return pd.DataFrame()

    if corners is None or corners.empty:
        return pd.DataFrame()

    if "Number" not in corners.columns or "Distance" not in corners.columns:
        return pd.DataFrame()

    out = corners[["Number", "Distance"]].dropna().copy()
    out["Number"] = out["Number"].astype(int)
    out["Distance"] = out["Distance"].astype(float)
    out = out.sort_values("Number")
    return out


def _fastest_lap(session_laps: pd.DataFrame):
    df = session_laps.copy()
    df = df[df["LapTime"].notna()]
    if "IsAccurate" in df.columns:
        df = df[df["IsAccurate"] == True]
    if df.empty:
        return None
    return df.loc[df["LapTime"].idxmin()]


def _corner_min_speeds(tel_r: pd.DataFrame, corners: pd.DataFrame, window_m: float = 60.0) -> pd.DataFrame:
    """
    For each official corner distance, compute min speed within ±window_m.
    """
    if tel_r.empty or corners.empty:
        return pd.DataFrame()
    if "Distance" not in tel_r.columns or "Speed" not in tel_r.columns:
        return pd.DataFrame()

    d = tel_r["Distance"].to_numpy(dtype=float)
    v = tel_r["Speed"].to_numpy(dtype=float)

    rows = []
    for _, cr in corners.iterrows():
        cn = int(cr["Number"])
        cd = float(cr["Distance"])
        m = (d >= cd - window_m) & (d <= cd + window_m)
        if not np.any(m):
            continue
        min_v = float(np.nanmin(v[m]))
        rows.append({"Corner": cn, "CornerDistance": cd, "MinSpeed": min_v, "Type": _corner_type(min_v)})
    return pd.DataFrame(rows).sort_values("Corner")


def _decel_proxy(tel_r: pd.DataFrame):
    """
    Decel proxy: -dSpeed/dDistance (kph per meter).
    """
    if tel_r.empty or "Speed" not in tel_r.columns or "Distance" not in tel_r.columns:
        return np.array([])

    v = tel_r["Speed"].to_numpy(dtype=float)
    d = tel_r["Distance"].to_numpy(dtype=float)
    dv = np.diff(v)
    dd = np.diff(d)
    with np.errstate(divide="ignore", invalid="ignore"):
        decel = -dv / dd  # kph/m
    return decel[np.isfinite(decel)]


def _braking_zones(tel_r: pd.DataFrame, decel_threshold: float = 0.25, min_len_m: float = 25.0):
    """
    Identify braking zones by contiguous samples where decel > threshold.
    Returns:
      count, avg_intensity, max_intensity
    Intensity proxy uses kph/m.
    """
    if tel_r.empty or "Speed" not in tel_r.columns or "Distance" not in tel_r.columns:
        return 0, np.nan, np.nan

    v = tel_r["Speed"].to_numpy(dtype=float)
    d = tel_r["Distance"].to_numpy(dtype=float)
    dv = np.diff(v)
    dd = np.diff(d)
    with np.errstate(divide="ignore", invalid="ignore"):
        decel = -dv / dd  # kph/m

    m = np.isfinite(decel) & (decel > decel_threshold)
    if not np.any(m):
        return 0, np.nan, np.nan

    # contiguous segments in m
    zones = []
    start = None
    for i, flag in enumerate(m):
        if flag and start is None:
            start = i
        if (not flag) and start is not None:
            end = i - 1
            zones.append((start, end))
            start = None
    if start is not None:
        zones.append((start, len(m) - 1))

    # filter by minimum length in meters
    kept = []
    for s, e in zones:
        # segment covers d[s] .. d[e+1]
        length = float(d[e + 1] - d[s]) if (e + 1) < len(d) else float(d[e] - d[s])
        if length >= min_len_m:
            kept.append((s, e))

    if not kept:
        return 0, np.nan, np.nan

    intensities = []
    for s, e in kept:
        intensities.append(float(np.nanmean(decel[s : e + 1])))

    return len(kept), float(np.nanmean(intensities)), float(np.nanmax(intensities))


def _straight_stats(tel_r: pd.DataFrame, speed_threshold: float = 280.0, min_len_m: float = 120.0):
    """
    Approximate straights as contiguous distance segments where Speed >= threshold.
    Returns:
      straight_count, total_straight_m, longest_straight_m, straight_dominance_score (0-1)
    """
    if tel_r.empty or "Speed" not in tel_r.columns or "Distance" not in tel_r.columns:
        return 0, np.nan, np.nan, np.nan

    v = tel_r["Speed"].to_numpy(dtype=float)
    d = tel_r["Distance"].to_numpy(dtype=float)

    m = np.isfinite(v) & (v >= speed_threshold)
    if not np.any(m):
        return 0, 0.0, 0.0, 0.0

    segs = []
    start = None
    for i, flag in enumerate(m):
        if flag and start is None:
            start = i
        if (not flag) and start is not None:
            segs.append((start, i - 1))
            start = None
    if start is not None:
        segs.append((start, len(m) - 1))

    lengths = []
    for s, e in segs:
        length = float(d[e] - d[s])
        if length >= min_len_m:
            lengths.append(length)

    if not lengths:
        return 0, 0.0, 0.0, 0.0

    total = float(np.sum(lengths))
    longest = float(np.max(lengths))
    track_len = float(np.nanmax(d) - np.nanmin(d)) if np.isfinite(d).any() else np.nan
    dominance = float(total / track_len) if np.isfinite(track_len) and track_len > 0 else np.nan
    return int(len(lengths)), total, longest, dominance


def _traction_demand_score(corner_df: pd.DataFrame):
    """
    Proxy traction demand:
    - More low-speed corners => higher traction demand.
    Return 0-1.
    """
    if corner_df is None or corner_df.empty:
        return np.nan
    total = len(corner_df)
    if total == 0:
        return np.nan
    low = int((corner_df["Type"] == "Low").sum())
    med = int((corner_df["Type"] == "Medium").sum())
    # give low corners more weight, medium some weight
    score = (1.0 * low + 0.4 * med) / total
    return float(np.clip(score, 0.0, 1.0))


def _corner_mix(corner_df: pd.DataFrame):
    if corner_df is None or corner_df.empty:
        return np.nan, np.nan, np.nan
    total = len(corner_df)
    if total == 0:
        return np.nan, np.nan, np.nan
    low = float((corner_df["Type"] == "Low").sum()) / total
    med = float((corner_df["Type"] == "Medium").sum()) / total
    high = float((corner_df["Type"] == "High").sum()) / total
    return low, med, high


# ----------------------------
# Page
# ----------------------------
st.set_page_config(layout="wide")
st.title("Track DNA")

if "bundle" not in st.session_state:
    st.error("Session bundle not loaded. Open the main page first.")
    st.stop()

bundle = st.session_state["bundle"]
session = bundle["session"]
laps = bundle["laps"]

st.caption(f"{bundle['year']} • {bundle['event']} • {bundle['session_name']}")

# Choose which lap to use for DNA (default fastest)
lap_mode = st.radio("Base lap for Track DNA", ["Fastest lap overall", "Choose a driver (their fastest lap)"], horizontal=True)

base_lap = None
if lap_mode == "Fastest lap overall":
    base_lap = _fastest_lap(laps)
else:
    drv = st.selectbox("Driver", options=sorted(bundle["drivers"]))
    df = laps[(laps["Driver"] == drv) & laps["LapTime"].notna()].copy()
    if "IsAccurate" in df.columns:
        df = df[df["IsAccurate"] == True]
    base_lap = df.loc[df["LapTime"].idxmin()] if not df.empty else None

if base_lap is None:
    st.error("Could not find a suitable base lap (no valid laps).")
    st.stop()

# Load & resample telemetry
with st.spinner("Building telemetry for Track DNA..."):
    tel = base_lap.get_telemetry().copy()
    tel_r = _resample_to_distance(tel, step_m=2.0)

if tel_r.empty or "Speed" not in tel_r.columns:
    st.error("Telemetry not available for this session/lap.")
    st.stop()

# Corner info
corners = _get_circuit_corners(session)
if corners.empty:
    st.warning("Circuit corner distances not available from FastF1. Corner-based DNA will be limited.")

window_m = st.slider("Corner window (± meters)", 25, 120, 60, 5)
corner_df = _corner_min_speeds(tel_r, corners, window_m=float(window_m)) if not corners.empty else pd.DataFrame()

# ----------------------------
# Track Profile
# ----------------------------
st.subheader("Track profile")

c1, c2, c3 = st.columns([1.2, 1, 1])

# Corner histogram
with c1:
    st.markdown("**Corner speed distribution (min speeds)**")
    if corner_df.empty:
        st.caption("No corner speed distribution available (missing circuit corners).")
    else:
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=corner_df["MinSpeed"], nbinsx=18, name="MinSpeed (kph)"))
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), xaxis_title="kph", yaxis_title="count")
        st.plotly_chart(fig, use_container_width=True)

# Corner counts
with c2:
    st.markdown("**Corner type counts**")
    if corner_df.empty:
        st.metric("Low-speed", "—")
        st.metric("Medium-speed", "—")
        st.metric("High-speed", "—")
    else:
        counts = corner_df["Type"].value_counts().to_dict()
        st.metric("Low-speed", int(counts.get("Low", 0)))
        st.metric("Medium-speed", int(counts.get("Medium", 0)))
        st.metric("High-speed", int(counts.get("High", 0)))

# Straights + braking
with c3:
    st.markdown("**Straights + braking zones (approx)**")
    straight_count, total_straight_m, longest_straight_m, straight_dom = _straight_stats(
        tel_r, speed_threshold=float(st.slider("Straight speed threshold (kph)", 240, 330, 280, 5)), min_len_m=120.0
    )
    bz_count, bz_avg, bz_max = _braking_zones(tel_r, decel_threshold=float(st.slider("Braking intensity threshold (kph/m)", 0.10, 0.60, 0.25, 0.01)))

    st.metric("Straight count", straight_count)
    st.metric("Total straight (m)", f"{total_straight_m:.0f}")
    st.metric("Braking zones", bz_count)

st.divider()

# ----------------------------
# Fingerprint Vector
# ----------------------------
st.subheader("Track fingerprint vector")

pct_low, pct_med, pct_high = _corner_mix(corner_df)
traction_score = _traction_demand_score(corner_df)

fingerprint = {
    "pct_low_corners": pct_low,
    "pct_med_corners": pct_med,
    "pct_high_corners": pct_high,
    "avg_braking_intensity_kph_per_m": bz_avg,
    "max_braking_intensity_kph_per_m": bz_max,
    "straight_dominance_score": straight_dom,
    "traction_demand_score": traction_score,
}

fp_df = pd.DataFrame([fingerprint]).T.reset_index()
fp_df.columns = ["feature", "value"]
st.dataframe(fp_df, use_container_width=True)

# Explain in plain language
with st.expander("How to read this (quick)", expanded=False):
    st.markdown(
        """
- **Corner mix (% low/med/high):** based on min speed near official corner distances.
- **Braking intensity (kph/m):** a *proxy* from telemetry speed drop per meter. Higher means heavier braking zones.
- **Straight dominance score:** fraction of lap distance where speed is above your straight threshold (proxy).
- **Traction demand score (0–1):** higher when the track has more low-speed (and some medium-speed) corners.
"""
    )

# Optional: show raw corner table
with st.expander("Show corner min speeds table", expanded=False):
    if corner_df.empty:
        st.caption("No data.")
    else:
        st.dataframe(corner_df, use_container_width=True)
