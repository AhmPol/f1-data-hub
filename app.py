# app.py
from __future__ import annotations

import streamlit as st

from fpd.ui.layout import configure_app
from fpd.ui.state import init_state
from fpd.data.fastf1_cache import ensure_cache


def main() -> None:
    # Global app setup
    configure_app()
    init_state()
    ensure_cache()

    # Home landing (optional). Your actual pages live in streamlit_pages/.
    st.title("Formula Performance Dashboard")
    st.caption(
        "Use the left sidebar to open pages: Home, Lap Compare, Corner & Sector, Long Runs."
    )

    st.divider()

    st.subheader("Quick Start")
    st.markdown(
        """
- Open **🏠 Home** to pick **Season / Event / Session**
- Then explore:
  - **🆚 Lap Compare**
  - **📐 Corner & Sector**
  - **📉 Long Runs**
"""
    )

    st.info(
        "Tip: If the sidebar is hidden, click the arrow in the top-left to open it.",
        icon="ℹ️",
    )


if __name__ == "__main__":
    main()
