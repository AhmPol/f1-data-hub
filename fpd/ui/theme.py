# fpd/ui/theme.py
from __future__ import annotations

import streamlit as st


def apply_theme_overrides() -> None:
    """
    Optional theme helpers.
    Your main colors live in .streamlit/config.toml.
    This is only for small UI polish (badges, spacing, etc.).
    """
    st.markdown(
        """
<style>
/* Small badge style for labels like "S1", "S2", "S3" */
.fpd-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  border: 1px solid rgba(255,255,255,0.15);
  background: rgba(255,255,255,0.05);
  margin-right: 6px;
}

/* Section headers tighter */
h2, h3 { margin-top: 0.25rem; }

/* Sidebar width a touch wider for controls */
section[data-testid="stSidebar"] { width: 340px !important; }
</style>
""",
        unsafe_allow_html=True,
    )


def badge(text: str) -> str:
    """
    Returns an HTML badge string. Use with st.markdown(..., unsafe_allow_html=True)
    """
    safe = (text or "").replace("<", "&lt;").replace(">", "&gt;")
    return f'<span class="fpd-badge">{safe}</span>'
