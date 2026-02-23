import numpy as np
import pandas as pd

def _smooth(x, win=21):
    if win < 3:
        return x
    win = int(win) if int(win) % 2 == 1 else int(win) + 1
    k = np.ones(win) / win
    return np.convolve(x, k, mode="same")

def detect_corners_from_speed(tel_resampled: pd.DataFrame,
                              min_separation_m: float = 250.0,
                              smooth_win: int = 41,
                              min_prominence_kph: float = 20.0,
                              window_m: float = 120.0):
    """
    Basic corner detection from local minima in smoothed Speed vs Distance.
    Returns list of corners: [{"corner":1, "d_min":..., "d_start":..., "d_end":...}, ...]
    """
    if "Speed" not in tel_resampled.columns:
        return []

    d = tel_resampled["Distance"].values
    v = tel_resampled["Speed"].values
    vs = _smooth(v, smooth_win)

    # local minima: sign change of derivative
    dv = np.diff(vs)
    sign = np.sign(dv)
    sign_change = np.diff(sign)
    minima_idx = np.where(sign_change > 1)[0] + 1  # from - to +

    # filter by prominence (speed drop compared to nearby)
    corners = []
    last_d = -1e9
    corner_id = 0

    for idx in minima_idx:
        dm = float(d[idx])
        if dm - last_d < min_separation_m:
            continue

        # estimate prominence using nearby max in a range
        left = max(0, idx - 200)
        right = min(len(vs) - 1, idx + 200)
        local_max = float(np.max(vs[left:right+1]))
        local_min = float(vs[idx])
        if (local_max - local_min) < min_prominence_kph:
            continue

        corner_id += 1
        last_d = dm
        corners.append({
            "corner": corner_id,
            "d_min": dm,
            "d_start": max(float(d[0]), dm - window_m),
            "d_end": min(float(d[-1]), dm + window_m),
        })

    return corners

def compute_corner_table(tel_resampled: pd.DataFrame, corners: list):
    """
    Compute simple corner metrics for each detected corner:
    entry speed, min speed, exit speed,
    brake start (distance), throttle-on (distance),
    time delta in segment (if Time_s exists)
    """
    df = tel_resampled.copy()
    out_rows = []

    for c in corners:
        seg = df[(df["Distance"] >= c["d_start"]) & (df["Distance"] <= c["d_end"])].copy()
        if seg.empty:
            continue

        # entry/min/exit
        entry_speed = float(seg["Speed"].iloc[0]) if "Speed" in seg else np.nan
        min_idx = int(seg["Speed"].idxmin()) if "Speed" in seg else seg.index[0]
        min_speed = float(df.loc[min_idx, "Speed"]) if "Speed" in df else np.nan
        exit_speed = float(seg["Speed"].iloc[-1]) if "Speed" in seg else np.nan
        d_min = float(df.loc[min_idx, "Distance"])

        # brake start: first point before d_min where Brake > 0.5 (if exists)
        brake_start = np.nan
        if "Brake" in df.columns:
            pre = seg[seg["Distance"] <= d_min]
            hit = pre[pre["Brake"] > 0.5]
            if not hit.empty:
                brake_start = float(hit["Distance"].iloc[0])

        # throttle on: first point after d_min where Throttle > 90 (if exists)
        throttle_on = np.nan
        if "Throttle" in df.columns:
            post = seg[seg["Distance"] >= d_min]
            hit = post[post["Throttle"] > 90]
            if not hit.empty:
                throttle_on = float(hit["Distance"].iloc[0])

        # time in segment
        seg_time = np.nan
        if "Time_s" in seg.columns:
            seg_time = float(seg["Time_s"].iloc[-1] - seg["Time_s"].iloc[0])

        # corner type by min speed
        if np.isfinite(min_speed):
            if min_speed < 120:
                ctype = "Low"
            elif min_speed < 200:
                ctype = "Medium"
            else:
                ctype = "High"
        else:
            ctype = "Unknown"

        out_rows.append({
            "Corner": c["corner"],
            "Type": ctype,
            "EntrySpeed": entry_speed,
            "MinSpeed": min_speed,
            "ExitSpeed": exit_speed,
            "BrakeStart_m": brake_start,
            "ThrottleOn_m": throttle_on,
            "SegTime_s": seg_time,
        })

    return pd.DataFrame(out_rows)

def sector_summary(laps_df: pd.DataFrame, drivers: list):
    """
    Sector deltas based on fastest lap per driver (S1/S2/S3).
    Returns dataframe sorted by LapTime and shows who wins sectors.
    """
    df = laps_df.copy()
    df = df[df["Driver"].isin(drivers)]
    df = df[df["LapTime"].notna()]
    idx = df.groupby("Driver")["LapTime"].idxmin()
    best = df.loc[idx].copy().sort_values("LapTime")

    cols = ["Driver", "LapTime", "Sector1Time", "Sector2Time", "Sector3Time"]
    present = [c for c in cols if c in best.columns]
    best = best[present]

    # compute sector deltas to best sector time
    for s in ["Sector1Time", "Sector2Time", "Sector3Time"]:
        if s in best.columns:
            best_s = best[s].min()
            best[s.replace("Time", "Delta")] = (best[s] - best_s)

    return best