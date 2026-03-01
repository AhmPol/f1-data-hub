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
    name: str
    type: EventType
    date_ddmm: str  # event date shown as dd/mm
    test_number: int | None = None  # 1..N for testing events


@dataclass(frozen=True)
class SessionItem:
    identifier: str | int          # what you pass to get_session/get_testing_session
    label: str                     # what you show in UI
    date_ddmm: str                 # dd/mm
    event_type: EventType          # race/testing
    test_number: int | None = None # 1..N for testing; None for races


def _ddmm(dt) -> str:
    if dt is None:
        return "--/--"
    try:
        ts = pd.to_datetime(dt, errors="coerce", utc=True)
        if pd.isna(ts):
            return "--/--"
        return ts.strftime("%d/%m")
    except Exception:
        return "--/--"


def _is_testing_event_name(event_name: str) -> bool:
    s = str(event_name).lower()
    return ("test" in s) or ("testing" in s) or ("pre-season" in s) or ("preseason" in s)


@lru_cache(maxsize=16)
def get_available_seasons(start: int = 2018, end: int = 2026) -> list[int]:
    return list(range(start, end + 1))


@lru_cache(maxsize=64)
def get_event_schedule(season: int) -> pd.DataFrame:
    """
    Get schedule INCLUDING testing events when supported.
    """
    # Newer FastF1 supports include_testing=True
    try:
        return fastf1.get_event_schedule(season, include_testing=True)
    except TypeError:
        # Older FastF1
        return fastf1.get_event_schedule(season)


@lru_cache(maxsize=64)
def get_events_for_season(season: int) -> list[EventItem]:
    """
    Returns events including testing. Shows date as dd/mm.
    Also assigns test_number for testing events based on their order in the schedule.
    """
    schedule = get_event_schedule(season)
    if schedule is None or schedule.empty:
        return []

    # Determine testing rows
    def row_is_testing(r: pd.Series) -> bool:
        fmt = str(r.get("EventFormat", "")).strip().lower()
        if fmt == "testing":
            return True
        # fallback by name
        return _is_testing_event_name(str(r.get("EventName", "")))

    is_testing_mask = schedule.apply(row_is_testing, axis=1)
    testing_schedule = schedule[is_testing_mask].copy()

    # Assign test_number by schedule order (1-based)
    testing_names = [str(x).strip() for x in testing_schedule.get("EventName", []).tolist()]
    testing_num_map = {name: i + 1 for i, name in enumerate(testing_names) if name}

    events: list[EventItem] = []
    for _, row in schedule.iterrows():
        event_name = str(row.get("EventName", "")).strip()
        if not event_name:
            continue

        is_testing = row_is_testing(row)
        event_type: EventType = "testing" if is_testing else "race"
        test_no = testing_num_map.get(event_name) if is_testing else None

        # EventDate exists in schedule; fallback to Session1Date if missing
        event_date = row.get("EventDate", None)
        if event_date is None:
            event_date = row.get("Session1Date", None)

        events.append(
            EventItem(
                name=event_name,
                type=event_type,
                date_ddmm=_ddmm(event_date),
                test_number=test_no,
            )
        )

    return events


def get_testing_number(season: int, event_name: str) -> int | None:
    """
    Derive test_number among testing events (1-based) using schedule order.
    """
    schedule = get_event_schedule(season)
    if schedule is None or schedule.empty:
        return None

    def row_is_testing(r: pd.Series) -> bool:
        fmt = str(r.get("EventFormat", "")).strip().lower()
        if fmt == "testing":
            return True
        return _is_testing_event_name(str(r.get("EventName", "")))

    testing = schedule[schedule.apply(row_is_testing, axis=1)]
    if testing.empty:
        return None

    names = [str(x).strip() for x in testing["EventName"].tolist()]
    try:
        return names.index(event_name.strip()) + 1
    except ValueError:
        return None


def get_sessions_for_event(season: int, event_name: str) -> list[SessionItem]:
    """
    Returns sessions with dd/mm labels.

    ✅ Race weekend: uses schedule Session1..Session5 (whatever exists)
    ✅ Testing: ALWAYS returns session numbers 1/2/3 (with dates) for FastF1.get_testing_session()
       This is the critical fix so preseason testing does NOT show FP/Q/R.
    """
    schedule = get_event_schedule(season)
    if schedule is None or schedule.empty or not event_name:
        return []

    # Find schedule row
    match = schedule[schedule["EventName"].astype(str).str.strip() == str(event_name).strip()]
    if match.empty:
        # fallback: try by partial match
        match = schedule[schedule["EventName"].astype(str).str.contains(str(event_name), na=False)]
    if match.empty:
        return []

    row = match.iloc[0]

    fmt = str(row.get("EventFormat", "")).strip().lower()
    is_testing = (fmt == "testing") or _is_testing_event_name(event_name)
    event_type: EventType = "testing" if is_testing else "race"

    if is_testing:
        test_no = get_testing_number(season, event_name)

        # Testing sessions are numbered 1/2/3
        s1 = _ddmm(row.get("Session1Date", None))
        s2 = _ddmm(row.get("Session2Date", None))
        s3 = _ddmm(row.get("Session3Date", None))

        return [
            SessionItem(identifier=1, label=f"1 ({s1})", date_ddmm=s1, event_type="testing", test_number=test_no),
            SessionItem(identifier=2, label=f"2 ({s2})", date_ddmm=s2, event_type="testing", test_number=test_no),
            SessionItem(identifier=3, label=f"3 ({s3})", date_ddmm=s3, event_type="testing", test_number=test_no),
        ]

    # Race weekend sessions (whatever exists in schedule row)
    sessions: list[SessionItem] = []
    for i in range(1, 6):
        sname = row.get(f"Session{i}", None)
        if sname is None or (isinstance(sname, float) and pd.isna(sname)):
            continue
        sname = str(sname).strip()
        if not sname:
            continue

        sdate = row.get(f"Session{i}Date", None)
        ddmm = _ddmm(sdate)

        sessions.append(
            SessionItem(
                identifier=sname,
                label=f"{sname} ({ddmm})",
                date_ddmm=ddmm,
                event_type=event_type,
                test_number=None,
            )
        )

    return sessions
