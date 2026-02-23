# pages/06_Track_Suitability.py
"""
TRACK SUITABILITY

Goal (your spec):
- Compute a team "capability vector" from past sessions (telemetry-derived indices)
- Compute a "track fingerprint" for a target track (based on Track DNA logic)
- Predict "fit" by comparing team vector vs track fingerprint
- Provide:
  - Similar tracks list (based on fingerprint distance)
  - For each team: expected strengths (high-speed / traction / braking / straights)
  - Confidence score based on data volume + recency

IMPORTANT NOTES (realistic + Streamlit Cloud safe):
- This is a v1 implementation designed to WORK reliably and be extendable.
- "Similar tracks" requires computing fingerprints for multiple tracks (can be heavy).
  So this page lets you choose which events to include in the similarity pool.
- Requires engine/data.py to provide: load_session(year, event_name, session_name)
- Do NOT init FastF1 cache here. Only in streamlit_app.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from engine.data import load_session


# ----------------------------
# Shared helpers (Track DNA-like)
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


def _fastest_lap_overall(laps: pd.DataFrame):
    df = laps.copy()
    df = df[df["LapTime"].notna()]
    if "IsAccurate" in df.columns:
        df = df[df["IsAccurate"] == True]
    if df.empty:
        return None
    return df.loc[df["LapTime"].idxmin()]


def _corner_min_speeds(tel_r: pd.DataFrame, corners: pd.DataFrame, window_m: float = 60.0) -> pd.DataFrame:
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


def _traction_demand_score(corner_df: pd.DataFrame):
    if corner_df is None or corner_df.empty:
        return np.nan
    total = len(corner_df)
    if total == 0:
        return np.nan
    low = int((corner_df["Type"] == "Low").sum())
    med = int((corner_df["Type"] == "Medium").sum())
    score = (1.0 * low + 0.4 * med) / total
    return float(np.clip(score, 0.0, 1.0))


def _braking_zones(tel_r: pd.DataFrame, decel_threshold: float = 0.25, min_len_m: float = 25.0):
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

    zones = []
    start = None
    for i, flag in enumerate(m):
        if flag and start is None:
            start = i
        if (not flag) and start is not None:
            zones.append((start, i - 1))
            start = None
    if start is not None:
        zones.append((start, len(m) - 1))

    kept = []
    for s, e in zones:
        length = float(d[e + 1] - d[s]) if (e + 1) < len(d) else float(d[e] - d[s])
        if length >= min_len_m:
            kept.append((s, e))

    if not kept:
        return 0, np.nan, np.nan

    intensities = [float(np.nanmean(decel[s : e + 1])) for s, e in kept]
    return int(len(kept)), float(np.nanmean(intensities)), float(np.nanmax(intensities))


def _straight_stats(tel_r: pd.DataFrame, speed_threshold: float = 280.0, min_len_m: float = 120.0):
    if tel_r.empty or "Speed" not in tel_r.columns or "Distance" not in tel_r.columns:
        return 0, 0.0, 0.0, np.nan

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


def _track_fingerprint_from_session(session, window_m: float, straight_kph: float, brake_thresh: float):
    laps = session.laps.copy()
    base_lap = _fastest_lap_overall(laps)
    if base_lap is None:
        return None

    tel = base_lap.get_telemetry().copy()
    tel_r = _resample_to_distance(tel, step_m=2.0)
    if tel_r.empty or "Speed" not in tel_r.columns:
        return None

    corners = _get_circuit_corners(session)
    corner_df = _corner_min_speeds(tel_r, corners, window_m=window_m) if not corners.empty else pd.DataFrame()

    pct_low, pct_med, pct_high = _corner_mix(corner_df)
    traction = _traction_demand_score(corner_df)

    bz_count, bz_avg, bz_max = _braking_zones(tel_r, decel_threshold=brake_thresh)
    _, _, _, straight_dom = _straight_stats(tel_r, speed_threshold=straight_kph)

    return {
        "pct_low_corners": pct_low,
        "pct_med_corners": pct_med,
        "pct_high_corners": pct_high,
        "avg_braking_intensity": bz_avg,
        "straight_dominance": straight_dom,
        "traction_demand": traction,
        "bz_count": bz_count,
        "bz_max": bz_max,
    }


# ----------------------------
# Capability vector (team)
# ----------------------------
def _capability_from_session(session, mode: str = "fastest_lap_per_driver"):
    """
    Team capability vector from telemetry (v1):
    - straight_speed: max speed on fastest lap (per driver, then team avg)
    - braking_eff: average decel intensity in braking zones (team avg)
    - traction_low: avg throttle when speed < 140 (team avg)
    - corner_strength_high/med/low: avg min speed by corner type (team avg)

    Returns: team_df with one row per Team.
    """
    laps = session.laps.copy()
    laps = laps[laps["LapTime"].notna()]
    if "IsAccurate" in laps.columns:
        laps = laps[laps["IsAccurate"] == True]
    if laps.empty:
        return pd.DataFrame()

    if "Team" not in laps.columns:
        return pd.DataFrame()

    # fastest lap per driver
    idx = laps.groupby("Driver")["LapTime"].idxmin()
    best = laps.loc[idx].copy()

    rows = []
    corners = _get_circuit_corners(session)

    for _, r in best.iterrows():
        drv = r.get("Driver")
        team = r.get("Team")
        if pd.isna(drv) or pd.isna(team):
            continue

        try:
            tel = r.get_telemetry().copy()
            tel_r = _resample_to_distance(tel, step_m=3.0)
            if tel_r.empty or "Speed" not in tel_r.columns:
                continue

            # straight speed proxy
            straight_speed = float(np.nanmax(tel_r["Speed"]))

            # braking proxy: avg braking zone intensity
            _, bz_avg, _ = _braking_zones(tel_r, decel_threshold=0.25)

            # traction proxy: avg throttle at low speeds
            traction_low = np.nan
            if "Throttle" in tel_r.columns:
                low = tel_r[tel_r["Speed"] < 140]
                if len(low) >= 20:
                    traction_low = float(np.nanmean(low["Throttle"].to_numpy(dtype=float)))

            # corner strengths: avg min speeds by type (using official corners)
            slow_s = med_s = high_s = np.nan
            if not corners.empty:
                cdf = _corner_min_speeds(tel_r, corners, window_m=60.0)
                if not cdf.empty:
                    slow = cdf[cdf["Type"] == "Low"]["MinSpeed"]
                    med = cdf[cdf["Type"] == "Medium"]["MinSpeed"]
                    high = cdf[cdf["Type"] == "High"]["MinSpeed"]
                    slow_s = float(np.nanmean(slow)) if len(slow) else np.nan
                    med_s = float(np.nanmean(med)) if len(med) else np.nan
                    high_s = float(np.nanmean(high)) if len(high) else np.nan

            rows.append(
                {
                    "Team": team,
                    "Driver": drv,
                    "straight_speed": straight_speed,
                    "braking_eff": bz_avg,
                    "traction_low": traction_low,
                    "corner_low": slow_s,
                    "corner_med": med_s,
                    "corner_high": high_s,
                }
            )
        except Exception:
            continue

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # team aggregate
    team = df.groupby("Team").agg(
        straight_speed=("straight_speed", "mean"),
        braking_eff=("braking_eff", "mean"),
        traction_low=("traction_low", "mean"),
        corner_low=("corner_low", "mean"),
        corner_med=("corner_med", "mean"),
        corner_high=("corner_high", "mean"),
        n_drivers=("Driver", "nunique"),
    ).reset_index()

    return team


def _normalize_0_1(series: pd.Series):
    s = pd.to_numeric(series, errors="coerce")
    lo, hi = np.nanmin(s), np.nanmax(s)
    if not np.isfinite(lo) or not np.isfinite(hi) or hi == lo:
        return pd.Series([np.nan] * len(s), index=s.index)
    return (s - lo) / (hi - lo)


def _fit_score(team_row: pd.Series, track_fp: dict):
    """
    Convert track fingerprint into "demand weights" and compute a fit score (0-100).

    Simple idea:
    - If straight_dominance high -> straight_speed matters more
    - If traction_demand high -> traction_low matters more
    - If avg_braking_intensity high -> braking_eff matters more
    - Corner mix weights -> corner_low/med/high matter accordingly

    Team metrics should be normalized (0-1) within the compared set.
    """
    w_straight = float(track_fp.get("straight_dominance", np.nan))
    w_traction = float(track_fp.get("traction_demand", np.nan))
    w_brake = float(track_fp.get("avg_braking_intensity", np.nan))

    # safe defaults if NaN
    if not np.isfinite(w_straight):
        w_straight = 0.33
    if not np.isfinite(w_traction):
        w_traction = 0.33
    if not np.isfinite(w_brake):
        w_brake = 0.33

    # corner mix
    w_low = float(track_fp.get("pct_low_corners", np.nan))
    w_med = float(track_fp.get("pct_med_corners", np.nan))
    w_high = float(track_fp.get("pct_high_corners", np.nan))
    if not np.isfinite(w_low + w_med + w_high):
        w_low, w_med, w_high = 0.33, 0.33, 0.33

    # normalize weights
    base = np.array([w_straight, w_traction, w_brake, w_low, w_med, w_high], dtype=float)
    base = np.clip(base, 0, None)
    if base.sum() <= 0:
        base = np.ones_like(base)
    base = base / base.sum()

    metrics = np.array(
        [
            team_row.get("straight_speed_n", np.nan),
            team_row.get("traction_low_n", np.nan),
            team_row.get("braking_eff_n", np.nan),
            team_row.get("corner_low_n", np.nan),
            team_row.get("corner_med_n", np.nan),
            team_row.get("corner_high_n", np.nan),
        ],
        dtype=float,
    )

    # replace NaNs with mid (neutral) to avoid killing score
    metrics = np.where(np.isfinite(metrics), metrics, 0.5)

    score_0_1 = float(np.dot(base, metrics))
    return 100.0 * score_0_1, base


def _strengths_text(track_fp: dict):
    """
    Human-readable "what matters" on this track.
    """
    parts = []
    sd = track_fp.get("straight_dominance", np.nan)
    td = track_fp.get("traction_demand", np.nan)
    br = track_fp.get("avg_braking_intensity", np.nan)

    if np.isfinite(sd) and sd >= 0.35:
        parts.append("Straights")
    if np.isfinite(td) and td >= 0.45:
        parts.append("Traction")
    if np.isfinite(br) and br >= 0.30:
        parts.append("Braking")

    # corner mix
    hi = track_fp.get("pct_high_corners", np.nan)
    lo = track_fp.get("pct_low_corners", np.nan)
    if np.isfinite(hi) and hi >= 0.35:
        parts.append("High-speed corners")
    if np.isfinite(lo) and lo >= 0.35:
        parts.append("Low-speed corners")

    return ", ".join(parts) if parts else "Balanced demands"


def _confidence(n_sessions_used: int, n_drivers_per_team_avg: float):
    """
    Basic confidence score 0-100 based on:
    - how many past sessions used for capability
    - how complete the team coverage is
    """
    a = np.clip(n_sessions_used / 6.0, 0.0, 1.0)  # 6 sessions ~ strong
    b = np.clip(n_drivers_per_team_avg / 2.0, 0.0, 1.0)  # 2 drivers ~ strong
    return float(100.0 * (0.6 * a + 0.4 * b))


# ----------------------------
# Cached session loading wrappers (important)
# ----------------------------
@st.cache_data(show_spinner=False)
def _load_session_cached(year: int, event: str, sess: str):
    s = load_session(year, event, sess)
    return s


@st.cache_data(show_spinner=False)
def _fingerprint_cached(year: int, event: str, sess: str, window_m: float, straight_kph: float, brake_thresh: float):
    s = _load_session_cached(year, event, sess)
    fp = _track_fingerprint_from_session(s, window_m=window_m, straight_kph=straight_kph, brake_thresh=brake_thresh)
    return fp


@st.cache_data(show_spinner=False)
def _team_capability_cached(year: int, event: str, sess: str):
    s = _load_session_cached(year, event, sess)
    return _capability_from_session(s)


# ----------------------------
# Page
# ----------------------------
st.set_page_config(layout="wide")
st.title("Track Suitability")

if "bundle" not in st.session_state:
    st.error("Session bundle not loaded. Open the main page first.")
    st.stop()

bundle = st.session_state["bundle"]
base_year = int(bundle["year"])
base_event = str(bundle["event"])
base_session_name = str(bundle["session_name"])

st.caption(f"Base selection: {base_year} • {base_event} • {base_session_name}")

st.markdown("### 1) Choose the *target* track (the one you want to predict for)")
cA, cB, cC = st.columns([2, 1, 1])
with cA:
    target_event = st.text_input("Target Event name (must match FastF1 event name)", value=base_event)
with cB:
    target_year = st.number_input("Target Year", min_value=2018, max_value=2026, value=base_year, step=1)
with cC:
    target_session = st.selectbox("Target Session", options=["FP1", "FP2", "FP3", "Q", "SQ", "S", "R"], index=["FP1","FP2","FP3","Q","SQ","S","R"].index(base_session_name) if base_session_name in ["FP1","FP2","FP3","Q","SQ","S","R"] else 3)

st.markdown("### 2) Track fingerprint parameters (these affect DNA + similarity)")
c1, c2, c3 = st.columns(3)
with c1:
    window_m = st.slider("Corner window (± meters)", 25, 120, 60, 5)
with c2:
    straight_kph = st.slider("Straight speed threshold (kph)", 240, 330, 280, 5)
with c3:
    brake_thresh = st.slider("Braking intensity threshold (kph/m)", 0.10, 0.60, 0.25, 0.01)

# Compute target fingerprint
with st.spinner("Computing target track fingerprint..."):
    target_fp = _fingerprint_cached(int(target_year), str(target_event), str(target_session), float(window_m), float(straight_kph), float(brake_thresh))

if target_fp is None:
    st.error("Could not compute target fingerprint (no telemetry or no valid fastest lap). Try another session (Q/R) or another year.")
    st.stop()

st.markdown("### Target track demands")
st.info(_strengths_text(target_fp))

fp_df = pd.DataFrame([target_fp]).T.reset_index()
fp_df.columns = ["feature", "value"]
st.dataframe(fp_df, use_container_width=True)

st.divider()

# ----------------------------
# Capability vector settings
# ----------------------------
st.markdown("### 3) Choose the history window to build team capability vectors")

st.caption(
    "V1 approach: you pick a set of past events/sessions (e.g., last 3 races, or a mix of Q + R). "
    "We compute team capability from telemetry and average across them."
)

# This is user-driven (safe + avoids huge automatic downloads on Streamlit Cloud)
history_year = st.number_input("History Year", min_value=2018, max_value=2026, value=base_year, step=1)
history_session = st.selectbox("History Session type", options=["Q", "R", "FP2", "FP3"], index=0)

# Let user choose event pool from the current season schedule (if available from their already loaded bundle's session)
# We can't rely on schedule here without engine.data exposing it; so we keep it manual input list.
default_events = [base_event]
events_text = st.text_area(
    "History events (one per line). Tip: paste 5–8 events max for Streamlit Cloud.",
    value="\n".join(default_events),
    height=150,
)
history_events = [e.strip() for e in events_text.splitlines() if e.strip()]

if len(history_events) == 0:
    st.warning("Add at least one history event.")
    st.stop()

# Compute capability from each selected event and average
team_tables = []
sessions_used = 0

with st.spinner("Computing team capability from history sessions..."):
    for ev in history_events:
        try:
            cap = _team_capability_cached(int(history_year), str(ev), str(history_session))
            if cap is not None and not cap.empty:
                cap["HistoryEvent"] = ev
                team_tables.append(cap)
                sessions_used += 1
        except Exception:
            continue

if not team_tables:
    st.error("Could not compute capability from the selected history pool. Try using Q or R and confirm event names match FastF1.")
    st.stop()

cap_all = pd.concat(team_tables, ignore_index=True)

# Average across history events
cap_avg = cap_all.groupby("Team").agg(
    straight_speed=("straight_speed", "mean"),
    braking_eff=("braking_eff", "mean"),
    traction_low=("traction_low", "mean"),
    corner_low=("corner_low", "mean"),
    corner_med=("corner_med", "mean"),
    corner_high=("corner_high", "mean"),
    n_drivers=("n_drivers", "mean"),
).reset_index()

# Normalize metrics for scoring
cap_avg["straight_speed_n"] = _normalize_0_1(cap_avg["straight_speed"])
cap_avg["braking_eff_n"] = _normalize_0_1(cap_avg["braking_eff"])
cap_avg["traction_low_n"] = _normalize_0_1(cap_avg["traction_low"])
cap_avg["corner_low_n"] = _normalize_0_1(cap_avg["corner_low"])
cap_avg["corner_med_n"] = _normalize_0_1(cap_avg["corner_med"])
cap_avg["corner_high_n"] = _normalize_0_1(cap_avg["corner_high"])

# Fit scores
scores = []
weights_used = None
for _, row in cap_avg.iterrows():
    score, w = _fit_score(row, target_fp)
    weights_used = w
    scores.append(score)

cap_avg["FitScore_0_100"] = scores

conf = _confidence(sessions_used, float(np.nanmean(cap_avg["n_drivers"].to_numpy(dtype=float))))
st.metric("Confidence (based on history pool)", f"{conf:.0f}/100", help="More events and full team coverage increases confidence.")

st.markdown("### Fit leaderboard (teams)")
cap_avg_sorted = cap_avg.sort_values("FitScore_0_100", ascending=False)
st.dataframe(
    cap_avg_sorted[
        ["Team", "FitScore_0_100", "straight_speed", "traction_low", "braking_eff", "corner_low", "corner_med", "corner_high", "n_drivers"]
    ],
    use_container_width=True,
)

# Plot
fig = go.Figure(go.Bar(x=cap_avg_sorted["Team"], y=cap_avg_sorted["FitScore_0_100"], name="Fit"))
fig.update_layout(height=350, margin=dict(l=10, r=10, t=40, b=10), title="Team Fit Score (0–100)")
fig.update_yaxes(title="Fit score")
st.plotly_chart(fig, use_container_width=True)

with st.expander("Weights used (derived from track fingerprint)", expanded=False):
    if weights_used is not None:
        st.write(
            {
                "straight_speed_weight": float(weights_used[0]),
                "traction_weight": float(weights_used[1]),
                "braking_weight": float(weights_used[2]),
                "corner_low_weight": float(weights_used[3]),
                "corner_med_weight": float(weights_used[4]),
                "corner_high_weight": float(weights_used[5]),
            }
        )

st.divider()

# ----------------------------
# Similar tracks (fingerprint distance)
# ----------------------------
st.markdown("### 4) Similar tracks (fingerprint distance)")
st.caption(
    "To avoid heavy downloads, you choose the candidate tracks (events) to compare against. "
    "We compute each candidate fingerprint and rank by distance to the target."
)

cand_year = st.number_input("Candidate year", min_value=2018, max_value=2026, value=int(target_year), step=1, key="cand_year")
cand_session = st.selectbox("Candidate session type", options=["Q", "R", "FP2", "FP3"], index=0, key="cand_sess")

cand_text = st.text_area(
    "Candidate events (one per line) to search for similar tracks",
    value="\n".join(history_events),
    height=150,
    key="cand_events",
)
cand_events = [e.strip() for e in cand_text.splitlines() if e.strip()]

if st.button("Compute similar tracks", use_container_width=False):
    sims = []
    with st.spinner("Computing fingerprints for candidates..."):
        for ev in cand_events:
            try:
                fp = _fingerprint_cached(int(cand_year), str(ev), str(cand_session), float(window_m), float(straight_kph), float(brake_thresh))
                if fp is None:
                    continue
                # distance on shared keys
                keys = ["pct_low_corners", "pct_med_corners", "pct_high_corners", "avg_braking_intensity", "straight_dominance", "traction_demand"]
                a = np.array([float(target_fp.get(k, np.nan)) for k in keys], dtype=float)
                b = np.array([float(fp.get(k, np.nan)) for k in keys], dtype=float)

                # replace NaN with mean of available (simple)
                am = np.nanmean(a) if np.isfinite(np.nanmean(a)) else 0.0
                bm = np.nanmean(b) if np.isfinite(np.nanmean(b)) else 0.0
                a = np.where(np.isfinite(a), a, am)
                b = np.where(np.isfinite(b), b, bm)

                dist = float(np.linalg.norm(a - b))
                sims.append({"Event": ev, "Year": int(cand_year), "Session": cand_session, "Distance": dist})
            except Exception:
                continue

    sim_df = pd.DataFrame(sims).sort_values("Distance") if sims else pd.DataFrame()
    if sim_df.empty:
        st.warning("No similar tracks computed (candidate fingerprints failed). Check event names and try Q or R.")
    else:
        st.dataframe(sim_df.head(15), use_container_width=True)

        fig2 = go.Figure(go.Bar(x=sim_df.head(15)["Event"], y=sim_df.head(15)["Distance"], name="Distance"))
        fig2.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10), title="Closest tracks (lower distance = more similar)")
        fig2.update_yaxes(title="Fingerprint distance")
        st.plotly_chart(fig2, use_container_width=True)

st.divider()

with st.expander("What to improve next (recommended)", expanded=False):
    st.markdown(
        """
1) **Auto-pull event lists** from schedule (so you don't paste event names).
2) Build a **fingerprint store** (parquet/json) so similar tracks is instant.
3) Improve capability vectors using:
   - straight efficiency (speed + throttle) not just max speed
   - braking start distance proxies
   - exit traction from throttle ramp after corner minimum
4) Add **recency weighting** for history pool (latest sessions count more).
"""
    )
