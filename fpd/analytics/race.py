# fpd/analytics/race.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


# -----------------------------
# Data models
# -----------------------------
@dataclass(frozen=True)
class RaceResultsResult:
    results: pd.DataFrame   # Pos, Driver, Team, TotalTime(s), Gap(s), FastestLap(s), Points, Status
    has_results: bool


@dataclass(frozen=True)
class PositionChartResult:
    """
    Long format position-by-lap for plotting.
    """
    positions: pd.DataFrame  # LapNumber, Driver, Position
    has_data: bool


# -----------------------------
# Public API
# -----------------------------
def race_results_table(session) -> RaceResultsResult:
    """
    Returns a clean race results table with numeric times where possible.

    Output columns:
      Pos, Driver, Team, TotalTime(s), Gap(s), FastestLap(s), Points, Status

    Notes:
      - Data availability varies by season/event.
      - Gap is computed from TotalTime when possible.
    """
    if session is None:
        return RaceResultsResult(results=pd.DataFrame(), has_results=False)

    res = getattr(session, "results", None)
    if res is None or len(res) == 0:
        return RaceResultsResult(results=pd.DataFrame(), has_results=False)

    df = _build_results_df(res)
    return RaceResultsResult(results=df, has_results=not df.empty)


def position_by_lap(session) -> PositionChartResult:
    """
    Build position-by-lap long dataframe for a race chart.

    Tries:
      1) session.laps -> use 'Position' column per lap
      2) fallback: session.results only (no lap-by-lap) => empty
    """
    if session is None:
        return PositionChartResult(positions=pd.DataFrame(), has_data=False)

    laps = getattr(session, "laps", None)
    if laps is None or len(laps) == 0:
        return PositionChartResult(positions=pd.DataFrame(), has_data=False)

    if "Position" not in laps.columns or "LapNumber" not in laps.columns:
        return PositionChartResult(positions=pd.DataFrame(), has_data=False)

    df = laps[["LapNumber", "Driver", "Position"]].copy()
    df["LapNumber"] = pd.to_numeric(df["LapNumber"], errors="coerce").astype("Int64")
    df["Position"] = pd.to_numeric(df["Position"], errors="coerce").astype("Int64")
    df["Driver"] = df["Driver"].astype(str).str.strip()

    df = df.dropna(subset=["LapNumber", "Position", "Driver"])
    if df.empty:
        return PositionChartResult(positions=pd.DataFrame(), has_data=False)

    # Keep one position per driver per lap (min position if duplicates)
    df = (
        df.groupby(["LapNumber", "Driver"], as_index=False)["Position"]
        .min()
        .sort_values(["LapNumber", "Position"])
        .reset_index(drop=True)
    )

    return PositionChartResult(positions=df, has_data=True)


# -----------------------------
# Internals
# -----------------------------
def _build_results_df(results: pd.DataFrame) -> pd.DataFrame:
    r = results.copy()

    pos = r["Position"] if "Position" in r.columns else pd.Series(range(1, len(r) + 1))

    # Driver label preference
    if "Abbreviation" in r.columns:
        driver = r["Abbreviation"]
    elif "BroadcastName" in r.columns:
        driver = r["BroadcastName"]
    elif "FullName" in r.columns:
        driver = r["FullName"]
    else:
        driver = pd.Series(["—"] * len(r))

    # Team label preference
    if "TeamName" in r.columns:
        team = r["TeamName"]
    elif "Team" in r.columns:
        team = r["Team"]
    else:
        team = pd.Series(["—"] * len(r))

    total_time = r["Time"] if "Time" in r.columns else pd.Series([pd.NaT] * len(r))
    points = r["Points"] if "Points" in r.columns else pd.Series([np.nan] * len(r))
    status = r["Status"] if "Status" in r.columns else pd.Series(["—"] * len(r))

    total_sec = total_time.apply(_td_sec)

    # Compute gaps vs winner (in seconds), if we have valid total_sec
    gap_sec = None
    if total_sec.notna().any():
        leader = float(total_sec.dropna().min())
        gap_sec = total_sec - leader

    # Fastest lap time: best effort
    if "FastestLapTime" in r.columns:
        fl_sec = r["FastestLapTime"].apply(_td_sec)
    else:
        fl_sec = pd.Series([np.nan] * len(r))

    df = pd.DataFrame(
        {
            "Pos": pd.to_numeric(pos, errors="coerce").astype("Int64"),
            "Driver": driver.astype(str).str.strip(),
            "Team": team.astype(str).str.strip(),
            "TotalTime(s)": total_sec,
            "Gap(s)": gap_sec if gap_sec is not None else np.nan,
            "FastestLap(s)": fl_sec,
            "Points": pd.to_numeric(points, errors="coerce"),
            "Status": status.astype(str),
        }
    )

    df = df.sort_values("Pos", ascending=True, na_position="last").reset_index(drop=True)
    return df


def _td_sec(x) -> float | None:
    if x is None or pd.isna(x):
        return np.nan
    try:
        return float(pd.to_timedelta(x).total_seconds())
    except Exception:
        # Sometimes it's already numeric seconds
        try:
            return float(x)
        except Exception:
            return np.nan
