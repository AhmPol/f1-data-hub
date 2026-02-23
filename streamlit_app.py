# streamlit_app.py
"""
Formula Performance Dashboard (Streamlit + FastF1)

- Initializes FastF1 cache safely (Streamlit Cloud compatible)
- Provides ONE shared Top Bar for Season / Event / Session
- Loads a "session bundle" once and reuses it across pages via st.session_state
- Sets basic styling and app-wide config

Pages live in /pages and should read the loaded bundle via:
    bundle = st.session_state["bundle"]
"""

from __future__ import annotations

import os
import streamlit as st

from engine.data import init_fastf1_cache
from app_state import top_bar_inputs, get_session_bundle


# -----------------------------
# Streamlit App Configuration
# -----------------------------
st.set_page_config(
    page_title="Formula Performance Dashboard",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Optional: lightweight global CSS (safe if assets/style.css exists)
def _load_css():
    css_path = os.path.join(os.getcwd(), "assets", "style.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

_load_css()


# -----------------------------
# FastF1 Cache Initialization
# IMPORTANT: do this ONLY here
# -----------------------------
cache_dir = os.path.join(os.getcwd(), ".fastf1_cache")
init_fastf1_cache(cache_dir)


# -----------------------------
# Header + Top Bar Inputs
# -----------------------------
st.title("Formula Performance Dashboard")

# Top bar inputs (single source of truth)
year, event_name, session_name, reload_now = top_bar_inputs()

# Load / reuse session bundle (cached & stored in session_state)
bundle = get_session_bundle(year, event_name, session_name, reload_now=reload_now)

# Optional: tiny status line
left, right = st.columns([3, 1])
with left:
    st.caption(
        f"Loaded: **{bundle['year']}** • **{bundle['event']}** • **{bundle['session_name']}**"
        + (" • **Race**" if bundle.get("is_race") else "")
    )
with right:
    st.caption(f"Drivers: **{len(bundle.get('drivers', []))}**")

# -----------------------------
# Helpful landing content
# -----------------------------
st.markdown(
    """
Use the pages on the left to explore:

- **Home**: Track map panel, fastest laps or race results, leaderboards, summary cards  
- **Lap Compare**: Current session vs all-time comparisons with stacked telemetry charts  
- **Corner & Sector**: Sector winners and corner-by-corner table + group averages  
- **Long Runs**: Stints, degradation slope, consistency, rankings  
- **Track DNA**: Track profile + fingerprint vector  
- **Track Suitability**: Similar tracks + predicted strengths + confidence  
"""
)

# -----------------------------
# Debug (optional)
# -----------------------------
with st.sidebar:
    with st.expander("Debug", expanded=False):
        st.write("Bundle key:", st.session_state.get("bundle_key"))
        st.write("Year:", bundle.get("year"))
        st.write("Event:", bundle.get("event"))
        st.write("Session:", bundle.get("session_name"))
        st.write("Is race:", bundle.get("is_race"))
        st.write("Drivers (first 10):", bundle.get("drivers", [])[:10])
