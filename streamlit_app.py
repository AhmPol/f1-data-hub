import os
import streamlit as st
from engine.data import init_fastf1_cache
from app_state import top_bar_inputs, get_session_bundle

st.set_page_config(page_title="F1 Data Hub", layout="wide")

cache_path = os.path.join(os.getcwd(), ".fastf1_cache")
init_fastf1_cache(cache_path)

st.title("Formula Performance Dashboard")

year, event, session_name, reload_now = top_bar_inputs()
bundle = get_session_bundle(year, event, session_name, reload_now=reload_now)

st.caption(f"Loaded: {bundle['year']} • {bundle['event']} • {bundle['session_name']}")
st.info("Use the pages on the left: Home, Lap Compare, Corner/Sector, Long Runs.")
