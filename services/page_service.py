"""Reusable page-loading service for the Engineering Monitoring Dashboard.

This module centralizes the loading pipeline that every dashboard page
previously duplicated: calling ``services.dashboard_loader.load_dashboard``,
handling every exception it can raise, rendering the appropriate error or
info banner via ``ui``, and resolving either the overview worksheet, a
discovered overview section, or a dedicated worksheet (with fallback to a
discovered overview section). It performs no engineering KPI calculation,
no chart-building, and no hardcoded row, column, meter, or department
names.
"""

from __future__ import annotations

import pandas as pd

import ui
from dashboard_data import build_overview_dashboard
from services.dashboard_loader import load_dashboard


def _load_dashboard_data() -> dict | None:
    """Load dashboard data, rendering an error banner on any failure.

    Returns:
        The dashboard data dictionary from
        ``services.dashboard_loader.load_dashboard``, or ``None`` after
        an error banner has been displayed.
    """
    try:
        return load_dashboard()
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


def _get_section(overview_dataframe: pd.DataFrame, keyword: str) -> dict | None:
    """Discover a section from the overview sheet by keyword.

    Args:
        overview_dataframe: The engineering overview worksheet DataFrame.
        keyword: A lowercase keyword to match against discovered section
            names, case-insensitively.

    Returns:
        The matching section dictionary (with keys ``name``, ``meters``,
        ``latest_values``, and ``dataframe``), or ``None`` if no section
        matches.
    """
    overview_dashboard = build_overview_dashboard(overview_dataframe)
    sections = overview_dashboard["sections"]

    return next(
        (
            section
            for section in sections
            if keyword in section["name"].lower()
        ),
        None,
    )


def load_overview() -> pd.DataFrame | None:
    """Load dashboard data and extract the engineering overview worksheet.

    Returns:
        The overview DataFrame if it was loaded successfully, otherwise
        ``None`` after an error or info banner has been displayed.
    """
    dashboard_data = _load_dashboard_data()
    if dashboard_data is None:
        return None

    overview_dataframe = dashboard_data["overview"]

    if overview_dataframe is None:
        ui.render_info_banner(
            "No engineering overview worksheet was found in the workbook."
        )
        return None

    return overview_dataframe


def load_section(keyword: str) -> dict | None:
    """Load the overview worksheet and discover a section by keyword.

    Args:
        keyword: A lowercase keyword to match against discovered section
            names, case-insensitively (e.g. ``"utility"``, ``"ammonia"``).

    Returns:
        The matching section dictionary (with keys ``name``, ``meters``,
        ``latest_values``, and ``dataframe``), or ``None`` after an
        error or info banner has been displayed.
    """
    overview_dataframe = load_overview()
    if overview_dataframe is None:
        return None

    section = _get_section(overview_dataframe, keyword)
    if section is None:
        ui.render_info_banner(
            f"No section matching '{keyword}' was discovered in the "
            "workbook."
        )
        return None

    return {**section, "overview_dataframe": overview_dataframe}


def load_dedicated_sheet(
    dashboard_key: str, fallback_keyword: str | None = None
) -> tuple[pd.DataFrame | None, dict | None]:
    """Load a dedicated worksheet, falling back to a discovered section.

    Prefers the dedicated worksheet stored under ``dashboard_key`` in the
    dashboard data dictionary. If that worksheet is not present and
    ``fallback_keyword`` is given, falls back to discovering a section
    with a matching name from the engineering overview worksheet.

    Args:
        dashboard_key: The key to look up in the dashboard data
            dictionary (e.g. ``"air_compressor"``, ``"freon"``,
            ``"ammonia"``).
        fallback_keyword: An optional lowercase keyword to use for
            discovering a fallback section from the overview worksheet
            when no dedicated worksheet is found.

    Returns:
        A tuple of ``(dataframe, section)``. When the dedicated
        worksheet is used, ``section`` is ``None`` and ``dataframe``
        holds that worksheet. When a discovered overview section is
        used instead, ``section`` holds the section dictionary and
        ``dataframe`` holds ``section["dataframe"]``. Returns
        ``(None, None)`` if no data could be found, after an
        appropriate banner has been displayed.
    """
    dashboard_data = _load_dashboard_data()
    if dashboard_data is None:
        return None, None

    dedicated_dataframe = dashboard_data.get(dashboard_key)
    if dedicated_dataframe is not None:
        return dedicated_dataframe, None

    if fallback_keyword is None:
        ui.render_info_banner(
            f"No '{dashboard_key}' worksheet was found in the workbook."
        )
        return None, None

    overview_dataframe = dashboard_data["overview"]
    if overview_dataframe is None:
        ui.render_info_banner(
            f"No '{dashboard_key}' worksheet or engineering overview "
            "worksheet was found in the workbook."
        )
        return None, None

    section = _get_section(overview_dataframe, fallback_keyword)
    if section is None:
        ui.render_info_banner(
            f"No section matching '{fallback_keyword}' was discovered "
            "in the workbook."
        )
        return None, None

    return section["dataframe"], section
