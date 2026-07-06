"""Air compressor monitoring page for the Engineering Monitoring Dashboard.

This module is currently a placeholder. It will later display air
compressor KPIs, pressure trends, running hours, efficiency metrics, and
alarms using the existing backend modules.
"""

from __future__ import annotations

import streamlit as st


def render() -> None:
    """Render the Air Compressor page with a title, description, and placeholder."""
    st.title("Air Compressor")
    st.caption("Air compressor load, output, and efficiency tracking.")

    with st.container(border=True):
        st.write(
            "This page will display compressor KPIs, pressure trends, "
            "running hours, efficiency metrics and alarms."
        )
