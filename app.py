"""Main Streamlit entry point for the Engineering Monitoring Dashboard.

This module orchestrates the first real engineering dashboard page by
delegating to existing modules: ``data_loader`` for downloading and
loading the workbook, ``parser`` for reading worksheets into DataFrames,
``dashboard_data`` for organizing dashboard-ready data, and ``ui`` for all
reusable rendering components. It contains no Excel parsing, no GitHub
logic, no engineering KPI calculation, and no chart logic of its own.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import ui
from config import PAGE_CONFIG
from dashboard_data import get_dashboard_data
from data_loader import load_excel
from parser import read_all_sheets

KPI_CARD_TITLES: tuple[str, ...] = (
    "NPCL",
    "Utility",
    "Engineering",
    "Air Compressor",
    "DG",
    "GG",
)
"""Titles for the top-level engineering overview KPI cards."""

PLACEHOLDER_SECTION_TITLES: tuple[str, ...] = (
    "Energy Monitoring",
    "Water Monitoring",
    "Air Compressor",
    "Freon Monitoring",
)
"""Titles for the bottom-row placeholder monitoring sections."""


def render_filters() -> None:
    """Render the placeholder month and department filter selectors."""
    ui.render_section("Filters")
    month_column, department_column = st.columns(2)

    with month_column:
        st.selectbox("Month", options=["All Months"])
    with department_column:
        st.selectbox("Department", options=["All Departments"])


def render_kpi_overview() -> None:
    """Render the responsive row of top-level engineering KPI cards."""
    ui.render_section("Overview")

    cards = [
        {"title": title, "value": "Coming Soon"} for title in KPI_CARD_TITLES
    ]
    ui.render_kpi_cards(cards)


def render_engineering_monitoring(overview_dataframe: pd.DataFrame) -> None:
    """Render the overview worksheet inside a full-width bordered container.

    Args:
        overview_dataframe: The DataFrame to display.
    """
    ui.render_section("Engineering Monitoring")
    with st.container(border=True):
        ui.render_dataframe(overview_dataframe)


def render_placeholder_section(title: str) -> None:
    """Render a bordered placeholder section for a future monitoring page.

    Args:
        title: The heading text for the placeholder section.
    """
    with st.container(border=True):
        st.write(f"**{title}**")
        st.caption("This section will be populated dynamically.")


def render_monitoring_sections() -> None:
    """Render the four bordered monitoring placeholder sections in a grid."""
    left_column, right_column = st.columns(2)
    columns = [left_column, right_column, left_column, right_column]

    for title, column in zip(PLACEHOLDER_SECTION_TITLES, columns):
        with column:
            render_placeholder_section(title)


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

    ui.render_page_title(
        "Engineering Monitoring Dashboard",
        "Daily Energy Monitoring",
    )

    dashboard_data = load_dashboard_data()
    if dashboard_data is None:
        return

    ui.render_success_banner("Workbook loaded successfully.")
    ui.render_divider()

    render_filters()
    ui.render_divider()

    render_kpi_overview()
    ui.render_divider()

    render_engineering_monitoring(dashboard_data["overview"])
    ui.render_divider()

    render_monitoring_sections()


if __name__ == "__main__":
    main()
