# fpd/data/selectors_data.py
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import fastf1
import pandas as pd


EventType = Literal["race", "testing"]


@dataclass(frozen=True)
class EventItem:
    key: int                 # ✅ unique schedule row index
    name: str
    type: EventType
    date_ddmm: str
    event_date_iso: str      # ✅ YYYY-MM-DD (for debugging / display)
    test_number: int | None = None


@dataclass(frozen=True)
class SessionItem:
    identifier: str | int
    label: str
    date_ddmm: str
    event_type: EventType
    test_number: int | None = None


def _ddmm(dt) -> str:
    try:
        ts = pd.to_datetime(dt, errors="coerce", utc=True)
        if pd.isna(ts):
            return "--/--"
        return ts.strftime("%d/%m")
    except Exception:
        return "--/--"


def _iso(dt) -> str:
    try:
        ts = pd.to_datetime(dt, errors="coerce", utc=True)
        if pd.isna(ts):
            return ""
        return ts.strftime("%Y-%m-%d")
    except Exception:
        return ""


def _is_testing_row(row: pd.Series) -> bool:
    fmt = str(row.get("EventFormat", "")).strip().lower()
    if fmt == "testing":
        return True
    # fallback by name
    name = str(row.get("EventName", "")).lower()
    return ("test" in name) or ("testing" in name) or ("pre-season" in name) or ("preseason" in name)


@lru_cache(maxsize=16)
def get_available_seasons(start: int = 2018, end: int = 2026) -> list[int]:
    return list(range(start, end + 1))


@lru_cache(maxsize=64)
def get_event_schedule(season: int) -> pd.DataFrame:
    """
    Get schedule INCLUDING testing when supported.
    """
    try:
        return fastf1.get_event_schedule(season, include_testing=True)
    except TypeError:
        return fastf1.get_event_schedule(season)


@lru_cache(maxsize=64)
def get_events_for_season(season: int) -> list[EventItem]:
    """
    Returns events including testing.
    Assigns test_number based on chronological order of testing rows.
    Uses schedule index as a unique key (fixes duplicate EventName issues).
    """
    schedule = get_event_schedule(season)
    if schedule is None or schedule.empty:
        return []

    # build testing order -> test_number
    testing = schedule[schedule.apply(_is_testing_row, axis=1)].copy()
    # sort by EventDate (fallback to Session1Date)
    testing["_sort_dt"] = testing["EventDate"].where(testing["EventDate"].notna(), testing.get("Session1Date"))
    testing = testing.sort_values("_sort_dt")

    testing_keys = testing.index.tolist()
    test_num_map = {int(k): i + 1 for i, k in enumerate(testing_keys)}

    events: list[EventItem] = []
    for key, row in schedule.iterrows():
        event_name = str(row.get("EventName", "")).strip()
        if not event_name:
            continue

        is_testing = _is_testing_row(row)
        etype: EventType = "testing" if is_testing else "race"

        event_dt = row.get("EventDate", None)
        if event_dt is None or (isinstance(event_dt, float) and pd.isna(event_dt)):
            event_dt = row.get("Session1Date", None)

        events.append(
            EventItem(
                key=int(key),
                name=event_name,
                type=etype,
                date_ddmm=_ddmm(event_dt),
                event_date_iso=_iso(event_dt),
                test_number=test_num_map.get(int(key)) if is_testing else None,
            )
        )

    return events


def get_sessions_for_event_key(season: int, event_key: int) -> list[SessionItem]:
    """
    ✅ The correct way: fetch sessions using the unique schedule row key.
    This fixes Pre-Season Testing 1 vs 2 mapping.
    """
    schedule = get_event_schedule(season)
    if schedule is None or schedule.empty:
        return []

    if event_key not in schedule.index:
        return []

    row = schedule.loc[event_key]
    is_testing = _is_testing_row(row)
    etype: EventType = "testing" if is_testing else "race"

    test_no = None
    if is_testing:
        # test_number based on chronological order of testing rows
        events = get_events_for_season(season)
        for e in events:
            if e.key == int(event_key):
                test_no = e.test_number
                break

        # testing sessions are 1/2/3
        s1 = _ddmm(row.get("Session1Date", None))
        s2 = _ddmm(row.get("Session2Date", None))
        s3 = _ddmm(row.get("Session3Date", None))

        return [
            SessionItem(identifier=1, label=f"1 ({s1})", date_ddmm=s1, event_type="testing", test_number=test_no),
            SessionItem(identifier=2, label=f"2 ({s2})", date_ddmm=s2, event_type="testing", test_number=test_no),
            SessionItem(identifier=3, label=f"3 ({s3})", date_ddmm=s3, event_type="testing", test_number=test_no),
        ]

    # race weekend sessions (whatever exists in schedule row)
    out: list[SessionItem] = []
    for i in range(1, 6):
        sname = row.get(f"Session{i}", None)
        if sname is None or (isinstance(sname, float) and pd.isna(sname)):
            continue
        sname = str(sname).strip()
        if not sname:
            continue

        sdate = row.get(f"Session{i}Date", None)
        ddmm = _ddmm(sdate)

        out.append(
            SessionItem(
                identifier=sname,
                label=f"{sname} ({ddmm})",
                date_ddmm=ddmm,
                event_type="race",
                test_number=None,
            )
        )

    return out
