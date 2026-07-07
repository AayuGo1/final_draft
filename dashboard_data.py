"""Business layer for the Engineering Monitoring Dashboard.

This module is the single source of truth for interpreting the parsed
workbook produced by ``parser.py``. It discovers, dynamically and
without any hardcoded worksheet/department/meter names or cell
locations, every piece of structural and derived information a
dashboard page needs: departments, flat sections, meters, date columns,
months, dates, latest/average/total values, and workbook-wide metadata.

It performs no rendering, no chart construction, and no workbook
downloading. Those responsibilities belong to ``app.py``/``pages/*``,
``chart_service.py``, and ``dashboard_loader.py`` respectively.

Backward compatibility: every function and dictionary key that existed
in the previous version of this module is preserved with identical
behavior. New keys and helper functions have been added alongside them;
nothing has been renamed or removed.
"""

from __future__ import annotations

import warnings

import pandas as pd

AIR_COMPRESSOR_KEYWORDS: tuple[str, ...] = ("air", "compressor")
"""Keywords used to locate the air compressor worksheet, case-insensitive."""

FREON_KEYWORD: str = "freon"
"""Keyword used to locate the freon worksheet, case-insensitive."""

AMMONIA_KEYWORD: str = "ammonia"
"""Keyword used to locate the ammonia worksheet, case-insensitive."""

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


# ==================================================
# TOP-LEVEL ASSEMBLY
# ==================================================


def get_dashboard_data(workbook: dict[str, pd.DataFrame]) -> dict:
    """Assemble a complete dashboard data model from the parsed workbook.

    This is the single entry point pages should use. It builds every
    section worksheet lookup, the discovered overview structure, a
    dynamically generated navigation list, a KPI-service-ready summary,
    filter options for the UI, and workbook-wide metadata. Nothing here
    is hardcoded: worksheet, department, and meter names are all
    discovered from the workbook contents.

    This is an alias-compatible wrapper around ``build_dashboard`` kept
    for backward compatibility; both return the identical dictionary.

    Args:
        workbook: A dictionary mapping sheet names to cleaned DataFrames,
            as returned by ``parser.read_all_sheets``.

    Returns:
        A dictionary with (at least) the keys ``overview``,
        ``departments``, ``navigation``, ``summary``, ``filters``,
        ``air_compressor``, ``freon``, ``ammonia``, ``metadata``,
        ``sheet_names``, ``sections``, ``months``, ``dates``,
        ``latest_values``, ``totals``, and ``averages``. Existing keys
        used by prior versions of this module are preserved for
        compatibility with ``dashboard_loader.py``, ``kpi_service.py``,
        and ``chart_service.py``.

    Raises:
        ValueError: If ``workbook`` is not a valid, non-empty dictionary
            of DataFrames.
    """
    return build_dashboard(workbook)


def build_dashboard(workbook: dict[str, pd.DataFrame]) -> dict:
    """Assemble the complete, richly-described dashboard data model.

    Args:
        workbook: A dictionary mapping sheet names to cleaned DataFrames,
            as returned by ``parser.read_all_sheets``.

    Returns:
        The full dashboard dictionary. See ``get_dashboard_data`` for the
        documented key set.

    Raises:
        ValueError: If ``workbook`` is not a valid, non-empty dictionary
            of DataFrames.
    """
    _validate_workbook(workbook)

    overview_dataframe = get_overview_dataframe(workbook)
    air_compressor_dataframe = get_air_compressor_data(workbook)
    freon_dataframe = get_freon_data(workbook)
    ammonia_dataframe = get_ammonia_data(workbook)

    overview_structure = get_dashboard_overview(overview_dataframe)
    overview_dashboard = build_overview_dashboard(overview_dataframe)

    air_compressor_dashboard = (
        build_air_compressor_dashboard(air_compressor_dataframe)
        if air_compressor_dataframe is not None
        else None
    )
    freon_dashboard = (
        build_air_compressor_dashboard(freon_dataframe)
        if freon_dataframe is not None
        else None
    )
    ammonia_dashboard = (
        build_air_compressor_dashboard(ammonia_dataframe)
        if ammonia_dataframe is not None
        else None
    )

    sections = {
        "overview": overview_dashboard,
        "air_compressor": air_compressor_dashboard,
        "freon": freon_dashboard,
        "ammonia": ammonia_dashboard,
    }

    navigation = build_navigation(workbook, sections)
    summary = build_summary(overview_structure, overview_dashboard, sections)
    filters = build_filters(overview_structure, overview_dashboard, workbook)
    metadata = build_metadata(workbook, overview_structure, sections)

    department_names = get_department_names(overview_structure)
    section_list = build_section_list(sections)
    months = get_available_months(overview_dataframe)
    dates = get_available_dates(overview_dataframe)
    latest_values = get_latest_values(overview_dashboard)
    totals = get_total_values(overview_dashboard)
    averages = get_average_values(overview_dashboard)

    return {
        # -------- existing keys (backward compatible) --------
        "overview": overview_dataframe,
        "departments": get_department_data(workbook),
        "navigation": navigation,
        "summary": summary,
        "filters": filters,
        "air_compressor": air_compressor_dataframe,
        "freon": freon_dataframe,
        "ammonia": ammonia_dataframe,
        "sheet_names": get_sheet_names(workbook),
        "metadata": metadata,
        # -------- richer additions --------
        "sections": section_list,
        "months": months,
        "dates": dates,
        "latest_values": latest_values,
        "totals": totals,
        "averages": averages,
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


def get_ammonia_data(workbook: dict[str, pd.DataFrame]) -> pd.DataFrame | None:
    """Find the worksheet related to ammonia monitoring.

    Searches all sheet names, case-insensitively, for "ammonia".

    Args:
        workbook: A dictionary mapping sheet names to cleaned DataFrames.

    Returns:
        The matching DataFrame, or ``None`` if no worksheet matches.

    Raises:
        ValueError: If ``workbook`` is not a valid, non-empty dictionary
            of DataFrames.
    """
    _validate_workbook(workbook)
    return _find_sheet_by_keywords(workbook, (AMMONIA_KEYWORD,))


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


def get_department_names(overview_structure: dict) -> list[str]:
    """Return the discovered department names from an overview structure.

    Thin, single-responsibility accessor kept separate from
    ``get_available_departments`` so callers that already hold a built
    ``overview_structure`` (from ``get_dashboard_overview``) don't need
    to re-scan the DataFrame.

    Args:
        overview_structure: The dictionary returned by
            ``get_dashboard_overview``.

    Returns:
        The list of discovered department names, in workbook order.
    """
    return list(overview_structure.get("departments", []))


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


def get_available_dates(overview_dataframe: pd.DataFrame) -> list[str]:
    """Discover every distinct date value present in date-like columns.

    Args:
        overview_dataframe: The overview worksheet DataFrame.

    Returns:
        A sorted, de-duplicated list of date strings (``"YYYY-MM-DD"``)
        found across all discovered date columns. Returns an empty list
        if no date columns or values could be discovered.

    Raises:
        ValueError: If ``overview_dataframe`` is not a valid
            ``pandas.DataFrame``.
    """
    _validate_dataframe(overview_dataframe)

    date_columns = get_date_columns(overview_dataframe)
    if not date_columns:
        return []

    discovered_dates: set[str] = set()

    for column_index in date_columns:
        column_values = overview_dataframe.iloc[:, column_index].dropna()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            parsed = pd.to_datetime(column_values, errors="coerce").dropna()

        for value in parsed:
            discovered_dates.add(value.strftime("%Y-%m-%d"))

    return sorted(discovered_dates)


def get_available_months(overview_dataframe: pd.DataFrame) -> list[str]:
    """Discover every distinct calendar month present in date-like columns.

    Args:
        overview_dataframe: The overview worksheet DataFrame.

    Returns:
        A sorted, de-duplicated list of month strings (``"YYYY-MM"``)
        found across all discovered date columns. Returns an empty list
        if no date columns or values could be discovered.

    Raises:
        ValueError: If ``overview_dataframe`` is not a valid
            ``pandas.DataFrame``.
    """
    _validate_dataframe(overview_dataframe)

    dates = get_available_dates(overview_dataframe)
    if not dates:
        return []

    months = sorted({date[:7] for date in dates})
    return months


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


def get_department_meter_structure(
    overview_dataframe: pd.DataFrame,
) -> dict[str, dict[str, pd.Series]]:
    """Build a nested department-to-meter data structure from the overview sheet.

    The first row of the worksheet is treated as the department / equipment
    group header (with merged cells forward-filled to reconstruct the
    group each meter belongs to), the second row is treated as the
    individual meter / panel name, and all rows from the third onward are
    treated as daily readings. Columns with no department label, no meter
    label, or that are entirely empty are treated as metadata or spacer
    columns and are ignored. Workbook order is preserved for both
    departments and meters within each department.

    Args:
        overview_dataframe: The overview worksheet DataFrame, as returned
            by ``parser.read_sheet`` / ``parser.read_all_sheets``.

    Returns:
        A nested dictionary of the form
        ``{department_name: {meter_name: pandas.Series}}``, where each
        ``pandas.Series`` holds the daily readings for that meter.

    Raises:
        ValueError: If ``overview_dataframe`` is not a valid
            ``pandas.DataFrame``, or does not contain at least a
            department row, a meter row, and one row of readings.
    """
    _validate_dataframe(overview_dataframe)

    if overview_dataframe.shape[0] < 3:
        raise ValueError(
            "The overview worksheet must contain at least three rows: a "
            "department header row, a meter header row, and one row of "
            "readings."
        )

    department_row = overview_dataframe.iloc[0].ffill()
    meter_row = overview_dataframe.iloc[1]
    readings = overview_dataframe.iloc[2:].reset_index(drop=True)

    structure: dict[str, dict[str, pd.Series]] = {}

    for position in range(overview_dataframe.shape[1]):
        department_value = department_row.iloc[position]
        meter_value = meter_row.iloc[position]

        department_name = _clean_label(department_value)
        meter_name = _clean_label(meter_value)

        if not department_name or not meter_name:
            continue

        meter_series = readings.iloc[:, position]
        if meter_series.dropna().empty:
            continue

        department_meters = structure.setdefault(department_name, {})
        department_meters[meter_name] = meter_series

    return structure


def _clean_label(value: object) -> str:
    """Normalize a header cell value into a clean, non-empty label or "".

    Args:
        value: The raw header cell value.

    Returns:
        The stripped string representation of the value, or an empty
        string if the value is null or blank.
    """
    if pd.isna(value):
        return ""

    return str(value).strip()


def build_overview_dashboard(overview_dataframe: pd.DataFrame) -> dict:
    """Build real dashboard-ready data for every discovered department section.

    Uses ``get_department_meter_structure`` to discover the department and
    meter hierarchy, then assembles, for every department, the meter list,
    latest available reading per meter, and a combined DataFrame (one
    column per meter) ready for rendering. No engineering KPI values are
    calculated here.

    Args:
        overview_dataframe: The overview worksheet DataFrame, as returned
            by ``parser.read_sheet`` / ``parser.read_all_sheets``.

    Returns:
        A dictionary of the form
        ``{"sections": [{"name": ..., "meters": ..., "latest_values": ...,
        "dataframe": ...}]}``, with one entry per discovered department, in
        workbook order.

    Raises:
        ValueError: If ``overview_dataframe`` is not a valid
            ``pandas.DataFrame``, or does not contain a department row, a
            meter row, and at least one row of readings.
    """
    _validate_dataframe(overview_dataframe)

    department_structure = get_department_meter_structure(overview_dataframe)

    sections = [
        {
            "name": department_name,
            "meters": list(meters.keys()),
            "latest_values": _get_latest_values(meters),
            "totals": _get_total_values(meters),
            "averages": _get_average_values(meters),
            "dataframe": _build_meters_dataframe(meters),
        }
        for department_name, meters in department_structure.items()
    ]

    return {"sections": sections}


def get_air_compressor_meter_structure(
    air_compressor_dataframe: pd.DataFrame,
) -> dict[str, dict[str, object]]:
    """Discover the per-meter structure of the air compressor worksheet.

    Unlike the main overview worksheet, the air compressor sheet is
    treated as a single, flat section (no department grouping row). The
    first row is treated as the meter / parameter header. A unit row is
    then located dynamically anywhere in the sheet using
    ``get_unit_row``; if found, everything from the row immediately after
    it onward is treated as daily readings and the unit row itself
    supplies each meter's unit label. If no unit row can be identified,
    all rows after the header are treated as readings and units are left
    as an empty string. Columns with no header label or with entirely
    empty readings are treated as metadata or spacer columns and are
    ignored. Workbook column order is preserved.

    Args:
        air_compressor_dataframe: The air compressor worksheet DataFrame,
            as returned by ``get_air_compressor_data``.

    Returns:
        A dictionary of the form
        ``{meter_name: {"unit": str, "readings": pandas.Series}}``, in
        workbook column order.

    Raises:
        ValueError: If ``air_compressor_dataframe`` is not a valid
            ``pandas.DataFrame``, or does not contain at least a header
            row and one row of readings.
    """
    _validate_dataframe(air_compressor_dataframe)

    if air_compressor_dataframe.shape[0] < 2:
        raise ValueError(
            "The air compressor worksheet must contain at least two "
            "rows: a meter header row and one row of readings."
        )

    header_row = air_compressor_dataframe.iloc[0]
    unit_row_index = get_unit_row(air_compressor_dataframe)

    if unit_row_index is not None and unit_row_index > 0:
        units_row = air_compressor_dataframe.iloc[unit_row_index]
        data_start_row = unit_row_index + 1
    else:
        units_row = None
        data_start_row = 1

    readings_block = air_compressor_dataframe.iloc[data_start_row:].reset_index(
        drop=True
    )

    structure: dict[str, dict[str, object]] = {}

    for position in range(air_compressor_dataframe.shape[1]):
        meter_name = _clean_label(header_row.iloc[position])
        if not meter_name:
            continue

        meter_series = readings_block.iloc[:, position]
        if meter_series.dropna().empty:
            continue

        unit_label = (
            _clean_label(units_row.iloc[position]) if units_row is not None else ""
        )

        structure[meter_name] = {"unit": unit_label, "readings": meter_series}

    return structure


def build_air_compressor_dashboard(air_compressor_dataframe: pd.DataFrame) -> dict:
    """Build dashboard-ready data for a flat, single-section worksheet.

    Despite the name, this builder is generic and is reused for any
    flat (non department-grouped) worksheet, such as air compressor,
    freon, or ammonia monitoring sheets. Discovers every available metric
    via ``get_air_compressor_meter_structure`` and assembles, for each
    metric, its unit, its latest available reading (for KPI cards), and
    its full reading history (for charts), plus a single combined
    DataFrame with one column per metric. No engineering KPI values are
    calculated here beyond surfacing the latest raw reading already
    present in the workbook.

    Args:
        air_compressor_dataframe: The flat worksheet DataFrame, as
            returned by ``get_air_compressor_data``, ``get_freon_data``,
            or ``get_ammonia_data``.

    Returns:
        A dictionary of the form::

            {
                "metrics": [
                    {
                        "name": str,
                        "unit": str,
                        "latest_value": object | None,
                        "readings": pandas.Series,
                    },
                    ...
                ],
                "dataframe": pandas.DataFrame,
                "date_columns": list[int],
            }

        ``metrics`` preserves workbook column order. ``dataframe`` has one
        column per discovered metric, ready for charting. ``date_columns``
        lists the positional indexes of any date-like columns discovered
        on the worksheet.

    Raises:
        ValueError: If ``air_compressor_dataframe`` is not a valid
            ``pandas.DataFrame``, or does not contain at least a header
            row and one row of readings.
    """
    _validate_dataframe(air_compressor_dataframe)

    meter_structure = get_air_compressor_meter_structure(air_compressor_dataframe)

    metrics = []
    readings_by_name: dict[str, pd.Series] = {}

    for meter_name, info in meter_structure.items():
        series = info["readings"]
        non_null_values = series.dropna()
        latest_value = (
            non_null_values.iloc[-1] if not non_null_values.empty else None
        )

        metrics.append(
            {
                "name": meter_name,
                "unit": info["unit"],
                "latest_value": latest_value,
                "readings": series,
            }
        )
        readings_by_name[meter_name] = series

    return {
        "metrics": metrics,
        "dataframe": _build_meters_dataframe(readings_by_name),
        "date_columns": get_date_columns(air_compressor_dataframe),
    }


def get_air_compressor_dashboard(workbook: dict[str, pd.DataFrame]) -> dict | None:
    """Locate the air compressor worksheet and build its dashboard data.

    Convenience wrapper that combines ``get_air_compressor_data`` and
    ``build_air_compressor_dashboard`` so pages can go straight from the
    parsed workbook to a render-ready structure in a single call.

    Args:
        workbook: A dictionary mapping sheet names to cleaned DataFrames.

    Returns:
        The dashboard-ready dictionary produced by
        ``build_air_compressor_dashboard``, or ``None`` if no air
        compressor worksheet was found in the workbook.

    Raises:
        ValueError: If ``workbook`` is not a valid, non-empty dictionary
            of DataFrames.
    """
    _validate_workbook(workbook)

    air_compressor_dataframe = get_air_compressor_data(workbook)
    if air_compressor_dataframe is None:
        return None

    return build_air_compressor_dashboard(air_compressor_dataframe)


# ==================================================
# SECTION / VALUE DISCOVERY HELPERS (NEW)
# ==================================================


def build_section_list(sections: dict[str, dict | None]) -> list[dict]:
    """Build a flat, UI-ready list describing every discovered section.

    Args:
        sections: A mapping of section key to its built dashboard data
            (or ``None`` if that section's worksheet was not found).

    Returns:
        A list of dictionaries, each with keys ``key``, ``label``, and
        ``available``, in the same stable order as ``sections``.
    """
    return [
        {
            "key": section_key,
            "label": section_key.replace("_", " ").title(),
            "available": section_data is not None,
        }
        for section_key, section_data in sections.items()
    ]


def find_section_by_keyword(
    sections: list[dict],
    keyword: str,
) -> dict | None:
    """Find a discovered section whose name contains the given keyword.

    Args:
        sections: A list of section-like dictionaries, each expected to
            have a ``"name"`` key (for example, the ``"sections"`` list
            inside ``build_overview_dashboard``'s return value).
        keyword: The keyword to search for, matched case-insensitively.

    Returns:
        The first matching section dictionary, or ``None`` if no section
        name contains the keyword.
    """
    keyword = keyword.lower()

    return next(
        (
            section
            for section in sections
            if keyword in section["name"].lower()
        ),
        None,
    )


def get_latest_values(overview_dashboard: dict) -> dict[str, dict[str, object]]:
    """Get the latest reading for every meter, grouped by department.

    Args:
        overview_dashboard: The dictionary returned by
            ``build_overview_dashboard``.

    Returns:
        A dictionary mapping each department name to a dictionary of
        ``{meter_name: latest_value}``.
    """
    return {
        section["name"]: section.get("latest_values", {})
        for section in overview_dashboard.get("sections", [])
    }


def get_total_values(overview_dashboard: dict) -> dict[str, dict[str, object]]:
    """Get the sum of all readings for every meter, grouped by department.

    Args:
        overview_dashboard: The dictionary returned by
            ``build_overview_dashboard``.

    Returns:
        A dictionary mapping each department name to a dictionary of
        ``{meter_name: total_value}``.
    """
    return {
        section["name"]: section.get("totals", {})
        for section in overview_dashboard.get("sections", [])
    }


def get_average_values(overview_dashboard: dict) -> dict[str, dict[str, object]]:
    """Get the average of all readings for every meter, grouped by department.

    Args:
        overview_dashboard: The dictionary returned by
            ``build_overview_dashboard``.

    Returns:
        A dictionary mapping each department name to a dictionary of
        ``{meter_name: average_value}``.
    """
    return {
        section["name"]: section.get("averages", {})
        for section in overview_dashboard.get("sections", [])
    }


def _get_latest_values(meters: dict[str, pd.Series]) -> dict[str, object]:
    """Get the most recent non-null reading for every meter.

    Args:
        meters: A mapping of meter name to its readings ``pandas.Series``.

    Returns:
        A dictionary mapping each meter name to its latest non-null
        reading, or ``None`` if the meter has no available readings.
    """
    latest_values: dict[str, object] = {}

    for meter_name, series in meters.items():
        non_null_values = series.dropna()
        latest_values[meter_name] = (
            non_null_values.iloc[-1] if not non_null_values.empty else None
        )

    return latest_values


def _get_total_values(meters: dict[str, pd.Series]) -> dict[str, object]:
    """Get the sum of all numeric, non-null readings for every meter.

    Args:
        meters: A mapping of meter name to its readings ``pandas.Series``.

    Returns:
        A dictionary mapping each meter name to the sum of its numeric
        readings, or ``None`` if the meter has no numeric readings.
    """
    total_values: dict[str, object] = {}

    for meter_name, series in meters.items():
        numeric_values = pd.to_numeric(series.dropna(), errors="coerce").dropna()
        total_values[meter_name] = (
            float(numeric_values.sum()) if not numeric_values.empty else None
        )

    return total_values


def _get_average_values(meters: dict[str, pd.Series]) -> dict[str, object]:
    """Get the mean of all numeric, non-null readings for every meter.

    Args:
        meters: A mapping of meter name to its readings ``pandas.Series``.

    Returns:
        A dictionary mapping each meter name to the mean of its numeric
        readings, or ``None`` if the meter has no numeric readings.
    """
    average_values: dict[str, object] = {}

    for meter_name, series in meters.items():
        numeric_values = pd.to_numeric(series.dropna(), errors="coerce").dropna()
        average_values[meter_name] = (
            float(numeric_values.mean()) if not numeric_values.empty else None
        )

    return average_values


# ==================================================
# NAVIGATION / SUMMARY / FILTERS / METADATA
# ==================================================


def build_navigation(
    workbook: dict[str, pd.DataFrame], sections: dict[str, dict | None]
) -> list[dict]:
    """Dynamically generate the dashboard's navigation list.

    One navigation entry is produced per discovered, non-empty section
    (``overview`` plus any flat worksheet section such as air compressor,
    freon, or ammonia that was actually found in the workbook). No page
    names or worksheet names are hardcoded beyond the label used to
    describe well-known section keys; entries are only ever included if
    the corresponding worksheet was discovered in this workbook.

    Args:
        workbook: A dictionary mapping sheet names to cleaned DataFrames.
        sections: A mapping of section key to its built dashboard data
            (or ``None`` if that section's worksheet was not found).

    Returns:
        A list of dictionaries, each with keys ``key``, ``label``, and
        ``available``, in a stable, discovery-driven order.

    Raises:
        ValueError: If ``workbook`` is not a valid, non-empty dictionary
            of DataFrames.
    """
    _validate_workbook(workbook)
    return build_section_list(sections)


def build_summary(
    overview_structure: dict,
    overview_dashboard: dict,
    sections: dict[str, dict | None],
) -> dict:
    """Assemble reusable summary information for KPI services.

    No engineering KPI calculation happens here; this only surfaces raw,
    already-discovered counts and values that ``kpi_service.py`` can
    combine into actual KPIs.

    Args:
        overview_structure: The dictionary returned by
            ``get_dashboard_overview``.
        overview_dashboard: The dictionary returned by
            ``build_overview_dashboard``.
        sections: A mapping of section key to its built dashboard data
            (or ``None`` if not found).

    Returns:
        A dictionary with keys ``department_count``, ``meter_count``,
        ``available_sections`` (backward-compatible), plus the richer
        ``latest_values_by_department`` (backward-compatible alias),
        ``latest_timestamp``, ``last_updated``,
        ``department_latest_values``, ``department_totals``,
        ``department_averages``, ``available_sheets``, and
        ``data_availability``.
    """
    department_sections = overview_dashboard.get("sections", [])

    meter_count = sum(len(section["meters"]) for section in department_sections)

    latest_values_by_department = {
        section["name"]: section["latest_values"] for section in department_sections
    }
    department_totals = {
        section["name"]: section.get("totals", {}) for section in department_sections
    }
    department_averages = {
        section["name"]: section.get("averages", {})
        for section in department_sections
    }

    available_sections = [
        section_key for section_key, section_data in sections.items()
        if section_data is not None
    ]

    overview_dataframe_shape = overview_structure.get("shape", (0, 0))
    total_rows, total_columns = overview_dataframe_shape
    total_cells = total_rows * total_columns

    populated_cells = sum(
        len(series.dropna())
        for section in department_sections
        for series in [section.get("dataframe")]
        if series is not None
    )
    data_availability = (
        min(populated_cells / total_cells, 1.0) if total_cells else 0.0
    )

    latest_timestamp = _get_latest_timestamp_from_sections(department_sections)

    return {
        # -------- existing keys (backward compatible) --------
        "department_count": len(overview_structure.get("departments", [])),
        "meter_count": meter_count,
        "available_sections": available_sections,
        "latest_values_by_department": latest_values_by_department,
        # -------- richer additions --------
        "latest_timestamp": latest_timestamp,
        "last_updated": latest_timestamp,
        "department_latest_values": latest_values_by_department,
        "department_totals": department_totals,
        "department_averages": department_averages,
        "available_sheets": available_sections,
        "data_availability": data_availability,
    }


def _get_latest_timestamp_from_sections(department_sections: list[dict]) -> str:
    """Find the most recent timestamp across every department's dataframe.

    Args:
        department_sections: The ``"sections"`` list produced by
            ``build_overview_dashboard``.

    Returns:
        The most recent date-like value found across all department
        dataframes, formatted as a string, or ``"N/A"`` if none was
        found.
    """
    latest_candidates: list[pd.Timestamp] = []

    for section in department_sections:
        dataframe = section.get("dataframe")
        if dataframe is None or dataframe.empty:
            continue

        date_columns = get_date_columns(dataframe)
        for column_index in date_columns:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                parsed = pd.to_datetime(
                    dataframe.iloc[:, column_index].dropna(), errors="coerce"
                ).dropna()
            if not parsed.empty:
                latest_candidates.append(parsed.max())

    if not latest_candidates:
        return "N/A"

    return str(max(latest_candidates))


def build_filters(
    overview_structure: dict,
    overview_dashboard: dict,
    workbook: dict[str, pd.DataFrame] | None = None,
) -> dict:
    """Assemble discovered filter options for the UI layer.

    Args:
        overview_structure: The dictionary returned by
            ``get_dashboard_overview``.
        overview_dashboard: The dictionary returned by
            ``build_overview_dashboard``.
        workbook: An optional workbook mapping, used to discover
            available flat sections (air compressor / freon / ammonia)
            for the ``"sections"`` filter. If omitted, ``"sections"`` is
            returned as an empty list for backward compatibility.

    Returns:
        A dictionary with keys ``departments`` (discovered department
        names), ``meters`` (all discovered meter names across
        departments, in discovery order, without duplicates),
        ``date_columns`` (positional indexes of discovered date
        columns), ``months``, ``dates``, and ``sections``.
    """
    departments = overview_structure.get("departments", [])

    meters: list[str] = []
    for section in overview_dashboard.get("sections", []):
        for meter_name in section["meters"]:
            if meter_name not in meters:
                meters.append(meter_name)

    section_names: list[str] = []
    if workbook is not None:
        overview_dataframe = get_overview_dataframe(workbook)
        section_names = [
            entry["label"]
            for entry in build_section_list(
                {
                    "overview": overview_dashboard,
                    "air_compressor": get_air_compressor_data(workbook),
                    "freon": get_freon_data(workbook),
                    "ammonia": get_ammonia_data(workbook),
                }
            )
            if entry["available"]
        ]
        months = get_available_months(overview_dataframe)
        dates = get_available_dates(overview_dataframe)
    else:
        months = []
        dates = []

    return {
        "departments": departments,
        "meters": meters,
        "date_columns": overview_structure.get("date_columns", []),
        "months": months,
        "dates": dates,
        "sections": section_names,
    }


def build_metadata(
    workbook: dict[str, pd.DataFrame],
    overview_structure: dict,
    sections: dict[str, dict | None],
) -> dict:
    """Assemble workbook-wide metadata describing what was discovered.

    Args:
        workbook: A dictionary mapping sheet names to cleaned DataFrames.
        overview_structure: The dictionary returned by
            ``get_dashboard_overview``.
        sections: A mapping of section key to its built dashboard data
            (or ``None`` if not found).

    Returns:
        A dictionary with keys ``sheet_names``, ``departments``,
        ``meters``, ``date_columns``, and ``available_sections``
        (backward compatible), plus ``sheet_count``, ``months``,
        ``month_range``, ``dates``, ``date_range``, and
        ``workbook_version``.
    """
    meters: list[str] = []
    for section in sections.get("overview", {}).get("sections", []) if sections.get("overview") else []:
        for meter_name in section["meters"]:
            if meter_name not in meters:
                meters.append(meter_name)

    available_sections = [
        section_key for section_key, section_data in sections.items()
        if section_data is not None
    ]

    overview_dataframe = get_overview_dataframe(workbook)
    months = get_available_months(overview_dataframe)
    dates = get_available_dates(overview_dataframe)

    month_range = (months[0], months[-1]) if months else (None, None)
    date_range = (dates[0], dates[-1]) if dates else (None, None)

    sheet_names = get_sheet_names(workbook)

    return {
        # -------- existing keys (backward compatible) --------
        "sheet_names": sheet_names,
        "departments": overview_structure.get("departments", []),
        "meters": meters,
        "date_columns": overview_structure.get("date_columns", []),
        "available_sections": available_sections,
        # -------- richer additions --------
        "sheet_count": len(sheet_names),
        "months": months,
        "month_range": month_range,
        "dates": dates,
        "date_range": date_range,
        "workbook_version": _discover_workbook_version(workbook),
    }


def _discover_workbook_version(workbook: dict[str, pd.DataFrame]) -> str | None:
    """Best-effort discovery of a workbook version, without any hardcoding.

    Scans the overview worksheet's non-numeric cells for a value that
    looks like a version token (for example ``"v1.2"`` or ``"Rev 3"``),
    since no fixed cell location can be assumed. This is purely
    best-effort metadata and never raises if nothing is found.

    Args:
        workbook: A dictionary mapping sheet names to cleaned DataFrames.

    Returns:
        The first plausible version-like string found, or ``None`` if
        no such value is discovered.
    """
    overview_dataframe = get_overview_dataframe(workbook)

    for _, row_values in overview_dataframe.iterrows():
        for value in row_values.dropna():
            text = str(value).strip().lower()
            if text.startswith("v") and any(character.isdigit() for character in text):
                return str(value).strip()
            if text.startswith("rev") and any(character.isdigit() for character in text):
                return str(value).strip()

    return None


def _build_meters_dataframe(meters: dict[str, pd.Series]) -> pd.DataFrame:
    """Combine every meter's readings into a single DataFrame.

    Each column represents one meter and each row represents one
    observation. Used for both department sections and single-section
    worksheets such as the air compressor sheet.

    Args:
        meters: A mapping of meter name to its readings ``pandas.Series``.

    Returns:
        A DataFrame with one column per meter, built via ``pd.concat``.
        Returns an empty DataFrame if there are no meters.
    """
    if not meters:
        return pd.DataFrame()

    series_list = [series.rename(name) for name, series in meters.items()]
    return pd.concat(series_list, axis=1)


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
