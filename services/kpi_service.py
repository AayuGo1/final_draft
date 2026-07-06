"""Reusable KPI calculation service for the Engineering Monitoring Dashboard.

This module computes generic, dynamically-discovered engineering KPIs
from already-loaded pandas DataFrames. It contains no Streamlit code, no
Plotly code, no workbook downloading, and no Excel parsing. Date columns
are discovered by reusing ``dashboard_data.get_date_columns`` rather than
re-implementing date detection logic. Meter counts are taken from a
provided section dictionary when available, or derived dynamically from
the DataFrame otherwise. No departments, meter names, worksheet names,
row numbers, or column numbers are ever hardcoded.
"""

from __future__ import annotations

import pandas as pd

from dashboard_data import get_date_columns


def count_rows(dataframe: pd.DataFrame) -> int:
    """Count the number of rows in a DataFrame.

    Args:
        dataframe: The DataFrame to inspect.

    Returns:
        The number of rows in ``dataframe``.
    """
    return int(dataframe.shape[0])


def count_columns(dataframe: pd.DataFrame) -> int:
    """Count the number of columns in a DataFrame.

    Args:
        dataframe: The DataFrame to inspect.

    Returns:
        The number of columns in ``dataframe``.
    """
    return int(dataframe.shape[1])


def count_non_empty_cells(dataframe: pd.DataFrame) -> int:
    """Count the total number of non-null cells in a DataFrame.

    Args:
        dataframe: The DataFrame to inspect.

    Returns:
        The total count of non-null cells across the whole DataFrame.
    """
    return int(dataframe.notna().sum().sum())


def count_empty_cells(dataframe: pd.DataFrame) -> int:
    """Count the total number of null (empty) cells in a DataFrame.

    Args:
        dataframe: The DataFrame to inspect.

    Returns:
        The total count of null cells across the whole DataFrame.
    """
    return int(dataframe.isna().sum().sum())


def count_available_readings(dataframe: pd.DataFrame) -> int:
    """Count the total number of available (non-null) readings.

    This is an alias for ``count_non_empty_cells``, expressed in
    dashboard terminology, since every non-null cell in an engineering
    worksheet represents one available reading.

    Args:
        dataframe: The DataFrame to inspect.

    Returns:
        The total count of available readings in ``dataframe``.
    """
    return count_non_empty_cells(dataframe)


def count_meters(
    dataframe: pd.DataFrame, section: dict | None = None
) -> int:
    """Determine the number of meters represented in the data.

    When a discovered section dictionary (as produced by
    ``dashboard_data.build_overview_dashboard`` or similar) is provided
    and contains a ``"meters"`` key, its meter list length is used
    directly. Otherwise, the meter count is derived dynamically as the
    number of columns that are not date columns, since worksheets
    typically use one column per meter alongside date column(s).

    Args:
        dataframe: The DataFrame to inspect.
        section: An optional section dictionary containing a ``"meters"``
            key with a list of meter names.

    Returns:
        The number of meters found in the data.
    """
    if section is not None and "meters" in section:
        return len(section["meters"])

    date_columns = get_date_columns(dataframe)
    return max(count_columns(dataframe) - len(date_columns), 0)


def calculate_data_availability(dataframe: pd.DataFrame) -> float:
    """Calculate the fraction of cells in a DataFrame that are populated.

    Args:
        dataframe: The DataFrame to inspect.

    Returns:
        The ratio of non-null cells to total cells, as a float between
        0.0 and 1.0. Returns 0.0 if the DataFrame has no cells.
    """
    total_cells = count_rows(dataframe) * count_columns(dataframe)
    if total_cells == 0:
        return 0.0

    return count_non_empty_cells(dataframe) / total_cells


def get_latest_timestamp(dataframe: pd.DataFrame) -> str:
    """Find the latest timestamp available in a DataFrame, if any.

    Date columns are discovered dynamically via
    ``dashboard_data.get_date_columns``. Columns are checked from the
    last discovered date column backward, returning the last non-null
    value found in the first column that has one.

    Args:
        dataframe: The DataFrame to inspect.

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


def build_kpi_summary(
    dataframe: pd.DataFrame, section: dict | None = None
) -> dict:
    """Assemble a complete KPI summary for a DataFrame.

    Args:
        dataframe: The DataFrame to summarize.
        section: An optional section dictionary (with a ``"meters"``
            key) used to determine the meter count, when available.

    Returns:
        A dictionary with keys ``rows``, ``columns``, ``meters``,
        ``available_readings``, ``empty_cells``, ``availability``, and
        ``latest_timestamp``.
    """
    return {
        "rows": count_rows(dataframe),
        "columns": count_columns(dataframe),
        "meters": count_meters(dataframe, section),
        "available_readings": count_available_readings(dataframe),
        "empty_cells": count_empty_cells(dataframe),
        "availability": calculate_data_availability(dataframe),
        "latest_timestamp": get_latest_timestamp(dataframe),
    }
