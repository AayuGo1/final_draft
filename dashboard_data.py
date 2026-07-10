"""Business layer for the Engineering Monitoring Dashboard.

This module acts as the single source of truth for interpreting the parsed
workbook produced by ``parser.py``. It enforces a rigid, high-performance
engineering layout mapped directly to the static column boundaries DH to GH
on the primary overview worksheet.

Dependency direction (STRICTLY one-way):

    data_loader ─┐
    parser ──────┼─▶ services.dashboard_loader ─▶ dashboard_data ─▶ chart_service ─▶ app
                 ┘

This module is the data layer. It must depend ONLY on the standard library
and third-party packages (pandas). It must NEVER import
``services.dashboard_loader`` (or ``parser`` / ``data_loader``): the loader
orchestrates this module, not the reverse. Importing the loader here creates a
``dashboard_loader ↔ dashboard_data`` cycle that breaks application start-up.
Keep this module free of any upstream import.
"""

from __future__ import annotations

import datetime
import logging
import re
import warnings
from typing import Any, Final

import pandas as pd

# Diagnostics-only logging. This module keeps its strict "no upstream imports"
# rule (it must not import app / loader), so it configures its own module logger
# rather than sharing app.py's. Logging here is purely for tracing where a
# native crash (e.g. a Streamlit Cloud segmentation fault, which produces no
# Python traceback) happens. It never logs cell values — only structural
# metadata — and never alters any calculation or return value.
logger = logging.getLogger(__name__)


def _df_meta(df: Any) -> str:
    """Return a safe, data-free description of a DataFrame/Series for diagnostics.

    Reports ONLY structural metadata — shape, row/column counts, approximate
    memory usage — never any cell values. Introspection failures are swallowed so
    diagnostics can never crash the pipeline.
    """
    try:
        if isinstance(df, pd.DataFrame):
            rows, cols = df.shape
            try:
                mem = f"{int(df.memory_usage(deep=True).sum()) / 1024:.1f} KB"
            except Exception:
                mem = "n/a"
            return f"shape=({rows},{cols}) rows={rows} cols={cols} mem={mem}"
        if isinstance(df, pd.Series):
            try:
                mem = f"{int(df.memory_usage(deep=True)) / 1024:.1f} KB"
            except Exception:
                mem = "n/a"
            return f"series len={len(df)} mem={mem}"
        if df is None:
            return "None"
        return f"type={type(df).__name__}"
    except Exception as exc:
        return f"<meta unavailable: {type(exc).__name__}>"


def _log_step(message: str) -> None:
    """Emit a diagnostic step marker (flushed immediately).

    Flushing matters: a native segfault can kill the process before buffered log
    lines reach the console, so each marker is pushed out right away.
    """
    try:
        logger.info(message)
        for handler in logging.getLogger().handlers:
            try:
                handler.flush()
            except Exception:
                pass
    except Exception:
        pass


# ==============================================================================
# PRODUCTION CONSTANTS & SPECIFICATIONS
# ==============================================================================

# The engineering telemetry block is discovered dynamically from the parsed
# worksheet structure rather than pinned to fixed spreadsheet column letters,
# so the dashboard keeps working if the block shifts horizontally in future
# workbook revisions. The block is identified by its structural signature: a
# column whose meter-header (row 1) is a date label AND whose immediately
# following column carries a known department name (row 0). The block then runs
# from that column to the last populated column. See ``_discover_engineering_block``.
DATE_HEADER_TOKENS: Final[set[str]] = {"date", "start time", "timestamp", "datetime"}

EXPECTED_DEPARTMENTS: Final[set[str]] = {
    "NPCL", "Overall PNG", "Dough", "Traywasher", "Popeyes", "Warehouse",
    "Transport", "Admin", "BMC", "New CK", "Old CK", "UPS", "CLC", "WTP",
    "ETP", "RO Plant", "EHS", "Utility", "Freon Refrigeration",
    "Ammonia Refrigeration", "Air compressor", "Rooftop Solar", "Engineering",
    "B2B", "Bread", "Donut", "Silo", "DG", "GG"
}

# Precomputed case/whitespace-insensitive view of the known department names,
# used for structural block discovery and robust aggregate matching. Built via
# a lightweight inline normalization (module-load time) so it never depends on
# exact capitalization or spacing in the workbook.
_EXPECTED_DEPARTMENTS_NORM: Final[set[str]] = {
    " ".join(str(name).strip().lower().split()) for name in EXPECTED_DEPARTMENTS
}

MIN_VALID_YEAR: Final[int] = 2020
MAX_VALID_YEAR: Final[int] = 2035

UNIT_TOKENS: Final[set[str]] = {
    "kwh", "kw", "kva", "kl", "l", "ml", "kg", "mt", "ton", "%", "°c", "c",
    "bar", "psi", "m3", "nm3", "hp", "ppm", "db", "hz", "rpm", "hrs", "hr",
    "units", "no.", "nos", "m³/hr", "kg/hr", "v", "a", "pf", "kw/tr", "tr"
}

REPRESENTATIVE_METER_PRIORITIES: Final[list[list[str]]] = [
    ["energy", "consumption", "electricity", "power", "kwh", "kw", "load"],
    ["flow", "png", "water", "steam", "air"],
    ["pressure", "bar", "psi"],
    ["voltage", "current", "frequency"],
]

# Name of the department whose meters are collapsed into a single synthetic
# aggregate channel (row-wise sum, missing treated as zero). The department is
# discovered dynamically by the parser; nothing about its column position is
# assumed here.
AGGREGATE_PNG_DEPARTMENT: Final[str] = "Overall PNG"

# Freon Refrigeration draws its subsection meters from a dedicated worksheet
# ("Freon Meter reading") rather than the engineering overview block. The
# worksheet is discovered by keyword (already available in the assembled
# dashboard as ``dashboard["freon"]``); meters are discovered dynamically from
# its header, never hardcoded. Only this department is affected.
FREON_DEPARTMENT: Final[str] = "Freon Refrigeration"
FREON_SHEET_KEYWORDS: Final[tuple[str, ...]] = ("freon",)

# ==============================================================================
# TOP-LEVEL APPLICATION ASSEMBLY INTERFACES
# ==============================================================================

def get_dashboard_data(workbook: dict[str, pd.DataFrame], start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
    _log_step(f"get_dashboard_data: ENTER start_date={start_date} end_date={end_date} sheets={list(workbook.keys()) if isinstance(workbook, dict) else type(workbook).__name__}")
    if isinstance(workbook, dict):
        for _sheet_name, _sheet_df in workbook.items():
            _log_step(f"  workbook sheet '{_sheet_name}': {_df_meta(_sheet_df)}")
    result = build_dashboard(workbook, start_date, end_date)
    _log_step("get_dashboard_data: EXIT")
    return result

def _is_valid_date_string(val: Any) -> bool:
    if pd.isna(val) or val is None: return False
    dt = None
    try:
        if isinstance(val, (datetime.datetime, datetime.date)):
            dt = val
        else:
            cleaned_str = str(val).strip().split()[0]
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
                try:
                    dt = datetime.datetime.strptime(cleaned_str, fmt)
                    break
                except ValueError:
                    continue
        if dt and MIN_VALID_YEAR <= dt.year <= MAX_VALID_YEAR:
            return True
    except Exception:
        pass
    return False

def _get_date_object(val: Any) -> datetime.date | None:
    if pd.isna(val) or val is None: return None
    dt = None
    try:
        if isinstance(val, (datetime.datetime, datetime.date)):
            dt = val
        else:
            cleaned_str = str(val).strip().split()[0]
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
                try:
                    dt = datetime.datetime.strptime(cleaned_str, fmt)
                    break
                except ValueError:
                    continue
        if dt and MIN_VALID_YEAR <= dt.year <= MAX_VALID_YEAR:
            return dt.date() if isinstance(dt, datetime.datetime) else dt
    except Exception:
        pass
    return None

def _get_date_string(val: Any) -> str | None:
    d = _get_date_object(val)
    if d: return d.strftime("%Y-%m-%d")
    return None

def _normalize_date_series(primary_df: pd.DataFrame, readings_matrix: pd.DataFrame) -> pd.Series:
    """Build one normalized ``pd.Timestamp`` date series aligned to the readings.

    Requirement: convert every workbook date to ``pandas.Timestamp`` **once** and
    reuse it for all filtering, so comparisons never mix ``datetime.date``,
    ``datetime.datetime`` and ``str`` values. The raw date column (column index
    1 of the primary worksheet) is selected positionally for exactly the rows of
    ``readings_matrix`` and re-indexed onto ``readings_matrix``'s own index, so
    the returned series is guaranteed to align 1:1 with the readings. Values that
    cannot be parsed, or that fall outside the valid year window, become ``NaT``.

    Args:
        primary_df: The cleaned primary worksheet.
        readings_matrix: The engineering readings rows (index defines alignment).

    Returns:
        A ``pd.Series`` of ``pd.Timestamp``/``NaT`` indexed like
        ``readings_matrix`` (same length, same index).
    """
    n = len(readings_matrix)
    # Positionally take the date column for just the readings rows, then re-index
    # onto the readings' own index so downstream boolean masks align exactly.
    if primary_df.shape[1] > 1 and n > 0:
        raw = primary_df.iloc[:, 1].to_numpy()
        # readings_matrix occupies the rows after the two header rows; take the
        # last ``n`` date cells positionally to match it 1:1.
        raw_slice = raw[-n:] if len(raw) >= n else raw
    else:
        raw_slice = []

    normalized: list[pd.Timestamp | Any] = []
    for val in raw_slice:
        d = _get_date_object(val)  # datetime.date | None, already year-validated
        normalized.append(pd.Timestamp(d) if d is not None else pd.NaT)

    # Pad/truncate defensively so the series length always equals n.
    if len(normalized) < n:
        normalized = normalized + [pd.NaT] * (n - len(normalized))
    elif len(normalized) > n:
        normalized = normalized[:n]

    return pd.Series(normalized, index=readings_matrix.index, dtype="datetime64[ns]")


def _resolve_date_bounds(
    start_date: str | None, end_date: str | None
) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Normalize selected date bounds to ``pd.Timestamp`` and fix a reversed range.

    Shared by every date filter (engineering block and the Freon worksheet) so
    the swap + Timestamp-conversion rule is defined exactly once. Returns
    ``(start_ts, end_ts)`` where either may be ``None``; if both are present and
    reversed they are swapped so the range is always well-formed.
    """
    start_ts = pd.Timestamp(start_date) if start_date else None
    end_ts = pd.Timestamp(end_date) if end_date else None
    if start_ts is not None and end_ts is not None and end_ts < start_ts:
        start_ts, end_ts = end_ts, start_ts
    return start_ts, end_ts


def _apply_date_range_to_mask(
    mask: pd.Series, normalized_dates: pd.Series, start_date: str | None, end_date: str | None
) -> pd.Series:
    """Restrict a boolean row mask to an inclusive [start, end] Timestamp range.

    ``normalized_dates`` must already be a ``pd.Timestamp``/``NaT`` series aligned
    to ``mask``. All comparisons are Timestamp-vs-Timestamp (never strings). This
    is the single implementation of the range test, used only by the one
    centralized filter below.
    """
    if not (start_date or end_date):
        return mask
    start_ts, end_ts = _resolve_date_bounds(start_date, end_date)
    if start_ts is not None:
        mask = mask & (normalized_dates >= start_ts)
    if end_ts is not None:
        mask = mask & (normalized_dates <= end_ts)
    return mask


def _normalize_timestamp_column(dataframe: pd.DataFrame, timestamp_column: Any, positional: bool) -> pd.Series:
    """Return a ``pd.Timestamp``/``NaT`` series for the given timestamp column.

    The column is selected by position (``positional=True``) or by label, then
    each cell is parsed via ``_get_date_object`` (mixed formats handled, values
    outside the valid-year window or unparseable become ``NaT``). The result is
    index-aligned 1:1 to ``dataframe``'s rows.
    """
    if positional:
        raw = dataframe.iloc[:, timestamp_column]
    else:
        raw = dataframe[timestamp_column]
    return pd.Series(
        [pd.Timestamp(d) if (d := _get_date_object(v)) is not None else pd.NaT for v in raw],
        index=dataframe.index,
        dtype="datetime64[ns]",
    )


def filter_dataframe_by_date(
    dataframe: pd.DataFrame,
    timestamp_column: Any,
    start_date: str | None = None,
    end_date: str | None = None,
    positional: bool = False,
) -> pd.DataFrame:
    """THE single, centralized date filter for the whole dashboard.

    Every department's data is filtered exactly once through this helper — no
    department performs its own date filtering. Given a dataframe and the name
    (or position, when ``positional=True``) of its timestamp column, it:

    * converts that column to ``pd.Timestamp`` once (mixed date/datetime/str
      formats handled; unparseable / out-of-range values become ``NaT`` and are
      dropped);
    * resolves the selected bounds, swapping them if ``end_date < start_date`` so
      a reversed range is never silently empty;
    * returns the rows whose timestamp is a valid date within the inclusive
      ``[start_date, end_date]`` range (all rows with a valid date when no bound
      is given, i.e. "All Dates").

    The returned frame preserves the input's columns and row order and carries
    the original row index of the surviving rows. If nothing survives (or the
    input is empty), an empty frame with the same columns is returned — callers
    can rely on that to build an empty-but-valid department safely, never
    crashing.

    Args:
        dataframe: The source frame to filter.
        timestamp_column: Label (default) or positional index (``positional``)
            of the timestamp column.
        start_date: Optional inclusive start (YYYY-MM-DD).
        end_date: Optional inclusive end (YYYY-MM-DD).
        positional: Interpret ``timestamp_column`` as an ``.iloc`` position.

    Returns:
        The date-filtered dataframe (possibly empty, never ``None``).
    """
    if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
        return dataframe if isinstance(dataframe, pd.DataFrame) else pd.DataFrame()

    normalized = _normalize_timestamp_column(dataframe, timestamp_column, positional)
    mask = normalized.notna()
    mask = _apply_date_range_to_mask(mask, normalized, start_date, end_date)
    mask = mask.fillna(False).astype(bool)
    return dataframe[mask.values]

def build_dashboard(workbook: dict[str, pd.DataFrame], start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
    _log_step("build_dashboard: ENTER")
    _validate_workbook(workbook)

    first_sheet_name: str = next(iter(workbook))
    primary_df: pd.DataFrame = workbook[first_sheet_name]
    _log_step(f"build_dashboard: primary sheet '{first_sheet_name}' {_df_meta(primary_df)}")

    start_idx, effective_end_idx = _discover_engineering_block(primary_df)
    _validate_boundaries(primary_df, start_idx, effective_end_idx)
    _log_step(f"build_dashboard: engineering block cols [{start_idx}..{effective_end_idx}]")

    engineering_block: pd.DataFrame = primary_df.iloc[:, start_idx : effective_end_idx + 1].copy()
    _validate_headers(engineering_block)
    _log_step(f"build_dashboard: engineering_block {_df_meta(engineering_block)}")

    dept_headers: pd.Series = engineering_block.iloc[0].ffill()
    meter_headers: pd.Series = engineering_block.iloc[1]
    
    readings_matrix: pd.DataFrame = engineering_block.iloc[2:]
    _log_step(f"build_dashboard: readings_matrix {_df_meta(readings_matrix)}")

    # CENTRALIZED DATE FILTERING (happens exactly once for the engineering data).
    # Attach the normalized timestamp as a temporary column so the readings and
    # their dates are filtered together through the single ``filter_dataframe_by_date``
    # helper — the same helper every other department uses. This guarantees the
    # filtered readings and filtered dates can never diverge in length, and no
    # department performs its own filtering.
    _DATE_COL = "__eng_date__"
    normalized_dates: pd.Series = _normalize_date_series(primary_df, readings_matrix)
    readings_with_date = readings_matrix.copy()
    readings_with_date[_DATE_COL] = normalized_dates.values

    _log_step("build_dashboard: filtering engineering readings once (centralized)...")
    filtered_with_date = filter_dataframe_by_date(
        readings_with_date, _DATE_COL, start_date, end_date
    )

    # Split the single filtered result back into readings + aligned date series.
    filtered_readings = filtered_with_date.drop(columns=[_DATE_COL])
    filtered_date_series = filtered_with_date[_DATE_COL]

    # Requirement: never assume any rows survive filtering. When a date range
    # selects no rows (or partially-empty selections leave nothing valid), we
    # must still build a coherent, empty-but-valid dashboard rather than crash.
    # ``has_filtered_rows`` gates every downstream step that would otherwise
    # touch row 0 / iloc[-1] / mismatched-length inserts. When it is False the
    # per-department payloads are still created (so the UI keeps its structure),
    # but with empty dataframes and ``None`` aggregates.
    has_filtered_rows: bool = len(filtered_readings) > 0
    _log_step(f"build_dashboard: has_filtered_rows={has_filtered_rows} filtered_rows={len(filtered_readings)}")

    available_dates: list[str] = []
    for val in filtered_date_series:
        d = _get_date_string(val)
        if d: available_dates.append(d)

    available_months: list[str] = sorted(list({date_str[:7] for date_str in available_dates}))

    # CREATE FILTERED OVERVIEW FOR CHARTS & DAILY TRENDS
    filtered_overview = engineering_block.iloc[:2].copy()
    filtered_overview = pd.concat([filtered_overview, filtered_readings])
    _log_step(f"build_dashboard: filtered_overview {_df_meta(filtered_overview)} filtered_readings {_df_meta(filtered_readings)}")

    # filtered_date_series and filtered_readings come from the SAME single
    # filtered frame, so they are always the same length. Keep a defensive guard
    # that falls back to a safe empty state if they ever diverge.
    if len(filtered_date_series) != len(filtered_readings):
        has_filtered_rows = False
        filtered_readings = readings_matrix.iloc[0:0]
        filtered_date_series = normalized_dates.iloc[0:0]
        filtered_overview = engineering_block.iloc[:2].copy()
        available_dates = []
        available_months = []

    dept_columns_map: dict[str, list[tuple[int, str]]] = {}
    dept_metadata_collector: dict[str, dict[str, Any]] = {}

    for pos in range(engineering_block.shape[1]):
        raw_dept: str = _clean_label(dept_headers.iloc[pos])
        raw_meter: str = _clean_label(meter_headers.iloc[pos])
        raw_unit: str = ""

        if not raw_dept or not raw_meter: continue

        if raw_dept not in dept_columns_map:
            dept_columns_map[raw_dept] = []
            dept_metadata_collector[raw_dept] = {
                "column_indexes": [], "source_sheet": first_sheet_name, "units_map": {},
            }

        global_col_idx: int = start_idx + pos
        dept_metadata_collector[raw_dept]["column_indexes"].append(global_col_idx)

        base_meter: str = raw_meter
        counter: int = 1
        existing_meters = {item[1] for item in dept_columns_map[raw_dept]}
        while base_meter in existing_meters:
            base_meter = f"{raw_meter}_{counter}"
            counter += 1

        dept_metadata_collector[raw_dept]["units_map"][base_meter] = raw_unit
        dept_columns_map[raw_dept].append((pos, base_meter))

    departments_payload: dict[str, dict[str, Any]] = {}
    _log_step(f"build_dashboard: processing {len(dept_columns_map)} departments...")
    for dept_name, col_info in dept_columns_map.items():
        _log_step(f"build_dashboard: department '{dept_name}' ({len(col_info)} meters)...")
        meta: dict[str, Any] = dept_metadata_collector[dept_name]
        
        positions = [info[0] for info in col_info]
        new_names = [info[1] for info in col_info]

        # Each department receives the ALREADY-FILTERED readings (filtered once,
        # centrally, above). It only selects its own columns — it never performs
        # its own date filtering.
        valid_dept_df = filtered_readings.iloc[:, positions].copy()
        valid_dept_df.columns = new_names

        meters_list: list[str] = new_names
        units_map: dict[str, str] = meta["units_map"]

        latest_values: dict[str, Any] = {}
        total_values: dict[str, Any] = {}
        average_values: dict[str, Any] = {}
        channels: dict[str, dict[str, Any]] = {}

        # INJECT DATE COLUMN FOR PERFECT CHART ALIGNMENT.
        # Guard against empty or length-mismatched filtered selections: only
        # insert the Date column when there are surviving rows AND the row counts
        # line up exactly. Otherwise produce an empty, correctly-shaped frame so
        # nothing downstream reads from a non-existent row.
        chart_df = valid_dept_df.copy()
        date_values = filtered_date_series.values
        if has_filtered_rows and len(chart_df) > 0 and len(date_values) == len(chart_df):
            chart_df.insert(0, "Date", date_values)
        else:
            chart_df = pd.DataFrame(columns=["Date", *meters_list])

        for meter in meters_list:
            series: pd.Series = valid_dept_df[meter]

            # The aggregation helpers below are already empty-safe (they return
            # None on an empty/all-NaN series and never call iloc[-1] on empty),
            # so no latest/total/average is computed from an empty dataframe.
            latest_val = _calculate_latest_valid_value(series)
            total_val = _calculate_sum(series)
            avg_val = _calculate_mean(series)

            latest_values[meter] = latest_val
            total_values[meter] = total_val
            average_values[meter] = avg_val

            # Requirement #6: assert equal lengths before constructing the
            # history DataFrame; if anything is empty or the arrays differ in
            # length, use an empty DataFrame instead of risking a mismatch crash.
            history_df = pd.DataFrame()
            if has_filtered_rows and not series.empty:
                final_dates = filtered_date_series.values
                final_vals = series.values
                if len(final_dates) > 0 and len(final_dates) == len(final_vals):
                    history_df = pd.DataFrame({"date": final_dates, "value": final_vals})

            channels[meter] = {
                "name": meter, "unit": units_map.get(meter, ""),
                "latest": latest_val, "average": avg_val, "total": total_val, "history": history_df,
            }

        departments_payload[dept_name] = {
            "name": dept_name, "meters": meters_list, "units": units_map,
            "latest_values": latest_values, "average_values": average_values, "total_values": total_values,
            "dataframe": chart_df, # NOW CONTAINS FILTERED DATA + DATE COLUMN
            "totals": total_values, "averages": average_values, "channels": channels,
            "metadata": {
                "column_indexes": meta["column_indexes"], "source_sheet": meta["source_sheet"],
                "meter_count": len(meters_list), "unit_count": len(set(units_map.values())),
            },
        }

    # --------------------------------------------------------------------------
    # SYNTHETIC AGGREGATE DEPARTMENTS
    # --------------------------------------------------------------------------
    # "Overall PNG" is discovered dynamically by the parser above as a normal
    # multi-meter department. Downstream it must behave as a single aggregate
    # value (the row-wise sum of its meters, e.g. Inside + Outside PNG). We
    # collapse it here, in the data layer, so app.py only ever renders finished
    # department objects. If the parser did not find the department (different
    # workbook), this is a no-op and nothing is invented.
    _log_step("build_dashboard: collapsing Overall PNG aggregate...")
    _collapse_department_to_aggregate(departments_payload, AGGREGATE_PNG_DEPARTMENT)
    _log_step("build_dashboard: aggregate collapse complete.")

    air_compressor_obj: dict[str, Any] | None = departments_payload.get("Air compressor")
    freon_obj: dict[str, Any] | None = departments_payload.get("Freon Refrigeration")
    ammonia_obj: dict[str, Any] | None = departments_payload.get("Ammonia Refrigeration")

    freon_sheet_df: pd.DataFrame | None = _find_sheet_by_keywords(workbook, ("freon",))
    ammonia_sheet_df: pd.DataFrame | None = _find_sheet_by_keywords(workbook, ("ammonia",))

    # CENTRALIZED FREON FILTERING (happens exactly once, here in build_dashboard).
    # The Freon worksheet is filtered a single time and the FILTERED worksheet is
    # what gets stored in dashboard["freon"] below — the raw worksheet is never
    # stored. Downstream, _discover_freon_columns only summarizes this filtered
    # worksheet and performs no filtering of its own.
    _log_step("build_dashboard: filtering Freon worksheet once (centralized)...")
    filtered_freon_df: pd.DataFrame | None = _filter_freon_sheet(freon_sheet_df, start_date, end_date)
    _log_step(f"build_dashboard: filtered freon {_df_meta(filtered_freon_df)} ammonia_sheet {_df_meta(ammonia_sheet_df)}")

    total_meter_count: int = sum(len(d["meters"]) for d in departments_payload.values())
    latest_timestamp: str = f"{available_dates[-1]} 00:00:00" if available_dates else "N/A"

    summary_payload: dict[str, Any] = {
        "department_count": len(departments_payload), "meter_count": total_meter_count,
        "latest_timestamp": latest_timestamp,
        "latest_values": {k: v["latest_values"] for k, v in departments_payload.items()},
        "average_values": {k: v["average_values"] for k, v in departments_payload.items()},
        "total_values": {k: v["total_values"] for k, v in departments_payload.items()},
        "available_sections": list(departments_payload.keys()),
        "department_latest_values": {k: v["latest_values"] for k, v in departments_payload.items()},
        "department_totals": {k: v["total_values"] for k, v in departments_payload.items()},
        "department_averages": {k: v["average_values"] for k, v in departments_payload.items()},
    }

    all_meters_set: set[str] = set()
    for d in departments_payload.values(): all_meters_set.update(d["meters"])

    filters_payload: dict[str, Any] = {
        "months": available_months, "dates": available_dates,
        "departments": list(departments_payload.keys()), "meters": sorted(list(all_meters_set)),
        "sections": list(departments_payload.keys()),
    }

    metadata_payload: dict[str, Any] = {
        "sheet_names": list(workbook.keys()), "departments": list(departments_payload.keys()),
        "sheet_count": len(workbook), "months": available_months, "dates": available_dates,
    }

    _log_step(f"build_dashboard: EXIT departments={len(departments_payload)} has_filtered_data={has_filtered_rows}")
    return {
        "overview": filtered_overview, # NOW FILTERED
        "departments": departments_payload,
        "air_compressor": air_compressor_obj["dataframe"] if air_compressor_obj else None,
        "freon": filtered_freon_df if filtered_freon_df is not None else (freon_obj["dataframe"] if freon_obj else None),
        "ammonia": ammonia_sheet_df if ammonia_sheet_df is not None else (ammonia_obj["dataframe"] if ammonia_obj else None),
        "summary": summary_payload, "filters": filters_payload, "metadata": metadata_payload,
        "navigation": [{"key": k, "label": k, "available": True} for k in departments_payload.keys()],
        "sheet_names": list(workbook.keys()), "months": available_months, "dates": available_dates,
        "latest_values": summary_payload["latest_values"],
        "totals": summary_payload["total_values"], "averages": summary_payload["average_values"],
        # True only when at least one row survived date filtering. Consumers such
        # as build_operations_overview use this to render "no data" safely
        # instead of assuming filtered rows exist.
        "has_filtered_data": has_filtered_rows,
        # The date bounds actually applied to this dashboard, so date-aware
        # consumers (e.g. Freon Refrigeration, which filters its dedicated
        # worksheet) can reuse exactly the same selection. Mirrors the same
        # start/end passed to the engineering-block filtering above.
        "date_filter": {"start_date": start_date, "end_date": end_date},
    }

# ==============================================================================
# BACKWARD COMPATIBLE PUBLIC ACCESSORS
# ==============================================================================

def get_sheet_names(workbook: dict[str, pd.DataFrame]) -> list[str]:
    _validate_workbook(workbook)
    return list(workbook.keys())

def get_overview_dataframe(workbook: dict[str, pd.DataFrame]) -> pd.DataFrame:
    _validate_workbook(workbook)
    return workbook[next(iter(workbook))]

def get_department_data(workbook: dict[str, pd.DataFrame]) -> dict[str, Any]:
    return build_dashboard(workbook)["departments"]

def get_air_compressor_data(workbook: dict[str, pd.DataFrame]) -> pd.DataFrame | None:
    return build_dashboard(workbook)["air_compressor"]

def get_freon_data(workbook: dict[str, pd.DataFrame]) -> pd.DataFrame | None:
    return build_dashboard(workbook)["freon"]

def get_ammonia_data(workbook: dict[str, pd.DataFrame]) -> pd.DataFrame | None:
    return build_dashboard(workbook)["ammonia"]

def get_available_departments(overview_dataframe: pd.DataFrame) -> list[str]:
    return sorted(list(EXPECTED_DEPARTMENTS))

def get_department_names(overview_structure: dict[str, Any]) -> list[str]:
    return overview_structure.get("departments", sorted(list(EXPECTED_DEPARTMENTS)))

def get_date_columns(overview_dataframe: pd.DataFrame) -> list[int]:
    """Return the positional index of the date column(s), located by label.

    The dashboard consistently injects a named ``"Date"`` column into every
    department/overview dataframe, so this resolves that column by name and
    reports its position rather than assuming a fixed positional index. The
    return type stays ``list[int]`` for backward compatibility with callers
    that index positionally (e.g. ``df.iloc[:, idx]``); when no named ``"Date"``
    column is present the legacy position is returned as a safe fallback so
    existing callers are never broken.
    """
    if isinstance(overview_dataframe, pd.DataFrame):
        for position, column in enumerate(overview_dataframe.columns):
            if _normalize_name(column) in DATE_HEADER_TOKENS:
                return [position]
    return [1]

def get_available_dates(overview_dataframe: pd.DataFrame) -> list[str]:
    return _extract_validated_dates(overview_dataframe)

def get_available_months(overview_dataframe: pd.DataFrame) -> list[str]:
    dates = _extract_validated_dates(overview_dataframe)
    return sorted(list({d[:7] for d in dates}))

def get_unit_row(overview_dataframe: pd.DataFrame) -> int | None:
    return None

def get_dashboard_overview(overview_dataframe: pd.DataFrame) -> dict[str, Any]:
    return {
        "departments": sorted(list(EXPECTED_DEPARTMENTS)), "date_columns": [1],
        "unit_row": None, "shape": overview_dataframe.shape,
    }

# ==============================================================================
# PRIVATE INTERNAL UTILITY CORE
# ==============================================================================

def select_representative_meter(section: dict[str, Any]) -> str:
    if not section: return ""
    meters = section.get("meters", [])
    latest_values = section.get("latest_values", {})
    if not meters: return ""

    def matches_keywords(meter_name: str, keywords: list[str]) -> bool:
        lower_name = meter_name.lower()
        return any(kw in lower_name for kw in keywords)

    for keyword_group in REPRESENTATIVE_METER_PRIORITIES:
        valid_matches = []
        for meter in meters:
            if matches_keywords(meter, keyword_group):
                val = latest_values.get(meter)
                if isinstance(val, (int, float)): valid_matches.append(meter)
        if valid_matches: return valid_matches[0]

    for meter in meters:
        val = latest_values.get(meter)
        if isinstance(val, (int, float)): return meter
    return ""


def build_operations_overview(dashboard: dict[str, Any]) -> list[dict[str, Any]]:
    """Assemble the expandable Plant Operations Overview structure.

    Business layer for the operations table. Consumes the already-parsed
    engineering departments (discovered from the DH–GH engineering block by
    ``build_dashboard``) and returns display-ready rows — one per department,
    each carrying its aggregate Total/Average/Latest/Status plus, when the
    department has more than one meter, the per-meter (subsection) breakdown.

    No department names, rows, or column letters are hardcoded: the parent
    rows are exactly the departments present in ``dashboard["departments"]``
    (in their discovered order — never sorted), and subsection names are the
    meter names the parser found in the engineering block's second header row.
    All figures are read from the department payload — nothing is recomputed or
    re-parsed here.

    Parent rows always show the department's aggregate figures (via its
    representative meter), matching the Executive Summary's single-value basis.
    Subsections show the ORIGINAL parsed meters: for a department that was
    collapsed into a synthetic aggregate (e.g. ``Overall PNG``), the originals
    are read from the preserved ``original_*`` keys, so the real workbook
    subsections (e.g. DJ/DK) are shown rather than the aggregate channel. For
    every other department the normal ``meters`` list is the original list, so
    it is used directly. Only departments whose ORIGINAL meter list has more
    than one entry are ``expandable``; single-meter departments expose no
    subsections.

    Args:
        dashboard: The assembled dashboard dictionary produced by
            ``build_dashboard`` / ``get_dashboard_data``.

    Returns:
        A list of parent-row dicts, each with keys:
        ``department`` (str), ``representative_meter`` (str),
        ``total`` / ``average`` / ``latest`` (float | None), ``online`` (bool),
        ``expandable`` (bool), and ``subsections`` — a list of dicts with
        ``name``, ``total``, ``average``, ``latest`` (float | None) and
        ``online`` (bool).
    """
    _log_step(f"build_operations_overview: ENTER departments={len(dashboard.get('departments', {})) if dashboard else 0}")
    departments = dashboard.get("departments", {}) if dashboard else {}
    rows: list[dict[str, Any]] = []

    # Requirement: when a date range leaves no filtered engineering data, the
    # overview must be empty rather than a list of rows full of ``None`` values
    # (or worse, a crash). The dashboard exposes ``has_filtered_data`` for this;
    # if it is explicitly False, return an empty overview. (Absent/True is
    # treated as "data present" to preserve existing behaviour.)
    if dashboard is not None and dashboard.get("has_filtered_data") is False:
        _log_step("build_operations_overview: EXIT (no filtered data -> empty)")
        return []

    for dept_name, dept_obj in departments.items():
        # Representative-meter figures are used as the parent values for
        # single-meter (non-expandable) departments. Multi-meter departments
        # override these below with the aggregated department values.
        total_values: dict[str, Any] = dept_obj.get("total_values", {})
        average_values: dict[str, Any] = dept_obj.get("average_values", {})
        latest_values: dict[str, Any] = dept_obj.get("latest_values", {})

        representative_meter = select_representative_meter(dept_obj)
        parent_total = total_values.get(representative_meter)
        parent_average = average_values.get(representative_meter)
        parent_latest = latest_values.get(representative_meter)

        # Subsections come from the ORIGINAL parsed meters. If the department was
        # collapsed into an aggregate, the originals live under ``original_*``;
        # otherwise the normal ``meters`` list already *is* the original.
        if dept_obj.get("original_meters"):
            sub_meters: list[str] = dept_obj.get("original_meters", [])
            sub_total_values: dict[str, Any] = dept_obj.get("original_total_values", {})
            sub_average_values: dict[str, Any] = dept_obj.get("original_average_values", {})
            sub_latest_values: dict[str, Any] = dept_obj.get("original_latest_values", {})
        else:
            sub_meters = dept_obj.get("meters", [])
            sub_total_values = total_values
            sub_average_values = average_values
            sub_latest_values = latest_values

        # Freon Refrigeration is the sole exception. Its data comes from the
        # dedicated "Freon Meter reading" worksheet (exposed as dashboard["freon"]),
        # NOT the engineering overview block:
        #   • SUBSECTIONS (shown when expanded) are the individual meter columns
        #     ("vN: <name> - Active energy"), discovered dynamically.
        #   • PARENT Total / Average are the sum of ONLY the rollup group columns
        #     (Dunkin / BMC / CLC / Deep) — NOT the sum of the meter subsections
        #     and NOT the engineering-sheet aggregate.
        # Both groups are discovered structurally from the worksheet header, so
        # meters or rollups added later appear automatically. Every other
        # department is completely unaffected.
        freon_rollup_total: float | None = None
        freon_rollup_average: float | None = None
        freon_subsections: list[dict[str, Any]] | None = None
        if dept_name == FREON_DEPARTMENT:
            # dashboard["freon"] is ALREADY the date-filtered worksheet (filtered
            # once in build_dashboard). The summarizer performs no filtering — it
            # only reads this filtered worksheet.
            _log_step(f"build_operations_overview: summarizing filtered Freon worksheet ({_df_meta(dashboard.get('freon') if dashboard else None)})...")
            freon_cols = _discover_freon_columns(dashboard.get("freon") if dashboard else None)
            discovered_meters = freon_cols.get("meters", [])
            discovered_rollups = freon_cols.get("rollups", [])
            _log_step(f"build_operations_overview: Freon discovery -> {len(discovered_meters)} meters, {len(discovered_rollups)} rollups.")
            if discovered_meters or discovered_rollups:
                # Subsections show BOTH the meter columns (v1..v9) AND the rollup
                # columns (Dunkin/BMC/CLC/Deep), in worksheet order: meters first,
                # then rollups.
                freon_subsections = list(discovered_meters) + list(discovered_rollups)

                # Parent Total = sum of rollup column totals (filtered rows).
                freon_rollup_total = freon_cols.get("rollup_total")
                # Parent Average = department-wide average of the combined rollup
                # columns (mean of per-row rollup sums), NOT a sum of averages.
                freon_rollup_average = freon_cols.get("rollup_overall_average")

        if freon_subsections is not None:
            # Subsections from the meter + rollup columns; parent Total/Average
            # set from the rollup columns below (not recomputed from subsections).
            subsections: list[dict[str, Any]] = freon_subsections
            is_expandable = len(subsections) > 1
            preserve_parent_values = True
        else:
            subsections = []
            is_expandable = len(sub_meters) > 1
            preserve_parent_values = False
            if is_expandable:
                for meter in sub_meters:
                    meter_latest = sub_latest_values.get(meter)
                    subsections.append(
                        {
                            "name": meter,
                            "total": sub_total_values.get(meter),
                            "average": sub_average_values.get(meter),
                            "latest": meter_latest,
                            "online": isinstance(meter_latest, (int, float)),
                        }
                    )

        # Parent figures for a multi-meter department:
        #   Total   = Σ subsection totals (sum is linear, so this is exact).
        #   Average = the department-wide average — the mean of the per-row
        #             department sums — NOT the sum of the subsections' averages.
        #             Sum-of-averages only equals the true average when every
        #             subsection shares the same valid-row count; in general it is
        #             mathematically wrong, so we compute the real overall average
        #             from the department's row-level dataframe.
        #   Latest  = Σ subsection latests (hidden by the UI for expandable rows).
        #
        # Freon Refrigeration is handled separately below (its parent comes from
        # the rollup columns), so it is excluded from this recomputation.
        if is_expandable and not preserve_parent_values:
            def _sum_present(values: list[Any]) -> float | None:
                nums = [v for v in values if isinstance(v, (int, float))]
                return float(sum(nums)) if nums else None

            parent_total = _sum_present([s["total"] for s in subsections])
            parent_latest = _sum_present([s["latest"] for s in subsections])

            # True department-wide average from the row-level dataframe (already
            # date-filtered upstream). For departments collapsed into an
            # aggregate (e.g. Overall PNG) the per-meter columns live on the
            # preserved ``original_dataframe``; otherwise the normal ``dataframe``
            # holds them. Fall back to sum-of-averages only if neither provides
            # the columns, so behaviour never regresses.
            if dept_obj.get("original_meters") and dept_obj.get("original_dataframe") is not None:
                avg_df = dept_obj.get("original_dataframe")
            else:
                avg_df = dept_obj.get("dataframe")
            value_cols = [c for c in (sub_meters or []) if avg_df is not None and c in avg_df.columns]
            overall_avg = _overall_average_of_columns(avg_df, value_cols) if value_cols else None
            if overall_avg is not None:
                parent_average = overall_avg
            else:
                parent_average = _sum_present([s["average"] for s in subsections])

        # Freon parent Total / Average come from the rollup columns. Previous Day
        # (latest) stays hidden by the UI because Freon is expandable — matching
        # the existing expandable-department behaviour; we do not set a summed
        # latest here.
        if dept_name == FREON_DEPARTMENT and freon_subsections is not None:
            parent_total = freon_rollup_total
            parent_average = freon_rollup_average

        rows.append(
            {
                "department": dept_name,
                "representative_meter": representative_meter,
                "total": parent_total,
                "average": parent_average,
                "latest": parent_latest,
                "online": isinstance(parent_latest, (int, float)),
                "expandable": is_expandable,
                "subsections": subsections,
            }
        )

    _log_step(f"build_operations_overview: EXIT rows={len(rows)}")
    return rows

def _collapse_department_to_aggregate(departments_payload: dict[str, dict[str, Any]], dept_name: str) -> None:
    """Collapse a discovered multi-meter department into a single aggregate meter
    while preserving its original per-meter (subsection) data.

    The aggregate channel is the row-wise sum of every meter belonging to the
    department, with missing / non-numeric readings treated as zero. The
    department's primary structure (``meters``, ``latest_values``,
    ``average_values``, ``total_values``, ``units``, ``dataframe``) is set to the
    single-channel aggregate, exactly as before — so consumers that read the
    representative meter (e.g. the Executive Summary) continue to see ONE
    aggregate value and are entirely unaffected.

    In addition, the ORIGINAL parsed per-meter data is retained on the same
    department object under dedicated ``original_*`` keys
    (``original_meters``, ``original_units``, ``original_latest_values``,
    ``original_average_values``, ``original_total_values``,
    ``original_dataframe``). Nothing else reads these except consumers that
    explicitly want the pre-aggregation subsections (e.g. the expandable
    Plant Operations Overview). This is how the aggregate value and the
    original subsection meters coexist on one department: the aggregate is the
    primary/representative view, the originals live alongside it untouched.

    This is a no-op if the department was not discovered by the parser (e.g. a
    workbook whose layout does not contain it), so no data is ever invented.

    The source department is resolved from the parser output by normalized
    name (case- and whitespace-insensitive), so a workbook labelling it
    ``"overall png"`` or ``"Overall  PNG"`` is matched just as reliably as the
    canonical spelling. No department is ever invented: if the parser did not
    discover a matching department, this is a no-op.

    Args:
        departments_payload: The fully-built department mapping to mutate.
        dept_name: The canonical department name to collapse (also the
            aggregate meter name and the key under which the result is stored).
    """
    _log_step(f"_collapse_department_to_aggregate: ENTER dept={dept_name!r}")
    target_norm = _normalize_name(dept_name)
    resolved_key: str | None = None
    if dept_name in departments_payload:
        resolved_key = dept_name
    else:
        for existing_key in departments_payload:
            if _normalize_name(existing_key) == target_norm:
                resolved_key = existing_key
                break

    if resolved_key is None:
        _log_step(f"_collapse_department_to_aggregate: EXIT (no matching department for {dept_name!r})")
        return

    source = departments_payload.get(resolved_key)
    if not source:
        _log_step("_collapse_department_to_aggregate: EXIT (source empty)")
        return

    source_meters: list[str] = source.get("meters", [])
    if not source_meters:
        _log_step("_collapse_department_to_aggregate: EXIT (no source meters)")
        return

    # Snapshot the ORIGINAL parsed per-meter data before the aggregate
    # overwrites the primary fields. These are retained on the aggregated
    # department so the expandable Operations Overview can show the real
    # subsection meters (e.g. DJ/DK) while the Executive Summary keeps using
    # the single aggregate value.
    original_meters: list[str] = list(source_meters)
    original_units: dict[str, Any] = dict(source.get("units", {}))
    original_latest_values: dict[str, Any] = dict(source.get("latest_values", {}))
    original_average_values: dict[str, Any] = dict(source.get("average_values", {}))
    original_total_values: dict[str, Any] = dict(source.get("total_values", {}))
    original_dataframe: pd.DataFrame = source.get("dataframe", pd.DataFrame())

    chart_df: pd.DataFrame = source.get("dataframe", pd.DataFrame())
    _log_step(f"_collapse_department_to_aggregate: source chart_df {_df_meta(chart_df)}")
    # The dataframe carries a leading "Date" column injected during build; the
    # remaining columns are the department's meters in discovery order.
    meter_cols = [c for c in chart_df.columns if c != "Date"]
    if not meter_cols:
        _log_step("_collapse_department_to_aggregate: EXIT (no meter columns)")
        return

    numeric_block = chart_df[meter_cols].apply(pd.to_numeric, errors="coerce")
    summed_series = numeric_block.fillna(0.0).sum(axis=1)

    # Preserve the unit of the first meter (all PNG meters share the same unit).
    source_units: dict[str, str] = source.get("units", {})
    aggregate_unit: str = source_units.get(source_meters[0], "")

    if "Date" in chart_df.columns:
        date_values = chart_df["Date"].values
    else:
        date_values = pd.RangeIndex(start=0, stop=len(summed_series)).values

    # Store the aggregate under the key the parser actually discovered
    # (``resolved_key``), preserving both the department's position in the
    # payload and its discovered spelling. The single synthetic meter reuses
    # that same name, exactly as the canonical (matching) case does today.
    aggregate_name = resolved_key

    aggregate_df = pd.DataFrame({"Date": date_values, aggregate_name: summed_series.values})

    valid_numeric = pd.to_numeric(summed_series, errors="coerce").dropna()
    latest_val: float | None = float(valid_numeric.iloc[-1]) if not valid_numeric.empty else None
    total_val: float | None = float(valid_numeric.sum()) if not valid_numeric.empty else None
    average_val: float | None = float(valid_numeric.mean()) if not valid_numeric.empty else None

    history_df = pd.DataFrame({"date": date_values, "value": summed_series.values})

    departments_payload[aggregate_name] = {
        "name": aggregate_name,
        "meters": [aggregate_name],
        "units": {aggregate_name: aggregate_unit},
        "latest_values": {aggregate_name: latest_val},
        "average_values": {aggregate_name: average_val},
        "total_values": {aggregate_name: total_val},
        "dataframe": aggregate_df,
        "totals": {aggregate_name: total_val},
        "averages": {aggregate_name: average_val},
        # Original parsed per-meter (subsection) data, preserved so the
        # expandable Operations Overview can show the real workbook meters while
        # the primary/aggregate fields above keep the Executive Summary intact.
        "original_meters": original_meters,
        "original_units": original_units,
        "original_latest_values": original_latest_values,
        "original_average_values": original_average_values,
        "original_total_values": original_total_values,
        "original_dataframe": original_dataframe,
        "channels": {
            aggregate_name: {
                "name": aggregate_name,
                "unit": aggregate_unit,
                "latest": latest_val,
                "average": average_val,
                "total": total_val,
                "history": history_df,
            }
        },
        "metadata": {
            "column_indexes": source.get("metadata", {}).get("column_indexes", []),
            "source_sheet": source.get("metadata", {}).get("source_sheet", ""),
            "meter_count": 1,
            "unit_count": 1,
            "synthetic_aggregate": True,
            "aggregated_from": source_meters,
        },
    }
    _log_step(f"_collapse_department_to_aggregate: EXIT (collapsed {resolved_key!r} from {len(source_meters)} meters)")

def _normalize_name(value: Any) -> str:
    """Normalize a label for case/whitespace-insensitive comparison.

    Lowercases, strips, and collapses internal whitespace so that
    ``"Overall PNG"``, ``"overall png"`` and ``"OVERALL  PNG"`` all compare
    equal. Used when matching department names discovered by the parser
    against known names, so matching never depends on exact capitalization
    or spacing.
    """
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).strip().lower().split())


def _discover_engineering_block(primary_df: pd.DataFrame) -> tuple[int, int]:
    """Locate the engineering telemetry block by structure, not by fixed letters.

    The block is identified by its structural signature rather than hardcoded
    spreadsheet columns: a column whose meter-header row (row index 1) holds a
    date-style label (see ``DATE_HEADER_TOKENS``) and whose immediately
    following column carries a known department name in the department-header
    row (row index 0). The block spans from that date column through the last
    populated column of the worksheet.

    This keeps working if the block shifts horizontally in future workbook
    revisions, and it deliberately ignores stray date labels that are not
    followed by a department column (e.g. an unrelated earlier timestamp
    column), so only the true engineering block is selected.

    Args:
        primary_df: The cleaned primary worksheet.

    Returns:
        A ``(start_idx, end_idx)`` inclusive column-index pair for the block.

    Raises:
        ValueError: If no block matching the structural signature is found.
    """
    if primary_df.shape[0] < 3 or primary_df.shape[1] < 2:
        raise ValueError(
            "Workbook structure error: worksheet is too small to contain an "
            "engineering block (need at least 3 rows and 2 columns)."
        )

    dept_header_row = primary_df.iloc[0]
    meter_header_row = primary_df.iloc[1]
    last_col_idx = primary_df.shape[1] - 1

    for pos in range(last_col_idx):
        if _normalize_name(meter_header_row.iloc[pos]) not in DATE_HEADER_TOKENS:
            continue
        following_dept = _normalize_name(dept_header_row.iloc[pos + 1])
        if following_dept and following_dept in _EXPECTED_DEPARTMENTS_NORM:
            return pos, last_col_idx

    raise ValueError(
        "Workbook structure error: could not locate the engineering telemetry "
        "block. Expected a date-labelled column immediately followed by a known "
        "department column."
    )


def _excel_col_to_index(col_str: str) -> int:
    exp: int = 0
    idx: int = 0
    for char in reversed(col_str.upper()):
        idx += (ord(char) - 64) * (26**exp)
        exp += 1
    return idx - 1

def _clean_label(value: Any) -> str:
    if pd.isna(value) or value is None: return ""
    text = str(value).strip()
    if text.lower() in {"nan", "null", "none", "", "0.0", "0"}:
        if text not in EXPECTED_DEPARTMENTS: return ""
    return text

def _extract_validated_dates(primary_df: pd.DataFrame) -> list[str]:
    if primary_df.shape[1] <= 1: return []
    raw_date_series = primary_df.iloc[2:, 1]
    validated_dates: list[str] = []
    for val in raw_date_series:
        d = _get_date_string(val)
        if d: validated_dates.append(d)
    return validated_dates

def _calculate_latest_valid_value(series: pd.Series) -> Any:
    numeric_series = pd.to_numeric(series, errors='coerce').dropna()
    if numeric_series.empty: return None
    return float(numeric_series.iloc[-1])

def _calculate_sum(series: pd.Series) -> float | None:
    numeric_series = pd.to_numeric(series, errors='coerce').dropna()
    return float(numeric_series.sum()) if not numeric_series.empty else None

def _calculate_mean(series: pd.Series) -> float | None:
    numeric_series = pd.to_numeric(series, errors='coerce').dropna()
    return float(numeric_series.mean()) if not numeric_series.empty else None

def _find_sheet_by_keywords(workbook: dict[str, pd.DataFrame], keywords: tuple[str, ...]) -> pd.DataFrame | None:
    for sheet_name, dataframe in workbook.items():
        lowered_name = sheet_name.lower()
        if any(keyword in lowered_name for keyword in keywords): return dataframe
    return None


# Header pattern for a named Freon meter column, e.g.
# "v1: DUNKIN IDU+CT - Active energy". The human-readable meter name is the
# captured group (the ``vN:`` prefix and the ``- Active energy`` suffix are
# stripped). Matching this pattern is how meters are discovered dynamically, so
# any future meter added to the worksheet is picked up automatically.
_FREON_METER_HEADER_RE: Final[re.Pattern[str]] = re.compile(
    r"^v\d+:\s*(.+?)\s*-\s*active energy", re.IGNORECASE
)

# Short meter-code columns (e.g. "v1", "v2" ...) that sit before the named
# meter columns. These are the raw cumulative-reading codes and are neither
# subsections nor rollups, so they are skipped during discovery.
_FREON_METER_CODE_RE: Final[re.Pattern[str]] = re.compile(r"^v\d+$", re.IGNORECASE)


def _summarize_freon_column(
    filtered_block: pd.DataFrame,
    col: int,
    name: str,
) -> dict[str, Any]:
    """Summarize one Freon column (from the ALREADY-FILTERED block) into a
    Total/Average/Previous-Day record.

    ``filtered_block`` has already been date-filtered once by the centralized
    ``filter_dataframe_by_date`` helper, so this performs NO filtering — it only
    reads its column positionally and aggregates. Non-numeric markers (e.g.
    ``"---"``) are treated as missing. Never touches ``iloc[-1]`` on an empty
    series, so an empty selection yields ``None`` figures rather than crashing.
    """
    column = filtered_block.iloc[:, col]
    series = pd.to_numeric(column, errors="coerce").dropna()
    if series.empty:
        total_val: float | None = None
        average_val: float | None = None
        latest_val: float | None = None
    else:
        total_val = float(series.sum())
        average_val = float(series.mean())
        latest_val = float(series.iloc[-1])
    return {
        "name": name,
        "total": total_val,
        "average": average_val,
        "latest": latest_val,
        "online": isinstance(latest_val, (int, float)),
    }


def _overall_average_of_columns(
    frame: pd.DataFrame,
    value_columns: list[Any],
    positional: bool = False,
) -> float | None:
    """Return the department-wide average: the mean of the per-row column sums.

    ``frame`` is expected to be ALREADY date-filtered (the centralized filter
    runs once, upstream); this performs no filtering. This is the mathematically
    correct "average of the whole" — for each row it sums the given value columns
    (missing/non-numeric treated as 0 within a row that has at least one value),
    then averages those per-row sums across the rows that have any data. It is
    NOT the sum of per-column averages, which only coincides with this when every
    column shares the same valid-row count.

    Args:
        frame: The (already-filtered) source dataframe.
        value_columns: The columns to combine per row. Interpreted as column
            LABELS by default, or as positional indices when ``positional`` is
            True (needed for sheets whose column labels are non-contiguous after
            cleaning, e.g. the Freon worksheet).
        positional: When True, ``value_columns`` are ``.iloc`` positions.

    Returns:
        The overall average as a float, or ``None`` if no rows contribute data.
    """
    if frame is None or len(value_columns) == 0:
        return None
    if positional:
        block = frame.iloc[:, value_columns]
    else:
        block = frame[value_columns]
    if block.empty:
        return None
    numeric = block.apply(pd.to_numeric, errors="coerce")
    # Per-row sum; a row with no numeric values at all contributes NaN (excluded
    # from the mean) rather than a misleading 0.
    row_sums = numeric.sum(axis=1, min_count=1)
    row_sums = row_sums.dropna()
    if row_sums.empty:
        return None
    return float(row_sums.mean())


def _locate_freon_header(freon_sheet: pd.DataFrame) -> tuple[int, int] | None:
    """Locate the Freon worksheet's header row and Timestamp column.

    Scans the first rows for a cell reading ``"Timestamp"`` anywhere in the row
    (the Timestamp column is NOT assumed to be column 0). Returns
    ``(header_row_idx, timestamp_col)`` or ``None`` if not found.
    """
    scan_rows = min(30, freon_sheet.shape[0])
    for r in range(scan_rows):
        for col in range(freon_sheet.shape[1]):
            cell = freon_sheet.iat[r, col]
            if isinstance(cell, str) and cell.strip().lower() == "timestamp":
                return r, col
    return None


def _filter_freon_sheet(
    freon_sheet: pd.DataFrame | None,
    start_date: str | None,
    end_date: str | None,
) -> pd.DataFrame | None:
    """Return the Freon worksheet with ONLY its data rows date-filtered ONCE.

    This is where the Freon worksheet is filtered — exactly once, during
    ``build_dashboard`` — so the value stored in ``dashboard["freon"]`` is the
    already-filtered worksheet, never the raw one. The header rows (everything
    up to and including the ``Timestamp`` header row) are preserved unchanged so
    the downstream summarizer can still locate the header and classify columns;
    only the data rows beneath are passed through the single centralized
    ``filter_dataframe_by_date`` helper, keyed on the discovered Timestamp column.

    The worksheet's structure (header rows on top, data rows beneath) and column
    layout are preserved, so ``_discover_freon_columns`` works on the result with
    no further filtering. If the sheet is missing/empty or has no locatable
    header, it is returned unchanged (an absent Freon department is handled
    safely downstream).

    Args:
        freon_sheet: The raw "Freon Meter reading" worksheet, or ``None``.
        start_date: Optional inclusive start (YYYY-MM-DD).
        end_date: Optional inclusive end (YYYY-MM-DD).

    Returns:
        The worksheet with its data rows filtered (header rows intact), or the
        original object when there is nothing to filter.
    """
    if freon_sheet is None or freon_sheet.empty:
        return freon_sheet

    located = _locate_freon_header(freon_sheet)
    if located is None:
        return freon_sheet

    header_row_idx, timestamp_col = located
    data_start = header_row_idx + 1

    head_rows = freon_sheet.iloc[: data_start]
    data_block = freon_sheet.iloc[data_start:]
    filtered_data = filter_dataframe_by_date(
        data_block, timestamp_col, start_date, end_date, positional=True
    )
    _log_step(
        f"_filter_freon_sheet: header_row={header_row_idx} timestamp_col={timestamp_col} "
        f"filtered rows={len(filtered_data)} of {len(data_block)}"
    )
    # Reassemble header rows + filtered data rows, preserving structure/columns.
    return pd.concat([head_rows, filtered_data])


def _discover_freon_columns(freon_sheet: pd.DataFrame | None) -> dict[str, Any]:
    """Summarize the ALREADY-FILTERED Freon worksheet into meters + rollups.

    This function performs NO date filtering. It receives the worksheet that was
    filtered once in ``build_dashboard`` (stored as ``dashboard["freon"]``) and
    only reads it: it locates the header row + Timestamp column, classifies the
    columns structurally, and summarizes each column's already-filtered data.

    The Freon worksheet uses its own legend + data-table layout: a header row
    containing a ``Timestamp`` cell (located dynamically — NOT assumed to be
    column 0), followed by three kinds of columns —

    * short meter codes (``v1``, ``v2`` ...) — skipped;
    * named meter columns (``vN: <name> - Active energy``) — the per-meter
      SUBSECTIONS shown when Freon Refrigeration is expanded; and
    * plain rollup label columns (e.g. ``Dunkin``, ``BMC``, ``CLC``, ``Deep``)
      — also shown as subsections, AND combined for the PARENT Total / Average.

    Column groups are discovered structurally from the header (never by hardcoded
    names or fixed letters), so meters/rollups added later appear automatically,
    in worksheet order. Non-numeric markers (``"---"``) are treated as missing.

    Returns:
        A dict with:
        * ``"meters"`` — list of meter subsection records;
        * ``"rollups"`` — list of rollup subsection records;
        * ``"rollup_total"`` — sum of the rollup column totals (parent Total);
        * ``"rollup_overall_average"`` — the department-wide average of the
          combined rollup columns (mean of per-row rollup sums), i.e. the
          mathematically correct parent Average.
        All figures come from the already-filtered worksheet. Empty/zero-safe
        when the sheet is missing or contains no data rows.
    """
    empty: dict[str, Any] = {
        "meters": [], "rollups": [], "rollup_total": None, "rollup_overall_average": None,
    }
    _log_step(f"_discover_freon_columns: ENTER freon_sheet={_df_meta(freon_sheet)}")
    if freon_sheet is None or freon_sheet.empty:
        _log_step("_discover_freon_columns: EXIT (sheet missing/empty)")
        return empty

    located = _locate_freon_header(freon_sheet)
    if located is None:
        return empty

    header_row_idx, timestamp_col = located
    header = freon_sheet.iloc[header_row_idx]
    data_start = header_row_idx + 1

    # The worksheet is already date-filtered (in build_dashboard). The rows below
    # the header are exactly the surviving rows — summarize them, no filtering.
    filtered_block = freon_sheet.iloc[data_start:]
    _log_step(f"_discover_freon_columns: header_row={header_row_idx} timestamp_col={timestamp_col} data_rows={len(filtered_block)}")

    # If there are no data rows (empty filtered worksheet), return empty safely.
    if filtered_block.empty:
        _log_step("_discover_freon_columns: EXIT (no data rows)")
        return empty

    meters: list[dict[str, Any]] = []
    rollups: list[dict[str, Any]] = []
    rollup_cols: list[int] = []

    for col in range(freon_sheet.shape[1]):
        raw_header = header.iat[col]
        if not isinstance(raw_header, str):
            continue
        head = raw_header.strip()
        if not head:
            continue

        # The Timestamp column and short vN code columns are not subsections.
        if col == timestamp_col or _FREON_METER_CODE_RE.match(head):
            continue

        meter_match = _FREON_METER_HEADER_RE.match(head)
        if meter_match:
            meter_name = meter_match.group(1).strip()
            if meter_name:
                meters.append(_summarize_freon_column(filtered_block, col, meter_name))
            continue

        # Anything else with a plain label after the meter block is a rollup
        # group column (e.g. Dunkin / BMC / CLC / Deep).
        rollups.append(_summarize_freon_column(filtered_block, col, head))
        rollup_cols.append(col)

    # Parent Total = sum of rollup column totals (from the already-filtered data).
    rollup_totals = [r["total"] for r in rollups if isinstance(r["total"], (int, float))]
    rollup_total: float | None = float(sum(rollup_totals)) if rollup_totals else None

    # Parent Average = department-wide average of the combined rollup columns:
    # the mean of the per-row rollup sums over the ALREADY-FILTERED block (NOT
    # the sum of the rollups' individual averages). ``rollup_cols`` are positional
    # indices (the Freon sheet's column labels are non-contiguous after cleaning),
    # so we read them positionally from the filtered block.
    rollup_overall_average = _overall_average_of_columns(
        filtered_block, rollup_cols, positional=True
    )

    _log_step(f"_discover_freon_columns: EXIT meters={len(meters)} rollups={len(rollups)}")
    return {
        "meters": meters,
        "rollups": rollups,
        "rollup_total": rollup_total,
        "rollup_overall_average": rollup_overall_average,
    }


def _discover_freon_meters(
    freon_sheet: pd.DataFrame | None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Backward-compatible accessor returning only the Freon meter subsections.

    Retained so any existing caller keeps working. Because
    ``_discover_freon_columns`` now summarizes an already-filtered worksheet, this
    wrapper filters the given (raw) sheet once via ``_filter_freon_sheet`` before
    summarizing, honouring the optional date range.
    """
    filtered = _filter_freon_sheet(freon_sheet, start_date, end_date)
    return _discover_freon_columns(filtered)["meters"]


# ==============================================================================
# VALIDATION ENFORCEMENT ARSENAL
# ==============================================================================

def _validate_workbook(workbook: dict[str, pd.DataFrame]) -> None:
    if not isinstance(workbook, dict) or not workbook:
        raise ValueError("Invalid Workbook payload: Context dictionary structure cannot be empty.")
    for sheet_name, df in workbook.items():
        if not isinstance(df, pd.DataFrame):
            raise ValueError(f"Sheet integration error: mapping context '{sheet_name}' must wrap a pandas.DataFrame.")

def _validate_boundaries(df: pd.DataFrame, start_idx: int, end_idx: int) -> None:
    if start_idx < 0 or end_idx >= df.shape[1] or start_idx > end_idx:
        raise ValueError(f"Boundary Access Violation: Engineering metrics tracking limit bounds map to indices exceeding available worksheet matrix limits.")

def _validate_headers(engineering_block: pd.DataFrame) -> None:
    if engineering_block.shape[0] < 3:
        raise ValueError("Structural Verification Failure: Target engineering block has inadequate vertical layout height.")
    row1_elements = engineering_block.iloc[0].ffill().dropna().tolist()
    if not any(_clean_label(item) for item in row1_elements):
        raise ValueError("Header Row 1 Structural Validation Failure: No valid department descriptors found.")
    row2_elements = engineering_block.iloc[1].dropna().tolist()
    if not any(_clean_label(item) for item in row2_elements):
        raise ValueError("Header Row 2 Structural Validation Failure: No valid meter tracking channel labels found.")
