import numpy as np
import pandas as pd

def select_quick_laps(laps_df: pd.DataFrame, drivers=None, only_quick=True):
    df = laps_df.copy()
    if drivers:
        df = df[df["Driver"].isin(drivers)]
    # Valid lap times
    df = df[df["LapTime"].notna()]
    if only_quick:
        # Remove in/out laps if columns exist
        for col in ["PitInTime", "PitOutTime"]:
            if col in df.columns:
                pass
        if "IsAccurate" in df.columns:
            df = df[df["IsAccurate"] == True]
    return df

def fastest_laps_by_driver(laps_df: pd.DataFrame, drivers):
    df = select_quick_laps(laps_df, drivers=drivers, only_quick=True)
    # pick min LapTime per driver
    idx = df.groupby("Driver")["LapTime"].idxmin()
    out = df.loc[idx].sort_values("LapTime")
    return out

def get_lap_telemetry_distance(lap) -> pd.DataFrame:
    """
    Returns telemetry with Distance axis.
    FastF1 lap.get_telemetry() usually includes Distance when add_distance() applied.
    """
    tel = lap.get_telemetry().copy()
    if "Distance" not in tel.columns:
        tel = tel.add_distance()
    return tel

def resample_to_distance(tel: pd.DataFrame, step_m: float = 1.0) -> pd.DataFrame:
    """
    Resample telemetry to uniform Distance step (meters).
    Keeps columns: Speed, Throttle, Brake, nGear, RPM, Distance, Time if present.
    """
    tel = tel.copy()
    tel = tel[tel["Distance"].notna()].sort_values("Distance")
    dmin, dmax = float(tel["Distance"].min()), float(tel["Distance"].max())
    grid = np.arange(dmin, dmax, step_m)

    out = pd.DataFrame({"Distance": grid})
    for col in ["Speed", "Throttle", "Brake", "nGear", "RPM"]:
        if col in tel.columns:
            out[col] = np.interp(grid, tel["Distance"].values, tel[col].values)
    # Time interpolation (convert to seconds if timedelta)
    if "Time" in tel.columns:
        t = tel["Time"]
        if hasattr(t.iloc[0], "total_seconds"):
            tsec = t.dt.total_seconds().values
        else:
            tsec = t.values.astype(float)
        out["Time_s"] = np.interp(grid, tel["Distance"].values, tsec)
    return out

def compute_delta_seconds(ref: pd.DataFrame, cmp: pd.DataFrame) -> pd.Series:
    """Delta = cmp time - ref time on the same Distance grid."""
    if "Time_s" not in ref.columns or "Time_s" not in cmp.columns:
        return None
    # Align to shortest common distance
    n = min(len(ref), len(cmp))
    return (cmp["Time_s"].iloc[:n].values - ref["Time_s"].iloc[:n].values)