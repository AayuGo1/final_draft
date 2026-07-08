"""Business layer for the Engineering Monitoring Dashboard.

This module acts as the single source of truth for interpreting the parsed
workbook produced by ``parser.py``. It enforces a rigid, high-performance
engineering layout mapped directly to the static column boundaries DH to GH
on the primary overview worksheet.
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

EXPECTED_DEPARTMENTS: Final[set[str]] = {
    "NPCL", "Overall PNG", "Dough", "Traywasher", "Popeyes", "Warehouse",
    "Transport", "Admin", "BMC", "New CK", "Old CK", "UPS", "CLC", "WTP",
    "ETP", "RO Plant", "EHS", "Utility", "Freon Refrigeration",
    "Ammonia Refrigeration", "Air compressor", "Rooftop Solar", "Engineering",
    "B2B", "Bread", "Donut", "Silo", "DG", "GG"
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

# ==============================================================================
# TOP-LEVEL APPLICATION ASSEMBLY INTERFACES
# ==============================================================================

def get_dashboard_data(workbook: dict[str, pd.DataFrame], start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
    return build_dashboard(workbook, start_date, end_date)

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

def _build_valid_row_mask(primary_df: pd.DataFrame, readings_matrix: pd.DataFrame, start_date: str | None = None, end_date: str | None = None) -> pd.Series:
    date_series = primary_df.iloc[readings_matrix.index, 1]
    mask = date_series.apply(_is_valid_date_string)
    
    if start_date or end_date:
        start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
        end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None
        
        def in_range(val):
            d = _get_date_object(val)
            if not d: return False
            if start_dt and d < start_dt: return False
            if end_dt and d > end_dt: return False
            return True
            
        mask = mask & date_series.apply(in_range)
    
    return mask

def build_dashboard(workbook: dict[str, pd.DataFrame], start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
    _validate_workbook(workbook)

    first_sheet_name: str = next(iter(workbook))
    primary_df: pd.DataFrame = workbook[first_sheet_name]

    start_idx: int = _excel_col_to_index(START_COL_NAME)
    end_idx: int = _excel_col_to_index(END_COL_NAME)

    max_col_idx = primary_df.shape[1] - 1
    if start_idx > max_col_idx:
        raise ValueError(f"Workbook structure error: Start column '{START_COL_NAME}' is beyond the available worksheet width.")
    
    effective_end_idx = min(end_idx, max_col_idx)
    _validate_boundaries(primary_df, start_idx, effective_end_idx)

    engineering_block: pd.DataFrame = primary_df.iloc[:, start_idx : effective_end_idx + 1].copy()
    _validate_headers(engineering_block)

    dept_headers: pd.Series = engineering_block.iloc[0].ffill()
    meter_headers: pd.Series = engineering_block.iloc[1]
    
    readings_matrix: pd.DataFrame = engineering_block.iloc[2:]

    valid_row_mask = _build_valid_row_mask(primary_df, readings_matrix, start_date, end_date)
    
    available_dates: list[str] = []
    date_series_b = primary_df.iloc[readings_matrix.index, 1]
    filtered_date_series = date_series_b[valid_row_mask]
    
    for val in filtered_date_series:
        d = _get_date_string(val)
        if d: available_dates.append(d)
            
    available_months: list[str] = sorted(list({date_str[:7] for date_str in available_dates}))

    # CREATE FILTERED OVERVIEW FOR CHARTS & DAILY TRENDS
    filtered_overview = engineering_block.iloc[:2].copy()
    filtered_readings = readings_matrix[valid_row_mask]
    filtered_overview = pd.concat([filtered_overview, filtered_readings])

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
    for dept_name, col_info in dept_columns_map.items():
        meta: dict[str, Any] = dept_metadata_collector[dept_name]
        
        positions = [info[0] for info in col_info]
        new_names = [info[1] for info in col_info]
        
        dept_df = readings_matrix.iloc[:, positions].copy()
        dept_df.columns = new_names
        
        meters_list: list[str] = new_names
        units_map: dict[str, str] = meta["units_map"]

        latest_values: dict[str, Any] = {}
        total_values: dict[str, Any] = {}
        average_values: dict[str, Any] = {}
        channels: dict[str, dict[str, Any]] = {}

        valid_dept_df = dept_df[valid_row_mask]
        
        # INJECT DATE COLUMN FOR PERFECT CHART ALIGNMENT
        chart_df = valid_dept_df.copy()
        chart_df.insert(0, "Date", filtered_date_series.values)

        for meter in meters_list:
            series: pd.Series = valid_dept_df[meter]
            
            latest_val = _calculate_latest_valid_value(series)
            total_val = _calculate_sum(series)
            avg_val = _calculate_mean(series)
            
            latest_values[meter] = latest_val
            total_values[meter] = total_val
            average_values[meter] = avg_val
            
            history_df = pd.DataFrame()
            if not series.empty:
                final_dates = filtered_date_series.values
                final_vals = series.values
                if len(final_dates) > 0:
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

    air_compressor_obj: dict[str, Any] | None = departments_payload.get("Air compressor")
    freon_obj: dict[str, Any] | None = departments_payload.get("Freon Refrigeration")
    ammonia_obj: dict[str, Any] | None = departments_payload.get("Ammonia Refrigeration")

    freon_sheet_df: pd.DataFrame | None = _find_sheet_by_keywords(workbook, ("freon",))
    ammonia_sheet_df: pd.DataFrame | None = _find_sheet_by_keywords(workbook, ("ammonia",))

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

    return {
        "overview": filtered_overview, # NOW FILTERED
        "departments": departments_payload,
        "air_compressor": air_compressor_obj["dataframe"] if air_compressor_obj else None,
        "freon": freon_sheet_df if freon_sheet_df is not None else (freon_obj["dataframe"] if freon_obj else None),
        "ammonia": ammonia_sheet_df if ammonia_sheet_df is not None else (ammonia_obj["dataframe"] if ammonia_obj else None),
        "summary": summary_payload, "filters": filters_payload, "metadata": metadata_payload,
        "navigation": [{"key": k, "label": k, "available": True} for k in departments_payload.keys()],
        "sheet_names": list(workbook.keys()), "months": available_months, "dates": available_dates,
        "latest_values": summary_payload["latest_values"],
        "totals": summary_payload["total_values"], "averages": summary_payload["average_values"],
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
