"""Business layer for the Engineering Monitoring Dashboard.

This module converts the raw DataFrames returned by ``parser.py`` into
dashboard-ready data. It organizes and locates relevant worksheets by
generic name matching, and dynamically discovers generic workbook
structure such as department labels, date columns, and the unit row. It
performs no engineering KPI calculation, no rendering, and creates no UI
or chart elements. No row numbers, column letters, merged cells, or
department/header locations are ever hardcoded.
"""

from __future__ import annotations

import warnings

import pandas as pd

AIR_COMPRESSOR_KEYWORDS: tuple[str, ...] = ("air", "compressor")
"""Keywords used to locate the air compressor worksheet, case-insensitive."""

FREON_KEYWORD: str = "freon"
"""Keyword used to locate the freon worksheet, case-insensitive."""

UNIT_TOKENS: tuple[str, ...] = (
    "kwh",
    "kw",
    "kva",
    "kl",
    "l",
    "ml",
    "kg",
    "mt",
    "ton",
    "%",
    "°c",
    "c",
    "bar",
    "psi",
    "m3",
    "nm3",
    "hp",
    "ppm",
    "db",
    "hz",
    "rpm",
    "hrs",
    "hr",
    "units",
    "no.",
    "nos",
)
"""Known engineering unit tokens used to identify a likely unit row."""

MIN_UNIT_MATCH_RATIO: float = 0.4
"""Minimum fraction of non-empty cells in a row that must match a known
unit token for that row to be considered the unit row."""

MIN_DATE_PARSE_RATIO: float = 0.6
"""Minimum fraction of non-empty cells in a column that must parse as
dates for that column to be considered a date column."""


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


def get_available_departments(overview_dataframe: pd.DataFrame) -> list[str]:
    """Discover department names present in the overview worksheet.

    The column most likely to hold department labels is identified
    dynamically as the text-heavy column with the most repeated,
    non-numeric, non-date values. Blank cells are ignored and the
    original workbook order is preserved.

    Args:
        overview_dataframe: The overview worksheet DataFrame.

    Returns:
        A list of discovered department names in their order of first
        appearance. Returns an empty list if no suitable column is found.

    Raises:
        ValueError: If ``overview_dataframe`` is not a valid
            ``pandas.DataFrame``.
    """
    _validate_dataframe(overview_dataframe)

    department_column = _find_department_column(overview_dataframe)
    if department_column is None:
        return []

    date_columns = set(get_date_columns(overview_dataframe))
    if department_column in date_columns:
        return []

    values = overview_dataframe.iloc[:, department_column].dropna()

    departments: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or _looks_like_unit(text) or _looks_like_number(text):
            continue
        if text not in departments:
            departments.append(text)

    return departments


def get_date_columns(overview_dataframe: pd.DataFrame) -> list[int]:
    """Discover the positional indexes of columns that contain dates.

    A column is considered a date column when a high proportion of its
    non-empty values can be interpreted as dates, either because they are
    already datetime-typed or because they parse successfully as dates.

    Args:
        overview_dataframe: The overview worksheet DataFrame.

    Returns:
        A list of column positional indexes, in ascending order, that
        are likely to represent dates.

    Raises:
        ValueError: If ``overview_dataframe`` is not a valid
            ``pandas.DataFrame``.
    """
    _validate_dataframe(overview_dataframe)

    date_column_indexes: list[int] = []

    for position in range(overview_dataframe.shape[1]):
        column_values = overview_dataframe.iloc[:, position].dropna()
        if column_values.empty:
            continue

        if pd.api.types.is_datetime64_any_dtype(column_values):
            date_column_indexes.append(position)
            continue

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            parsed = pd.to_datetime(column_values, errors="coerce")
        parse_ratio = parsed.notna().sum() / len(column_values)

        if parse_ratio >= MIN_DATE_PARSE_RATIO:
            date_column_indexes.append(position)

    return date_column_indexes


def get_unit_row(overview_dataframe: pd.DataFrame) -> int | None:
    """Discover the row most likely to contain engineering units.

    A row is identified as the unit row when a high proportion of its
    non-empty cells match known engineering unit tokens (for example
    "kWh", "kL", "kg", "%", "bar", "m3").

    Args:
        overview_dataframe: The overview worksheet DataFrame.

    Returns:
        The row index most likely to contain units, or ``None`` if no
        row meets the matching threshold.

    Raises:
        ValueError: If ``overview_dataframe`` is not a valid
            ``pandas.DataFrame``.
    """
    _validate_dataframe(overview_dataframe)

    best_row_index: int | None = None
    best_match_ratio = 0.0

    for row_index, row_values in overview_dataframe.iterrows():
        non_empty_values = row_values.dropna()
        if non_empty_values.empty:
            continue

        unit_matches = sum(
            1 for value in non_empty_values if _looks_like_unit(str(value))
        )
        match_ratio = unit_matches / len(non_empty_values)

        if match_ratio >= MIN_UNIT_MATCH_RATIO and match_ratio > best_match_ratio:
            best_match_ratio = match_ratio
            best_row_index = row_index

    return best_row_index


def get_dashboard_overview(overview_dataframe: pd.DataFrame) -> dict:
    """Assemble discovered structural information about the overview sheet.

    Args:
        overview_dataframe: The overview worksheet DataFrame.

    Returns:
        A dictionary with keys ``departments``, ``date_columns``,
        ``unit_row``, and ``shape``.

    Raises:
        ValueError: If ``overview_dataframe`` is not a valid
            ``pandas.DataFrame``.
    """
    _validate_dataframe(overview_dataframe)

    return {
        "departments": get_available_departments(overview_dataframe),
        "date_columns": get_date_columns(overview_dataframe),
        "unit_row": get_unit_row(overview_dataframe),
        "shape": overview_dataframe.shape,
    }


def _find_department_column(overview_dataframe: pd.DataFrame) -> int | None:
    """Identify the column most likely to hold department labels.

    The candidate column is the one with the highest count of repeated,
    non-numeric, non-unit text values among its non-empty cells.

    Args:
        overview_dataframe: The overview worksheet DataFrame.

    Returns:
        The positional index of the best candidate column, or ``None``
        if no column contains suitable text values.
    """
    best_column_index: int | None = None
    best_score = 0

    for position in range(overview_dataframe.shape[1]):
        column_values = overview_dataframe.iloc[:, position].dropna()
        if column_values.empty:
            continue

        text_values = [
            str(value).strip()
            for value in column_values
            if str(value).strip()
            and not _looks_like_number(str(value))
            and not _looks_like_unit(str(value))
        ]

        if len(text_values) < 2:
            continue

        repeated_value_count = len(text_values) - len(set(text_values))
        score = len(text_values) + repeated_value_count

        if score > best_score:
            best_score = score
            best_column_index = position

    return best_column_index


def _looks_like_unit(value: str) -> bool:
    """Check whether a value matches a known engineering unit token.

    Args:
        value: The value to check.

    Returns:
        True if the stripped, lowercased value matches a known unit
        token; False otherwise.
    """
    normalized = value.strip().lower()
    return normalized in UNIT_TOKENS


def _looks_like_number(value: str) -> bool:
    """Check whether a value parses cleanly as a number.

    Args:
        value: The value to check.

    Returns:
        True if the value can be parsed as a float; False otherwise.
    """
    try:
        float(value.strip())
        return True
    except ValueError:
        return False


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


def _validate_dataframe(dataframe: pd.DataFrame) -> None:
    """Validate that the given object is a ``pandas.DataFrame``.

    Args:
        dataframe: The object to validate.

    Raises:
        ValueError: If ``dataframe`` is not a valid ``pandas.DataFrame``.
    """
    if not isinstance(dataframe, pd.DataFrame):
        raise ValueError(
            f"Expected a pandas.DataFrame, got {type(dataframe).__name__}."
        )


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
