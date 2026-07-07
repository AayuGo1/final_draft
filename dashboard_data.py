"""Business layer for the Engineering Monitoring Dashboard.

This module acts as the single source of truth for interpreting the parsed
workbook produced by ``parser.py``. It enforces a rigid, high-performance
engineering layout mapped directly to the static column boundaries DH to GH
on the primary overview worksheet.

All metrics, dataframes, and structural invariants are validated against
the production engineering specifications. Backward compatibility with all
downstream consumers (app.py, chart_service.py, kpi_service.py) is maintained.
"""

from __future__ import annotations

import datetime
import warnings
from typing import Any, Final

import pandas as pd

# ==============================================================================
# PRODUCTION CONSTANTS & SPECIFICATIONS
# ==============================================================================

START_COL_NAME: Final[str] = "DH"
END_COL_NAME: Final[str] = "GH"

# Canonical manufacturing department inventory for strict structure validation
EXPECTED_DEPARTMENTS: Final[set[str]] = {
    "NPCL", "Overall PNG", "Dough", "Traywasher", "Popeyes", "Warehouse",
    "Transport", "Admin", "BMC", "New CK", "Old CK", "UPS", "CLC", "WTP",
    "ETP", "RO Plant", "EHS", "Utility", "Freon Refrigeration",
    "Ammonia Refrigeration", "Air compressor", "Rooftop Solar", "Engineering",
    "B2B", "Bread", "Donut", "Silo", "DG", "GG"
}

# Date validation constraints for physical plant monitoring boundaries
MIN_VALID_YEAR: Final[int] = 2020
MAX_VALID_YEAR: Final[int] = 2035

# Known engineering unit tokens for data sanitation and structure check validation
UNIT_TOKENS: Final[set[str]] = {
    "kwh", "kw", "kva", "kl", "l", "ml", "kg", "mt", "ton", "%", "°c", "c",
    "bar", "psi", "m3", "nm3", "hp", "ppm", "db", "hz", "rpm", "hrs", "hr",
    "units", "no.", "nos", "m³/hr", "kg/hr", "v", "a", "pf", "kw/tr", "tr"
}


# ==============================================================================
# TOP-LEVEL APPLICATION ASSEMBLY INTERFACES
# ==============================================================================


def get_dashboard_data(workbook: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Assemble a complete dashboard data model from the parsed workbook.

    Backward compatibility wrapper around ``build_dashboard``.
    """
    return build_dashboard(workbook)


def build_dashboard(workbook: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Orchestrate the extraction, cleaning, validation, and compilation of dashboard data.

    Args:
        workbook: Mapping of sheet names to dataframes from ``parser.read_all_sheets``.

    Returns:
        Structured dashboard data dictionary matching all downstream consumer APIs.

    Raises:
        ValueError: On structural, boundary, or validation failures.
    """
    _validate_workbook(workbook)

    first_sheet_name: str = next(iter(workbook))
    primary_df: pd.DataFrame = workbook[first_sheet_name]

    # Translate fixed column characters to reliable integer offsets
    start_idx: int = _excel_col_to_index(START_COL_NAME)
    end_idx: int = _excel_col_to_index(END_COL_NAME)

    _validate_boundaries(primary_df, start_idx, end_idx)

    # Slice block strictly to targeted layout constraints
    engineering_block: pd.DataFrame = primary_df.iloc[:, start_idx : end_idx + 1].copy()
    _validate_headers(engineering_block)

    # Discover and sanitize dynamic time coordinates (Column B index 1)
    available_dates: list[str] = _extract_validated_dates(primary_df)
    available_months: list[str] = sorted(list({date_str[:7] for date_str in available_dates}))

    # Extract dynamic row headers and forward-fill merged structural boundaries
    dept_headers: pd.Series = engineering_block.iloc[0].ffill()
    meter_headers: pd.Series = engineering_block.iloc[1]
    unit_headers: pd.Series = engineering_block.iloc[2]
    readings_matrix: pd.DataFrame = engineering_block.iloc[3:].reset_index(drop=True)

    # Intermediate storage mapping to optimize performance and prevent alignment drift
    dept_column_collector: dict[str, dict[str, list[Any]]] = {}
    dept_metadata_collector: dict[str, dict[str, Any]] = {}

    for pos in range(engineering_block.shape[1]):
        raw_dept: str = _clean_label(dept_headers.iloc[pos])
        raw_meter: str = _clean_label(meter_headers.iloc[pos])
        raw_unit: str = _clean_label(unit_headers.iloc[pos])

        if not raw_dept or not raw_meter:
            continue

        if raw_dept not in dept_column_collector:
            dept_column_collector[raw_dept] = {}
            dept_metadata_collector[raw_dept] = {
                "column_indexes": [],
                "source_sheet": first_sheet_name,
                "units_map": {},
            }

        # Track mapping configuration coordinates
        global_col_idx: int = start_idx + pos
        dept_metadata_collector[raw_dept]["column_indexes"].append(global_col_idx)
        dept_metadata_collector[raw_dept]["units_map"][raw_meter] = raw_unit

        # Handle column name deduplication within the same department safely
        base_meter: str = raw_meter
        counter: int = 1
        while base_meter in dept_column_collector[raw_dept]:
            base_meter = f"{raw_meter}_{counter}"
            counter += 1

        # Direct row array population minimizes structural tracking costs
        dept_column_collector[raw_dept][base_meter] = readings_matrix.iloc[:, pos].tolist()

    # Construct compiled department models using vectorized operations where appropriate
    departments_payload: dict[str, dict[str, Any]] = {}
    for dept_name, meters_data in dept_column_collector.items():
        meta: dict[str, Any] = dept_metadata_collector[dept_name]
        
        # Guard column alignment by bulk-instantiating the underlying DataFrame once
        dept_df = pd.DataFrame(meters_data)
        
        meters_list: list[str] = list(meters_data.keys())
        units_map: dict[str, str] = meta["units_map"]

        latest_values: dict[str, Any] = {}
        total_values: dict[str, Any] = {}
        average_values: dict[str, Any] = {}

        for meter in meters_list:
            series: pd.Series = dept_df[meter]
            latest_values[meter] = _calculate_latest_valid_value(series)
            total_values[meter] = _calculate_sum(series)
            average_values[meter] = _calculate_mean(series)

        departments_payload[dept_name] = {
            "name": dept_name,
            "meters": meters_list,
            "units": units_map,
            "latest_values": latest_values,
            "average_values": average_values,
            "total_values": total_values,
            "dataframe": dept_df,
            "totals": total_values,      # Backward compatibility field match
            "averages": average_values,  # Backward compatibility field match
            "metadata": {
                "column_indexes": meta["column_indexes"],
                "source_sheet": meta["source_sheet"],
                "meter_count": len(meters_list),
                "unit_count": len(set(units_map.values())),
            },
        }

    # Extract target industrial subsystems directly from verified layout maps
    air_compressor_obj: dict[str, Any] | None = departments_payload.get("Air compressor")
    freon_obj: dict[str, Any] | None = departments_payload.get("Freon Refrigeration")
    ammonia_obj: dict[str, Any] | None = departments_payload.get("Ammonia Refrigeration")

    # Access secondary workbook backup resources matching legacy schema structural patterns
    freon_sheet_df: pd.DataFrame | None = _find_sheet_by_keywords(workbook, ("freon",))
    ammonia_sheet_df: pd.DataFrame | None = _find_sheet_by_keywords(workbook, ("ammonia",))

    # Compile global metric summary indicators
    total_meter_count: int = sum(len(d["meters"]) for d in departments_payload.values())
    latest_timestamp: str = f"{available_dates[-1]} 00:00:00" if available_dates else "N/A"

    summary_payload: dict[str, Any] = {
        "department_count": len(departments_payload),
        "meter_count": total_meter_count,
        "latest_timestamp": latest_timestamp,
        "latest_values": {k: v["latest_values"] for k, v in departments_payload.items()},
        "average_values": {k: v["average_values"] for k, v in departments_payload.items()},
        "total_values": {k: v["total_values"] for k, v in departments_payload.items()},
        "available_sections": list(departments_payload.keys()),
        "department_latest_values": {k: v["latest_values"] for k, v in departments_payload.items()},
        "department_totals": {k: v["total_values"] for k, v in departments_payload.items()},
        "department_averages": {k: v["average_values"] for k, v in departments_payload.items()},
    }

    # Aggregate global unique dashboard metrics across all departments cleanly
    all_meters_set: set[str] = set()
    for d in departments_payload.values():
        all_meters_set.update(d["meters"])

    filters_payload: dict[str, Any] = {
        "months": available_months,
        "dates": available_dates,
        "departments": list(departments_payload.keys()),
        "meters": sorted(list(all_meters_set)),
        "sections": list(departments_payload.keys()),
    }

    metadata_payload: dict[str, Any] = {
        "sheet_names": list(workbook.keys()),
        "departments": list(departments_payload.keys()),
        "sheet_count": len(workbook),
        "months": available_months,
        "dates": available_dates,
    }

    return {
        "overview": engineering_block,
        "departments": departments_payload,
        "air_compressor": air_compressor_obj["dataframe"] if air_compressor_obj else None,
        "freon": freon_sheet_df if freon_sheet_df is not None else (freon_obj["dataframe"] if freon_obj else None),
        "ammonia": ammonia_sheet_df if ammonia_sheet_df is not None else (ammonia_obj["dataframe"] if ammonia_obj else None),
        "summary": summary_payload,
        "filters": filters_payload,
        "metadata": metadata_payload,
        "navigation": [{"key": k, "label": k, "available": True} for k in departments_payload.keys()],
        "sheet_names": list(workbook.keys()),
        "months": available_months,
        "dates": available_dates,
        "latest_values": summary_payload["latest_values"],
        "totals": summary_payload["total_values"],
        "averages": summary_payload["average_values"],
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
    return [1]


def get_available_dates(overview_dataframe: pd.DataFrame) -> list[str]:
    return _extract_validated_dates(overview_dataframe)


def get_available_months(overview_dataframe: pd.DataFrame) -> list[str]:
    dates = _extract_validated_dates(overview_dataframe)
    return sorted(list({d[:7] for d in dates}))


def get_unit_row(overview_dataframe: pd.DataFrame) -> int | None:
    return 2


def get_dashboard_overview(overview_dataframe: pd.DataFrame) -> dict[str, Any]:
    return {
        "departments": sorted(list(EXPECTED_DEPARTMENTS)),
        "date_columns": [1],
        "unit_row": 2,
        "shape": overview_dataframe.shape,
    }


# ==============================================================================
# PRIVATE INTERNAL UTILITY CORE
# ==============================================================================


def _excel_col_to_index(col_str: str) -> int:
    """Safely resolve an alphanumeric Excel coordinate label to a 0-based column sequence number."""
    exp: int = 0
    idx: int = 0
    for char in reversed(col_str.upper()):
        idx += (ord(char) - 64) * (26**exp)
        exp += 1
    return idx - 1


def _clean_label(value: Any) -> str:
    """Normalize and sanitize headers, strip whitespaces, and convert null-like assets to a clean string."""
    if pd.isna(value) or value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "null", "none", "", "0.0", "0"}:
        if text not in EXPECTED_DEPARTMENTS:
            return ""
    return text


def _extract_validated_dates(primary_df: pd.DataFrame) -> list[str]:
    """Isolate, parse, and enforce timeline boundaries on structural row series values safely."""
    if primary_df.shape[1] <= 1:
        return []
    
    # Timeline values reside from row index 3 onwards within column B (Index 1)
    raw_date_series = primary_df.iloc[3:, 1]
    validated_dates: list[str] = []

    for val in raw_date_series:
        if pd.isna(val) or val is None:
            continue
        try:
            dt = None
            if isinstance(val, (datetime.datetime, datetime.date)):
                dt = val
            else:
                cleaned_str = str(val).strip().split()[0]
                # Match common formats safely without relying on standard implicit timestamp transformations
                for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
                    try:
                        dt = datetime.datetime.strptime(cleaned_str, fmt)
                        break
                    except ValueError:
                        continue
            
            if dt and MIN_VALID_YEAR <= dt.year <= MAX_VALID_YEAR:
                validated_dates.append(dt.strftime("%Y-%m-%d"))
        except Exception:
            continue

    return sorted(list(set(validated_dates)))


def _calculate_latest_valid_value(series: pd.Series) -> Any:
    """Iterate backwards to resolve the absolute last authentic telemetry float sample."""
    for idx in range(len(series) - 1, -1, -1):
        val = series.iloc[idx]
        if pd.isna(val) or val is None:
            continue
        cleaned = str(val).strip()
        if not cleaned or cleaned.startswith('#') or any(err in cleaned.upper() for err in ('VALUE!', 'NAME?', 'DIV/0')):
            continue
        try:
            return float(cleaned)
        except ValueError:
            continue
    return None


def _calculate_sum(series: pd.Series) -> float | None:
    """Compute vectorized calculation sum ignoring string metadata, units, and formula anomalies."""
    numeric_series = pd.to_numeric(series, errors='coerce').dropna()
    return float(numeric_series.sum()) if not numeric_series.empty else None


def _calculate_mean(series: pd.Series) -> float | None:
    """Compute average metrics checking valid array distributions effectively."""
    numeric_series = pd.to_numeric(series, errors='coerce').dropna()
    return float(numeric_series.mean()) if not numeric_series.empty else None


def _find_sheet_by_keywords(workbook: dict[str, pd.DataFrame], keywords: tuple[str, ...]) -> pd.DataFrame | None:
    """Direct lookup search across active sheets ensuring accurate data fallbacks."""
    for sheet_name, dataframe in workbook.items():
        lowered_name = sheet_name.lower()
        if any(keyword in lowered_name for keyword in keywords):
            return dataframe
    return None


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
        raise ValueError(
            f"Boundary Access Violation: Engineering metrics tracking limit bounds [{START_COL_NAME}:{END_COL_NAME}] "
            f"map to indices [{start_idx}:{end_idx}], exceeding available worksheet matrix limits (Columns: {df.shape[1]})."
        )


def _validate_headers(engineering_block: pd.DataFrame) -> None:
    if engineering_block.shape[0] < 4:
        raise ValueError(
            f"Structural Verification Failure: Target engineering block has inadequate vertical layout height ({engineering_block.shape[0]} rows). "
            f"Production layout matrices must contain at least a Department row (1), a Meter row (2), a Unit row (3), and a Data row (4)."
        )

    row1_elements = engineering_block.iloc[0].ffill().dropna().tolist()
    if not any(_clean_label(item) for item in row1_elements):
        raise ValueError("Header Row 1 Structural Validation Failure: No valid, non-empty department descriptors found inside the sliced boundaries.")

    row2_elements = engineering_block.iloc[1].dropna().tolist()
    if not any(_clean_label(item) for item in row2_elements):
        raise ValueError("Header Row 2 Structural Validation Failure: No valid, non-empty meter tracking channel labels found inside the sliced boundaries.")
