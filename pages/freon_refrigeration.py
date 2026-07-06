"""Freon Refrigeration monitoring page for the Engineering Monitoring
Dashboard.

This module renders the real Freon Refrigeration overview. It prefers a
dedicated Freon worksheet when the workbook provides one, and falls back
to dynamically discovering a Freon Refrigeration section from the
engineering overview worksheet otherwise, via ``services.page_service``.
It performs no engineering KPI calculation beyond simple counts, no fake
data generation, and no hardcoded row, column, or meter names.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import ui
from dashboard_data import get_date_columns
from services.page_service import load_dedicated_sheet

FREON_KEY: str = "freon"
"""Dashboard data key used to locate the dedicated Freon worksheet."""

FREON_KEYWORD: str = "freon"
"""Keyword used to identify the Freon section among discovered sections."""


def count_available_readings(dataframe: pd.DataFrame) -> int:
    """Count the total number of non-null readings in a worksheet.

    Args:
        dataframe: The Freon Refrigeration DataFrame.

    Returns:
        The total count of non-null cells in the DataFrame.
    """
    return int(dataframe.notna().sum().sum())


def count_meters(dataframe: pd.DataFrame, section: dict | None) -> int:
    """Determine the number of meters represented in the Freon data.

    When a discovered overview section is available, its meter list is
    used directly. Otherwise, for a dedicated Freon worksheet, the
    number of meters is derived as the number of columns that are not
    date columns, since dedicated worksheets typically use one column
    per meter alongside a date column.

    Args:
        dataframe: The Freon Refrigeration DataFrame.
        section: The discovered overview section dictionary, or ``None``
            when a dedicated Freon worksheet is used.

    Returns:
        The number of meters found in the Freon data.
    """
    if section is not None:
        return len(section["meters"])

    date_columns = get_date_columns(dataframe)
    return max(dataframe.shape[1] - len(date_columns), 0)


def get_latest_timestamp(dataframe: pd.DataFrame) -> str:
    """Find the latest timestamp available in the Freon data, if any.

    Args:
        dataframe: The Freon Refrigeration DataFrame.

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


def render_kpi_row(dataframe: pd.DataFrame, section: dict | None) -> None:
    """Render the top KPI row derived from the Freon Refrigeration data.

    Args:
        dataframe: The Freon Refrigeration DataFrame.
        section: The discovered overview section dictionary, or ``None``
            when a dedicated Freon worksheet is used.
    """
    cards = [
        {"title": "Number of Meters", "value": count_meters(dataframe, section)},
        {
            "title": "Available Readings",
            "value": count_available_readings(dataframe),
        },
        {
            "title": "Latest Timestamp",
            "value": get_latest_timestamp(dataframe),
        },
        {"title": "Status", "value": "Monitoring"},
    ]
    ui.render_kpi_cards(cards)


def render_data_section(dataframe: pd.DataFrame) -> None:
    """Render the Freon Refrigeration data table, limited to 15 rows.

    Args:
        dataframe: The Freon Refrigeration DataFrame.
    """
    ui.render_section("Data")
    with st.container(border=True):
        st.dataframe(dataframe.head(15))


def render_trend_section() -> None:
    """Render the bordered Trend Analysis placeholder section."""
    with st.container(border=True):
        st.write("**Trend Analysis**")
        st.caption("Charts and engineering KPIs will be implemented here.")


def render() -> None:
    """Render the complete Freon Refrigeration page."""
    ui.render_page_title(
        "Freon Refrigeration",
        "Freon-based refrigeration monitoring and performance.",
    )

    freon_dataframe, section = load_dedicated_sheet(
        FREON_KEY, fallback_keyword=FREON_KEYWORD
    )
    if freon_dataframe is None:
        return

    render_kpi_row(freon_dataframe, section)
    ui.render_divider()

    render_data_section(freon_dataframe)
    ui.render_divider()

    render_trend_section()
