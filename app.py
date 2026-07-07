# filepath: services/filter_service.py
"""Filtering and Context Preparation Service for the Engineering Monitoring Dashboard.

This service acts as an abstraction layer between the raw analytical data models
and the presentation views. It performs immutable temporal slicing, delegates
KPI recalculation, and packages the result into a strict contextual dataclass.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any

import pandas as pd

from dashboard_data import get_date_columns
import services.kpi_service as kpi_service


@dataclass(frozen=True)
class DepartmentContext:
    """Immutable data transfer object encapsulating an operational department state."""
    department_dataframe: pd.DataFrame
    overview_dataframe: pd.DataFrame
    latest_values: dict[str, Any]
    average_values: dict[str, float | None]
    total_values: dict[str, float | None]
    latest_timestamp: str
    active_meter_count: int


def prepare_department_context(
    dept_obj: dict[str, Any],
    overview_df: pd.DataFrame,
    summary: dict[str, Any],
    selected_month: str,
    selected_date: str,
) -> DepartmentContext:
    """Orchestrate temporal filtering and operational context resolution for a department.

    Args:
        dept_obj: The raw structural department dictionary mapping.
        overview_df: Master chronological tracking overview slice.
        summary: Global system KPI operational boundary dictionary.
        selected_month: Target filtering month identifier ("YYYY-MM" or "All").
        selected_date: Target filtering exact date identifier ("YYYY-MM-DD" or "All").

    Returns:
        An immutable `DepartmentContext` dataclass populated with filtered assets.
    """
    raw_dept_df = dept_obj.get("dataframe", pd.DataFrame())
    meters = dept_obj.get("meters", [])

    is_unfiltered = (selected_month in ("All", "N/A", "")) and (selected_date in ("All", "N/A", ""))

    if is_unfiltered:
        return _prepare_unfiltered_context(dept_obj, raw_dept_df, overview_df, summary)

    # Resolve alignment mapping temporal bounds
    date_cols = get_date_columns(overview_df)
    if not date_cols or overview_df.shape[0] <= 3 or raw_dept_df.empty:
        return _prepare_unfiltered_context(dept_obj, raw_dept_df, overview_df, summary)

    parsed_dates = _resolve_date_series(overview_df, date_cols[0])
    
    # Construct binary chronological constraint map array
    temporal_mask = _build_temporal_mask(parsed_dates, selected_month, selected_date)

    filtered_dept_df = _filter_department_dataframe(raw_dept_df, temporal_mask)
    filtered_overview_df = _filter_overview_dataframe(overview_df, temporal_mask)

    latest_vals, avg_vals, total_vals, active_count = _recalculate_kpis(filtered_dept_df, meters)

    latest_ts_display = _resolve_latest_timestamp(filtered_dept_df, parsed_dates, temporal_mask)

    return DepartmentContext(
        department_dataframe=filtered_dept_df,
        overview_dataframe=filtered_overview_df,
        latest_values=latest_vals,
        average_values=avg_vals,
        total_values=total_vals,
        latest_timestamp=latest_ts_display,
        active_meter_count=active_count,
    )


# ==============================================================================
# PRIVATE DOMAIN HELPERS
# ==============================================================================


def _prepare_unfiltered_context(
    dept_obj: dict[str, Any],
    raw_dept_df: pd.DataFrame,
    overview_df: pd.DataFrame,
    summary: dict[str, Any]
) -> DepartmentContext:
    """Extract standard fallback presentation layers avoiding recalculation loops."""
    latest_vals = dept_obj.get("latest_values", {})
    active_count = sum(1 for v in latest_vals.values() if v is not None)

    latest_ts_raw = summary.get("latest_timestamp", "N/A")
    if isinstance(latest_ts_raw, str):
        latest_ts_display = latest_ts_raw.split()[0] if " " in latest_ts_raw else latest_ts_raw
    elif hasattr(latest_ts_raw, "strftime"):
        latest_ts_display = latest_ts_raw.strftime("%Y-%m-%d")
    else:
        latest_ts_display = "N/A"

    return DepartmentContext(
        department_dataframe=raw_dept_df,
        overview_dataframe=overview_df,
        latest_values=latest_vals,
        average_values=dept_obj.get("average_values", {}),
        total_values=dept_obj.get("total_values", {}),
        latest_timestamp=latest_ts_display,
        active_meter_count=active_count,
    )


def _resolve_date_series(overview_df: pd.DataFrame, target_col_idx: int) -> pd.Series:
    """Isolate and coerce the structural timestamp anchor axis safely."""
    raw_dates = overview_df.iloc[3:, target_col_idx].reset_index(drop=True)
    return pd.to_datetime(raw_dates, errors="coerce")


def _build_temporal_mask(
    parsed_dates: pd.Series, selected_month: str, selected_date: str
) -> pd.Series:
    """Generate boolean tracking index arrays for performance-optimized slicing."""
    mask = pd.Series(True, index=parsed_dates.index)
    
    if selected_date not in ("All", "N/A", ""):
        mask &= (parsed_dates.dt.strftime("%Y-%m-%d") == selected_date)
    elif selected_month not in ("All", "N/A", ""):
        mask &= (parsed_dates.dt.strftime("%Y-%m") == selected_month)
        
    return mask


def _filter_department_dataframe(raw_dept_df: pd.DataFrame, temporal_mask: pd.Series) -> pd.DataFrame:
    """Isolate chronological telemetry matrix boundaries mapping safely."""
    mask_vals = temporal_mask.values[:len(raw_dept_df)]
    return raw_dept_df[mask_vals].reset_index(drop=True)


def _filter_overview_dataframe(overview_df: pd.DataFrame, temporal_mask: pd.Series) -> pd.DataFrame:
    """Extract and compile master context tracking parameters preserving legacy structural headers."""
    header_rows = overview_df.iloc[:3]
    mask_vals = temporal_mask.values[:(overview_df.shape[0] - 3)]
    
    data_rows = overview_df.iloc[3:].reset_index(drop=True)[mask_vals]
    return pd.concat([header_rows, data_rows]).reset_index(drop=True)


def _recalculate_kpis(filtered_dept_df: pd.DataFrame, meters: list[str]) -> tuple[dict, dict, dict, int]:
    """Execute clean arithmetic derivations routing exclusively through kpi_service."""
    latest_vals = {}
    avg_vals = {}
    total_vals = {}
    
    for m in meters:
        series = filtered_dept_df[m] if m in filtered_dept_df.columns else pd.Series(dtype=float)
        
        latest_vals[m] = kpi_service.get_latest_value(series)
        avg_vals[m] = kpi_service.calculate_average(series)
        total_vals[m] = _calculate_sum(series)

    active_count = sum(1 for v in latest_vals.values() if v is not None)
    
    return latest_vals, avg_vals, total_vals, active_count


def _calculate_sum(series: pd.Series) -> float | None:
    """Compute local vectorized calculation matching kpi_service internal parameters."""
    numeric_series = pd.to_numeric(series, errors="coerce").dropna()
    return float(numeric_series.sum()) if not numeric_series.empty else None


def _resolve_latest_timestamp(
    filtered_dept_df: pd.DataFrame, parsed_dates: pd.Series, temporal_mask: pd.Series
) -> str:
    """Resolve and format the highest valid chronological coordinate constraint."""
    valid_dates = parsed_dates[temporal_mask].dropna()
    
    if not filtered_dept_df.empty and not valid_dates.empty:
        return valid_dates.max().strftime("%Y-%m-%d")
    return "N/A"
