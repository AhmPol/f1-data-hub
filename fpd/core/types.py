# fpd/core/types.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


EventType = Literal["race", "testing"]


@dataclass(frozen=True)
class SessionRef:
    """
    A minimal reference to load a session.
    For race: event_type='race', event_name provided, test_number=None
    For testing: event_type='testing', test_number provided
    """
    season: int
    event_name: str
    session_identifier: str
    event_type: EventType = "race"
    test_number: Optional[int] = None


@dataclass(frozen=True)
class DriverSelection:
    drivers: list[str]
    laps: list[int] | None = None
