# pages/04_Long_Runs.py
"""
LONG RUNS & TIRE DEGRADATION

Matches your spec:
Tools:
- Auto-detect stints (simple heuristic) OR manual lap range
- Plot lap time vs lap number (per driver)
- Degradation slope (s/lap)
- Consistency (std dev)
- Optional: compare stints across drivers/teams

Outputs:
- “Best deg” ranking (lowest slope)
- “Best consistency” ranking (lowest std dev)
- Stint-to-stint pace drop-off
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go


# ----------------------------
# Helpers
# ----------------------------
def _valid_laps(laps: pd.DataFrame, drivers: list[str]) -> pd.DataFrame:
    df = laps.copy()
    df = df[df["Driver"].isin(drivers)]
    df = df[df["LapTime"].notna()]
    if "IsAccurate" in df.columns:
        df = df[df["IsAccurate"] == True]
    # Exclude obvious outliers (inlaps/outlaps often huge). Keep it simple:
    df["Lap_s"] = df["LapTime"].dt.total_seconds()
    df = df[np.isfinite(df["Lap_s"])]
    # Drop extreme values (e.g., 3x median for that driver) as a quick cleanup
    out = []
    for drv, sub in df.groupby("Driver"):
        med = np.nanmedian(sub["Lap_s"].to_numpy(dtype=float))
        clean = sub[sub["Lap_s"] < 3.0 * med] if np.isfinite(med) else sub
        out.append(clean)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def _plot_laptimes(df: pd.DataFrame, title: str):
    fig = go.Figure()
    for drv in df["Driver"].unique():
        sub = df[df["Driver"] == drv].sort_values("LapNumber")
        fig.add_trace(go.Scatter(x=sub["LapNumber"], y=sub["Lap_s"], mode="lines+markers", name=drv))
    fig.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=40, b=10),
        title=title,
        xaxis_title="Lap Number",
        yaxis_title="Lap Time (s)",
        legend=dict(orientation="h"),
    )
    return fig


def _auto_detect_stints(df: pd.DataFrame, gap_laps: int = 2, pit_time_jump_s: float = 6.0):
    """
    Very simple stint segmentation:
    - Sort by LapNumber
    - New stint when:
      - LapNumber gap > gap_laps, OR
      - Lap time jump > pit_time_jump_s (often indicates pit / traffic / reset)
      - Compound changes (if available)
    Returns df with a 'Stint' integer column per driver.
    """
    out = []
    for drv, sub in df.groupby("Driver"):
        sub = sub.sort_values("LapNumber").copy()
        stint = 1
        sub["Stint"] = stint

        last_lap = None
        last_time = None
        last_comp = None
        for i, r in sub.iterrows():
            lapno = int(r["LapNumber"])
            lap_s = float(r["Lap_s"])
            comp = r.get("Compound", None)

            new = False
            if last_lap is not None and (lapno - last_lap) > gap_laps:
                new = True
            if last_time is not None and (lap_s - last_time) > pit_time_jump_s:
                new = True
            if ("Compound" in sub.columns) and (last_comp is not None) and (comp is not None) and (comp != last_comp):
                new = True

            if new:
                stint += 1

            sub.at[i, "Stint"] = stint
            last_lap = lapno
            last_time = lap_s
            last_comp = comp

        out.append(sub)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def _fit_deg_slope(sub: pd.DataFrame):
    """
    Fit lap_s = a + b*lapNumber within a stint.
    b = degradation slope (s/lap). Lower is better.
    """
    if len(sub) < 4:
        return np.nan
    x = sub["LapNumber"].to_numpy(dtype=float)
    y = sub["Lap_s"].to_numpy(dtype=float)
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        return np.nan
    b = np.polyfit(x, y, 1)[0]
    return float(b)


def _stint_summary(df: pd.DataFrame):
    """
    Returns stint-level summary:
    - Deg_s_per_lap
    - Consistency_std_s
    - AvgLap_s
    - StartLap / EndLap
    """
    rows = []
    for (drv, stint), sub in df.groupby(["Driver", "Stint"]):
        sub = sub.sort_values("LapNumber")
        slope = _fit_deg_slope(sub)
        std = float(np.std(sub["Lap_s"].to_numpy(dtype=float)))
        avg = float(np.mean(sub["Lap_s"].to_numpy(dtype=float)))
        comp = sub["Compound"].mode().iloc[0] if "Compound" in sub.columns and not sub["Compound"].isna().all() else None

        rows.append(
            {
                "Driver": drv,
                "Stint": int(stint),
                "Compound": comp,
                "N": int(len(sub)),
                "StartLap": int(sub["LapNumber"].iloc[0]),
                "EndLap": int(sub["LapNumber"].iloc[-1]),
                "AvgLap_s": avg,
                "Deg_s_per_lap": slope,
                "Consistency_std_s": std,
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["Driver", "Stint"])


def _pace_dropoff(stint_summary: pd.DataFrame):
    """
    For each driver, compute pace drop-off between consecutive stints:
    DropOff = AvgLap_s(stint k+1) - AvgLap_s(stint k)
    """
    rows = []
    for drv, sub in stint_summary.groupby("Driver"):
        sub = sub.sort_values("Stint")
        for i in range(len(sub) - 1):
            a = sub.iloc[i]
            b = sub.iloc[i + 1]
            rows.append(
                {
                    "Driver": drv,
                    "FromStint": int(a["Stint"]),
                    "ToStint": int(b["Stint"]),
                    "FromAvg_s": float(a["AvgLap_s"]),
                    "ToAvg_s": float(b["AvgLap_s"]),
                    "DropOff_s": float(b["AvgLap_s"] - a["AvgLap_s"]),
                }
            )
    return pd.DataFrame(rows)


# ----------------------------
# Page
# ----------------------------
st.set_page_config(layout="wide")
st.title("Long Runs & Tire Degradation")

if "bundle" not in st.session_state:
    st.error("Session bundle not loaded. Open the main page first.")
    st.stop()

bundle = st.session_state["bundle"]
laps = bundle["laps"]
drivers_all = sorted(bundle["drivers"])

# Inputs
c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    drivers = st.multiselect("Drivers", drivers_all, default=drivers_all[:3] if len(drivers_all) >= 3 else drivers_all)
with c2:
    mode = st.selectbox("Stint mode", ["Auto-detect stints", "Manual lap range"])
with c3:
    min_laps_required = st.slider("Min laps per stint", 3, 12, 6, 1)

if not drivers:
    st.warning("Select at least one driver.")
    st.stop()

df = _valid_laps(laps, drivers)
if df.empty:
    st.error("No valid laps found for the selected drivers.")
    st.stop()

# Manual range controls
lap_min = int(df["LapNumber"].min())
lap_max = int(df["LapNumber"].max())
lap_range = (lap_min, lap_max)
if mode == "Manual lap range":
    lap_range = st.slider("Lap range", min_value=lap_min, max_value=lap_max, value=(lap_min, lap_max))
    df = df[(df["LapNumber"] >= lap_range[0]) & (df["LapNumber"] <= lap_range[1])]

st.subheader("Lap time vs lap number")
st.plotly_chart(_plot_laptimes(df, "Lap Times"), use_container_width=True)

st.divider()

# Stints
if mode == "Auto-detect stints":
    with st.spinner("Detecting stints..."):
        df_stints = _auto_detect_stints(df, gap_laps=2, pit_time_jump_s=6.0)
else:
    # Manual mode: treat each driver as one stint (Stint=1)
    df_stints = df.copy()
    df_stints["Stint"] = 1

# Filter by min laps per stint
counts = df_stints.groupby(["Driver", "Stint"]).size().reset_index(name="N")
good = counts[counts["N"] >= int(min_laps_required)][["Driver", "Stint"]]
df_stints = df_stints.merge(good, on=["Driver", "Stint"], how="inner")

if df_stints.empty:
    st.warning("No stints meet the minimum lap requirement. Lower the threshold or widen the lap range.")
    st.stop()

# Stint-level summaries
st.subheader("Stint summaries")
summary = _stint_summary(df_stints)
st.dataframe(summary, use_container_width=True)

st.divider()

# Rankings
st.subheader("Rankings")

best_deg = summary.dropna(subset=["Deg_s_per_lap"]).sort_values("Deg_s_per_lap").copy()
best_cons = summary.dropna(subset=["Consistency_std_s"]).sort_values("Consistency_std_s").copy()

c1, c2 = st.columns(2)
with c1:
    st.caption("Best degradation (lowest slope s/lap)")
    st.dataframe(best_deg[["Driver", "Stint", "Compound", "N", "Deg_s_per_lap", "AvgLap_s"]].head(10), use_container_width=True)
with c2:
    st.caption("Best consistency (lowest std dev)")
    st.dataframe(best_cons[["Driver", "Stint", "Compound", "N", "Consistency_std_s", "AvgLap_s"]].head(10), use_container_width=True)

st.divider()

# Pace drop-off
st.subheader("Stint-to-stint pace drop-off")
drop = _pace_dropoff(summary)
if drop.empty:
    st.caption("No pace drop-off computed (need at least 2 stints per driver).")
else:
    st.dataframe(drop.sort_values(["Driver", "FromStint"]), use_container_width=True)

with st.expander("Notes / limitations (for now)", expanded=False):
    st.markdown(
        """
- Auto-detected stints use a **simple heuristic**:
  - Lap number gaps, lap time jumps, and compound changes (if available).
- Degradation slope is a **linear fit** (seconds per lap). Lower is better.
- Consistency is **standard deviation** of lap time within the stint. Lower is better.
- Next upgrade: pit stop detection via official pit data + tyre life thresholds for more accurate stints.
"""
    )
