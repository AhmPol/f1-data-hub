# fpd/analytics/long_runs.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Optional

import numpy as np
import pandas as pd


StintMode = Literal["auto", "manual"]


# -----------------------------
# Data models
# -----------------------------
@dataclass(frozen=True)
class StintDef:
    driver: str
    stint_id: int
    lap_start: int
    lap_end: int
    compound: str | None


@dataclass(frozen=True)
class LongRunRequest:
    drivers: list[str]
    mode: StintMode = "auto"
    min_laps_per_stint: int = 6
    manual_lap_start: int | None = None
    manual_lap_end: int | None = None
    include_in_out_laps: bool = False  # placeholder (later)
    drop_pit_laps: bool = True


@dataclass(frozen=True)
class LongRunResult:
    lap_times: pd.DataFrame        # Driver, LapNumber, LapTime(s), StintId, Compound
    stints: pd.DataFrame           # Driver, StintId, LapStart, LapEnd, Laps, Compound
    stint_metrics: pd.DataFrame    # Driver, StintId, Slope(s/lap), ConsistencyStd(s), AvgLap(s)
    best_deg: pd.DataFrame         # ranking: Driver, BestSlope(s/lap)
    best_consistency: pd.DataFrame # ranking: Driver, BestStd(s)
    pace_dropoff: pd.DataFrame     # Driver, StintA, StintB, AvgA, AvgB, Dropoff(s)


# -----------------------------
# Public API
# -----------------------------
def analyze_long_runs(session, req: LongRunRequest) -> LongRunResult:
    """
    Long runs & tire degradation analysis.

    What it does (best-effort):
      - Extract lap times for selected drivers
      - Detect stints automatically (by compound + pit gaps) OR use manual lap range
      - Compute:
          * degradation slope (linear fit lap_time vs lap_number)
          * consistency (std dev)
          * average lap time
      - Rankings:
          * best deg (lowest slope)
          * best consistency (lowest std dev)
      - Stint-to-stint pace drop-off (avg lap time differences)

    Notes:
      - Fuel correction / traffic modeling not included (later).
      - Data quality varies across sessions.
    """
    if session is None:
        raise ValueError("Session required.")

    if not req.drivers:
        raise ValueError("LongRunRequest.drivers is empty.")

    laps = getattr(session, "laps", None)
    if laps is None or len(laps) == 0:
        raise ValueError("No laps in session.")

    drivers_u = [d.strip().upper() for d in req.drivers if d and d.strip()]
    if not drivers_u:
        raise ValueError("No valid drivers provided.")

    lap_times = _extract_lap_times(laps, drivers_u, drop_pit_laps=req.drop_pit_laps)

    if lap_times.empty:
        raise ValueError("No timed laps found for selected drivers.")

    if req.mode == "manual":
        stints = _manual_stints(lap_times, drivers_u, req.manual_lap_start, req.manual_lap_end)
    else:
        stints = _auto_detect_stints(lap_times, min_laps=req.min_laps_per_stint)

    # Attach stint ids to each lap
    lap_times = _assign_stint_ids(lap_times, stints)

    # Compute per-stint metrics
    stint_metrics = _compute_stint_metrics(lap_times)

    # Rankings
    best_deg = _rank_best_deg(stint_metrics)
    best_consistency = _rank_best_consistency(stint_metrics)

    # Pace dropoff between consecutive stints
    pace_dropoff = _compute_pace_dropoff(stint_metrics)

    return LongRunResult(
        lap_times=lap_times,
        stints=stints,
        stint_metrics=stint_metrics,
        best_deg=best_deg,
        best_consistency=best_consistency,
        pace_dropoff=pace_dropoff,
    )


# -----------------------------
# Extraction
# -----------------------------
def _extract_lap_times(laps, drivers: list[str], drop_pit_laps: bool = True) -> pd.DataFrame:
    """
    Extract lap times per driver with best-effort compound and pit info.
    Output: Driver, LapNumber, LapTime(s), Compound, PitIn, PitOut
    """
    df = laps.copy()
    df = df[df["Driver"].astype(str).str.upper().isin(set(drivers))]

    # Require lap time
    df = df.dropna(subset=["LapTime"]).copy()

    df["LapNumber"] = pd.to_numeric(df.get("LapNumber"), errors="coerce").astype("Int64")
    df["LapTime(s)"] = df["LapTime"].apply(_td_sec)

    # Optional fields
    df["Compound"] = df["Compound"] if "Compound" in df.columns else None
    df["PitIn"] = df["PitInTime"].notna() if "PitInTime" in df.columns else False
    df["PitOut"] = df["PitOutTime"].notna() if "PitOutTime" in df.columns else False

    # Drop obvious non-representative laps if desired
    if drop_pit_laps:
        # PitIn or PitOut often indicates in/out laps
        if "PitInTime" in df.columns:
            df = df[df["PitInTime"].isna()]
        if "PitOutTime" in df.columns:
            df = df[df["PitOutTime"].isna()]

    df = df.dropna(subset=["LapNumber", "LapTime(s)"])
    df = df.sort_values(["Driver", "LapNumber"]).reset_index(drop=True)

    return df[["Driver", "LapNumber", "LapTime(s)", "Compound", "PitIn", "PitOut"]]


def _td_sec(x) -> float | None:
    if x is None or pd.isna(x):
        return None
    try:
        return float(pd.to_timedelta(x).total_seconds())
    except Exception:
        return None


# -----------------------------
# Stints
# -----------------------------
def _manual_stints(
    lap_times: pd.DataFrame,
    drivers: list[str],
    lap_start: int | None,
    lap_end: int | None,
) -> pd.DataFrame:
    """
    Create one stint per driver using a single manual lap range.
    """
    if lap_start is None or lap_end is None:
        # fallback to full range per driver
        lap_start = int(lap_times["LapNumber"].min())
        lap_end = int(lap_times["LapNumber"].max())

    lap_start = int(lap_start)
    lap_end = int(lap_end)

    rows = []
    for d in drivers:
        subset = lap_times[(lap_times["Driver"] == d) & (lap_times["LapNumber"].between(lap_start, lap_end))]
        if subset.empty:
            continue
        compound = _mode_or_none(subset["Compound"])
        rows.append(
            {
                "Driver": d,
                "StintId": 1,
                "LapStart": lap_start,
                "LapEnd": lap_end,
                "Laps": int(subset.shape[0]),
                "Compound": compound,
            }
        )

    return pd.DataFrame(rows)


def _auto_detect_stints(lap_times: pd.DataFrame, min_laps: int = 6) -> pd.DataFrame:
    """
    Auto-detect stints using:
      - Compound changes (primary)
      - Large lap number gaps (pit / missing data proxy)

    This is intentionally simple, but works decently as a baseline.
    """
    min_laps = max(3, int(min_laps))
    rows = []

    for driver, ddf in lap_times.groupby("Driver", sort=False):
        ddf = ddf.sort_values("LapNumber").reset_index(drop=True)

        # Identify boundaries: compound change OR lap gap > 1
        comp = ddf["Compound"].astype(str).fillna("UNK")
        lapn = ddf["LapNumber"].astype(int).to_numpy()

        comp_change = comp.ne(comp.shift(1)).fillna(False).to_numpy()
        gap_break = np.zeros_like(comp_change, dtype=bool)
        gap_break[1:] = (lapn[1:] - lapn[:-1]) > 1

        boundary = comp_change | gap_break
        # start indices of segments
        start_idxs = np.where(boundary)[0]
        if len(start_idxs) == 0 or start_idxs[0] != 0:
            start_idxs = np.insert(start_idxs, 0, 0)

        # end indices are next start - 1, last to end
        for stint_id, start in enumerate(start_idxs, start=1):
            end = (start_idxs[stint_id - 1 + 1] - 1) if (stint_id - 1 + 1) < len(start_idxs) else len(ddf) - 1

            seg = ddf.iloc[start : end + 1]
            if seg.shape[0] < min_laps:
                continue

            rows.append(
                {
                    "Driver": driver,
                    "StintId": stint_id,
                    "LapStart": int(seg["LapNumber"].iloc[0]),
                    "LapEnd": int(seg["LapNumber"].iloc[-1]),
                    "Laps": int(seg.shape[0]),
                    "Compound": _mode_or_none(seg["Compound"]),
                }
            )

    return pd.DataFrame(rows)


def _assign_stint_ids(lap_times: pd.DataFrame, stints: pd.DataFrame) -> pd.DataFrame:
    """
    Adds StintId to each lap row based on stint ranges.
    """
    lap_times = lap_times.copy()
    lap_times["StintId"] = pd.NA

    if stints is None or stints.empty:
        return lap_times

    for _, s in stints.iterrows():
        mask = (
            (lap_times["Driver"] == s["Driver"])
            & (lap_times["LapNumber"].between(int(s["LapStart"]), int(s["LapEnd"])))
        )
        lap_times.loc[mask, "StintId"] = int(s["StintId"])

    lap_times["StintId"] = pd.to_numeric(lap_times["StintId"], errors="coerce").astype("Int64")
    return lap_times


# -----------------------------
# Metrics
# -----------------------------
def _compute_stint_metrics(lap_times: pd.DataFrame) -> pd.DataFrame:
    """
    Per (Driver, StintId):
      - Slope(s/lap): linear fit lap time vs lap number
      - ConsistencyStd(s): std dev of lap times
      - AvgLap(s): mean lap time
    """
    rows = []

    valid = lap_times.dropna(subset=["StintId", "LapTime(s)", "LapNumber"]).copy()
    if valid.empty:
        return pd.DataFrame(columns=["Driver", "StintId", "Slope(s/lap)", "ConsistencyStd(s)", "AvgLap(s)", "Compound", "Laps"])

    for (driver, stint_id), seg in valid.groupby(["Driver", "StintId"], sort=False):
        y = seg["LapTime(s)"].astype(float).to_numpy()
        x = seg["LapNumber"].astype(int).to_numpy()

        slope = _linear_slope(x, y)
        std = float(np.nanstd(y, ddof=1)) if len(y) >= 2 else np.nan
        avg = float(np.nanmean(y)) if len(y) > 0 else np.nan
        compound = _mode_or_none(seg["Compound"])

        rows.append(
            {
                "Driver": driver,
                "StintId": int(stint_id),
                "Laps": int(seg.shape[0]),
                "Compound": compound,
                "Slope(s/lap)": slope,
                "ConsistencyStd(s)": std,
                "AvgLap(s)": avg,
            }
        )

    return pd.DataFrame(rows).sort_values(["Driver", "StintId"]).reset_index(drop=True)


def _linear_slope(x: np.ndarray, y: np.ndarray) -> float:
    """
    Robust-ish slope for y ~ a + b*x (returns b).
    """
    if len(x) < 2:
        return np.nan

    mask = np.isfinite(x) & np.isfinite(y)
    x2 = x[mask]
    y2 = y[mask]
    if len(x2) < 2:
        return np.nan

    # Center x for numerical stability
    x0 = x2 - np.mean(x2)
    denom = np.sum(x0 * x0)
    if denom <= 0:
        return np.nan

    b = float(np.sum(x0 * (y2 - np.mean(y2))) / denom)
    return b


# -----------------------------
# Rankings / Dropoff
# -----------------------------
def _rank_best_deg(stint_metrics: pd.DataFrame) -> pd.DataFrame:
    if stint_metrics is None or stint_metrics.empty:
        return pd.DataFrame(columns=["Driver", "BestSlope(s/lap)"])

    # best = minimum slope among stints
    best = (
        stint_metrics.dropna(subset=["Slope(s/lap)"])
        .groupby("Driver", as_index=False)["Slope(s/lap)"]
        .min()
        .rename(columns={"Slope(s/lap)": "BestSlope(s/lap)"})
        .sort_values("BestSlope(s/lap)", ascending=True)
        .reset_index(drop=True)
    )
    return best


def _rank_best_consistency(stint_metrics: pd.DataFrame) -> pd.DataFrame:
    if stint_metrics is None or stint_metrics.empty:
        return pd.DataFrame(columns=["Driver", "BestStd(s)"])

    best = (
        stint_metrics.dropna(subset=["ConsistencyStd(s)"])
        .groupby("Driver", as_index=False)["ConsistencyStd(s)"]
        .min()
        .rename(columns={"ConsistencyStd(s)": "BestStd(s)"})
        .sort_values("BestStd(s)", ascending=True)
        .reset_index(drop=True)
    )
    return best


def _compute_pace_dropoff(stint_metrics: pd.DataFrame) -> pd.DataFrame:
    """
    For each driver, compute drop-off between consecutive stints:
      Dropoff = AvgLap(stint B) - AvgLap(stint A)
    """
    if stint_metrics is None or stint_metrics.empty:
        return pd.DataFrame(columns=["Driver", "StintA", "StintB", "AvgA", "AvgB", "Dropoff(s)"])

    rows = []
    for driver, ddf in stint_metrics.sort_values(["Driver", "StintId"]).groupby("Driver", sort=False):
        ddf = ddf.reset_index(drop=True)
        for i in range(len(ddf) - 1):
            a = ddf.iloc[i]
            b = ddf.iloc[i + 1]
            if pd.isna(a["AvgLap(s)"]) or pd.isna(b["AvgLap(s)"]):
                continue
            rows.append(
                {
                    "Driver": driver,
                    "StintA": int(a["StintId"]),
                    "StintB": int(b["StintId"]),
                    "AvgA": float(a["AvgLap(s)"]),
                    "AvgB": float(b["AvgLap(s)"]),
                    "Dropoff(s)": float(b["AvgLap(s)"] - a["AvgLap(s)"]),
                }
            )

    return pd.DataFrame(rows)


# -----------------------------
# Helpers
# -----------------------------
def _mode_or_none(series: pd.Series) -> str | None:
    try:
        s = series.dropna().astype(str)
        if s.empty:
            return None
        return s.mode().iloc[0]
    except Exception:
        return None
