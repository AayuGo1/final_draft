"""Engineering monitoring page for the Engineering Monitoring Dashboard.

This module renders the real Engineering overview, allowing selection of
any department discovered dynamically from the workbook. It reuses the
shared ``services.dashboard_loader`` service for loading dashboard data
and ``dashboard_data.build_overview_dashboard`` for department discovery.
It performs no engineering KPI calculation beyond simple counts, no fake
data generation, and no hardcoded department names.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import ui
from dashboard_data import build_overview_dashboard, get_date_columns
from services.dashboard_loader import load_dashboard


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


def get_department_sections(overview_dataframe: pd.DataFrame) -> list[dict]:
    """Discover every engineering department section from the overview sheet.

    Args:
        overview_dataframe: The engineering overview worksheet DataFrame.

    Returns:
        A list of section dictionaries as produced by
        ``dashboard_data.build_overview_dashboard``, each with keys
        ``name``, ``meters``, ``latest_values``, and ``dataframe``.
    """
    overview_dashboard = build_overview_dashboard(overview_dataframe)
    return overview_dashboard["sections"]


def count_available_readings(dataframe: pd.DataFrame) -> int:
    """Count the total number of non-null readings in a department worksheet.

    Args:
        dataframe: The department DataFrame.

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


def render_department_selector(sections: list[dict]) -> dict:
    """Render a department selector and return the selected section.

    Args:
        sections: The list of discovered department sections.

    Returns:
        The section dictionary corresponding to the selected department.
    """
    department_names = [section["name"] for section in sections]
    selected_name = st.selectbox("Department", department_names)
    return next(
        section for section in sections if section["name"] == selected_name
    )


def render_kpi_row(section: dict, overview_dataframe: pd.DataFrame) -> None:
    """Render the top KPI row derived from the selected department section.

    Args:
        section: The selected department section dictionary.
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
    """Render the department data table, limited to the first 15 rows.

    Args:
        dataframe: The selected department DataFrame.
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
    """Render the complete Engineering page."""
    ui.render_page_title(
        "Engineering",
        "Overall engineering performance and asset health.",
    )

    overview_dataframe = load_overview_dataframe()
    if overview_dataframe is None:
        return

    sections = get_department_sections(overview_dataframe)
    if not sections:
        ui.render_info_banner(
            "No engineering departments were discovered in the workbook."
        )
        return

    selected_section = render_department_selector(sections)
    ui.render_divider()

    render_kpi_row(selected_section, overview_dataframe)
    ui.render_divider()

    render_data_section(selected_section["dataframe"])
    ui.render_divider()

    render_trend_section()
