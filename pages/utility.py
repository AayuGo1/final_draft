"""Engineering overview page for the Engineering Monitoring Dashboard.

This module renders the top-level Engineering overview, combining every
department/section discovered on the engineering overview worksheet via
``services.page_service``. It performs no engineering KPI calculation
beyond simple counts, no fake data generation, and no hardcoded
department or meter names.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import ui
from dashboard_data import build_overview_dashboard, get_date_columns
from services.page_service import load_overview


def count_total_meters(sections: list[dict]) -> int:
    """Count the total number of meters across every discovered section.

    Args:
        sections: The list of section dictionaries produced by
            ``dashboard_data.build_overview_dashboard``.

    Returns:
        The combined number of meters across all sections.
    """
    return sum(len(section["meters"]) for section in sections)


def count_available_readings(dataframe: pd.DataFrame) -> int:
    """Count the total number of non-null readings in a worksheet.

    Args:
        dataframe: The overview DataFrame.

    Returns:
        The total count of non-null cells in the DataFrame.
    """
    return int(dataframe.notna().sum().sum())


def get_latest_timestamp(overview_dataframe: pd.DataFrame) -> str:
    """Find the latest timestamp available in the overview worksheet, if any.

    Args:
        overview_dataframe: The engineering overview worksheet DataFrame.

    Returns:
        The latest date value found in a discovered date column,
        formatted as a string, or ``"N/A"`` if no date column or value
        is available.
    """
    date_columns = get_date_columns(overview_dataframe)
    if not date_columns:
        return "N/A"

    for column_index in reversed(date_columns):
        column_values = overview_dataframe.iloc[:, column_index].dropna()
        if not column_values.empty:
            return str(column_values.iloc[-1])

    return "N/A"


def render_kpi_row(overview_dataframe: pd.DataFrame, sections: list[dict]) -> None:
    """Render the top KPI row derived from the engineering overview.

    Args:
        overview_dataframe: The engineering overview worksheet DataFrame.
        sections: The list of discovered section dictionaries.
    """
    cards = [
        {"title": "Number of Meters", "value": count_total_meters(sections)},
        {
            "title": "Available Readings",
            "value": count_available_readings(overview_dataframe),
        },
        {
            "title": "Latest Timestamp",
            "value": get_latest_timestamp(overview_dataframe),
        },
        {"title": "Status", "value": "Monitoring"},
    ]
    ui.render_kpi_cards(cards)


def render_data_section(overview_dataframe: pd.DataFrame) -> None:
    """Render the engineering overview data table, limited to 15 rows.

    Args:
        overview_dataframe: The engineering overview worksheet DataFrame.
    """
    ui.render_section("Data")
    with st.container(border=True):
        ui.render_dataframe(overview_dataframe.head(15))


def render_trend_section() -> None:
    """Render the bordered Trend Analysis placeholder section."""
    with st.container(border=True):
        st.write("**Trend Analysis**")
        st.caption("Charts and engineering KPIs will be implemented here.")


def render() -> None:
    """Render the complete Engineering overview page."""
    ui.render_page_title(
        "Engineering",
        "Consolidated engineering overview across all departments.",
    )

    overview_dataframe = load_overview()
    if overview_dataframe is None:
        return

    sections = build_overview_dashboard(overview_dataframe)["sections"]

    render_kpi_row(overview_dataframe, sections)
    ui.render_divider()

    render_data_section(overview_dataframe)
    ui.render_divider()

    render_trend_section()
