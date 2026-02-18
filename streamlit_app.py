import streamlit as st
import fastf1

fastf1.Cache.enable_cache("fastf1_cache")

st.set_page_config(page_title="F1 Data Hub", layout="wide")
st.title("F1 Data Dashboard")

from app.ui_sidebar import sidebar_controls
from app.ui_main import load_session, render_dashboard

year, schedule, gp_label, selected_event, is_testing, session_type, testing_session_number, compare_mode = sidebar_controls()
session = load_session(year, schedule, gp_label, selected_event, is_testing, session_type, testing_session_number)
render_dashboard(session, is_testing, compare_mode)
