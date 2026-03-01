# fpd/analytics/compare.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

import numpy as np
import pandas as pd


CompareMode = Literal["current", "all_time"]


# -----------------------------
# Data models
# -----------------------------
@dataclass(frozen=True)
class LapRef:
    driver: str                  # e.g., "VER"
    lap_number: int | None = None  # if None => fastest lap


@dataclass(frozen=True)
class CompareRequest:
    mode: CompareMode
    laps: list[LapRef]
    channels: tuple[str, ...] = ("Speed", "Throttle", "Brake", "Gear", "RPM")
    resample_m: float = 1.0      # distance grid step (meters)


@dataclass(frozen=True)
class CompareResult:
    """
    Plot-ready dataframes.
    All dfs are aligned on the same Distance grid.
    """
    telemetry: pd.DataFrame       # long format: Distance, Driver, Speed, Throttle, Brake, Gear, RPM
    delta: pd.DataFrame           # long format: Distance, Driver, DeltaSeconds (vs baseline)
    meta: pd.DataFrame            # per driver info: Driver, LapNumber, LapTime, Compound, Team, IsBaseline


# -----------------------------
# Public API
# -----------------------------
def build_compare(session, req: CompareRequest) -> CompareResult:
    """
    Main entry point.
    For now, supports 'current' mode (FastF1 session provided).
    'all_time' mode is scaffolded (raise if session is None).
    """
    if req.mode == "all_time":
        raise NotImplementedError(
            "All-time mode needs your data source (multiple seasons). "
            "Use current mode first."
        )

    if session is None:
        raise ValueError("Session is required for current mode compare.")

    if not req.laps:
        raise ValueError("CompareRequest.laps must contain at least 1 LapRef.")

    # 1) Resolve laps to actual FastF1 Lap objects
    lap_objs = _resolve_laps(session, req.laps)

    # 2) Extract telemetry per lap (distance-based), keep only channels we need
    per_driver_tel = []
    meta_rows = []
    for lap in lap_objs:
        driver = str(lap.get("Driver", "")).strip() or "UNK"
        tel = _extract_telemetry_distance(lap, req.channels)

        if tel is None or tel.empty:
            continue

        # Standardize
        tel["Driver"] = driver
        per_driver_tel.append(tel)

        meta_rows.append(_lap_meta_row(lap))

    if not per_driver_tel:
        raise ValueError("No telemetry found for requested laps.")

    meta = pd.DataFrame(meta_rows)
    meta = _ensure_meta_types(meta)

    # 3) Choose baseline = first LapRef in request order
    baseline_driver = req.laps[0].driver.strip().upper()
    meta["IsBaseline"] = meta["Driver"].astype(str).str.upper().eq(baseline_driver)

    # 4) Align all telemetry to a shared distance grid
    distance_grid = _make_distance_grid(per_driver_tel, step_m=req.resample_m)
    aligned = _align_all_to_grid(per_driver_tel, distance_grid, req.channels)

    # 5) Compute delta time trace vs baseline driver
    delta = _compute_delta_time(aligned, baseline_driver=baseline_driver)

    return CompareResult(
        telemetry=aligned,
        delta=delta,
        meta=meta,
    )


# -----------------------------
# Lap resolution
# -----------------------------
def _resolve_laps(session, lap_refs: list[LapRef]):
    """
    Turns LapRef selections into FastF1 lap objects.
    - If lap_number is None => fastest lap for that driver
    - Else => specific lap number for that driver
    """
    laps = session.laps
    if laps is None or len(laps) == 0:
        raise ValueError("Session has no laps.")

    out = []
    for ref in lap_refs:
        drv = ref.driver.strip().upper()
        if not drv:
            continue

        drv_laps = laps.pick_driver(drv)
        if drv_laps is None or len(drv_laps) == 0:
            continue

        if ref.lap_number is None:
            lap = drv_laps.pick_fastest()
            if hasattr(lap, "iloc"):
                lap = lap.iloc[0]
        else:
            # LapNumber in FastF1 is numeric (float sometimes); best-effort match
            ln = ref.lap_number
            match = drv_laps[pd.to_numeric(drv_laps["LapNumber"], errors="coerce") == ln]
            if match is None or len(match) == 0:
                # fallback: nearest
                nums = pd.to_numeric(drv_laps["LapNumber"], errors="coerce")
                idx = (nums - ln).abs().idxmin()
                lap = drv_laps.loc[idx]
            else:
                lap = match.iloc[0]

        out.append(lap)

    if not out:
        raise ValueError("Could not resolve any requested laps (check driver codes / lap numbers).")

    return out


# -----------------------------
# Telemetry extraction
# -----------------------------
def _extract_telemetry_distance(lap, channels: Iterable[str]) -> pd.DataFrame:
    """
    Returns telemetry dataframe with:
      - Distance (meters)
      - channels requested (if present)
    Uses add_distance() and interpolates missing numeric telemetry lightly.
    """
    try:
        tel = lap.get_telemetry()
    except Exception:
        return pd.DataFrame()

    if tel is None or len(tel) == 0:
        return pd.DataFrame()

    # Ensure Distance exists
    if "Distance" not in tel.columns:
        try:
            tel = tel.add_distance()
        except Exception:
            return pd.DataFrame()

    keep = ["Distance"]
    for c in channels:
        if c in tel.columns:
            keep.append(c)

    df = tel[keep].copy()
    df = df.dropna(subset=["Distance"]).sort_values("Distance")

    # Make numeric where possible (Speed etc). Gear can be int-ish.
    for c in df.columns:
        if c == "Distance":
            continue
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Light cleaning: forward fill small gaps then backfill for start gaps
    for c in df.columns:
        if c == "Distance":
            continue
        df[c] = df[c].ffill(limit=5).bfill(limit=5)

    return df


# -----------------------------
# Alignment / Resampling
# -----------------------------
def _make_distance_grid(per_driver_tel: list[pd.DataFrame], step_m: float = 1.0) -> np.ndarray:
    """
    Build a common distance grid from 0..min(max_distance across drivers).
    We use the minimum max distance so all traces overlap.
    """
    if step_m <= 0:
        step_m = 1.0

    max_dists = []
    for df in per_driver_tel:
        if "Distance" in df.columns and len(df) > 0:
            max_dists.append(float(df["Distance"].max()))

    if not max_dists:
        raise ValueError("No valid distance found in telemetry.")

    max_common = max(0.0, min(max_dists))
    return np.arange(0.0, max_common + step_m, step_m, dtype=float)


def _align_all_to_grid(
    per_driver_tel: list[pd.DataFrame],
    grid: np.ndarray,
    channels: Iterable[str],
) -> pd.DataFrame:
    """
    Returns long dataframe aligned on grid:
      Distance, Driver, <channels...>
    Uses linear interpolation for numeric channels.
    """
    out_frames = []
    channels = tuple(channels)

    for df in per_driver_tel:
        if df is None or df.empty:
            continue

        driver = str(df.get("Driver", pd.Series(["UNK"])).iloc[0])

        aligned = pd.DataFrame({"Distance": grid})
        x = df["Distance"].to_numpy(dtype=float)

        for c in channels:
            if c not in df.columns:
                aligned[c] = np.nan
                continue

            y = pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=float)

            # Interpolate y over grid
            aligned[c] = _interp_1d(x, y, grid)

        aligned["Driver"] = driver
        out_frames.append(aligned)

    if not out_frames:
        raise ValueError("No telemetry could be aligned.")

    wide = pd.concat(out_frames, ignore_index=True)

    # Convert Gear to integer-ish if present
    if "Gear" in wide.columns:
        wide["Gear"] = pd.to_numeric(wide["Gear"], errors="coerce").round().astype("Int64")

    # Long format not strictly required, but easier for plotly overlays
    return wide[["Distance", "Driver", *[c for c in channels if c in wide.columns]]]


def _interp_1d(x: np.ndarray, y: np.ndarray, x_new: np.ndarray) -> np.ndarray:
    """
    Safe linear interpolation that handles NaNs.
    """
    if len(x) < 2:
        return np.full_like(x_new, np.nan, dtype=float)

    mask = np.isfinite(x) & np.isfinite(y)
    x2 = x[mask]
    y2 = y[mask]

    if len(x2) < 2:
        return np.full_like(x_new, np.nan, dtype=float)

    # Ensure strictly increasing x
    order = np.argsort(x2)
    x2 = x2[order]
    y2 = y2[order]

    # np.interp requires monotonic x; it will extrapolate ends with edge values
    return np.interp(x_new, x2, y2)


# -----------------------------
# Delta time computation
# -----------------------------
def _compute_delta_time(aligned: pd.DataFrame, baseline_driver: str) -> pd.DataFrame:
    """
    Computes cumulative delta time vs baseline using speed traces:
      dt ≈ dDistance / Speed

    - Speed assumed km/h; convert to m/s
    - DeltaSeconds positive => slower than baseline at that distance
    """
    if "Speed" not in aligned.columns:
        # Without speed, we can't compute delta. Return empty.
        return pd.DataFrame(columns=["Distance", "Driver", "DeltaSeconds"])

    base = baseline_driver.strip().upper()

    # Pivot to get per-driver Speed arrays on same Distance grid
    pivot = aligned.pivot_table(index="Distance", columns="Driver", values="Speed", aggfunc="mean")
    if pivot.empty:
        return pd.DataFrame(columns=["Distance", "Driver", "DeltaSeconds"])

    # Find actual baseline column (case-insensitive)
    cols_upper = {str(c).upper(): c for c in pivot.columns}
    if base not in cols_upper:
        # fallback: first driver as baseline
        base_col = pivot.columns[0]
    else:
        base_col = cols_upper[base]

    dist = pivot.index.to_numpy(dtype=float)

    # Distance step (assume uniform)
    if len(dist) < 2:
        return pd.DataFrame(columns=["Distance", "Driver", "DeltaSeconds"])

    d_dist = np.diff(dist, prepend=dist[0])
    d_dist[0] = d_dist[1] if len(d_dist) > 1 else 0.0

    def to_time_seconds(speed_kmh: np.ndarray) -> np.ndarray:
        speed_ms = np.maximum(0.1, speed_kmh / 3.6)  # avoid div0
        dt = d_dist / speed_ms
        return np.cumsum(dt)

    base_time = to_time_seconds(pivot[base_col].to_numpy(dtype=float))

    rows = []
    for drv in pivot.columns:
        t = to_time_seconds(pivot[drv].to_numpy(dtype=float))
        delta = t - base_time
        rows.append(
            pd.DataFrame(
                {
                    "Distance": dist,
                    "Driver": drv,
                    "DeltaSeconds": delta,
                }
            )
        )

    return pd.concat(rows, ignore_index=True)


# -----------------------------
# Meta
# -----------------------------
def _lap_meta_row(lap) -> dict:
    """
    Best-effort metadata for display.
    """
    def safe(v):
        return None if v is None or (isinstance(v, float) and np.isnan(v)) else v

    driver = str(lap.get("Driver", "")).strip()
    team = str(lap.get("Team", "")).strip() if "Team" in lap else None
    compound = str(lap.get("Compound", "")).strip() if "Compound" in lap else None
    lap_no = safe(lap.get("LapNumber", None))
    lap_time = lap.get("LapTime", None)

    return {
        "Driver": driver,
        "Team": team,
        "Compound": compound,
        "LapNumber": int(lap_no) if lap_no is not None else None,
        "LapTime": _fmt_timedelta(lap_time),
    }


def _ensure_meta_types(meta: pd.DataFrame) -> pd.DataFrame:
    if meta.empty:
        return meta
    if "LapNumber" in meta.columns:
        meta["LapNumber"] = pd.to_numeric(meta["LapNumber"], errors="coerce").astype("Int64")
    return meta


def _fmt_timedelta(x) -> str:
    if x is None or (hasattr(pd, "isna") and pd.isna(x)):
        return "—"
    try:
        td = pd.to_timedelta(x)
        total_ms = int(td.total_seconds() * 1000)
        minutes = total_ms // 60000
        seconds = (total_ms % 60000) // 1000
        ms = total_ms % 1000
        return f"{minutes}:{seconds:02d}.{ms:03d}"
    except Exception:
        return str(x)
