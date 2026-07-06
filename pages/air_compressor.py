"""Air compressor monitoring page for the Engineering Monitoring Dashboard.

This module renders the real Air Compressor section discovered from the
workbook via ``services.page_service``. It performs no engineering KPI
calculation, no fake data generation, and no hardcoded row, column, or
meter references.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import ui
from dashboard_data import get_date_columns, get_department_meter_structure
from services.page_service import load_dedicated_sheet

AIR_COMPRESSOR_KEY: str = "air_compressor"
"""Dashboard data key used to locate the Air Compressor worksheet."""


def count_meters(dataframe: pd.DataFrame) -> int:
    """Count the total number of meters discovered in the worksheet.

    Args:
        dataframe: The Air Compressor DataFrame.

    Returns:
        The total number of meters across all discovered department
        groups, using the same two-level header discovery as the home
        page.
    """
    department_structure = get_department_meter_structure(dataframe)
    return sum(len(meters) for meters in department_structure.values())


def count_available_readings(dataframe: pd.DataFrame) -> int:
    """Count the total number of non-null readings in the worksheet.

    Args:
        dataframe: The Air Compressor DataFrame.

    Returns:
        The total count of non-null cells in the DataFrame.
    """
    return int(dataframe.notna().sum().sum())


def get_latest_timestamp(dataframe: pd.DataFrame) -> str:
    """Find the latest timestamp available in the worksheet, if any.

    Args:
        dataframe: The Air Compressor DataFrame.

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


def render_kpi_row(dataframe: pd.DataFrame) -> None:
    """Render the top KPI row derived from the Air Compressor worksheet.

    Args:
        dataframe: The Air Compressor DataFrame.
    """
    cards = [
        {"title": "Number of Meters", "value": count_meters(dataframe)},
        {
            "title": "Available Readings",
            "value": count_available_readings(dataframe),
        },
        {"title": "Latest Timestamp", "value": get_latest_timestamp(dataframe)},
        {"title": "Status", "value": "Monitoring"},
    ]
    ui.render_kpi_cards(cards)


def render_data_section(dataframe: pd.DataFrame) -> None:
    """Render the Air Compressor data table, limited to the first 15 rows.

    Args:
        dataframe: The Air Compressor DataFrame.
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
    """Render the complete Air Compressor page."""
    ui.render_page_title(
        "Air Compressor",
        "Air compressor load, output, and efficiency tracking.",
    )

    dataframe, _section = load_dedicated_sheet(AIR_COMPRESSOR_KEY)
    if dataframe is None:
        return

    render_kpi_row(dataframe)
    ui.render_divider()

    render_data_section(dataframe)
    ui.render_divider()

    render_trend_section()
