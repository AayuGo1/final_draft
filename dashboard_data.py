"""Business layer for the Engineering Monitoring Dashboard.

This module converts the raw DataFrames returned by ``parser.py`` into
dashboard-ready data. It organizes and locates relevant worksheets by
generic name matching, without detecting headers, units, merged cells, or
calculating any engineering KPIs. It performs no rendering and creates no
UI or chart elements.
"""

from __future__ import annotations

import pandas as pd

AIR_COMPRESSOR_KEYWORDS: tuple[str, ...] = ("air", "compressor")
"""Keywords used to locate the air compressor worksheet, case-insensitive."""

FREON_KEYWORD: str = "freon"
"""Keyword used to locate the freon worksheet, case-insensitive."""


def get_dashboard_data(workbook: dict[str, pd.DataFrame]) -> dict:
    """Assemble all dashboard-ready data from the parsed workbook.

    Args:
        workbook: A dictionary mapping sheet names to cleaned DataFrames,
            as returned by ``parser.read_all_sheets``.

    Returns:
        A dictionary with keys ``overview``, ``departments``,
        ``air_compressor``, ``freon``, and ``sheet_names``, containing
        the corresponding worksheet data (or ``None`` where not found).

    Raises:
        ValueError: If ``workbook`` is not a valid, non-empty dictionary
            of DataFrames.
    """
    _validate_workbook(workbook)

    return {
        "overview": get_overview_dataframe(workbook),
        "departments": get_department_data(workbook),
        "air_compressor": get_air_compressor_data(workbook),
        "freon": get_freon_data(workbook),
        "sheet_names": get_sheet_names(workbook),
    }


def get_sheet_names(workbook: dict[str, pd.DataFrame]) -> list[str]:
    """Get the list of sheet names present in the workbook.

    Args:
        workbook: A dictionary mapping sheet names to cleaned DataFrames.

    Returns:
        A list of sheet names in their original workbook order.

    Raises:
        ValueError: If ``workbook`` is not a valid, non-empty dictionary
            of DataFrames.
    """
    _validate_workbook(workbook)
    return list(workbook.keys())


def get_overview_dataframe(workbook: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Get the primary worksheet that will drive the dashboard overview.

    The first worksheet in workbook order is used, since no fixed sheet
    name can be assumed across monthly workbook replacements.

    Args:
        workbook: A dictionary mapping sheet names to cleaned DataFrames.

    Returns:
        The DataFrame for the first worksheet in the workbook.

    Raises:
        ValueError: If ``workbook`` is not a valid, non-empty dictionary
            of DataFrames.
    """
    _validate_workbook(workbook)
    first_sheet_name = next(iter(workbook))
    return workbook[first_sheet_name]


def get_department_data(workbook: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Get the engineering monitoring worksheet for department pages.

    The first worksheet in workbook order is used as the source for
    department-level breakdowns, consistent with the overview worksheet.
    No KPI calculation is performed here.

    Args:
        workbook: A dictionary mapping sheet names to cleaned DataFrames.

    Returns:
        A cleaned DataFrame containing the engineering monitoring data.

    Raises:
        ValueError: If ``workbook`` is not a valid, non-empty dictionary
            of DataFrames.
    """
    _validate_workbook(workbook)
    return get_overview_dataframe(workbook)


def get_air_compressor_data(
    workbook: dict[str, pd.DataFrame]
) -> pd.DataFrame | None:
    """Find the worksheet related to air compressors.

    Searches all sheet names, case-insensitively, for either "air" or
    "compressor".

    Args:
        workbook: A dictionary mapping sheet names to cleaned DataFrames.

    Returns:
        The matching DataFrame, or ``None`` if no worksheet matches.

    Raises:
        ValueError: If ``workbook`` is not a valid, non-empty dictionary
            of DataFrames.
    """
    _validate_workbook(workbook)
    return _find_sheet_by_keywords(workbook, AIR_COMPRESSOR_KEYWORDS)


def get_freon_data(workbook: dict[str, pd.DataFrame]) -> pd.DataFrame | None:
    """Find the worksheet related to freon monitoring.

    Searches all sheet names, case-insensitively, for "freon".

    Args:
        workbook: A dictionary mapping sheet names to cleaned DataFrames.

    Returns:
        The matching DataFrame, or ``None`` if no worksheet matches.

    Raises:
        ValueError: If ``workbook`` is not a valid, non-empty dictionary
            of DataFrames.
    """
    _validate_workbook(workbook)
    return _find_sheet_by_keywords(workbook, (FREON_KEYWORD,))


def _find_sheet_by_keywords(
    workbook: dict[str, pd.DataFrame], keywords: tuple[str, ...]
) -> pd.DataFrame | None:
    """Find the first worksheet whose name contains any of the keywords.

    Args:
        workbook: A dictionary mapping sheet names to cleaned DataFrames.
        keywords: Keywords to search for within sheet names, matched
            case-insensitively.

    Returns:
        The DataFrame for the first matching sheet in workbook order, or
        ``None`` if no sheet name matches any keyword.
    """
    for sheet_name, dataframe in workbook.items():
        lowered_name = sheet_name.lower()
        if any(keyword in lowered_name for keyword in keywords):
            return dataframe

    return None


def _validate_workbook(workbook: dict[str, pd.DataFrame]) -> None:
    """Validate that the workbook is a non-empty dictionary of DataFrames.

    Args:
        workbook: The object to validate.

    Raises:
        ValueError: If ``workbook`` is not a dictionary, is empty, or
            contains values that are not ``pandas.DataFrame`` instances.
    """
    if not isinstance(workbook, dict):
        raise ValueError(
            f"Expected a dict[str, pandas.DataFrame], got "
            f"{type(workbook).__name__}."
        )

    if not workbook:
        raise ValueError(
            "The workbook dictionary is empty; no worksheets were "
            "provided."
        )

    for sheet_name, dataframe in workbook.items():
        if not isinstance(dataframe, pd.DataFrame):
            raise ValueError(
                f"Sheet '{sheet_name}' does not contain a valid "
                f"pandas.DataFrame (got {type(dataframe).__name__})."
            )
