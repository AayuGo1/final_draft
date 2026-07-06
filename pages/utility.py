"""Utility monitoring page for the Engineering Monitoring Dashboard.

This module renders the real Utility overview, discovering the Utility
section dynamically via ``services.page_service``. It performs no
engineering KPI calculation beyond simple counts, no fake data
generation, and no hardcoded meter names.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import ui
from dashboard_data import get_date_columns
from services.page_service import load_section

UTILITY_KEYWORD: str = "utility"
"""Keyword used to identify the Utility section among discovered sections."""


def count_available_readings(dataframe: pd.DataFrame) -> int:
    """Count the total number of non-null readings in a section worksheet.

    Args:
        dataframe: The section DataFrame.

    Returns:
        The total count of non-null cells in the DataFrame.
    """
    return int(dataframe.notna().sum().sum())


def get_latest_timestamp(dataframe: pd.DataFrame) -> str:
    """Find the latest timestamp available in a worksheet, if any.

    Args:
        dataframe: The DataFrame to search for a date column.

    Returns:
        The latest date value found in a discovered date column,
        formatted as a string, or ``"N/A"`` if no date column or value
        is available.
    """
    date_columns = get_date_columns(dataframe)
    if not date_columns:
        return "N/A"

    for column_index in reversed(date_columns):
        column_values = dataframe.iloc[:, column_index].dropna()
        if not column_values.empty:
            return str(column_values.iloc[-1])

    return "N/A"


def render_kpi_row(section: dict) -> None:
    """Render the top KPI row derived from the Utility section.

    Args:
        section: The discovered Utility section dictionary.
    """
    cards = [
        {"title": "Number of Meters", "value": len(section["meters"])},
        {
            "title": "Available Readings",
            "value": count_available_readings(section["dataframe"]),
        },
        {
            "title": "Latest Timestamp",
            "value": get_latest_timestamp(section["overview_dataframe"]),
        },
        {"title": "Status", "value": "Monitoring"},
    ]
    ui.render_kpi_cards(cards)


def render_data_section(dataframe: pd.DataFrame) -> None:
    """Render the Utility data table, limited to the first 15 rows.

    Args:
        dataframe: The Utility section DataFrame.
    """
    ui.render_section("Data")
    with st.container(border=True):
        ui.render_dataframe(dataframe.head(15))


def render_trend_section() -> None:
    """Render the bordered Trend Analysis placeholder section."""
    with st.container(border=True):
        st.write("**Trend Analysis**")
        st.caption("Charts and engineering KPIs will be implemented here.")


def render() -> None:
    """Render the complete Utility page."""
    ui.render_page_title(
        "Utility",
        "General utility consumption and performance tracking.",
    )

    utility_section = load_section(UTILITY_KEYWORD)
    if utility_section is None:
        return

    render_kpi_row(utility_section)
    ui.render_divider()

    render_data_section(utility_section["dataframe"])
    ui.render_divider()

    render_trend_section()
