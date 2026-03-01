# fpd/analytics/laps.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np
import pandas as pd


# -----------------------------
# Data models
# -----------------------------
@dataclass(frozen=True)
class FastestLapRow:
    team: str | None
    driver: str
    lap_number: int | None
    lap_time_s: float | None
    s1_s: float | None
    s2_s: float | None
    s3_s: float | None
    compound: str | None
    top_speed_kmh: float | None


# -----------------------------
# Public API
# -----------------------------
def fastest_laps_table(session, drivers: Optional[Iterable[str]] = None) -> pd.DataFrame:
    """
    Returns one fastest lap per driver for the given session.

    Output columns:
      Team, Driver, LapNumber, LapTime(s), S1(s), S2(s), S3(s), Compound, TopSpeed(km/h)

    Note:
      - Top speed uses telemetry and may be slow if many drivers are selected.
      - You can later cache per-driver telemetry results if needed.
    """
    if session is None:
        return pd.DataFrame()

    laps = getattr(session, "laps", None)
    if laps is None or len(laps) == 0:
        return pd.DataFrame()

    # Filter drivers if provided
    if drivers:
        drivers_u = {d.strip().upper() for d in drivers if d and d.strip()}
        laps = laps[laps["Driver"].astype(str).str.upper().isin(drivers_u)]

    # Pick fastest lap for each driver (best effort)
    try:
        fastest = laps.pick_fastest()
        if hasattr(fastest, "groupby"):
            # Sometimes pick_fastest returns multiple rows; normalize to 1 per driver
            fastest = fastest.sort_values("LapTime").groupby("Driver", as_index=False).first()
    except Exception:
        # Manual fallback
        timed = laps.dropna(subset=["LapTime"]).copy()
        if timed.empty:
            return pd.DataFrame()
        fastest = timed.sort_values("LapTime").groupby("Driver", as_index=False).first()

    rows: list[dict] = []
    for _, lap in fastest.iterrows():
        rows.append(_fastest_lap_row(lap))

    df = pd.DataFrame(rows)

    # Sort by lap time ascending where possible
    if "LapTime(s)" in df.columns:
        df = df.sort_values("LapTime(s)", ascending=True, na_position="last")

    return df


def pick_driver_lap(session, driver: str, lap_number: int | None = None):
    """
    Returns a FastF1 lap object/row:
      - lap_number None => fastest lap
      - lap_number specified => closest matching lap number
    """
    if session is None:
        return None
    laps = getattr(session, "laps", None)
    if laps is None or len(laps) == 0:
        return None

    drv = (driver or "").strip().upper()
    if not drv:
        return None

    drv_laps = laps.pick_driver(drv)
    if drv_laps is None or len(drv_laps) == 0:
        return None

    if lap_number is None:
        try:
            lap = drv_laps.pick_fastest()
            if hasattr(lap, "iloc"):
                lap = lap.iloc[0]
            return lap
        except Exception:
            pass

        timed = drv_laps.dropna(subset=["LapTime"])
        return timed.iloc[0] if len(timed) > 0 else drv_laps.iloc[0]

    # specific lap number (best-effort)
    nums = pd.to_numeric(drv_laps["LapNumber"], errors="coerce")
    if nums.isna().all():
        return drv_laps.iloc[0]

    target = int(lap_number)
    exact = drv_laps[nums == target]
    if len(exact) > 0:
        return exact.iloc[0]

    idx = (nums - target).abs().idxmin()
    return drv_laps.loc[idx]


def compute_top_speed_kmh(lap) -> float | None:
    """
    Computes max telemetry speed for the lap.
    Returns None if telemetry unavailable.
    """
    try:
        tel = lap.get_telemetry()
    except Exception:
        return None

    if tel is None or len(tel) == 0 or "Speed" not in tel.columns:
        return None

    sp = pd.to_numeric(tel["Speed"], errors="coerce")
    if sp.isna().all():
        return None
    return float(sp.max())


# -----------------------------
# Internals
# -----------------------------
def _fastest_lap_row(lap) -> dict:
    driver = str(lap.get("Driver", "")).strip()
    team = str(lap.get("Team", "")).strip() if "Team" in lap else None
    compound = str(lap.get("Compound", "")).strip() if "Compound" in lap else None

    lap_no = _to_int(lap.get("LapNumber", None))
    lap_time_s = _td_sec(lap.get("LapTime", None))
    s1_s = _td_sec(lap.get("Sector1Time", None))
    s2_s = _td_sec(lap.get("Sector2Time", None))
    s3_s = _td_sec(lap.get("Sector3Time", None))

    top_speed = compute_top_speed_kmh(lap)

    return {
        "Team": team,
        "Driver": driver,
        "LapNumber": lap_no,
        "LapTime(s)": lap_time_s,
        "S1(s)": s1_s,
        "S2(s)": s2_s,
        "S3(s)": s3_s,
        "Compound": compound,
        "TopSpeed(km/h)": top_speed,
    }


def _td_sec(x) -> float | None:
    if x is None or pd.isna(x):
        return None
    try:
        return float(pd.to_timedelta(x).total_seconds())
    except Exception:
        return None


def _to_int(x) -> int | None:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    try:
        return int(x)
    except Exception:
        try:
            v = pd.to_numeric(x, errors="coerce")
            return None if pd.isna(v) else int(v)
        except Exception:
            return None
