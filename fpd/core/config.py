# fpd/core/config.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    app_name: str = "Formula Performance Dashboard"
    cache_dir: str = "data/cache"
    exports_dir: str = "data/exports"

    # Selector defaults
    default_season: int = 2026
    default_event_name: str = "Bahrain"
    default_session: str = "R"

    # General UI defaults
    max_drivers_compare: int = 4
    show_debug_sidebar: bool = False


CONFIG = AppConfig()
