# fpd/components/cards_summary.py
from __future__ import annotations

import streamlit as st


def render_summary_cards(session) -> None:
    """
    Small, UI-only summary cards.

    For now these are placeholders ("—").
    Later, you’ll feed real values from analytics modules:
      - straight-line speed/efficiency
      - low/medium/high-speed corner strengths
      - braking efficiency
      - tire degradation resistance
    """
    st.subheader("Session Summary Cards")

    row1 = st.columns(3)
    row1[0].metric("Top straight-line speed", "—")
    row1[1].metric("Best low-speed traction", "—")
    row1[2].metric("Best medium-speed corners", "—")

    row2 = st.columns(3)
    row2[0].metric("Best high-speed corners", "—")
    row2[1].metric("Best braking efficiency", "—")
    row2[2].metric("Tire degradation resistance", "—")

    with st.expander("How these will be computed (planned)", expanded=False):
        st.markdown(
            """
- **Top straight-line speed**: peak speed on longest straights (or top percentile speed)
- **Low/Medium/High-speed corner strength**: average delta in corner groups using min speed + exit speed + time loss
- **Braking efficiency**: distance-to-min-speed proxy, braking duration, and stability under braking
- **Tire degradation resistance**: stint slope (s/lap) adjusted for fuel/traffic where possible
"""
        )
