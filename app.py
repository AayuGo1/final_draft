"""Main Streamlit entry point for the Engineering Monitoring Dashboard.

This module orchestrates the first real dashboard page by delegating to
existing modules: ``data_loader`` for downloading and loading the
workbook, ``parser`` for reading worksheets into DataFrames,
``dashboard_data`` for organizing dashboard-ready data, and ``ui`` for all
reusable rendering components. It contains no Excel parsing, no GitHub
logic, no engineering KPI calculation, and no chart logic of its own.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import ui
from config import PAGE_CONFIG, WORKBOOK_FILENAME
from dashboard_data import get_dashboard_data
from data_loader import load_excel
from parser import read_all_sheets


def render_dashboard_cards(sheet_names: list[str]) -> None:
    """Render the top row of high-level dashboard cards.

    Args:
        sheet_names: The list of sheet names available in the workbook.
    """
    cards = [
        {"title": "Workbook", "value": WORKBOOK_FILENAME},
        {"title": "Last Updated", "value": "—"},
        {"title": "Sheets Loaded", "value": len(sheet_names)},
        {"title": "Dashboard Status", "value": "Online"},
    ]
    ui.render_kpi_cards(cards)


def render_overview_summary(overview_dataframe: pd.DataFrame) -> None:
    """Render generic summary metrics for the overview worksheet.

    Args:
        overview_dataframe: The DataFrame to summarize.
    """
    rows, columns = overview_dataframe.shape
    non_empty_cells = int(overview_dataframe.notna().sum().sum())
    memory_usage_kb = overview_dataframe.memory_usage(deep=True).sum() / 1024

    cards = [
        {"title": "Rows", "value": rows},
        {"title": "Columns", "value": columns},
        {"title": "Non-empty Cells", "value": non_empty_cells},
        {"title": "Memory Usage (KB)", "value": f"{memory_usage_kb:.1f}"},
    ]
    ui.render_kpi_cards(cards)


def render_overview_panel(overview_dataframe: pd.DataFrame) -> None:
    """Render the overview summary and worksheet inside a bordered container.

    Args:
        overview_dataframe: The DataFrame to display as the overview.
    """
    ui.render_section("Overview Data")
    with st.container(border=True):
        st.write("**Overview Summary**")
        render_overview_summary(overview_dataframe)
        st.divider()
        ui.render_dataframe(overview_dataframe)


def render_placeholder_section(title: str) -> None:
    """Render a bordered placeholder section for a future dashboard page.

    Args:
        title: The heading text for the placeholder section.
    """
    with st.container(border=True):
        st.write(f"**{title}**")
        st.caption("This section will be implemented in the next iteration.")


def render_placeholder_sections() -> None:
    """Render the four bordered placeholder sections in a responsive grid."""
    ui.render_section("Coming Soon")

    titles = [
        "Engineering Overview",
        "Department Analysis",
        "Air Compressor",
        "Freon Monitoring",
    ]

    left_column, right_column = st.columns(2)
    columns = [left_column, right_column, left_column, right_column]

    for title, column in zip(titles, columns):
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
        "Live workbook overview and diagnostics",
    )

    dashboard_data = load_dashboard_data()
    if dashboard_data is None:
        return

    ui.render_success_banner("Workbook loaded successfully.")

    sheet_names = dashboard_data["sheet_names"]
    render_dashboard_cards(sheet_names)
    ui.render_divider()

    render_overview_panel(dashboard_data["overview"])
    ui.render_divider()

    render_placeholder_sections()


if __name__ == "__main__":
    main()
