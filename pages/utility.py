"""Utility monitoring page for the Engineering Monitoring Dashboard.

This module is currently a placeholder. It will later display utility
monitoring, KPIs, trends, and equipment performance using the existing
backend modules.
"""

from __future__ import annotations

import streamlit as st


def render() -> None:
    """Render the Utility page with a title, description, and placeholder."""
    st.title("Utility")
    st.caption("General utility consumption and performance tracking.")

    with st.container(border=True):
        st.write(
            "This page will display utility monitoring, KPIs, trends and "
            "equipment performance."
        )
