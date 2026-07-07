"""Worksheet reading and cleaning for the Engineering Monitoring Dashboard.

This module is responsible ONLY for reading worksheets from a
``pandas.ExcelFile`` and returning clean, unopinionated DataFrames. It
performs no header detection, no unit or section inference, no KPI
calculation, and no dashboard or chart logic. All workbook intelligence
lives in later modules.
"""

from __future__ import annotations

import pandas as pd


def read_sheet(excel_file: pd.ExcelFile, sheet_name: str) -> pd.DataFrame:
    """Read a single worksheet into a clean DataFrame.

    Args:
        excel_file: A loaded ``pandas.ExcelFile`` instance.
        sheet_name: Name of the worksheet to read.

    Returns:
        A cleaned DataFrame with empty rows and columns removed and the
        index reset. All original values are preserved exactly as read,
        including merged-cell values already propagated by pandas.

    Raises:
        ValueError: If ``sheet_name`` does not exist in the workbook.
        RuntimeError: If the worksheet cannot be read for any other
            reason.
    """
    if sheet_name not in excel_file.sheet_names:
        raise ValueError(
            f"Worksheet '{sheet_name}' was not found in the workbook. "
            f"Available sheets: {list(excel_file.sheet_names)}."
        )
    try:
        raw_dataframe = excel_file.parse(sheet_name=sheet_name, header=None)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to read worksheet '{sheet_name}' from the workbook: "
            f"{exc}"
        ) from exc
    return clean_dataframe(raw_dataframe)


def read_all_sheets(excel_file: pd.ExcelFile) -> dict[str, pd.DataFrame]:
    """Read every worksheet in the workbook into clean DataFrames.

    Args:
        excel_file: A loaded ``pandas.ExcelFile`` instance.

    Returns:
        A dictionary mapping each sheet name to its cleaned DataFrame,
        preserving the original sheet order from the workbook.

    Raises:
        RuntimeError: If any worksheet cannot be read.
    """
    return {
        sheet_name: read_sheet(excel_file, sheet_name)
        for sheet_name in excel_file.sheet_names
    }


def clean_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Remove completely empty rows and columns and reset the index.

    Args:
        dataframe: The raw DataFrame to clean.

    Returns:
        A new DataFrame with fully empty rows and columns dropped and a
        fresh, sequential index. No values are modified, filled, or
        renamed.

    Raises:
        ValueError: If ``dataframe`` is not a valid ``pandas.DataFrame``.
    """
    if not isinstance(dataframe, pd.DataFrame):
        raise ValueError(
            f"Expected a pandas.DataFrame, got {type(dataframe).__name__}."
        )
    cleaned = dataframe.dropna(axis=0, how="all")
    cleaned = cleaned.dropna(axis=1, how="all")
    cleaned = cleaned.reset_index(drop=True)
    return cleaned


def get_sheet_dimensions(dataframe: pd.DataFrame) -> tuple[int, int]:
    """Get the number of rows and columns in a DataFrame.

    Args:
        dataframe: The DataFrame to measure.

    Returns:
        A tuple of ``(rows, columns)``.

    Raises:
        ValueError: If ``dataframe`` is not a valid ``pandas.DataFrame``.
    """
    if not isinstance(dataframe, pd.DataFrame):
        raise ValueError(
            f"Expected a pandas.DataFrame, got {type(dataframe).__name__}."
        )
    rows, columns = dataframe.shape
    return rows, columns
