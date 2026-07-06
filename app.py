"""Main Streamlit entry point for the Engineering Monitoring Dashboard.

This module orchestrates the professional engineering dashboard homepage
by delegating to existing modules: ``data_loader`` for downloading and
loading the workbook, ``parser`` for reading worksheets into DataFrames,
``dashboard_data`` for organizing dashboard-ready data, and ``ui`` for all
reusable rendering components. It contains no Excel parsing, no GitHub
logic, no engineering KPI calculation, and no chart logic of its own. No
workbook structure, meters, or pandas objects are exposed to the user.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

import ui
from config import PAGE_CONFIG
from dashboard_data import get_dashboard_data
from data_loader import load_excel
from parser import read_all_sheets

MONITORING_SECTIONS: tuple[tuple[str, str], ...] = (
    ("Energy Monitoring", "Electrical energy consumption across all metered points."),
    ("Water Monitoring", "Water usage and consumption tracking across departments."),
    ("Utility Monitoring", "General utility consumption and performance tracking."),
    ("Engineering Monitoring", "Overall engineering performance and asset health."),
    ("Air Compressor Monitoring", "Air compressor load, output, and efficiency tracking."),
    ("Freon Monitoring", "Refrigerant and cold storage system monitoring."),
)
"""Titles and descriptions for the six main monitoring sections."""

OVERVIEW_KPI_TITLES: tuple[str, ...] = (
    "Energy",
    "Water",
    "Air Compressor",
    "Utility",
    "Engineering",
    "Freon",
)
"""Titles for the top-level overview KPI cards."""


def render_top_navigation() -> None:
    """Render the dashboard title, subtitle, and last refresh indicator."""
    ui.render_page_title(
        "Engineering Monitoring Dashboard",
        "Daily Energy Monitoring",
    )
    last_refresh = datetime.now().strftime("%Y-%m-%d %H:%M")
    st.caption(f"Last Refresh: {last_refresh}")


def render_filters() -> None:
    """Render the month and department filter selectors."""
    ui.render_section("Filters")
    month_column, department_column = st.columns(2)

    with month_column:
        st.selectbox("Month", options=["All Months"])
    with department_column:
        st.selectbox("Department", options=["All Departments"])


def render_overview_kpis() -> None:
    """Render the top-level overview KPI cards with placeholder values."""
    ui.render_section("Overview")

    cards = [
        {"title": title, "value": "Coming Soon"} for title in OVERVIEW_KPI_TITLES
    ]
    ui.render_kpi_cards(cards)


def render_monitoring_section(title: str, description: str) -> None:
    """Render a single bordered monitoring section with placeholder content.

    Args:
        title: The section heading.
        description: A short description of what the section monitors.
    """
    with st.container(border=True):
        st.write(f"**{title}**")
        st.caption(description)
        ui.render_divider()

        placeholder_cards = [
            {"title": "KPI 1", "value": "—"},
            {"title": "KPI 2", "value": "—"},
            {"title": "KPI 3", "value": "—"},
        ]
        ui.render_kpi_cards(placeholder_cards)
        st.caption("KPI calculations will be implemented.")

        ui.render_divider()
        st.caption("Charts will be implemented.")

        ui.render_divider()
        st.caption("Latest readings will appear here.")


def render_main_dashboard() -> None:
    """Render the six bordered monitoring sections in a responsive grid."""
    ui.render_section("Main Dashboard")

    left_column, right_column = st.columns(2)
    columns = [
        left_column,
        right_column,
        left_column,
        right_column,
        left_column,
        right_column,
    ]

    for (title, description), column in zip(MONITORING_SECTIONS, columns):
        with column:
            render_monitoring_section(title, description)


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


def main() -> None:
    """Configure the page and orchestrate the dashboard rendering."""
    st.set_page_config(**PAGE_CONFIG)

    render_top_navigation()

    dashboard_data = load_dashboard_data()
    if dashboard_data is None:
        return

    ui.render_divider()

    render_filters()
    ui.render_divider()

    render_overview_kpis()
    ui.render_divider()

    render_main_dashboard()


if __name__ == "__main__":
    main()
