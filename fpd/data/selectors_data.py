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


@dataclass(frozen=True)
class SessionItem:
    identifier: str          # what you pass to get_session/get_testing_session
    label: str               # what you show in UI
    date_ddmm: str           # dd/mm
    event_type: EventType    # race/testing
    test_number: int | None  # 1..N for testing; None for races


def _ddmm(dt) -> str:
    if dt is None or (isinstance(dt, float) and pd.isna(dt)):
        return "--/--"
    try:
        # dt can be pandas Timestamp
        return pd.to_datetime(dt).strftime("%d/%m")
    except Exception:
        return "--/--"


@lru_cache(maxsize=16)
def get_available_seasons(start: int = 2018, end: int = 2026) -> list[int]:
    return list(range(start, end + 1))


@lru_cache(maxsize=64)
def get_event_schedule(season: int) -> pd.DataFrame:
    """
    FastF1 schedule includes both race weekends and testing events.
    """
    return fastf1.get_event_schedule(season)


@lru_cache(maxsize=64)
def get_events_for_season(season: int) -> list[EventItem]:
    """
    Returns events including testing. Shows date as dd/mm.
    """
    schedule = get_event_schedule(season)

    events: list[EventItem] = []
    for _, row in schedule.iterrows():
        event_name = str(row.get("EventName", "")).strip()
        if not event_name:
            continue

        fmt = str(row.get("EventFormat", "")).strip().lower()
        event_type: EventType = "testing" if fmt == "testing" else "race"

        # Usually "EventDate" exists; if not, fall back to "Session5Date"/etc.
        event_date = row.get("EventDate", None)
        events.append(
            EventItem(
                name=event_name,
                type=event_type,
                date_ddmm=_ddmm(event_date),
            )
        )

    # keep order as schedule order (don’t sort alphabetically; schedule order is nicer)
    return events


def get_testing_number(season: int, event_name: str) -> int | None:
    """
    For testing events, FastF1 uses get_testing_session(year, test_number, session).
    We derive test_number from schedule ordering among testing events (1-based).
    """
    schedule = get_event_schedule(season)
    testing = schedule[schedule["EventFormat"].astype(str).str.lower() == "testing"].copy()

    if testing.empty:
        return None

    # keep schedule order
    testing_names = [str(x).strip() for x in testing["EventName"].tolist()]
    try:
        return testing_names.index(event_name.strip()) + 1
    except ValueError:
        return None


def get_sessions_for_event(season: int, event_name: str) -> list[SessionItem]:
    """
    Returns session identifiers + UI labels including dd/mm.

    - Race weekend: FP1/FP2/FP3/Q/R (only if they exist)
    - Testing: Practice 1/2/3 (typical) with dd/mm
    """
    schedule = get_event_schedule(season)

    # Determine event type from schedule
    row = schedule[schedule["EventName"].astype(str) == event_name].head(1)
    if row.empty:
        # fallback: assume race
        event_type: EventType = "race"
    else:
        fmt = str(row.iloc[0].get("EventFormat", "")).lower()
        event_type = "testing" if fmt == "testing" else "race"

    if event_type == "testing":
        test_no = get_testing_number(season, event_name)

        # Best effort: pull dates via FastF1 Event object if available
        # If this fails, dates will show "--/--"
        sessions: list[SessionItem] = []
        try:
            event = fastf1.get_event(season, event_name)
            # event is a pandas Series with keys like 'Session1', 'Session1Date', etc.
            for i in range(1, 6):
                sname = event.get(f"Session{i}", None)
                sdate = event.get(f"Session{i}Date", None)
                if not sname:
                    continue
                sname = str(sname).strip()

                # Testing sessions are often named like "Practice 1", "Practice 2"...
                identifier = sname
                date_ddmm = _ddmm(sdate)
                label = f"{sname} ({date_ddmm})"

                sessions.append(
                    SessionItem(
                        identifier=identifier,
                        label=label,
                        date_ddmm=date_ddmm,
                        event_type="testing",
                        test_number=test_no,
                    )
                )

        except Exception:
            # fallback typical testing names (still shows dd/mm unknown)
            for sname in ["Practice 1", "Practice 2", "Practice 3"]:
                sessions.append(
                    SessionItem(
                        identifier=sname,
                        label=f"{sname} (--/--)",
                        date_ddmm="--/--",
                        event_type="testing",
                        test_number=test_no,
                    )
                )

        return sessions

    # race weekend
    sessions: list[SessionItem] = []
    try:
        event = fastf1.get_event(season, event_name)

        # We only include sessions that exist in the event object.
        # Typically: FP1 FP2 FP3 Q R (plus Sprint formats in some years)
        for i in range(1, 6):
            sname = event.get(f"Session{i}", None)
            sdate = event.get(f"Session{i}Date", None)
            if not sname:
                continue
            sname = str(sname).strip()

            # identifiers that FastF1 accepts often include abbreviations like FP1/FP2/Q/R
            identifier = sname
            date_ddmm = _ddmm(sdate)
            label = f"{sname} ({date_ddmm})"

            sessions.append(
                SessionItem(
                    identifier=identifier,
                    label=label,
                    date_ddmm=date_ddmm,
                    event_type="race",
                    test_number=None,
                )
            )

        return sessions

    except Exception:
        # last-resort fallback (no dates)
        for s in ["FP1", "FP2", "FP3", "Q", "R"]:
            sessions.append(
                SessionItem(
                    identifier=s,
                    label=f"{s} (--/--)",
                    date_ddmm="--/--",
                    event_type="race",
                    test_number=None,
                )
            )
        return sessions
