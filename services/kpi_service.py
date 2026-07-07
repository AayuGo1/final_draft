"""Reusable KPI calculation service for the Engineering Monitoring Dashboard.

This module computes generic, dynamically-discovered engineering KPIs
from already-loaded pandas DataFrames and Series. It contains no
Streamlit code, no Plotly code, no workbook downloading, and no Excel
parsing. Date columns are discovered by reusing
``dashboard_data.get_date_columns`` rather than re-implementing date
detection logic. Meter counts are taken from a provided section
dictionary when available, or derived dynamically from the DataFrame
otherwise. No departments, meter names, worksheet names, row numbers, or
column numbers are ever hardcoded.
"""

from __future__ import annotations

import pandas as pd

from dashboard_data import get_date_columns


# ==================================================
# WORKSHEET-LEVEL KPIs (existing functionality)
# ==================================================


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


# ==================================================
# METER-LEVEL (SERIES-BASED) KPI HELPERS
# ==================================================
#
# These operate on a single meter's readings, typically a
# ``pandas.Series`` such as those produced by
# ``dashboard_data.get_department_meter_structure`` or
# ``dashboard_data.get_air_compressor_meter_structure``. No meter or
# department name is ever assumed or hardcoded; callers pass in whatever
# series they have discovered.


def get_latest_value(readings: pd.Series) -> object | None:
    """Get the most recent non-null reading in a meter's series.

    Args:
        readings: A Series of readings for a single meter, in
            chronological order.

    Returns:
        The last non-null value in ``readings``, or ``None`` if every
        value is null or the series is empty.
    """
    non_null_values = readings.dropna()
    if non_null_values.empty:
        return None

    return non_null_values.iloc[-1]


def get_previous_value(readings: pd.Series) -> object | None:
    """Get the second-most-recent non-null reading in a meter's series.

    Used alongside ``get_latest_value`` to compute period-over-period
    changes such as trend percentage.

    Args:
        readings: A Series of readings for a single meter, in
            chronological order.

    Returns:
        The second-to-last non-null value in ``readings``, or ``None``
        if fewer than two non-null values are available.
    """
    non_null_values = readings.dropna()
    if len(non_null_values) < 2:
        return None

    return non_null_values.iloc[-2]


def calculate_average(readings: pd.Series) -> float | None:
    """Calculate the mean of all available readings in a meter's series.

    Args:
        readings: A Series of readings for a single meter.

    Returns:
        The mean of the non-null values as a float, or ``None`` if no
        non-null values are available.
    """
    non_null_values = pd.to_numeric(readings.dropna(), errors="coerce").dropna()
    if non_null_values.empty:
        return None

    return float(non_null_values.mean())


def calculate_minimum(readings: pd.Series) -> float | None:
    """Calculate the minimum of all available readings in a meter's series.

    Args:
        readings: A Series of readings for a single meter.

    Returns:
        The minimum non-null value as a float, or ``None`` if no
        non-null values are available.
    """
    non_null_values = pd.to_numeric(readings.dropna(), errors="coerce").dropna()
    if non_null_values.empty:
        return None

    return float(non_null_values.min())


def calculate_maximum(readings: pd.Series) -> float | None:
    """Calculate the maximum of all available readings in a meter's series.

    Args:
        readings: A Series of readings for a single meter.

    Returns:
        The maximum non-null value as a float, or ``None`` if no
        non-null values are available.
    """
    non_null_values = pd.to_numeric(readings.dropna(), errors="coerce").dropna()
    if non_null_values.empty:
        return None

    return float(non_null_values.max())


def calculate_running_average(readings: pd.Series) -> pd.Series:
    """Calculate the running (cumulative) average of a meter's readings.

    Non-null values are treated in their existing order; each point in
    the returned series is the mean of all non-null values up to and
    including that point. Null values are preserved in their original
    position with a null running average.

    Args:
        readings: A Series of readings for a single meter, in
            chronological order.

    Returns:
        A Series, aligned to ``readings``' original index, containing
        the running average at each point. Positions with no reading
        yet available are ``NaN``.
    """
    numeric_readings = pd.to_numeric(readings, errors="coerce")
    return numeric_readings.expanding().mean()


def calculate_monthly_average(
    readings: pd.Series, dates: pd.Series
) -> dict[str, float]:
    """Calculate the average reading per calendar month.

    Args:
        readings: A Series of readings for a single meter.
        dates: A Series of date-like values aligned by position with
            ``readings`` (for example, a discovered date column from the
            same worksheet).

    Returns:
        A dictionary mapping each month (formatted as ``"YYYY-MM"``) to
        the average of that month's non-null readings, in chronological
        order. Returns an empty dictionary if no valid date/reading
        pairs are available.
    """
    numeric_readings = pd.to_numeric(readings, errors="coerce").reset_index(drop=True)
    parsed_dates = pd.to_datetime(dates, errors="coerce").reset_index(drop=True)

    combined = pd.DataFrame({"value": numeric_readings, "date": parsed_dates})
    combined = combined.dropna(subset=["value", "date"])

    if combined.empty:
        return {}

    combined["month"] = combined["date"].dt.strftime("%Y-%m")
    monthly_means = combined.groupby("month")["value"].mean().sort_index()

    return {month: float(value) for month, value in monthly_means.items()}


def calculate_trend_percentage(readings: pd.Series) -> float | None:
    """Calculate the percentage change between the two latest readings.

    Args:
        readings: A Series of readings for a single meter, in
            chronological order.

    Returns:
        The percentage change from the previous non-null value to the
        latest non-null value, as a float (for example, ``12.5`` means a
        12.5% increase). Returns ``None`` if fewer than two non-null
        values are available, or if the previous value is zero (making a
        percentage change undefined).
    """
    latest_value = get_latest_value(readings)
    previous_value = get_previous_value(readings)

    if latest_value is None or previous_value is None:
        return None

    try:
        latest_numeric = float(latest_value)
        previous_numeric = float(previous_value)
    except (TypeError, ValueError):
        return None

    if previous_numeric == 0:
        return None

    return ((latest_numeric - previous_numeric) / previous_numeric) * 100


def count_missing_readings(readings: pd.Series) -> int:
    """Count the number of missing (null) readings in a meter's series.

    Args:
        readings: A Series of readings for a single meter.

    Returns:
        The count of null values in ``readings``.
    """
    return int(readings.isna().sum())


def count_total_readings(readings: pd.Series) -> int:
    """Count the number of available (non-null) readings in a meter's series.

    Args:
        readings: A Series of readings for a single meter.

    Returns:
        The count of non-null values in ``readings``.
    """
    return int(readings.notna().sum())


def calculate_meter_availability(readings: pd.Series) -> float:
    """Calculate the fraction of populated readings in a meter's series.

    Args:
        readings: A Series of readings for a single meter.

    Returns:
        The ratio of non-null readings to total readings, as a float
        between 0.0 and 1.0. Returns 0.0 if the series is empty.
    """
    total_readings = len(readings)
    if total_readings == 0:
        return 0.0

    return count_total_readings(readings) / total_readings


def build_meter_kpis(
    readings: pd.Series, dates: pd.Series | None = None
) -> dict:
    """Assemble a complete set of KPIs for a single meter.

    Combines every meter-level KPI helper into one reusable dictionary,
    suitable for KPI cards or downstream chart/summary services. No
    meter or department name is included here; callers already know
    which meter this series belongs to.

    Args:
        readings: A Series of readings for a single meter, in
            chronological order.
        dates: An optional Series of date-like values aligned by
            position with ``readings``, used to compute
            ``monthly_average``. If omitted, ``monthly_average`` is
            returned as an empty dictionary.

    Returns:
        A dictionary with keys ``latest_value``, ``previous_value``,
        ``average``, ``minimum``, ``maximum``, ``running_average``,
        ``monthly_average``, ``trend_percentage``, ``missing_readings``,
        ``total_readings``, and ``availability``.
    """
    monthly_average = (
        calculate_monthly_average(readings, dates) if dates is not None else {}
    )

    return {
        "latest_value": get_latest_value(readings),
        "previous_value": get_previous_value(readings),
        "average": calculate_average(readings),
        "minimum": calculate_minimum(readings),
        "maximum": calculate_maximum(readings),
        "running_average": calculate_running_average(readings),
        "monthly_average": monthly_average,
        "trend_percentage": calculate_trend_percentage(readings),
        "missing_readings": count_missing_readings(readings),
        "total_readings": count_total_readings(readings),
        "availability": calculate_meter_availability(readings),
    }
