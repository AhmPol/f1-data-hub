# fpd/data/fastf1_cache.py
from __future__ import annotations

from pathlib import Path
import os
import fastf1
import streamlit as st

DEFAULT_CACHE_DIR = "data/cache"


def ensure_cache(cache_dir: str = DEFAULT_CACHE_DIR, show_status: bool = False) -> None:
    """
    Enable FastF1 caching.

    Should be called once at app startup (in app.py).
    Safe to call multiple times.
    """
    path = Path(cache_dir)
    path.mkdir(parents=True, exist_ok=True)

    # Enable FastF1 cache
    fastf1.Cache.enable_cache(str(path))

    # Store in session_state so other modules can reference it if needed
    st.session_state.setdefault("fastf1_cache_dir", str(path))

    if show_status:
        st.sidebar.success(f"FastF1 cache enabled: {path}")


def clear_cache(cache_dir: str = DEFAULT_CACHE_DIR) -> None:
    """
    Deletes all files inside the FastF1 cache directory.
    Use carefully.
    """
    path = Path(cache_dir)

    if not path.exists():
        return

    for item in path.iterdir():
        try:
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                for sub in item.rglob("*"):
                    if sub.is_file():
                        sub.unlink()
                sub_dirs = sorted(
                    [p for p in item.rglob("*") if p.is_dir()],
                    reverse=True,
                )
                for d in sub_dirs:
                    d.rmdir()
                item.rmdir()
        except Exception as e:
            st.warning(f"Could not remove {item.name}: {e}")


def get_cache_size_mb(cache_dir: str = DEFAULT_CACHE_DIR) -> float:
    """
    Returns total cache size in MB.
    """
    path = Path(cache_dir)
    if not path.exists():
        return 0.0

    total_bytes = 0
    for f in path.rglob("*"):
        if f.is_file():
            total_bytes += f.stat().st_size

    return round(total_bytes / (1024 * 1024), 2)


def cache_controls_sidebar() -> None:
    """
    Optional developer utility.
    Call this inside sidebar if you want cache controls.
    """
    st.sidebar.subheader("FastF1 Cache")

    size = get_cache_size_mb()
    st.sidebar.caption(f"Cache size: {size} MB")

    if st.sidebar.button("Clear Cache"):
        clear_cache()
        st.sidebar.success("Cache cleared. Restart app.")
