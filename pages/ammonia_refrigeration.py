"""Ammonia refrigeration monitoring page for the Engineering Monitoring Dashboard.

This module is currently a placeholder. It will later display ammonia
refrigeration monitoring, performance trends, and operational insights
using the existing backend modules.
"""

from __future__ import annotations

import streamlit as st


def render() -> None:
    """Render the Ammonia Refrigeration page with a title, description, and placeholder."""
    st.title("Ammonia Refrigeration")
    st.caption("Ammonia-based refrigeration system monitoring.")

    with st.container(border=True):
        st.write(
            "This page will display ammonia refrigeration monitoring, "
            "performance trends and operational insights."
        )
