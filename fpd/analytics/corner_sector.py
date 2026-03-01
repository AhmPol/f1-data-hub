# fpd/analytics/corner_sector.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Literal, Optional

import numpy as np
import pandas as pd


CornerGroup = Literal["Low-speed", "Medium-speed", "High-speed"]


# -----------------------------
# Data models
# -----------------------------
@dataclass(frozen=True)
class CornerDef:
    """
    Corner segment definition in distance space.

    You can later replace these with real corner markers from a track database.
    For now, we can generate approximate segments (equal slices) as a fallback.
    """
    corner_number: int
    start_m: float
    end_m: float


@dataclass(frozen=True)
class CornerMetrics:
    corner_number: int
    group: CornerGroup
    entry_speed: float | None
    min_speed: float | None
    exit_speed: float | None
    brake_start_m: float | None
    throttle_on_m: float | None
    segment_time_s: float | None


@dataclass(frozen=True)
class SectorSummaryResult:
    """
    Sector results per driver:
      - sector times and deltas vs baseline
      - winners per sector
    """
    per_driver: pd.DataFrame   # Driver, S1, S2, S3, Lap, dS1, dS2, dS3, dLap
    winners: pd.DataFrame      # Sector, Winner, MarginSeconds


@dataclass(frozen=True)
class CornerBreakdownResult:
    """
    Corner table rows + group-level aggregates.
    """
    corners: pd.DataFrame      # Driver, Corner, Type, EntrySpeed, MinSpeed, ExitSpeed, BrakeStart(m), ThrottleOn(m), CornerTime(s)
    group_avgs: pd.DataFrame   # Driver, Group, Avg Entry, Avg Min, Avg Exit, Avg CornerTime


# -----------------------------
# Public API
# -----------------------------
def compute_sector_summary(
    session,
    drivers: list[str],
    baseline_driver: str | None = None,
    use_fastest_laps: bool = True,
) -> SectorSummaryResult:
    """
    Compute sector times for selected drivers and deltas vs baseline.
    Uses lap sector times if available (fast, reliable).

    baseline_driver:
      - if None: first driver in drivers list
    """
    if session is None:
        raise ValueError("Session required.")

    if not drivers:
        raise ValueError("Drivers list is empty.")

    laps = session.laps
    if laps is None or len(laps) == 0:
        raise ValueError("No laps in session.")

    drivers_u = [d.strip().upper() for d in drivers if d and d.strip()]
    if not drivers_u:
        raise ValueError("No valid drivers provided.")

    if baseline_driver is None:
        baseline_driver = drivers_u[0]
    baseline_driver = baseline_driver.strip().upper()

    rows = []
    for d in drivers_u:
        lap = _pick_driver_lap(laps, d, use_fastest_laps=use_fastest_laps)
        if lap is None:
            continue

        s1 = lap.get("Sector1Time", None)
        s2 = lap.get("Sector2Time", None)
        s3 = lap.get("Sector3Time", None)
        lt = lap.get("LapTime", None)

        rows.append(
            {
                "Driver": d,
                "S1": _td_sec(s1),
                "S2": _td_sec(s2),
                "S3": _td_sec(s3),
                "Lap": _td_sec(lt),
            }
        )

    per = pd.DataFrame(rows)
    if per.empty:
        raise ValueError("No sector data available for selected drivers.")

    # Baseline row
    if baseline_driver not in per["Driver"].values:
        baseline_driver = per["Driver"].iloc[0]

    base = per[per["Driver"] == baseline_driver].iloc[0]

    for col in ["S1", "S2", "S3", "Lap"]:
        per[f"d{col}"] = per[col] - float(base[col])

    # Winners: sector best time among selected drivers
    winners = []
    for col in ["S1", "S2", "S3"]:
        tmp = per.dropna(subset=[col]).sort_values(col)
        if tmp.empty:
            winners.append({"Sector": col, "Winner": "—", "MarginSeconds": np.nan})
            continue
        winner = tmp.iloc[0]["Driver"]
        margin = float(tmp.iloc[1][col] - tmp.iloc[0][col]) if len(tmp) > 1 else 0.0
        winners.append({"Sector": col, "Winner": winner, "MarginSeconds": margin})

    winners_df = pd.DataFrame(winners)

    return SectorSummaryResult(per_driver=per, winners=winners_df)


def compute_corner_breakdown(
    session,
    drivers: list[str],
    baseline_driver: str | None = None,
    corners: list[CornerDef] | None = None,
    use_fastest_laps: bool = True,
    min_speed_thresholds: tuple[float, float] = (120.0, 190.0),
) -> CornerBreakdownResult:
    """
    Compute per-corner metrics using telemetry distance space.

    Inputs:
      - corners: If None, creates approximate corner segments (equal slices).
      - min_speed_thresholds: (low_max, med_max) km/h thresholds based on MIN SPEED
          min <= low_max  -> Low-speed
          low_max < min <= med_max -> Medium-speed
          min > med_max -> High-speed
    """
    if session is None:
        raise ValueError("Session required.")

    if not drivers:
        raise ValueError("Drivers list is empty.")

    laps = session.laps
    if laps is None or len(laps) == 0:
        raise ValueError("No laps in session.")

    drivers_u = [d.strip().upper() for d in drivers if d and d.strip()]
    if not drivers_u:
        raise ValueError("No valid drivers provided.")

    if baseline_driver is None:
        baseline_driver = drivers_u[0]
    baseline_driver = baseline_driver.strip().upper()

    # Get a reference distance length from baseline lap
    base_lap = _pick_driver_lap(laps, baseline_driver, use_fastest_laps=use_fastest_laps)
    if base_lap is None:
        base_lap = _pick_driver_lap(laps, drivers_u[0], use_fastest_laps=use_fastest_laps)

    base_tel = _get_tel(base_lap)
    if base_tel is None or base_tel.empty:
        raise ValueError("No telemetry available to build corner segments.")

    lap_len = float(base_tel["Distance"].max())
    if corners is None:
        corners = build_fallback_corners(lap_len, n_corners=18)

    # Compute per driver
    corner_rows = []
    group_rows = []

    for d in drivers_u:
        lap = _pick_driver_lap(laps, d, use_fastest_laps=use_fastest_laps)
        if lap is None:
            continue

        tel = _get_tel(lap)
        if tel is None or tel.empty:
            continue

        per_corner = []
        for c in corners:
            seg = tel[(tel["Distance"] >= c.start_m) & (tel["Distance"] <= c.end_m)].copy()
            if seg.empty:
                per_corner.append(_empty_corner_row(d, c.corner_number))
                continue

            metrics = _compute_corner_metrics(seg, c.corner_number, min_speed_thresholds)
            per_corner.append(metrics)

        corners_df = pd.DataFrame([_metrics_to_row(d, m) for m in per_corner])
        corner_rows.append(corners_df)

        group_df = (
            corners_df.groupby("Type", as_index=False)
            .agg(
                **{
                    "Avg Entry": ("EntrySpeed", "mean"),
                    "Avg Min": ("MinSpeed", "mean"),
                    "Avg Exit": ("ExitSpeed", "mean"),
                    "Avg CornerTime": ("CornerTime(s)", "mean"),
                }
            )
        )
        group_df.insert(0, "Driver", d)
        group_rows.append(group_df)

    corners_all = pd.concat(corner_rows, ignore_index=True) if corner_rows else pd.DataFrame()
    groups_all = pd.concat(group_rows, ignore_index=True) if group_rows else pd.DataFrame()

    return CornerBreakdownResult(corners=corners_all, group_avgs=groups_all)


def build_fallback_corners(lap_length_m: float, n_corners: int = 18) -> list[CornerDef]:
    """
    Creates approximate corner segments by slicing lap distance into n segments.
    This is a placeholder until you add real corner definitions per track.
    """
    n_corners = max(6, int(n_corners))
    seg = lap_length_m / n_corners
    out = []
    for i in range(n_corners):
        start = i * seg
        end = (i + 1) * seg
        out.append(CornerDef(corner_number=i + 1, start_m=float(start), end_m=float(end)))
    return out


# -----------------------------
# Internals
# -----------------------------
def _pick_driver_lap(laps, driver: str, use_fastest_laps: bool = True):
    driver = driver.strip().upper()
    drv_laps = laps.pick_driver(driver)
    if drv_laps is None or len(drv_laps) == 0:
        return None

    if use_fastest_laps:
        try:
            lap = drv_laps.pick_fastest()
            if hasattr(lap, "iloc"):
                lap = lap.iloc[0]
            return lap
        except Exception:
            pass

    # fallback: first timed lap
    try:
        timed = drv_laps.dropna(subset=["LapTime"])
        if len(timed) > 0:
            return timed.iloc[0]
        return drv_laps.iloc[0]
    except Exception:
        return None


def _get_tel(lap) -> pd.DataFrame:
    try:
        tel = lap.get_telemetry()
    except Exception:
        return pd.DataFrame()

    if tel is None or len(tel) == 0:
        return pd.DataFrame()

    if "Distance" not in tel.columns:
        try:
            tel = tel.add_distance()
        except Exception:
            return pd.DataFrame()

    # Need at least Speed, and ideally Brake/Throttle
    keep = [c for c in ["Distance", "Speed", "Throttle", "Brake"] if c in tel.columns]
    df = tel[keep].copy().dropna(subset=["Distance"]).sort_values("Distance")

    for c in keep:
        if c != "Distance":
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Light fill for small holes
    for c in ["Speed", "Throttle", "Brake"]:
        if c in df.columns:
            df[c] = df[c].ffill(limit=5).bfill(limit=5)

    return df


def _compute_corner_metrics(seg: pd.DataFrame, corner_no: int, thresholds: tuple[float, float]) -> CornerMetrics:
    """
    Compute entry/min/exit speeds + braking/throttle points + segment time.
    Assumes seg is sorted by Distance.
    """
    low_max, med_max = thresholds

    speed = seg["Speed"].to_numpy(dtype=float) if "Speed" in seg.columns else None
    dist = seg["Distance"].to_numpy(dtype=float)

    entry_speed = float(np.nanmean(speed[: max(3, len(speed) // 10)])) if speed is not None and len(speed) > 0 else np.nan
    exit_speed = float(np.nanmean(speed[-max(3, len(speed) // 10) :])) if speed is not None and len(speed) > 0 else np.nan
    min_speed = float(np.nanmin(speed)) if speed is not None and len(speed) > 0 else np.nan

    group: CornerGroup
    if np.isnan(min_speed):
        group = "Medium-speed"
    elif min_speed <= low_max:
        group = "Low-speed"
    elif min_speed <= med_max:
        group = "Medium-speed"
    else:
        group = "High-speed"

    brake_start_m = _brake_start(seg)
    throttle_on_m = _throttle_on(seg)

    # Segment time: integrate dt = dDist / v
    seg_time = _segment_time_seconds(dist, speed)

    return CornerMetrics(
        corner_number=corner_no,
        group=group,
        entry_speed=_nan_to_none(entry_speed),
        min_speed=_nan_to_none(min_speed),
        exit_speed=_nan_to_none(exit_speed),
        brake_start_m=_nan_to_none(brake_start_m),
        throttle_on_m=_nan_to_none(throttle_on_m),
        segment_time_s=_nan_to_none(seg_time),
    )


def _segment_time_seconds(dist: np.ndarray, speed_kmh: np.ndarray | None) -> float:
    if speed_kmh is None or len(dist) < 2 or len(speed_kmh) < 2:
        return np.nan

    d = np.diff(dist, prepend=dist[0])
    d[0] = d[1] if len(d) > 1 else 0.0

    v_ms = np.maximum(0.1, speed_kmh / 3.6)
    dt = d / v_ms
    return float(np.nansum(dt))


def _brake_start(seg: pd.DataFrame) -> float:
    """
    Distance where braking starts (proxy):
      - if Brake channel exists: first point where Brake > 0.1
      - else: first point where speed drops sharply
    """
    if "Brake" in seg.columns:
        br = seg["Brake"].to_numpy(dtype=float)
        dist = seg["Distance"].to_numpy(dtype=float)
        idx = np.where(br > 0.1)[0]
        if len(idx) > 0:
            return float(dist[idx[0]])

    # speed drop proxy
    if "Speed" in seg.columns:
        sp = seg["Speed"].to_numpy(dtype=float)
        dist = seg["Distance"].to_numpy(dtype=float)
        dsp = np.diff(sp, prepend=sp[0])
        idx = np.where(dsp < -2.5)[0]  # km/h step threshold (rough)
        if len(idx) > 0:
            return float(dist[idx[0]])

    return np.nan


def _throttle_on(seg: pd.DataFrame) -> float:
    """
    Distance where throttle ramps up after apex (proxy):
      - first point where Throttle > 0.6 after minimum speed index
    """
    if "Throttle" not in seg.columns or "Speed" not in seg.columns:
        return np.nan

    th = seg["Throttle"].to_numpy(dtype=float)
    sp = seg["Speed"].to_numpy(dtype=float)
    dist = seg["Distance"].to_numpy(dtype=float)

    if len(sp) < 3:
        return np.nan

    apex_idx = int(np.nanargmin(sp))
    after = np.where(th[apex_idx:] > 0.6)[0]
    if len(after) == 0:
        return np.nan

    return float(dist[apex_idx + after[0]])


def _metrics_to_row(driver: str, m: CornerMetrics) -> dict:
    return {
        "Driver": driver,
        "Corner": m.corner_number,
        "Type": m.group,
        "EntrySpeed": m.entry_speed,
        "MinSpeed": m.min_speed,
        "ExitSpeed": m.exit_speed,
        "BrakeStart(m)": m.brake_start_m,
        "ThrottleOn(m)": m.throttle_on_m,
        "CornerTime(s)": m.segment_time_s,
    }


def _empty_corner_row(driver: str, corner_no: int) -> CornerMetrics:
    return CornerMetrics(
        corner_number=corner_no,
        group="Medium-speed",
        entry_speed=None,
        min_speed=None,
        exit_speed=None,
        brake_start_m=None,
        throttle_on_m=None,
        segment_time_s=None,
    )


def _td_sec(x) -> float:
    if x is None or pd.isna(x):
        return np.nan
    try:
        return float(pd.to_timedelta(x).total_seconds())
    except Exception:
        return np.nan


def _nan_to_none(x: float) -> float | None:
    try:
        return None if np.isnan(x) else float(x)
    except Exception:
        return None
