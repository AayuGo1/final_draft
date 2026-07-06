"""Reusable Streamlit UI components for the Engineering Monitoring Dashboard.

This module is responsible ONLY for rendering UI elements using native
Streamlit components. It performs no data downloading, no Excel parsing,
no KPI calculation, and no workbook inspection. Future dashboard pages
should rely exclusively on the functions defined here for rendering.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render_page_title(title: str, subtitle: str | None = None) -> None:
    """Render the dashboard page title with an optional subtitle.

    Args:
        title: Main title text to display.
        subtitle: Optional subtitle or descriptive caption shown below
            the title.
    """
    st.title(title)
    if subtitle:
        st.caption(subtitle)


def render_success_banner(message: str) -> None:
    """Render a green success message.

    Args:
        message: The success message to display.
    """
    st.success(message)


def render_error_banner(message: str) -> None:
    """Render a red error message.

    Args:
        message: The error message to display.
    """
    st.error(message)


def render_info_banner(message: str) -> None:
    """Render an informational message.

    Args:
        message: The informational message to display.
    """
    st.info(message)


def render_kpi_cards(cards: list[dict]) -> None:
    """Render a responsive row of KPI cards using ``st.metric``.

    Args:
        cards: A list of dictionaries, each with keys ``title``,
            ``value``, and the optional keys ``delta`` and ``help``. Each
            card is rendered in its own column.
    """
    if not cards:
        return

    columns = st.columns(len(cards))

    for column, card in zip(columns, cards):
        with column:
            st.metric(
                label=card.get("title", ""),
                value=card.get("value", ""),
                delta=card.get("delta"),
                help=card.get("help"),
            )


def render_dataframe(dataframe: pd.DataFrame) -> None:
    """Display a DataFrame using the full container width.

    Args:
        dataframe: The DataFrame to display.
    """
    st.dataframe(dataframe, use_container_width=True)


def render_section(title: str) -> None:
    """Render a section heading with surrounding spacing.

    Args:
        title: The section heading text.
    """
    st.write("")
    st.subheader(title)


def render_divider() -> None:
    """Render a horizontal divider."""
    st.divider()
