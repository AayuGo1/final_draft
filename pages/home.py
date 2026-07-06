"""Home page for the Engineering Monitoring Dashboard.

This module renders the real overview dashboard by delegating to existing
modules: ``data_loader`` for downloading and loading the workbook,
``parser`` for reading worksheets into DataFrames, ``dashboard_data`` for
organizing real dashboard-ready data via ``build_overview_dashboard``, and
``ui`` for all reusable rendering components. It contains no Excel
parsing, no GitHub logic, no engineering KPI calculation, and no chart
logic of its own.
"""

from __future__ import annotations

import streamlit as st

import ui
from dashboard_data import build_overview_dashboard, get_dashboard_data
from data_loader import load_excel
from parser import read_all_sheets


def render_filters() -> None:
    """Render the month and department filter selectors."""
    ui.render_section("Filters")
    month_column, department_column = st.columns(2)

    with month_column:
        st.selectbox("Month", options=["All Months"])
    with department_column:
        st.selectbox("Department", options=["All Departments"])


def render_overview_kpis(overview_dashboard: dict) -> None:
    """Render the top-level overview KPI row computed from real section data.

    Args:
        overview_dashboard: The dictionary returned by
            ``dashboard_data.build_overview_dashboard``.
    """
    ui.render_section("Overview")

    sections = overview_dashboard["sections"]

    number_of_departments = len(sections)
    total_meters = sum(len(section["meters"]) for section in sections)
    total_readings = sum(
        int(section["dataframe"].notna().sum().sum()) for section in sections
    )

    cards = [
        {"title": "Number of Departments", "value": number_of_departments},
        {"title": "Total Meters", "value": total_meters},
        {"title": "Total Readings", "value": total_readings},
        {"title": "Workbook Status", "value": "Online"},
    ]
    ui.render_kpi_cards(cards)


def render_monitoring_section(section: dict) -> None:
    """Render a single bordered monitoring section for one department.

    Args:
        section: A section dictionary with keys ``name``, ``meters``,
            ``latest_values``, and ``dataframe``.
    """
    latest_reading_count = sum(
        1 for value in section["latest_values"].values() if value is not None
    )

    with st.container(border=True):
        st.write(f"**{section['name']}**")

        info_column, meters_column, readings_column = st.columns(3)
        with info_column:
            st.metric("Number of Meters", len(section["meters"]))
        with meters_column:
            st.metric("Latest Reading Count", latest_reading_count)
        with readings_column:
            st.metric("Total Rows", section["dataframe"].shape[0])

        ui.render_divider()
        ui.render_dataframe(section["dataframe"].head(10))


def render_monitoring_sections(overview_dashboard: dict) -> None:
    """Render one bordered monitoring section for every discovered department.

    Args:
        overview_dashboard: The dictionary returned by
            ``dashboard_data.build_overview_dashboard``.
    """
    ui.render_section("Monitoring Sections")

    sections = overview_dashboard["sections"]
    if not sections:
        ui.render_info_banner("No departments were discovered in the workbook.")
        return

    for section in sections:
        render_monitoring_section(section)


def load_dashboard_data() -> dict | None:
    """Load the workbook and assemble dashboard-ready data.

    Returns:
        The dashboard data dictionary produced by
        ``dashboard_data.get_dashboard_data``, or ``None`` if loading
        failed after an error banner has been displayed.
    """
    try:
        excel_file = load_excel()
        sheets = read_all_sheets(excel_file)
        return get_dashboard_data(sheets)
    except TimeoutError as exc:
        ui.render_error_banner(f"The workbook source timed out: {exc}")
    except ConnectionError as exc:
        ui.render_error_banner(
            f"Could not connect to the workbook source: {exc}"
        )
    except FileNotFoundError as exc:
        ui.render_error_banner(f"Workbook not found: {exc}")
    except ValueError as exc:
        ui.render_error_banner(f"The workbook data is invalid: {exc}")
    except RuntimeError as exc:
        ui.render_error_banner(
            f"An error occurred while loading the workbook: {exc}"
        )

    return None


def render() -> None:
    """Render the complete home page: filters, overview KPIs, and sections."""
    ui.render_page_title(
        "Engineering Monitoring Dashboard",
        "Daily Energy Monitoring",
    )

    dashboard_data = load_dashboard_data()
    if dashboard_data is None:
        return

    ui.render_divider()

    render_filters()
    ui.render_divider()

    overview_dashboard = build_overview_dashboard(dashboard_data["overview"])

    render_overview_kpis(overview_dashboard)
    ui.render_divider()

    render_monitoring_sections(overview_dashboard)
