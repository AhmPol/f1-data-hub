# fpd/ui/layout.py
from __future__ import annotations

import streamlit as st


def configure_app() -> None:
    """
    Streamlit page-level configuration.
    Keep this tiny—no app logic here.
    """
    st.set_page_config(
        page_title="Formula Performance Dashboard",
        page_icon="🏎️",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            "Get Help": None,
            "Report a bug": None,
            "About": "Formula Performance Dashboard — telemetry & session analysis.",
        },
    )

    # Optional global CSS tweaks (small + safe)
    _inject_base_css()


def _inject_base_css() -> None:
    st.markdown(
        """
<style>
/* Slightly tighten vertical spacing */
.block-container { padding-top: 1rem; padding-bottom: 2rem; }
/* Make dataframes feel more dashboard-like */
[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
/* Cleaner metric cards */
[data-testid="stMetric"] { border-radius: 12px; padding: 12px; }
</style>
""",
        unsafe_allow_html=True,
    )
