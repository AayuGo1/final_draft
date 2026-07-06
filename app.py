"""Main Streamlit entry point for the Engineering Monitoring Dashboard.

This module is responsible ONLY for configuring the Streamlit page,
rendering the sidebar navigation, and routing to the selected page's
``render()`` function. All page content lives in the ``pages`` package.
"""

from __future__ import annotations

import streamlit as st

from config import PAGE_CONFIG
from pages import (
    air_compressor,
    ammonia_refrigeration,
    engineering,
    freon_refrigeration,
    home,
    utility,
)

NAV_OPTIONS: dict[str, object] = {
    "🏠 Home": home,
    "⚙ Engineering": engineering,
    "⚡ Utility": utility,
    "🛠 Air Compressor": air_compressor,
    "❄ Freon Refrigeration": freon_refrigeration,
    "🧊 Ammonia Refrigeration": ammonia_refrigeration,
}
"""Mapping of sidebar navigation labels to their corresponding page module."""


def render_sidebar() -> object:
    """Render the sidebar navigation and return the selected page module.

    Returns:
        The page module corresponding to the option chosen in the
        sidebar.
    """
    with st.sidebar:
        st.title("Engineering Monitoring Dashboard")
        st.divider()
        selected_label = st.radio(
            "Navigation",
            options=list(NAV_OPTIONS.keys()),
            label_visibility="collapsed",
        )

    return NAV_OPTIONS[selected_label]


def main() -> None:
    """Configure the page and route to the selected page's render function."""
    st.set_page_config(**PAGE_CONFIG)

    selected_page = render_sidebar()
    selected_page.render()


if __name__ == "__main__":
    main()
