"""Utility monitoring page for the Engineering Monitoring Dashboard.

This module renders the real Utility overview, discovering the Utility
section dynamically from the departments/sections found in the overview
worksheet. It reuses the shared ``services.dashboard_loader`` service for
loading dashboard data and ``dashboard_data.build_overview_dashboard`` for
section discovery. It performs no engineering KPI calculation beyond
simple counts, no fake data generation, and no hardcoded meter names.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import ui
from dashboard_data import build_overview_dashboard, get_date_columns
from services.dashboard_loader import load_dashboard

UTILITY_KEYWORD: str = "utility"
"""Keyword used to identify the Utility section among discovered sections."""


def load_overview_dataframe() -> pd.DataFrame | None:
    """Load dashboard data and extract the engineering overview worksheet.

    Returns:
        The overview DataFrame if it was loaded successfully, otherwise
        ``None`` after an error banner has been displayed.
    """
    try:
        dashboard_data = load_dashboard()
    except TimeoutError as exc:
        ui.render_error_banner(f"The workbook source timed out: {exc}")
        return None
    except ConnectionError as exc:
        ui.render_error_banner(
            f"Could not connect to the workbook source: {exc}"
        )
        return None
    except FileNotFoundError as exc:
        ui.render_error_banner(f"Workbook not found: {exc}")
        return None
    except ValueError as exc:
        ui.render_error_banner(f"The workbook data is invalid: {exc}")
        return None
    except RuntimeError as exc:
        ui.render_error_banner(
            f"An error occurred while loading the workbook: {exc}"
        )
        return None

    overview_dataframe = dashboard_data["overview"]

    if overview_dataframe is None:
        ui.render_info_banner(
            "No engineering overview worksheet was found in the workbook."
        )
        return None

    return overview_dataframe


def get_utility_section(overview_dataframe: pd.DataFrame) -> dict | None:
    """Discover the Utility section from the overview sheet's sections.

    Args:
        overview_dataframe: The engineering overview worksheet DataFrame.

    Returns:
        The section dictionary (with keys ``name``, ``meters``,
        ``latest_values``, and ``dataframe``) whose name matches the
        Utility keyword, case-insensitively, or ``None`` if no such
        section was discovered.
    """
    overview_dashboard = build_overview_dashboard(overview_dataframe)
    sections = overview_dashboard["sections"]

    return next(
        (
            section
            for section in sections
            if UTILITY_KEYWORD in section["name"].lower()
        ),
        None,
    )


def count_available_readings(dataframe: pd.DataFrame) -> int:
    """Count the total number of non-null readings in a section worksheet.

    Args:
        dataframe: The section DataFrame.

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


def render_kpi_row(section: dict, overview_dataframe: pd.DataFrame) -> None:
    """Render the top KPI row derived from the Utility section.

    Args:
        section: The discovered Utility section dictionary.
        overview_dataframe: The engineering overview worksheet DataFrame,
            used to discover the latest available timestamp.
    """
    cards = [
        {"title": "Number of Meters", "value": len(section["meters"])},
        {
            "title": "Available Readings",
            "value": count_available_readings(section["dataframe"]),
        },
        {
            "title": "Latest Timestamp",
            "value": get_latest_timestamp(overview_dataframe),
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

    overview_dataframe = load_overview_dataframe()
    if overview_dataframe is None:
        return

    utility_section = get_utility_section(overview_dataframe)
    if utility_section is None:
        ui.render_info_banner(
            "No Utility section was discovered in the workbook."
        )
        return

    render_kpi_row(utility_section, overview_dataframe)
    ui.render_divider()

    render_data_section(utility_section["dataframe"])
    ui.render_divider()

    render_trend_section()
