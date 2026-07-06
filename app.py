"""Main Streamlit entry point for the Engineering Monitoring Dashboard.

This module orchestrates the dashboard by delegating to existing modules:
``data_loader`` for downloading and loading the workbook, ``parser`` for
reading worksheets into DataFrames, ``dashboard_data`` for organizing
dashboard-ready data, and ``ui`` for all rendering. It contains no Excel
parsing, no GitHub logic, no DataFrame manipulation, and no business or
chart logic of its own.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import ui
from config import (
    GITHUB_BRANCH,
    GITHUB_OWNER,
    GITHUB_REPO,
    PAGE_CONFIG,
    WORKBOOK_FILENAME,
)
from dashboard_data import get_dashboard_data
from data_loader import load_excel
from parser import read_all_sheets


def render_workbook_information(sheet_names: list[str]) -> None:
    """Render repository and workbook metadata.

    Args:
        sheet_names: The list of sheet names available in the workbook.
    """
    ui.render_section("Workbook Information")

    cards = [
        {"title": "Repository", "value": f"{GITHUB_OWNER}/{GITHUB_REPO}"},
        {"title": "Branch", "value": GITHUB_BRANCH},
        {"title": "Workbook", "value": WORKBOOK_FILENAME},
        {"title": "Sheet count", "value": len(sheet_names)},
    ]
    ui.render_kpi_cards(cards)


def render_available_sheets(sheet_names: list[str]) -> None:
    """Render the list of available sheet names.

    Args:
        sheet_names: The list of sheet names available in the workbook.
    """
    ui.render_section("Available Sheets")
    for name in sheet_names:
        st.write(f"- {name}")


def render_overview(overview_dataframe: pd.DataFrame) -> None:
    """Render the overview worksheet as a dataframe.

    Args:
        overview_dataframe: The DataFrame to display as the overview.
    """
    ui.render_section("Overview")
    ui.render_dataframe(overview_dataframe)


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
    ui.render_divider()

    sheet_names = dashboard_data["sheet_names"]
    render_workbook_information(sheet_names)
    ui.render_divider()

    render_available_sheets(sheet_names)
    ui.render_divider()

    render_overview(dashboard_data["overview"])


if __name__ == "__main__":
    main()
