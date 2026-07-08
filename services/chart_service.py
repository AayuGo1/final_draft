"""Reusable Plotly chart service for the Engineering Monitoring Dashboard.
ARCHITECTURE NOTE: This service ONLY plots. It assumes input DataFrames are 
already cleaned, aligned, and validated by the caller.
"""
from __future__ import annotations

import datetime
import logging
import warnings
from typing import Any, Final

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config import (
    THEME_BACKGROUND_COLOR,
    THEME_CHART_PALETTE,
    THEME_DANGER_COLOR,
    THEME_FONT,
    THEME_PRIMARY_COLOR,
    THEME_SECONDARY_BACKGROUND_COLOR,
    THEME_SUCCESS_COLOR,
    THEME_TEXT_COLOR,
    THEME_WARNING_COLOR,
)
from dashboard_data import get_date_columns

# Setup logger
logger = logging.getLogger(__name__)

# Updated Theme Constants for Dark Mode Charts
DEFAULT_TEMPLATE: str = "plotly_dark"
DEFAULT_HOVER_MODE: str = "x unified"
DEFAULT_DATE_COLUMN_LABEL: str = "Date"

SCADA_PALETTE: Final[list[str]] = [
    "#3B82F6", "#10B981", "#F59E0B", "#EF4444", 
    "#8B5CF6", "#EC4899", "#06B6D4", "#84CC16"
]

BG_APP = "#0B0D12"
BG_CARD = "#111827"
BG_HOVER = "#1F2937"
BORDER_SUBTLE = "#1F2937"
TEXT_PRIMARY = "#F9FAFB"
TEXT_SECONDARY = "#9CA3AF"
TEXT_MUTED = "#6B7280"
GRID_COLOR = "rgba(255,255,255,0.04)"
ZERO_COLOR = "rgba(255,255,255,0.08)"

FONT_FAMILY: Final[str] = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"


def validate_columns(dataframe: pd.DataFrame, columns: list[str]) -> None:
    """Validate that the specified columns exist in the dataframe."""
    if not isinstance(dataframe, pd.DataFrame):
        raise ValueError(f"Expected pandas.DataFrame, got {type(dataframe).__name__}.")
    if dataframe.empty:
        raise ValueError("DataFrame is empty.")
    
    # Get actual column names as strings for comparison
    actual_cols = [str(c) for c in dataframe.columns]
    missing = [col for col in columns if str(col) not in actual_cols]
    
    if missing:
        raise ValueError(f"Columns not found in the dataframe: {missing}. Available: {list(dataframe.columns)}")


def prepare_numeric_columns(dataframe: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Convert specified columns to numeric types."""
    validate_columns(dataframe, columns)
    prepared = dataframe.copy()
    for column in columns:
        # Use the original column object for indexing, but ensure it exists
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
        else:
            # Fallback for string matching if exact object match failed
            for col in prepared.columns:
                if str(col) == str(column):
                    prepared[col] = pd.to_numeric(prepared[col], errors="coerce")
                    break
    return prepared


def find_first_numeric_column(dataframe: pd.DataFrame) -> str | None:
    """
    Find the first column in the dataframe that contains numeric data.
    
    Robustness features:
    - Handles non-string column names (int, float, tuple, Timestamp, etc.)
    - Handles MultiIndex columns by flattening to string representation.
    - Safely skips date-like columns without crashing on non-string types.
    - Verifies numeric content using pd.to_numeric.
    """
    if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
        return None

    # Define date-like keywords to skip (case-insensitive)
    date_keywords = {"date", "time", "timestamp", "datetime"}

    for column in dataframe.columns:
        try:
            # 1. Safe String Conversion for checking keywords
            # This handles int, float, tuple, Timestamp, etc. column names
            col_str = str(column).lower().strip()
            
            # 2. Skip likely date/time columns based on name
            if any(keyword in col_str for keyword in date_keywords):
                continue

            # 3. Check if column has any valid numeric data
            # pd.to_numeric with coerce will turn non-numeric into NaN
            numeric_series = pd.to_numeric(dataframe[column], errors="coerce")
            
            if numeric_series.notna().any():
                # Return the ORIGINAL column object (not the string) to ensure 
                # correct indexing in subsequent operations
                return column
                
        except Exception as e:
            # If a specific column causes an error (e.g. complex object), skip it
            logger.debug(f"Skipping column {column} due to processing error: {e}")
            continue

    return None


def align_dates_with_meter(
    overview_dataframe: pd.DataFrame, meter_series: pd.Series,
    date_column_label: str = DEFAULT_DATE_COLUMN_LABEL,
) -> pd.DataFrame | None:
    """Align a meter series with the date column from the overview dataframe."""
    try:
        if not isinstance(overview_dataframe, pd.DataFrame) or overview_dataframe.empty:
            logger.warning("Overview dataframe is invalid or empty.")
            return None
        if meter_series is None or meter_series.dropna().empty:
            logger.warning("Meter series is invalid or empty.")
            return None

        date_cols = get_date_columns(overview_dataframe)
        if not date_cols:
            logger.warning("No date columns found in overview dataframe.")
            return None

        # Use the first date column
        date_col_name = date_cols[0]
        
        # Ensure date_col_name exists in dataframe
        if date_col_name not in overview_dataframe.columns:
             # Try string matching if exact object failed
             found = False
             for c in overview_dataframe.columns:
                 if str(c) == str(date_col_name):
                     date_col_name = c
                     found = True
                     break
             if not found:
                 logger.warning(f"Date column {date_col_name} not found in overview.")
                 return None

        date_values = overview_dataframe[date_col_name].reset_index(drop=True)
        
        # Align lengths
        min_len = min(len(date_values), len(meter_series))
        if min_len == 0:
            return None
            
        date_values = date_values.iloc[:min_len]
        meter_values = meter_series.iloc[:min_len].reset_index(drop=True)
        
        meter_name = meter_series.name or "Value"
        trend_df = pd.DataFrame({
            date_column_label: date_values.values,
            meter_name: meter_values.values,
        })
        
        # Convert types
        trend_df[date_column_label] = pd.to_datetime(trend_df[date_column_label], errors="coerce")
        trend_df[meter_name] = pd.to_numeric(trend_df[meter_name], errors="coerce")
        
        # Drop rows where either date or value is missing
        initial_rows = len(trend_df)
        trend_df = trend_df.dropna(subset=[date_column_label, meter_name])
        final_rows = len(trend_df)
        
        logger.debug(f"Align Dates: Initial rows={initial_rows}, Final rows={final_rows}")
        
        return trend_df if not trend_df.empty else None
    except Exception as e:
        logger.error(f"Error in align_dates_with_meter: {e}", exc_info=True)
        return None


def _align_dates_with_multiple_meters(
    overview_dataframe: pd.DataFrame, dataframe_block: pd.DataFrame,
    columns: list[str], date_column_label: str = DEFAULT_DATE_COLUMN_LABEL,
) -> pd.DataFrame | None:
    """Align multiple meter series with the date column from the overview dataframe."""
    try:
        if not isinstance(overview_dataframe, pd.DataFrame) or overview_dataframe.empty:
            logger.warning("Overview dataframe is invalid or empty.")
            return None
        if not isinstance(dataframe_block, pd.DataFrame) or dataframe_block.empty or not columns:
            logger.warning("Dataframe block is invalid, empty, or no columns provided.")
            return None

        date_cols = get_date_columns(overview_dataframe)
        if not date_cols:
            logger.warning("No date columns found in overview dataframe.")
            return None

        date_col_name = date_cols[0]
        
        # Ensure date_col_name exists
        if date_col_name not in overview_dataframe.columns:
             found = False
             for c in overview_dataframe.columns:
                 if str(c) == str(date_col_name):
                     date_col_name = c
                     found = True
                     break
             if not found:
                 return None

        date_values = overview_dataframe[date_col_name].reset_index(drop=True)
        
        min_len = min(len(date_values), len(dataframe_block))
        if min_len == 0:
            return None
            
        date_values = date_values.iloc[:min_len]
        
        compiled_df = pd.DataFrame({date_column_label: date_values.values})
        
        for col in columns:
            if col in dataframe_block.columns:
                compiled_df[col] = pd.to_numeric(
                    dataframe_block[col].iloc[:min_len].reset_index(drop=True), errors="coerce"
                )
            else:
                # Try string match
                for c in dataframe_block.columns:
                    if str(c) == str(col):
                        compiled_df[col] = pd.to_numeric(
                            dataframe_block[c].iloc[:min_len].reset_index(drop=True), errors="coerce"
                        )
                        break
        
        # Drop rows where date is missing
        initial_rows = len(compiled_df)
        compiled_df = compiled_df.dropna(subset=[date_column_label])
        final_rows = len(compiled_df)
        
        logger.debug(f"Align Multi-Meter: Initial rows={initial_rows}, Final rows={final_rows}")
        
        return compiled_df if not compiled_df.empty else None
    except Exception as e:
        logger.error(f"Error in _align_dates_with_multiple_meters: {e}", exc_info=True)
        return None


def build_section_trend_data(
    overview_dataframe: pd.DataFrame, section: dict[str, Any],
    date_column_label: str = DEFAULT_DATE_COLUMN_LABEL,
) -> tuple[pd.DataFrame, str, str] | None:
    """Build trend data for a specific section."""
    try:
        if not section or "dataframe" not in section:
            logger.warning("Section is invalid or missing 'dataframe' key.")
            return None
            
        meters_df = section["dataframe"]
        if not isinstance(meters_df, pd.DataFrame) or meters_df.empty:
            logger.warning("Meters dataframe is invalid or empty.")
            return None
            
        meter_col = find_first_numeric_column(meters_df)
        if meter_col is None:
            logger.warning("No numeric column found in meters dataframe.")
            return None
            
        trend_df = align_dates_with_meter(
            overview_dataframe, meters_df[meter_col], date_column_label=date_column_label,
        )
        
        if trend_df is None:
            return None
            
        return (trend_df, date_column_label, str(meter_col))
    except Exception as e:
        logger.error(f"Error in build_section_trend_data: {e}", exc_info=True)
        return None


def build_section_trend_chart(
    overview_dataframe: pd.DataFrame, section: dict[str, Any],
    date_column_label: str = DEFAULT_DATE_COLUMN_LABEL,
) -> go.Figure | None:
    """Build a trend chart for a specific section."""
    try:
        trend_data = build_section_trend_data(overview_dataframe, section, date_column_label=date_column_label)
        if trend_data is None:
            return None
            
        trend_df, date_col, meter_col = trend_data
        
        # Get unit suffix if available
        unit_suffix = ""
        if "units" in section and isinstance(section["units"], dict):
            unit_suffix = section["units"].get(meter_col, "")
            
        y_axis_title = f"{meter_col} ({unit_suffix})" if unit_suffix else meter_col
        
        return create_line_chart(
            trend_df, x_column=date_col, y_column=meter_col,
            title=f"{meter_col} Trend",
            x_label=date_col, y_label=y_axis_title,
        )
    except Exception as e:
        logger.error(f"Error in build_section_trend_chart: {e}", exc_info=True)
        return None


def create_department_multi_line_chart(
    overview_dataframe: pd.DataFrame, section: dict[str, Any], title: str,
    x_label: str | None = None, y_label: str | None = None,
) -> go.Figure | None:
    """Create a multi-line chart for all meters in a department."""
    try:
        if not section or "dataframe" not in section or "meters" not in section:
            logger.warning("Section is invalid or missing required keys.")
            return None
            
        dept_df = section["dataframe"]
        meters = section["meters"]
        
        if not isinstance(dept_df, pd.DataFrame) or dept_df.empty or not meters:
            logger.warning("Department dataframe is invalid/empty or no meters provided.")
            return None
            
        # Filter for numeric meters that exist in the dataframe
        numeric_meters = []
        for col in meters:
            # Check existence safely
            col_exists = col in dept_df.columns
            if not col_exists:
                for c in dept_df.columns:
                    if str(c) == str(col):
                        col_exists = True
                        break
            
            if col_exists:
                try:
                    if pd.to_numeric(dept_df[col], errors="coerce").notna().any():
                        numeric_meters.append(col)
                except:
                    continue
            
        if not numeric_meters:
            logger.warning("No valid numeric meters found.")
            return None
            
        aligned_df = _align_dates_with_multiple_meters(
            overview_dataframe=overview_dataframe, dataframe_block=dept_df,
            columns=numeric_meters, date_column_label=DEFAULT_DATE_COLUMN_LABEL,
        )
        
        if aligned_df is None or aligned_df.empty:
            logger.warning("Aligned dataframe is empty.")
            return None
            
        return create_multi_line_chart(
            dataframe=aligned_df, x_column=DEFAULT_DATE_COLUMN_LABEL,
            y_columns=numeric_meters, title=title, x_label=x_label, y_label=y_label,
        )
    except Exception as e:
        logger.error(f"Error in create_department_multi_line_chart: {e}", exc_info=True)
        return None


def apply_default_layout(
    figure: go.Figure, title: str, x_label: str | None = None, y_label: str | None = None,
) -> go.Figure:
    """Apply the default dark SCADA layout to a Plotly figure."""
    figure.update_layout(
        title={"text": title, "font": {"size": 14, "color": TEXT_SECONDARY, "family": FONT_FAMILY}, "x": 0.01, "y": 0.98, "xanchor": "left", "yanchor": "top"},
        template=DEFAULT_TEMPLATE, hovermode=DEFAULT_HOVER_MODE,
        hoverlabel={"bgcolor": BG_HOVER, "bordercolor": BORDER_SUBTLE, "font": {"family": FONT_FAMILY, "size": 11, "color": TEXT_PRIMARY}},
        showlegend=True, autosize=True, paper_bgcolor=BG_CARD, plot_bgcolor=BG_CARD,
        margin={"l": 40, "r": 20, "t": 50, "b": 40},
        font={"family": FONT_FAMILY, "color": TEXT_SECONDARY, "size": 11},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0.0, "bgcolor": "rgba(0,0,0,0)", "font": {"size": 10, "color": TEXT_SECONDARY, "family": FONT_FAMILY}},
        xaxis={"gridcolor": GRID_COLOR, "zerolinecolor": ZERO_COLOR, "linecolor": BORDER_SUBTLE, "linewidth": 1, "showline": True, "showgrid": True, "tickfont": {"size": 10, "color": TEXT_MUTED}, "title_font": {"size": 11, "color": TEXT_SECONDARY}},
        yaxis={"gridcolor": GRID_COLOR, "zerolinecolor": ZERO_COLOR, "linecolor": BORDER_SUBTLE, "linewidth": 1, "showline": True, "showgrid": True, "tickfont": {"size": 10, "color": TEXT_MUTED}, "title_font": {"size": 11, "color": TEXT_SECONDARY}},
        colorway=SCADA_PALETTE,
    )
    if x_label is not None: figure.update_xaxes(title_text=x_label)
    if y_label is not None: figure.update_yaxes(title_text=y_label)
    return figure


def apply_minimal_layout(figure: go.Figure) -> go.Figure:
    """Apply a minimal layout (no axes, no background) for sparklines."""
    figure.update_layout(
        template=DEFAULT_TEMPLATE, showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        xaxis={"visible": False, "showgrid": False, "fixedrange": True},
        yaxis={"visible": False, "showgrid": False, "fixedrange": True}, autosize=True,
    )
    return figure


def create_line_chart(dataframe: pd.DataFrame, x_column: str, y_column: str, title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    """Create a single line chart. Input DF must be pre-aligned."""
    try:
        logger.debug(f"create_line_chart Input: shape={dataframe.shape}, cols={list(dataframe.columns)}")
        validate_columns(dataframe, [x_column, y_column])
        prepared = prepare_numeric_columns(dataframe, [y_column]).dropna(subset=[y_column])
        logger.debug(f"create_line_chart After Prep: shape={prepared.shape}")
        
        if prepared.empty: 
            logger.warning(f"No data to plot for {y_column}")
            return None
            
        figure = go.Figure()
        figure.add_trace(go.Scatter(
            x=prepared[x_column], 
            y=prepared[y_column], 
            mode="lines", 
            name=str(y_column), 
            line={"color": SCADA_PALETTE[0], "width": 2.5}, 
            fill="tozeroy", 
            fillcolor="rgba(59, 130, 246, 0.1)", 
            hovertemplate=f"<b>%{{x}}</b><br>{y_column}: %{{y:,.2f}}<extra></extra>"
        ))
        return apply_default_layout(figure, title=title, x_label=x_label or str(x_column), y_label=y_label or str(y_column))
    except Exception as e:
        logger.error(f"Error in create_line_chart: {e}", exc_info=True)
        return None


def create_multi_line_chart(dataframe: pd.DataFrame, x_column: str, y_columns: list[str], title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    """Create a multi-line chart. Input DF must be pre-aligned."""
    try:
        if not y_columns: 
            return None
        logger.debug(f"create_multi_line_chart Input: shape={dataframe.shape}, cols={list(dataframe.columns)}")
        validate_columns(dataframe, [x_column, *y_columns])
        prepared = prepare_numeric_columns(dataframe, y_columns)
        
        figure = go.Figure()
        for i, col in enumerate(y_columns):
            # Skip if column has no data after preparation
            if prepared[col].dropna().empty:
                continue
                
            color = SCADA_PALETTE[i % len(SCADA_PALETTE)]
            figure.add_trace(go.Scatter(
                x=prepared[x_column], 
                y=prepared[col], 
                mode="lines", 
                name=str(col), 
                line={"color": color, "width": 2}, 
                hovertemplate=f"<b>%{{x}}</b><br>{col}: %{{y:,.2f}}<extra></extra>"
            ))
            
        if not figure.data:
            logger.warning("No data traces added to multi-line chart.")
            return None
            
        return apply_default_layout(figure, title=title, x_label=x_label or str(x_column), y_label=y_label or "Readings")
    except Exception as e:
        logger.error(f"Error in create_multi_line_chart: {e}", exc_info=True)
        return None


def create_bar_chart(dataframe: pd.DataFrame, x_column: str, y_columns: str | list[str], title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    """Create a bar chart."""
    try:
        cols_list = [y_columns] if isinstance(y_columns, str) else y_columns
        if not cols_list: return None
        validate_columns(dataframe, [x_column, *cols_list])
        prepared = prepare_numeric_columns(dataframe, cols_list)
        figure = px.bar(prepared, x=x_column, y=y_columns, barmode="group", color_discrete_sequence=SCADA_PALETTE)
        figure.update_traces(marker_line_width=0, opacity=0.85)
        return apply_default_layout(figure, title=title, x_label=x_label or str(x_column), y_label=y_label or (str(cols_list[0]) if len(cols_list) == 1 else "Value"))
    except Exception as e:
        logger.error(f"Error in create_bar_chart: {e}", exc_info=True)
        return None


def create_stacked_bar_chart(dataframe: pd.DataFrame, x_column: str, y_columns: list[str], title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    """Create a stacked bar chart."""
    try:
        if not y_columns: return None
        validate_columns(dataframe, [x_column, *y_columns])
        prepared = prepare_numeric_columns(dataframe, y_columns)
        figure = px.bar(prepared, x=x_column, y=y_columns, barmode="stack", color_discrete_sequence=SCADA_PALETTE)
        figure.update_traces(marker_line_width=0, opacity=0.85)
        return apply_default_layout(figure, title=title, x_label=x_label or str(x_column), y_label=y_label or "Total Load")
    except Exception as e:
        logger.error(f"Error in create_stacked_bar_chart: {e}", exc_info=True)
        return None


def create_area_chart(dataframe: pd.DataFrame, x_column: str, y_columns: str | list[str], title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    """Create an area chart."""
    try:
        cols_list = [y_columns] if isinstance(y_columns, str) else y_columns
        if not cols_list: return None
        validate_columns(dataframe, [x_column, *cols_list])
        prepared = prepare_numeric_columns(dataframe, cols_list)
        figure = px.area(prepared, x=x_column, y=y_columns, color_discrete_sequence=SCADA_PALETTE)
        figure.update_traces(line={"width": 1.5}, opacity=0.6)
        return apply_default_layout(figure, title=title, x_label=x_label or str(x_column), y_label=y_label or "Accumulated Value")
    except Exception as e:
        logger.error(f"Error in create_area_chart: {e}", exc_info=True)
        return None


def create_pie_chart(dataframe: pd.DataFrame, names_column: str, values_column: str, title: str) -> go.Figure | None:
    """Create a pie chart."""
    try:
        validate_columns(dataframe, [names_column, values_column])
        prepared = prepare_numeric_columns(dataframe, [values_column]).dropna(subset=[values_column])
        if prepared.empty: return None
        figure = px.pie(prepared, names=names_column, values=values_column, color_discrete_sequence=SCADA_PALETTE)
        figure.update_traces(textposition="inside", textinfo="percent+label", marker={"line": {"color": BG_CARD, "width": 1}})
        return apply_default_layout(figure, title=title)
    except Exception as e:
        logger.error(f"Error in create_pie_chart: {e}", exc_info=True)
        return None


def create_donut_chart(dataframe: pd.DataFrame, names_column: str, values_column: str, title: str, hole_size: float = 0.6) -> go.Figure | None:
    """Create a donut chart."""
    try:
        validate_columns(dataframe, [names_column, values_column])
        prepared = prepare_numeric_columns(dataframe, [values_column]).dropna(subset=[values_column])
        if prepared.empty: return None
        figure = px.pie(prepared, names=names_column, values=values_column, hole=hole_size, color_discrete_sequence=SCADA_PALETTE)
        figure.update_traces(textposition="inside", textinfo="percent+label", marker={"line": {"color": BG_CARD, "width": 1}})
        return apply_default_layout(figure, title=title)
    except Exception as e:
        logger.error(f"Error in create_donut_chart: {e}", exc_info=True)
        return None


def create_gauge_chart(value: float, title: str, minimum: float = 0.0, maximum: float = 100.0, warning_threshold: float | None = None, danger_threshold: float | None = None, unit: str = "") -> go.Figure | None:
    """Create a gauge chart."""
    try:
        if pd.isna(value) or value is None: return None
        steps = []
        band_start = minimum
        range_span = maximum - minimum if maximum > minimum else 1.0
        green_end = minimum + range_span * 0.60
        steps.append({"range": [band_start, green_end], "color": "rgba(16, 185, 129, 0.15)"})
        band_start = green_end
        yellow_end = minimum + range_span * 0.80
        steps.append({"range": [band_start, yellow_end], "color": "rgba(245, 158, 11, 0.15)"})
        band_start = yellow_end
        steps.append({"range": [band_start, maximum], "color": "rgba(239, 68, 68, 0.15)"})
        
        unit_suffix = f" {unit}".strip() if unit else ""
        figure = go.Figure(go.Indicator(
            mode="gauge+number", value=value,
            number={"suffix": f" {unit_suffix}" if unit_suffix else "", "font": {"size": 20, "color": TEXT_PRIMARY, "family": FONT_FAMILY}, "valueformat": ",.1f"},
            gauge={"axis": {"range": [minimum, maximum], "tickwidth": 1, "tickcolor": TEXT_MUTED, "tickfont": {"size": 8, "color": TEXT_MUTED, "family": FONT_FAMILY}, "ticklen": 4, "nticks": 6}, "bar": {"color": SCADA_PALETTE[0], "thickness": 0.15, "line": {"width": 0}}, "bgcolor": BG_CARD, "borderwidth": 1, "bordercolor": BORDER_SUBTLE, "steps": steps}
        ))
        figure.update_layout(title={"text": title, "font": {"size": 10, "color": TEXT_SECONDARY, "family": FONT_FAMILY}, "y": 0.85, "x": 0.5, "xanchor": "center", "yanchor": "top"}, template=DEFAULT_TEMPLATE, paper_bgcolor=BG_CARD, plot_bgcolor=BG_CARD, margin={"l": 20, "r": 20, "t": 35, "b": 20}, autosize=True, font={"family": FONT_FAMILY})
        return figure
    except Exception as e:
        logger.error(f"Error in create_gauge_chart: {e}", exc_info=True)
        return None


def create_scatter_chart(dataframe: pd.DataFrame, x_column: str, y_column: str, title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    """Create a scatter chart."""
    try:
        validate_columns(dataframe, [x_column, y_column])
        prepared = prepare_numeric_columns(dataframe, [x_column, y_column]).dropna(subset=[x_column, y_column])
        if prepared.empty: return None
        figure = go.Figure(go.Scatter(x=prepared[x_column], y=prepared[y_column], mode="markers", marker={"color": SCADA_PALETTE[0], "size": 6, "opacity": 0.7, "line": {"width": 0}}))
        return apply_default_layout(figure, title=title, x_label=x_label or str(x_column), y_label=y_label or str(y_column))
    except Exception as e:
        logger.error(f"Error in create_scatter_chart: {e}", exc_info=True)
        return None


def create_histogram(dataframe: pd.DataFrame, x_column: str, title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    """Create a histogram."""
    try:
        validate_columns(dataframe, [x_column])
        prepared = prepare_numeric_columns(dataframe, [x_column]).dropna(subset=[x_column])
        if prepared.empty: return None
        figure = px.histogram(prepared, x=x_column, color_discrete_sequence=[SCADA_PALETTE[0]])
        figure.update_layout(bargap=0.05)
        figure.update_traces(marker_line_width=0, opacity=0.8)
        return apply_default_layout(figure, title=title, x_label=x_label or str(x_column), y_label=y_label or "Count")
    except Exception as e:
        logger.error(f"Error in create_histogram: {e}", exc_info=True)
        return None


def create_heatmap(dataframe: pd.DataFrame, columns: list[str] | None = None, title: str = "Heatmap", x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    """Create a heatmap. Uses actual dates from DF index or column if available."""
    try:
        if not isinstance(dataframe, pd.DataFrame): return None
        if columns is None: 
            columns = [col for col in dataframe.columns if pd.to_numeric(dataframe[col], errors="coerce").notna().any()]
        if not columns: return None
        
        # Ensure we have a date-like index or column for X-axis
        x_values = list(range(len(dataframe)))
        if "Date" in dataframe.columns:
             x_values = dataframe["Date"].tolist()
        elif isinstance(dataframe.index, pd.DatetimeIndex):
             x_values = dataframe.index.tolist()

        prepared = prepare_numeric_columns(dataframe, columns)
        figure = go.Figure(data=go.Heatmap(
            z=prepared[columns].to_numpy().T, 
            x=x_values, 
            y=[str(c) for c in columns], 
            colorscale=[[0.0, BG_CARD], [0.5, "#1E3A8A"], [1.0, SCADA_PALETTE[0]]], 
            showscale=True, 
            colorbar={"tickfont": {"size": 8, "color": TEXT_MUTED}, "outlinewidth": 0, "thickness": 10, "len": 0.8}
        ))
        return apply_default_layout(figure, title=title, x_label=x_label or "Date", y_label=y_label or "Meter Channel")
    except Exception as e:
        logger.error(f"Error in create_heatmap: {e}", exc_info=True)
        return None


def create_sparkline(values: pd.Series, line_color: str = THEME_PRIMARY_COLOR) -> go.Figure | None:
    """Create a sparkline."""
    try:
        if values is None or values.empty: return None
        numeric_values = pd.to_numeric(values, errors="coerce").dropna()
        if numeric_values.empty: return None
        resolved_color = line_color or SCADA_PALETTE[0]
        figure = go.Figure(data=go.Scatter(x=list(range(len(numeric_values))), y=numeric_values, mode="lines", line={"color": resolved_color, "width": 1.5}, fill="tozeroy", fillcolor="rgba(59, 130, 246, 0.1)"))
        return apply_minimal_layout(figure)
    except Exception as e:
        logger.error(f"Error in create_sparkline: {e}", exc_info=True)
        return None


def create_kpi_trend(dataframe: pd.DataFrame, x_column: str, y_column: str, title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    """Create a KPI trend chart (alias for line chart)."""
    return create_line_chart(dataframe, x_column, y_column, title, x_label, y_label)


def create_radar_chart(dataframe: pd.DataFrame, columns: list[str], title: str) -> go.Figure | None:
    """Create a radar chart."""
    try:
        if not columns: return None
        normalized = []
        for col in columns:
            series = pd.to_numeric(dataframe[col], errors='coerce').dropna()
            if series.empty: normalized.append(0)
            else:
                max_val = series.max()
                latest_val = series.iloc[-1]
                norm_val = (latest_val / max_val * 100) if max_val > 0 else 0
                normalized.append(norm_val)
        categories = [str(c) for c in columns] + [str(columns[0])]
        values = normalized + [normalized[0]]
        fig = go.Figure(data=go.Scatterpolar(r=values, theta=categories, fill='toself', fillcolor='rgba(59, 130, 246, 0.1)', line=dict(color=SCADA_PALETTE[0], width=1.5), marker=dict(size=4, color=SCADA_PALETTE[0])))
        fig.update_layout(
            polar=dict(bgcolor=BG_CARD, radialaxis=dict(visible=True, range=[0, 100], gridcolor=GRID_COLOR, tickfont=dict(size=8, color=TEXT_MUTED)), angularaxis=dict(gridcolor=GRID_COLOR, tickfont=dict(size=9, color=TEXT_SECONDARY))),
            showlegend=False, title={"text": title, "font": {"size": 10, "color": TEXT_PRIMARY, "family": FONT_FAMILY}, "y": 0.95, "x": 0.5, "xanchor": "center", "yanchor": "top"},
            paper_bgcolor=BG_CARD, plot_bgcolor=BG_CARD, margin=dict(l=40, r=40, t=40, b=40), font=dict(family=FONT_FAMILY, color=TEXT_SECONDARY),
        )
        return fig
    except Exception as e:
        logger.error(f"Error in create_radar_chart: {e}", exc_info=True)
        return None


def create_waterfall_chart(dataframe: pd.DataFrame, x_column: str, y_column: str, title: str) -> go.Figure | None:
    """Create a waterfall chart."""
    try:
        validate_columns(dataframe, [x_column, y_column])
        prepared = prepare_numeric_columns(dataframe, [y_column]).dropna(subset=[y_column])
        if prepared.empty: return None
        fig = go.Figure(go.Waterfall(x=prepared[x_column], y=prepared[y_column], measure="relative", connector={"line": {"color": BORDER_SUBTLE, "width": 1}}, decreasing={"marker": {"color": SCADA_PALETTE[3]}}, increasing={"marker": {"color": SCADA_PALETTE[0]}}, totals={"marker": {"color": SCADA_PALETTE[4]}}))
        return apply_default_layout(fig, title=title, x_label=str(x_column), y_label=str(y_column))
    except Exception as e:
        logger.error(f"Error in create_waterfall_chart: {e}", exc_info=True)
        return None


def create_combined_line_area_chart(dataframe: pd.DataFrame, x_column: str, area_column: str, line_column: str, title: str) -> go.Figure | None:
    """Create a combined line and area chart."""
    try:
        validate_columns(dataframe, [x_column, area_column, line_column])
        prepared = prepare_numeric_columns(dataframe, [area_column, line_column]).dropna(subset=[x_column])
        if prepared.empty: return None
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=prepared[x_column], y=prepared[area_column], fill='tozeroy', mode='lines', name=str(area_column), line=dict(color=SCADA_PALETTE[0], width=1), fillcolor='rgba(59, 130, 246, 0.1)'))
        fig.add_trace(go.Scatter(x=prepared[x_column], y=prepared[line_column], mode='lines', name=str(line_column), line=dict(color=SCADA_PALETTE[1], width=2)))
        return apply_default_layout(fig, title=title, x_label=str(x_column))
    except Exception as e:
        logger.error(f"Error in create_combined_line_area_chart: {e}", exc_info=True)
        return None


def create_horizontal_bar_chart(dataframe: pd.DataFrame, x_column: str, y_column: str, title: str) -> go.Figure | None:
    """Create a horizontal bar chart."""
    try:
        validate_columns(dataframe, [x_column, y_column])
        prepared = prepare_numeric_columns(dataframe, [y_column]).dropna(subset=[y_column])
        if prepared.empty: return None
        fig = px.bar(prepared, x=y_column, y=x_column, orientation='h', color_discrete_sequence=[SCADA_PALETTE[0]])
        fig.update_traces(marker_line_width=0, opacity=0.8)
        return apply_default_layout(fig, title=title, x_label=str(y_column), y_label=str(x_column))
    except Exception as e:
        logger.error(f"Error in create_horizontal_bar_chart: {e}", exc_info=True)
        return None


def create_bullet_chart(actual: float, target: float, title: str, unit: str = "") -> go.Figure | None:
    """Create a bullet chart."""
    try:
        if pd.isna(actual) or pd.isna(target): return None
        max_val = max(actual, target) * 1.2 if max(actual, target) > 0 else 100
        fig = go.Figure()
        fig.add_trace(go.Bar(x=[max_val], y=[title], orientation='h', marker=dict(color='rgba(255, 255, 255, 0.02)'), hoverinfo='skip', showlegend=False))
        fig.add_trace(go.Scatter(x=[target, target], y=[title, title], mode='lines', line=dict(color=SCADA_PALETTE[2], width=2), name='Target', hoverinfo='name+x'))
        fig.add_trace(go.Bar(x=[actual], y=[title], orientation='h', marker=dict(color=SCADA_PALETTE[0], opacity=0.8), name='Actual'))
        fig.update_layout(
            barmode='overlay', 
            title={"text": title, "font": {"size": 10, "color": TEXT_PRIMARY, "family": FONT_FAMILY}, "y": 0.9, "x": 0.5, "xanchor": "center", "yanchor": "top"}, 
            xaxis=dict(range=[0, max_val], gridcolor=GRID_COLOR, zerolinecolor=ZERO_COLOR, tickfont=dict(size=9, color=TEXT_MUTED)), 
            yaxis=dict(showticklabels=False, showgrid=False, zeroline=False), 
            showlegend=False, 
            paper_bgcolor=BG_CARD, 
            plot_bgcolor=BG_CARD, 
            margin=dict(l=20, r=20, t=35, b=20), 
            font=dict(family=FONT_FAMILY, color=TEXT_SECONDARY)
        )
        return fig
    except Exception as e:
        logger.error(f"Error in create_bullet_chart: {e}", exc_info=True)
        return None


# ==================================================================
# TASK 6 & 7: Daily Trend Chart & Statistics Helpers
# ==================================================================

def create_daily_trend_chart(
    dataframe: pd.DataFrame, date_column: str, meter_column: str, title: str = "Daily Trend"
) -> go.Figure | None:
    """Create a daily trend chart with zoom, hover, legend, and grid."""
    try:
        validate_columns(dataframe, [date_column, meter_column])
        prepared = prepare_numeric_columns(dataframe, [meter_column]).dropna(subset=[meter_column])
        if prepared.empty:
            return None
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=prepared[date_column], 
            y=prepared[meter_column], 
            mode="lines+markers", 
            name=str(meter_column), 
            line={"color": SCADA_PALETTE[0], "width": 2},
            marker={"size": 4},
            hovertemplate=f"<b>%{{x}}</b><br>{meter_column}: %{{y:,.2f}}<extra></extra>"
        ))
        
        fig.update_layout(
            title={"text": title, "font": {"size": 14, "color": TEXT_PRIMARY, "family": FONT_FAMILY}, "x": 0.02, "y": 0.95},
            template=DEFAULT_TEMPLATE,
            hovermode="x unified",
            showlegend=True,
            xaxis={"title": "Date", "gridcolor": GRID_COLOR, "showgrid": True},
            yaxis={"title": str(meter_column), "gridcolor": GRID_COLOR, "showgrid": True},
            margin={"l": 40, "r": 20, "t": 50, "b": 40},
            paper_bgcolor=BG_CARD,
            plot_bgcolor=BG_CARD,
        )
        return fig
    except Exception as e:
        logger.error(f"Error in create_daily_trend_chart: {e}", exc_info=True)
        return None


def calculate_daily_stats(dataframe: pd.DataFrame, meter_column: str) -> dict[str, Any]:
    """Calculate Average, Maximum, Minimum, and Latest for a specific meter."""
    try:
        numeric_series = pd.to_numeric(dataframe[meter_column], errors="coerce").dropna()
        if numeric_series.empty:
            return {"Average": "—", "Maximum": "—", "Minimum": "—", "Latest": "—"}
        
        return {
            "Average": f"{float(numeric_series.mean()):,.2f}",
            "Maximum": f"{float(numeric_series.max()):,.2f}",
            "Minimum": f"{float(numeric_series.min()):,.2f}",
            "Latest": f"{float(numeric_series.iloc[-1]):,.2f}",
        }
    except Exception as e:
        logger.error(f"Error in calculate_daily_stats: {e}", exc_info=True)
        return {"Average": "—", "Maximum": "—", "Minimum": "—", "Latest": "—"}


def get_daily_trend_figure_and_stats(
    dataframe: pd.DataFrame, meter_column: str, date_column: str
) -> tuple[go.Figure | None, dict[str, Any]]:
    """Get the daily trend figure and stats for a specific meter."""
    fig = create_daily_trend_chart(dataframe, date_column, meter_column, title=f"{meter_column} Daily Trend")
    stats = calculate_daily_stats(dataframe, meter_column)
    return fig, stats
