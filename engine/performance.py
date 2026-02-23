import numpy as np
import pandas as pd
from utils import scale_0_100

def session_summary_indices(tel_resampled: pd.DataFrame):
    """
    Very simple “car reaction” indices from one lap telemetry.
    Outputs dict of 0–100 scores (higher = better).
    You can refine formulas later.
    """
    df = tel_resampled.copy()
    out = {}

    if "Speed" in df.columns:
        out["TopSpeed"] = float(np.nanmax(df["Speed"]))
    else:
        out["TopSpeed"] = np.nan

    # Braking efficiency proxy: average decel during brake zones
    # Approx: speed drop per meter when Brake > 0.5
    if "Brake" in df.columns and "Speed" in df.columns:
        br = df[df["Brake"] > 0.5].copy()
        if len(br) > 5:
            dv = np.diff(br["Speed"].values)
            dd = np.diff(br["Distance"].values)
            with np.errstate(divide="ignore", invalid="ignore"):
                decel = -dv / dd  # kph per meter
            out["BrakingEfficiency_raw"] = float(np.nanmean(decel))
        else:
            out["BrakingEfficiency_raw"] = np.nan
    else:
        out["BrakingEfficiency_raw"] = np.nan

    # Traction proxy: throttle ramp after low-speed points
    if "Throttle" in df.columns and "Speed" in df.columns:
        low = df[df["Speed"] < 140]
        if len(low) > 10:
            out["LowSpeedThrottle_raw"] = float(np.nanmean(low["Throttle"]))
        else:
            out["LowSpeedThrottle_raw"] = np.nan
    else:
        out["LowSpeedThrottle_raw"] = np.nan

    # High-speed stability proxy: throttle maintained at high speed
    if "Throttle" in df.columns and "Speed" in df.columns:
        high = df[df["Speed"] > 240]
        if len(high) > 10:
            out["HighSpeedThrottle_raw"] = float(np.nanmean(high["Throttle"]))
        else:
            out["HighSpeedThrottle_raw"] = np.nan
    else:
        out["HighSpeedThrottle_raw"] = np.nan

    return out

def normalize_indices_across_drivers(raw_list: list):
    """
    raw_list: [{"Driver":"VER", **raws}, ...]
    Returns df with 0–100 scaled scores per metric.
    """
    df = pd.DataFrame(raw_list)
    if df.empty:
        return df

    # Decide which raw columns to scale
    mapping = {
        "TopSpeed": "StraightLine",
        "BrakingEfficiency_raw": "Braking",
        "LowSpeedThrottle_raw": "LowSpeedTraction",
        "HighSpeedThrottle_raw": "HighSpeedConfidence",
    }

    for raw_col, score_col in mapping.items():
        if raw_col in df.columns:
            vals = df[raw_col].values.astype(float)
            df[score_col] = scale_0_100(vals)

    keep = ["Driver"] + [c for c in mapping.values() if c in df.columns] + [c for c in df.columns if c.endswith("_raw") or c == "TopSpeed"]
    return df[keep].sort_values(by=[c for c in ["StraightLine", "Braking", "LowSpeedTraction", "HighSpeedConfidence"] if c in df.columns], ascending=False)