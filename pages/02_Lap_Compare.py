# pages/02_Lap_Compare.py
"""
LAP COMPARE

Matches your spec:
- Mode: Current Session or All Time
- Current Session:
  - Select drivers
  - For each driver: choose lap number (fastest lap pre-selected)
- All Time:
  - Compare across years (add another year button)
  - Uses same Event + Session type as the current bundle by default
  - Fastest lap per driver per year (you can expand later)

Output layout:
- Charts stacked vertically (rows)
  Speed, Throttle, Brake, Gear, RPM, Delta
- Gear map (Distance vs Gear)
- Track map with fastest sectors (best S1/S2/S3 among selected laps)
Add-ons implemented:
- Corner markers (from circuit info, if available)
- Sector shading on telemetry charts (S1/S2/S3)
- "Corner focus" dropdown to zoom around a chosen corner across charts
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from engine.data import load_session


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

    for col in ["Speed", "Throttle", "Brake", "nGear", "RPM", "X", "Y"]:
        if col in tel.columns:
            out[col] = np.interp(grid, d, tel[col].to_numpy(dtype=float))

    if "Time" in tel.columns:
        t = tel["Time"]
        if len(t) > 0 and hasattr(t.iloc[0], "total_seconds"):
            tsec = t.dt.total_seconds().to_numpy(dtype=float)
        else:
            tsec = pd.to_numeric(t, errors="coerce").to_numpy(dtype=float)
        # if time is all NaN, don't add
        if np.isfinite(tsec).any():
            out["Time_s"] = np.interp(grid, d, tsec)

    return out


def _sector_end_distances(lap, tel_r: pd.DataFrame):
    """
    Map sector split times to distances using Time_s.
    Returns (d_s1_end, d_s2_end) or (None, None).
    """
    if "Time_s" not in tel_r.columns:
        return None, None

    s1 = _to_seconds(getattr(lap, "Sector1Time", None))
    s2 = _to_seconds(getattr(lap, "Sector2Time", None))
    if not np.isfinite(s1) or not np.isfinite(s2):
        return None, None

    t = tel_r["Time_s"].to_numpy(dtype=float)
    d = tel_r["Distance"].to_numpy(dtype=float)

    t1 = s1
    t2 = s1 + s2
    d1 = float(np.interp(t1, t, d))
    d2 = float(np.interp(t2, t, d))
    return d1, d2


def _get_corners(session):
    """
    Returns circuit corners dataframe with Number, Distance (if available).
    """
    try:
        ci = session.get_circuit_info()
        corners = ci.corners.copy()
        if corners is None or corners.empty:
            return pd.DataFrame()
        # Normalize
        keep = []
        for c in ["Number", "Distance", "X", "Y", "Angle"]:
            if c in corners.columns:
                keep.append(c)
        corners = corners[keep].copy()
        return corners
    except Exception:
        return pd.DataFrame()


def _vlines_from_corners(fig, corners_df, x_col="Distance", max_lines=30):
    """
    Add vertical lines to a telemetry figure at corner distances.
    """
    if corners_df is None or corners_df.empty or x_col not in corners_df.columns:
        return fig
    df = corners_df.dropna(subset=[x_col]).copy()
    df = df.head(max_lines)  # avoid too many
    for _, r in df.iterrows():
        x = float(r[x_col])
        num = r.get("Number", "")
        fig.add_vline(x=x, line_width=1, opacity=0.2)
        if num != "":
            # light label at top
            fig.add_annotation(x=x, y=1.02, yref="paper", text=f"T{int(num)}", showarrow=False, font=dict(size=9))
    return fig


def _add_sector_shading(fig, d1, d2):
    """
    Shade S1/S2/S3 on Distance axis using vrects.
    """
    if not (np.isfinite(d1) and np.isfinite(d2)):
        return fig

    # S1: [0, d1], S2: [d1, d2], S3: [d2, end]
    fig.add_vrect(x0=0, x1=d1, opacity=0.06, layer="below", line_width=0)
    fig.add_vrect(x0=d1, x1=d2, opacity=0.04, layer="below", line_width=0)
    # S3 shading is optional; leaving it clean helps readability
    return fig


def _plot_multi(drivers_data: dict[str, pd.DataFrame], col: str, title: str, x_range=None,
                corners_df=None, sector_splits=None):
    fig = go.Figure()
    for drv, df in drivers_data.items():
        if df is None or df.empty or col not in df.columns:
            continue
        fig.add_trace(go.Scatter(x=df["Distance"], y=df[col], mode="lines", name=drv))

    fig.update_layout(
        height=260,
        margin=dict(l=10, r=10, t=40, b=10),
        title=title,
        xaxis_title="Distance (m)",
        yaxis_title=col,
        legend=dict(orientation="h"),
    )

    if x_range is not None:
        fig.update_xaxes(range=list(x_range))

    # sector shading (use reference / first lap split distances)
    if sector_splits is not None:
        d1, d2 = sector_splits
        if d1 is not None and d2 is not None:
            fig = _add_sector_shading(fig, d1, d2)

    # corner markers
    fig = _vlines_from_corners(fig, corners_df, x_col="Distance")
    return fig


def _compute_delta(ref: pd.DataFrame, cmp: pd.DataFrame):
    """
    Delta = cmp Time_s - ref Time_s on common distance length.
    """
    if ref is None or cmp is None or ref.empty or cmp.empty:
        return None, None
    if "Time_s" not in ref.columns or "Time_s" not in cmp.columns:
        return None, None
    n = min(len(ref), len(cmp))
    d = ref["Distance"].iloc[:n].to_numpy(dtype=float)
    delta = (cmp["Time_s"].iloc[:n].to_numpy(dtype=float) - ref["Time_s"].iloc[:n].to_numpy(dtype=float))
    return d, delta


def _plot_delta(ref_driver: str, deltas: dict[str, tuple[np.ndarray, np.ndarray]], x_range=None, corners_df=None,
                sector_splits=None):
    fig = go.Figure()
    for drv, (d, delta) in deltas.items():
        if drv == ref_driver:
            continue
        fig.add_trace(go.Scatter(x=d, y=delta, mode="lines", name=f"{drv} - {ref_driver}"))

    fig.update_layout(
        height=260,
        margin=dict(l=10, r=10, t=40, b=10),
        title="Delta Time Trace (vs reference)",
        xaxis_title="Distance (m)",
        yaxis_title="Seconds",
        legend=dict(orientation="h"),
    )

    if x_range is not None:
        fig.update_xaxes(range=list(x_range))

    if sector_splits is not None:
        d1, d2 = sector_splits
        if d1 is not None and d2 is not None:
            fig = _add_sector_shading(fig, d1, d2)

    fig = _vlines_from_corners(fig, corners_df, x_col="Distance")
    return fig


def _plot_gear_map(drivers_data: dict[str, pd.DataFrame], x_range=None, corners_df=None, sector_splits=None):
    """
    Gear map: Distance vs nGear (scatter/line)
    """
    fig = go.Figure()
    for drv, df in drivers_data.items():
        if df is None or df.empty or "nGear" not in df.columns:
            continue
        fig.add_trace(go.Scatter(x=df["Distance"], y=df["nGear"], mode="lines", name=drv))

    fig.update_layout(
        height=240,
        margin=dict(l=10, r=10, t=40, b=10),
        title="Gear Map",
        xaxis_title="Distance (m)",
        yaxis_title="Gear",
        legend=dict(orientation="h"),
    )
    fig.update_yaxes(dtick=1)

    if x_range is not None:
        fig.update_xaxes(range=list(x_range))

    if sector_splits is not None:
        d1, d2 = sector_splits
        if d1 is not None and d2 is not None:
            fig = _add_sector_shading(fig, d1, d2)

    fig = _vlines_from_corners(fig, corners_df, x_col="Distance")
    return fig


def _plot_track_map_fastest_sectors(session, laps_selected: dict[str, object], step_m=3.0):
    """
    Track map with fastest sectors among selected laps:
    - Find best S1/S2/S3 time across selected laps
    - Plot that lap's telemetry segment in thicker line for each sector
    Requires telemetry XY; if missing, returns a fallback message.
    """
    # pick best sector winners
    best = {"S1": (None, np.inf), "S2": (None, np.inf), "S3": (None, np.inf)}
    for drv, lap in laps_selected.items():
        if lap is None:
            continue
        s1 = _to_seconds(getattr(lap, "Sector1Time", None))
        s2 = _to_seconds(getattr(lap, "Sector2Time", None))
        s3 = _to_seconds(getattr(lap, "Sector3Time", None))
        if np.isfinite(s1) and s1 < best["S1"][1]:
            best["S1"] = (drv, s1)
        if np.isfinite(s2) and s2 < best["S2"][1]:
            best["S2"] = (drv, s2)
        if np.isfinite(s3) and s3 < best["S3"][1]:
            best["S3"] = (drv, s3)

    # base outline from first available lap
    any_lap = next((lap for lap in laps_selected.values() if lap is not None), None)
    if any_lap is None:
        return None

    tel = any_lap.get_telemetry().copy()
    tel_r = _resample_to_distance(tel, step_m=step_m)

    if "X" not in tel_r.columns or "Y" not in tel_r.columns:
        return None

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tel_r["X"], y=tel_r["Y"], mode="lines", name="Outline", opacity=0.35))

    # for each sector winner, overlay that lap's sector segment
    for sector, (drv, _) in best.items():
        if drv is None:
            continue
        lap = laps_selected[drv]
        t = lap.get_telemetry().copy()
        tr = _resample_to_distance(t, step_m=step_m)
        if "X" not in tr.columns or "Y" not in tr.columns:
            continue

        d1, d2 = _sector_end_distances(lap, tr)
        if d1 is None or d2 is None:
            continue

        d = tr["Distance"].to_numpy(dtype=float)
        if sector == "S1":
            m = d <= d1
        elif sector == "S2":
            m = (d >= d1) & (d <= d2)
        else:
            m = d >= d2

        fig.add_trace(go.Scatter(x=tr.loc[m, "X"], y=tr.loc[m, "Y"], mode="lines", name=f"{sector} best: {drv}"))

    # corners labels (optional)
    corners_df = _get_corners(session)
    if not corners_df.empty and "Distance" in corners_df.columns:
        # map corner distance -> xy from base outline
        d = tel_r["Distance"].to_numpy(dtype=float)
        xs = tel_r["X"].to_numpy(dtype=float)
        ys = tel_r["Y"].to_numpy(dtype=float)
        cx, cy, labels = [], [], []
        for _, r in corners_df.dropna(subset=["Distance"]).iterrows():
            cd = float(r["Distance"])
            idx = int(np.argmin(np.abs(d - cd)))
            cx.append(xs[idx])
            cy.append(ys[idx])
            labels.append(f"T{int(r['Number'])}")
        if cx:
            fig.add_trace(go.Scatter(x=cx, y=cy, mode="markers+text", text=labels, textposition="top center", name="Turns"))

    fig.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=40, b=10),
        title="Track Map with Fastest Sectors (among selected laps)",
        showlegend=True,
        legend=dict(orientation="h"),
    )
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    return fig


def _get_driver_laps(laps_df: pd.DataFrame, driver: str) -> pd.DataFrame:
    df = laps_df[laps_df["Driver"] == driver].copy()
    df = df[df["LapTime"].notna()]
    if "IsAccurate" in df.columns:
        df = df[df["IsAccurate"] == True]
    return df.sort_values("LapNumber")


def _fastest_lap_row(laps_df: pd.DataFrame, driver: str):
    df = _get_driver_laps(laps_df, driver)
    if df.empty:
        return None
    return df.loc[df["LapTime"].idxmin()]


# ----------------------------
# Page
# ----------------------------
st.set_page_config(layout="wide")
st.title("Lap Compare")

if "bundle" not in st.session_state:
    st.error("Session bundle not loaded. Open the main page first.")
    st.stop()

bundle = st.session_state["bundle"]
base_year = int(bundle["year"])
base_event = str(bundle["event"])
base_session_name = str(bundle["session_name"])
base_session = bundle["session"]
base_laps = bundle["laps"]
base_drivers = sorted(bundle["drivers"])

corners_df = _get_corners(base_session)

# Mode selector
mode = st.radio("Mode", ["Current Session", "All Time"], horizontal=True)

# ----------------------------
# Build selected laps per driver (depending on mode)
# ----------------------------
selected_laps_by_driver: dict[str, object] = {}
drivers_selected: list[str] = []

if mode == "Current Session":
    drivers_selected = st.multiselect(
        "Drivers",
        options=base_drivers,
        default=base_drivers[:2] if len(base_drivers) >= 2 else base_drivers,
    )

    if len(drivers_selected) < 1:
        st.warning("Select at least 1 driver.")
        st.stop()

    # Lap number selection per driver
    with st.expander("Lap selection (fastest lap is pre-selected)", expanded=True):
        for drv in drivers_selected:
            df = _get_driver_laps(base_laps, drv)
            if df.empty:
                st.caption(f"{drv}: no valid laps")
                selected_laps_by_driver[drv] = None
                continue

            fastest = df.loc[df["LapTime"].idxmin()]
            lap_numbers = df["LapNumber"].astype(int).tolist()
            default_idx = lap_numbers.index(int(fastest["LapNumber"])) if int(fastest["LapNumber"]) in lap_numbers else 0

            lap_no = st.selectbox(
                f"{drv} lap number",
                options=lap_numbers,
                index=default_idx,
                key=f"lap_{drv}",
            )
            lap_row = df[df["LapNumber"] == lap_no].iloc[0]
            selected_laps_by_driver[drv] = lap_row

else:
    # All Time mode: add years to compare
    st.caption("All Time compares fastest laps per driver for selected year(s), using the same Event + Session type as the base selection.")

    if "compare_years" not in st.session_state:
        st.session_state["compare_years"] = [base_year]

    c1, c2 = st.columns([3, 1])
    with c1:
        years = st.multiselect(
            "Years to include",
            options=list(range(2018, 2027)),
            default=st.session_state["compare_years"],
        )
        st.session_state["compare_years"] = years

    with c2:
        if st.button("➕ Add another year"):
            # add a reasonable next year (or base_year-1) if available
            cand = base_year - 1
            if cand >= 2018 and cand not in st.session_state["compare_years"]:
                st.session_state["compare_years"].append(cand)
            else:
                # otherwise add any missing year
                for y in range(base_year - 1, 2017, -1):
                    if y not in st.session_state["compare_years"]:
                        st.session_state["compare_years"].append(y)
                        break

    drivers_selected = st.multiselect(
        "Drivers (these are driver codes from the CURRENT session; older years may not match perfectly)",
        options=base_drivers,
        default=base_drivers[:2] if len(base_drivers) >= 2 else base_drivers,
    )

    if len(drivers_selected) < 1:
        st.warning("Select at least 1 driver.")
        st.stop()

    # Choose which year acts as "reference" for each driver (default: newest year in list)
    ref_year = st.selectbox("Reference year (for delta)", options=sorted(st.session_state["compare_years"]), index=len(sorted(st.session_state["compare_years"])) - 1)

    # Load sessions per year, then select fastest lap per driver
    loaded_sessions = {}
    loaded_laps = {}

    with st.spinner("Loading sessions for selected years..."):
        for y in sorted(st.session_state["compare_years"]):
            try:
                s = load_session(y, base_event, base_session_name)
                loaded_sessions[y] = s
                loaded_laps[y] = s.laps.copy()
            except Exception:
                loaded_sessions[y] = None
                loaded_laps[y] = None

    # Select a single "comparison lap" per driver by picking the fastest lap in the reference year
    # and then also storing fastest laps for other years in a separate map (shown later).
    # For now, we compare drivers within the reference year to keep the UI consistent.
    laps_ref = loaded_laps.get(ref_year)
    if laps_ref is None:
        st.error(f"Could not load {ref_year} {base_event} {base_session_name}. Try different year(s).")
        st.stop()

    # Build selected laps per driver from reference year fastest lap
    for drv in drivers_selected:
        row = _fastest_lap_row(laps_ref, drv)
        selected_laps_by_driver[f"{drv} ({ref_year})"] = row

    # Update driver labels for plotting
    drivers_selected = list(selected_laps_by_driver.keys())
    base_session = loaded_sessions[ref_year]
    corners_df = _get_corners(base_session)

# Remove any Nones
selected_laps_by_driver = {k: v for k, v in selected_laps_by_driver.items() if v is not None}
if len(selected_laps_by_driver) < 1:
    st.error("No valid laps found for the selected driver(s).")
    st.stop()

# Choose reference driver for delta (first in list)
ref_driver = st.selectbox("Reference (delta baseline)", options=list(selected_laps_by_driver.keys()), index=0)

# Build telemetry dict
telemetry = {}
sector_splits_ref = (None, None)

with st.spinner("Building telemetry (resampling to distance)..."):
    for label, lap_row in selected_laps_by_driver.items():
        try:
            tel = lap_row.get_telemetry().copy()
            tel_r = _resample_to_distance(tel, step_m=2.0)
            telemetry[label] = tel_r
        except Exception:
            telemetry[label] = pd.DataFrame()

# Sector shading reference from reference lap
if ref_driver in selected_laps_by_driver and ref_driver in telemetry and not telemetry[ref_driver].empty:
    sector_splits_ref = _sector_end_distances(selected_laps_by_driver[ref_driver], telemetry[ref_driver])

# Corner focus zoom
focus_corner = None
x_range = None
if corners_df is not None and not corners_df.empty and "Distance" in corners_df.columns:
    corner_nums = corners_df.dropna(subset=["Number", "Distance"]).copy()
    corner_nums["Number"] = corner_nums["Number"].astype(int)
    options = ["(No zoom)"] + [f"T{n}" for n in corner_nums["Number"].tolist()]
    choice = st.selectbox("Corner focus (auto-zoom charts)", options=options, index=0)
    if choice != "(No zoom)":
        n = int(choice.replace("T", ""))
        row = corner_nums[corner_nums["Number"] == n].iloc[0]
        focus_corner = n
        cd = float(row["Distance"])
        x_range = (cd - 250, cd + 250)

# ----------------------------
# Output charts (stacked)
# ----------------------------
st.subheader("Telemetry (stacked rows)")

# Speed
st.plotly_chart(
    _plot_multi(telemetry, "Speed", "Speed", x_range=x_range, corners_df=corners_df, sector_splits=sector_splits_ref),
    use_container_width=True,
)

# Throttle
if any((not df.empty and "Throttle" in df.columns) for df in telemetry.values()):
    st.plotly_chart(
        _plot_multi(telemetry, "Throttle", "Throttle", x_range=x_range, corners_df=corners_df, sector_splits=sector_splits_ref),
        use_container_width=True,
    )

# Brake
if any((not df.empty and "Brake" in df.columns) for df in telemetry.values()):
    st.plotly_chart(
        _plot_multi(telemetry, "Brake", "Brake", x_range=x_range, corners_df=corners_df, sector_splits=sector_splits_ref),
        use_container_width=True,
    )

# Gear
if any((not df.empty and "nGear" in df.columns) for df in telemetry.values()):
    st.plotly_chart(
        _plot_multi(telemetry, "nGear", "Gear", x_range=x_range, corners_df=corners_df, sector_splits=sector_splits_ref),
        use_container_width=True,
    )

# RPM
if any((not df.empty and "RPM" in df.columns) for df in telemetry.values()):
    st.plotly_chart(
        _plot_multi(telemetry, "RPM", "RPM", x_range=x_range, corners_df=corners_df, sector_splits=sector_splits_ref),
        use_container_width=True,
    )

# Delta Time Trace (vs reference)
deltas = {}
ref_df = telemetry.get(ref_driver)
for drv, df in telemetry.items():
    if drv == ref_driver:
        continue
    d, delta = _compute_delta(ref_df, df)
    if d is not None and delta is not None:
        deltas[drv] = (d, delta)

if deltas:
    st.plotly_chart(
        _plot_delta(ref_driver, deltas, x_range=x_range, corners_df=corners_df, sector_splits=sector_splits_ref),
        use_container_width=True,
    )
else:
    st.caption("Delta trace unavailable (missing Time data for one or more laps).")

# Gear map
if any((not df.empty and "nGear" in df.columns) for df in telemetry.values()):
    st.plotly_chart(
        _plot_gear_map(telemetry, x_range=x_range, corners_df=corners_df, sector_splits=sector_splits_ref),
        use_container_width=True,
    )

st.divider()

# ----------------------------
# Track map with fastest sectors
# ----------------------------
st.subheader("Track Map with Fastest Sectors (selected laps)")

fig_track = _plot_track_map_fastest_sectors(base_session, selected_laps_by_driver)
if fig_track is None:
    st.caption("Track map not available for this session (XY telemetry missing).")
else:
    st.plotly_chart(fig_track, use_container_width=True)

# Notes
with st.expander("Notes / limitations (for now)", expanded=False):
    st.markdown(
        """
- **Corner auto-zoom** is implemented via a dropdown (not click-to-zoom yet).
- **Sector shading** uses Sector1Time/Sector2Time mapped onto telemetry Time_s.
- **All Time mode** currently compares within a chosen **reference year** using the same event/session type.
  You can extend it to show multiple-year overlays per driver (next step).
"""
    )
