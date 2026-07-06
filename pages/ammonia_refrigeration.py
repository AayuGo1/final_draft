"""Ammonia Refrigeration monitoring page for the Engineering Monitoring
Dashboard.

This module renders the real Ammonia Refrigeration overview. It mirrors
the architecture used by the Freon Refrigeration page: it would prefer a
dedicated Ammonia Refrigeration worksheet if the shared dashboard data
exposed one, and falls back to dynamically discovering an Ammonia
Refrigeration section from the engineering overview worksheet otherwise.
Since ``services.dashboard_loader.load_dashboard`` currently exposes no
dedicated Ammonia worksheet key, this page relies on the overview-section
discovery path. It reuses the existing helper functions in
``dashboard_data`` and performs no engineering KPI calculation beyond
simple counts, no fake data generation, and no hardcoded row, column, or
meter names.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import ui
from dashboard_data import build_overview_dashboard, get_date_columns
from services.dashboard_loader import load_dashboard

AMMONIA_KEYWORD: str = "ammonia"
"""Keyword used to identify the Ammonia Refrigeration section among
discovered sections."""


def load_ammonia_data() -> tuple[pd.DataFrame | None, dict | None]:
    """Load dashboard data and resolve the Ammonia Refrigeration source.

    Would prefer a dedicated Ammonia Refrigeration worksheet if the
    shared dashboard data exposed one. Since it currently does not, this
    falls back to discovering an Ammonia Refrigeration section from the
    engineering overview worksheet's department/section structure.

    Returns:
        A tuple of ``(ammonia_dataframe, section)``. ``section`` holds
        the discovered section dictionary (with keys ``name``,
        ``meters``, ``latest_values``, and ``dataframe``) and
        ``ammonia_dataframe`` holds ``section["dataframe"]``. Returns
        ``(None, None)`` if no Ammonia Refrigeration data could be
        found, after an appropriate banner has been displayed.
    """
    try:
        dashboard_data = load_dashboard()
    except TimeoutError as exc:
        ui.render_error_banner(f"The workbook source timed out: {exc}")
        return None, None
    except ConnectionError as exc:
        ui.render_error_banner(
            f"Could not connect to the workbook source: {exc}"
        )
        return None, None
    except FileNotFoundError as exc:
        ui.render_error_banner(f"Workbook not found: {exc}")
        return None, None
    except ValueError as exc:
        ui.render_error_banner(f"The workbook data is invalid: {exc}")
        return None, None
    except RuntimeError as exc:
        ui.render_error_banner(
            f"An error occurred while loading the workbook: {exc}"
        )
        return None, None

    dedicated_ammonia_dataframe = dashboard_data.get("ammonia")
    if dedicated_ammonia_dataframe is not None:
        return dedicated_ammonia_dataframe, None

    overview_dataframe = dashboard_data["overview"]
    if overview_dataframe is None:
        ui.render_info_banner(
            "No Ammonia Refrigeration worksheet or engineering overview "
            "worksheet was found in the workbook."
        )
        return None, None

    section = get_ammonia_section(overview_dataframe)
    if section is None:
        return None, None

    return section["dataframe"], section


def get_ammonia_section(overview_dataframe: pd.DataFrame) -> dict | None:
    """Discover the Ammonia Refrigeration section from the overview sheet.

    Args:
        overview_dataframe: The engineering overview worksheet DataFrame.

    Returns:
        The section dictionary (with keys ``name``, ``meters``,
        ``latest_values``, and ``dataframe``) whose name matches the
        Ammonia keyword, case-insensitively, or ``None`` if no such
        section was discovered.
    """
    overview_dashboard = build_overview_dashboard(overview_dataframe)
    sections = overview_dashboard["sections"]

    section = next(
        (
            candidate
            for candidate in sections
            if AMMONIA_KEYWORD in candidate["name"].lower()
        ),
        None,
    )

    if section is None:
        ui.render_info_banner(
            "No Ammonia Refrigeration section was discovered in the "
            "workbook."
        )

    return section


def count_available_readings(dataframe: pd.DataFrame) -> int:
    """Count the total number of non-null readings in a worksheet.

    Args:
        dataframe: The Ammonia Refrigeration DataFrame.

    Returns:
        The total count of non-null cells in the DataFrame.
    """
    return int(dataframe.notna().sum().sum())


def count_meters(dataframe: pd.DataFrame, section: dict | None) -> int:
    """Determine the number of meters represented in the Ammonia data.

    When a discovered overview section is available, its meter list is
    used directly. Otherwise, for a dedicated Ammonia worksheet, the
    number of meters is derived as the number of columns that are not
    date columns, since dedicated worksheets typically use one column
    per meter alongside a date column.

    Args:
        dataframe: The Ammonia Refrigeration DataFrame.
        section: The discovered overview section dictionary, or ``None``
            when a dedicated Ammonia worksheet is used.

    Returns:
        The number of meters found in the Ammonia data.
    """
    if section is not None:
        return len(section["meters"])

    date_columns = get_date_columns(dataframe)
    return max(dataframe.shape[1] - len(date_columns), 0)


def get_latest_timestamp(dataframe: pd.DataFrame) -> str:
    """Find the latest timestamp available in the Ammonia data, if any.

    Args:
        dataframe: The Ammonia Refrigeration DataFrame.

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
    """Render the top KPI row derived from the Ammonia Refrigeration data.

    Args:
        dataframe: The Ammonia Refrigeration DataFrame.
        section: The discovered overview section dictionary, or ``None``
            when a dedicated Ammonia worksheet is used.
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
    """Render the Ammonia Refrigeration data table, limited to 15 rows.

    Args:
        dataframe: The Ammonia Refrigeration DataFrame.
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
    """Render the complete Ammonia Refrigeration page."""
    ui.render_page_title(
        "Ammonia Refrigeration",
        "Ammonia refrigeration monitoring and performance.",
    )

    ammonia_dataframe, section = load_ammonia_data()
    if ammonia_dataframe is None:
        return

    render_kpi_row(ammonia_dataframe, section)
    ui.render_divider()

    render_data_section(ammonia_dataframe)
    ui.render_divider()

    render_trend_section()
