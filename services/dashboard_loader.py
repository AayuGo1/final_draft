"""Reusable dashboard loading service for the Engineering Monitoring Dashboard.

This module is responsible ONLY for orchestrating the existing workbook
download, parsing, and dashboard-data assembly functions into a single
reusable entry point. It performs no parsing, no KPI calculation, no
rendering, and introduces no new business logic beyond composing calls
to the existing backend modules.
"""

from __future__ import annotations

from data_loader import load_excel
from parser import read_all_sheets
from dashboard_data import get_dashboard_data


def load_dashboard() -> dict:
    """Load the workbook and assemble dashboard-ready data.

    Downloads and loads the workbook, reads every worksheet into cleaned
    DataFrames, and assembles the dashboard data dictionary. This is the
    single reusable entry point that all dashboard pages should use
    instead of duplicating the loading pipeline themselves.

    Returns:
        The dashboard data dictionary produced by
        ``dashboard_data.get_dashboard_data``, containing keys such as
        ``overview``, ``departments``, ``air_compressor``, ``freon``,
        and ``sheet_names``.

    Raises:
        ValueError: If the downloaded content is not a valid Excel file,
            or if the resulting worksheets are not valid for dashboard
            assembly.
        ConnectionError: If GitHub cannot be reached due to a network
            issue.
        TimeoutError: If the download request exceeds the configured
            timeout.
        FileNotFoundError: If the workbook does not exist at the
            configured URL.
        RuntimeError: If GitHub responds with any other non-success
            status code, or if a worksheet cannot be read.
    """
    excel_file = load_excel()
    sheets = read_all_sheets(excel_file)
    return get_dashboard_data(sheets)


def load_dashboard_safe() -> tuple[dict | None, str | None]:
    """Load dashboard while converting exceptions into friendly messages."""

    try:
        return load_dashboard(), None

    except ConnectionError:
        return (
            None,
            "Could not connect to the data source. Please check your network connection and try again.",
        )

    except TimeoutError:
        return (
            None,
            "The request to load the workbook timed out. Please try again.",
        )

    except FileNotFoundError:
        return (
            None,
            "The workbook could not be found at the configured source.",
        )

    except (ValueError, RuntimeError) as error:
        return None, f"Failed to load engineering data: {error}"
