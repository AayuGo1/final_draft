"""Reusable Plotly chart service for the Engineering Monitoring Dashboard.

This module acts as the definitive data visualization layer for the dashboard.
It consumes structured datasets exposed by ``dashboard_data.py`` and processes
them into production-grade Plotly figures. It adheres to an industrial dark 
theme optimized for premium Power BI style executive reporting.
"""

from __future__ import annotations

import datetime
import warnings
from typing import Any

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

# Dark Theme Visualization Parameters
DEFAULT_TEMPLATE: str = "plotly_dark"
DEFAULT_HOVER_MODE: str = "x unified"
DEFAULT_DATE_COLUMN_LABEL: str = "Date"
DEFAULT_COLOR_SEQUENCE: list[str] = THEME_CHART_PALETTE


# ==============================================================================
# DATA PREPARATION & SANITIZATION HELPERS
# ==============================================================================


def validate_columns(dataframe: pd.DataFrame, columns: list[str]) -> None:
    """Validate that the target column identifiers exist in the DataFrame.

    Raises:
        ValueError: If columns are missing or type checks fail.
    """
    if not isinstance(dataframe, pd.DataFrame):
        raise ValueError(f"Expected pandas.DataFrame, got {type(dataframe).__name__}.")
    
    missing = [col for col in columns if col not in dataframe.columns]
    if missing:
        raise ValueError(f"Columns not found in the matrix workspace: {missing}.")


def prepare_numeric_columns(dataframe: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Safely coerce non-numeric string data, spaces, and formula errors to NaN values."""
    validate_columns(dataframe, columns)
    prepared = dataframe.copy()
    for column in columns:
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    return prepared


def find_first_numeric_column(dataframe: pd.DataFrame) -> str | None:
    """Identify the first non-empty column populated with valid numbers."""
    if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
        return None
    for column in dataframe.columns:
        if pd.to_numeric(dataframe[column], errors="coerce").notna().any():
            return column
    return None


def align_dates_with_meter(
    overview_dataframe: pd.DataFrame,
    meter_series: pd.Series,
    date_column_label: str = DEFAULT_DATE_COLUMN_LABEL,
) -> pd.DataFrame | None:
    """Map timeline dates against telemetry logs, stripping formula anomalies."""
    if not isinstance(overview_dataframe, pd.DataFrame) or overview_dataframe.empty:
        return None
    if meter_series is None or meter_series.dropna().empty:
        return None

    date_cols = get_date_columns(overview_dataframe)
    if not date_cols:
        return None

    # Dates are verified and parsed out starting from index 3 onwards
    date_values = overview_dataframe.iloc[3:, date_cols[0]].reset_index(drop=True)
    meter_values = meter_series.reset_index(drop=True)

    row_count = min(len(date_values), len(meter_values))
    if row_count == 0:
        return None

    meter_name = meter_series.name or "Value"
    
    # Bundle matching historical rows cleanly
    trend_df = pd.DataFrame({
        date_column_label: date_values.iloc[:row_count].values,
        meter_name: meter_values.iloc[:row_count].values,
    })
    
    # Coerce metric points while preserving original timeline format
    trend_df[meter_name] = pd.to_numeric(trend_df[meter_name], errors="coerce")
    trend_df = trend_df.dropna(subset=[date_column_label, meter_name])

    return trend_df if not trend_df.empty else None


def _align_dates_with_multiple_meters(
    overview_dataframe: pd.DataFrame,
    dataframe_block: pd.DataFrame,
    columns: list[str],
    date_column_label: str = DEFAULT_DATE_COLUMN_LABEL,
) -> pd.DataFrame | None:
    """Internal helper to align a date index series with multiple target metrics columns.
    
    Prevents presentation layers from manually executing date resolution mappings.
    """
    if not isinstance(overview_dataframe, pd.DataFrame) or overview_dataframe.empty:
        return None
    if not isinstance(dataframe_block, pd.DataFrame) or dataframe_block.empty or not columns:
        return None

    date_cols = get_date_columns(overview_dataframe)
    if not date_cols:
        return None

    date_values = overview_dataframe.iloc[3:, date_cols[0]].reset_index(drop=True)
    row_count = min(len(date_values), len(dataframe_block))
    if row_count == 0:
        return None

    compiled_df = pd.DataFrame({date_column_label: date_values.iloc[:row_count].values})
    
    for col in columns:
        if col in dataframe_block.columns:
            compiled_df[col] = pd.to_numeric(dataframe_block[col].iloc[:row_count].reset_index(drop=True), errors="coerce")

    compiled_df = compiled_df.dropna(subset=[date_column_label])
    return compiled_df if not compiled_df.empty else None


def build_section_trend_data(
    overview_dataframe: pd.DataFrame,
    section: dict[str, Any],
    date_column_label: str = DEFAULT_DATE_COLUMN_LABEL,
) -> tuple[pd.DataFrame, str, str] | None:
    """Extract chart-ready alignment rows for a specific department structure."""
    if not section or "dataframe" not in section:
        return None

    meters_df = section["dataframe"]
    if not isinstance(meters_df, pd.DataFrame) or meters_df.empty:
        return None

    meter_col = find_first_numeric_column(meters_df)
    if meter_col is None:
        return None

    trend_df = align_dates_with_meter(
        overview_dataframe,
        meters_df[meter_col],
        date_column_label=date_column_label,
    )
    if trend_df is None:
        return None

    return trend_df, date_column_label, meter_col


def build_section_trend_chart(
    overview_dataframe: pd.DataFrame,
    section: dict[str, Any],
    date_column_label: str = DEFAULT_DATE_COLUMN_LABEL,
) -> go.Figure | None:
    """Build a styled, timeline trend chart for a target department section."""
    try:
        trend_data = build_section_trend_data(
            overview_dataframe, section, date_column_label=date_column_label
        )
        if trend_data is None:
            return None

        trend_df, date_col, meter_col = trend_data
        unit_suffix = section.get("units", {}).get(meter_col, "")
        y_axis_title = f"{meter_col} ({unit_suffix})" if unit_suffix else meter_col

        return create_line_chart(
            trend_df,
            x_column=date_col,
            y_column=meter_col,
            title=f"{section.get('name', 'Department')} - {meter_col} Trend",
            x_label=date_col,
            y_label=y_axis_title,
        )
    except Exception:
        return None


# ==============================================================================
# SPECIALIZED BUSINESS COMPONENT HELPERS
# ==============================================================================


def create_department_multi_line_chart(
    overview_dataframe: pd.DataFrame,
    section: dict[str, Any],
    title: str,
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure | None:
    """Extract, align, and construct a multi-series figure for a specific department section.

    Args:
        overview_dataframe: Raw master overview workbook slice for calendar dates discovery.
        section: Formatted department structure object dictionary from dashboard_data layers.
        title: Descriptive diagram banner text string.
        x_label: Optional label signature parameter configuration for the x-axis track.
        y_label: Optional label signature parameter configuration for the y-axis track.

    Returns:
        A production-grade, dark-themed industrial multi-line telemetry Plotly graph.
    """
    if not section or "dataframe" not in section or "meters" not in section:
        return None

    dept_df = section["dataframe"]
    meters = section["meters"]

    if not isinstance(dept_df, pd.DataFrame) or dept_df.empty or not meters:
        return None

    # Discover and resolve only active numeric columns, filtering out text metrics channels
    numeric_meters = [
        col for col in meters if col in dept_df.columns and pd.to_numeric(dept_df[col], errors="coerce").notna().any()
    ]
    if not numeric_meters:
        return None

    # Enforce chronological master vector context tracking layout alignments strictly
    aligned_df = _align_dates_with_multiple_meters(
        overview_dataframe=overview_dataframe,
        dataframe_block=dept_df,
        columns=numeric_meters,
        date_column_label=DEFAULT_DATE_COLUMN_LABEL
    )
    if aligned_df is None or aligned_df.empty:
        return None

    return create_multi_line_chart(
        dataframe=aligned_df,
        x_column=DEFAULT_DATE_COLUMN_LABEL,
        y_columns=numeric_meters,
        title=title,
        x_label=x_label,
        y_label=y_label
    )


# ==============================================================================
# PREMIUM DARK VISUALIZATION THEME LAYOUTS
# ==============================================================================


def apply_default_layout(
    figure: go.Figure,
    title: str,
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure:
    """Inject a Power BI quality engineering dark styling template into a figure."""
    figure.update_layout(
        title={
            "text": title,
            "font": {"size": 16, "color": THEME_TEXT_COLOR, "family": THEME_FONT},
            "y": 0.95,
            "x": 0.02,
            "xanchor": "left",
            "yanchor": "top",
        },
        template=DEFAULT_TEMPLATE,
        hovermode=DEFAULT_HOVER_MODE,
        showlegend=True,
        autosize=True,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 50, "r": 30, "t": 80, "b": 50},
        font={"family": THEME_FONT, "color": THEME_TEXT_COLOR},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0.02,
            "bgcolor": "rgba(0,0,0,0)",
            "font": {"size": 11, "color": THEME_TEXT_COLOR},
        },
    )

    grid_style = {"gridcolor": "rgba(255, 255, 255, 0.08)", "zerolinecolor": "rgba(255, 255, 255, 0.15)"}
    
    if x_label is not None:
        figure.update_xaxes(title_text=x_label, title_font={"size": 12}, **grid_style)
    else:
        figure.update_xaxes(**grid_style)
        
    if y_label is not None:
        figure.update_yaxes(title_text=y_label, title_font={"size": 12}, **grid_style)
    else:
        figure.update_yaxes(**grid_style)

    return figure


def apply_minimal_layout(figure: go.Figure) -> go.Figure:
    """Format a stripped compact visualization suitable for inline card displays."""
    figure.update_layout(
        template=DEFAULT_TEMPLATE,
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 2, "r": 2, "t": 2, "b": 2},
        xaxis={"visible": False, "showgrid": False},
        yaxis={"visible": False, "showgrid": False},
        autosize=True,
    )
    return figure


# ==============================================================================
# CORE REUSABLE CHART INTERFACES
# ==============================================================================


def create_line_chart(
    dataframe: pd.DataFrame,
    x_column: str,
    y_column: str,
    title: str,
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure | None:
    """Create a single-series time timeline line chart."""
    try:
        validate_columns(dataframe, [x_column, y_column])
        prepared = prepare_numeric_columns(dataframe, [y_column]).dropna(subset=[y_column])
        if prepared.empty:
            return None

        figure = px.line(
            prepared,
            x=x_column,
            y=y_column,
            color_discrete_sequence=[THEME_PRIMARY_COLOR],
        )
        figure.update_traces(line={"width": 2.5}, mode="lines")
        
        return apply_default_layout(
            figure,
            title=title,
            x_label=x_label or x_column,
            y_label=y_label or y_column,
        )
    except Exception:
        return None


def create_multi_line_chart(
    dataframe: pd.DataFrame,
    x_column: str,
    y_columns: list[str],
    title: str,
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure | None:
    """Create a high-performance multi-line trend comparison visualization."""
    try:
        if not y_columns:
            return None
        validate_columns(dataframe, [x_column, *y_columns])
        prepared = prepare_numeric_columns(dataframe, y_columns)
        
        figure = px.line(
            prepared,
            x=x_column,
            y=y_columns,
            color_discrete_sequence=DEFAULT_COLOR_SEQUENCE,
        )
        figure.update_traces(line={"width": 2.0}, mode="lines")
        
        return apply_default_layout(
            figure,
            title=title,
            x_label=x_label or x_column,
            y_label=y_label or "Readings",
        )
    except Exception:
        return None


def create_trend_comparison_chart(
    dataframe: pd.DataFrame,
    x_column: str,
    y_columns: list[str],
    title: str,
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure | None:
    """Semantic abstraction layer over multi-line plots for comparing telemetry logs."""
    return create_multi_line_chart(dataframe, x_column, y_columns, title, x_label, y_label)


def create_bar_chart(
    dataframe: pd.DataFrame,
    x_column: str,
    y_columns: str | list[str],
    title: str,
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure | None:
    """Generate side-by-side grouped or individual bar metrics."""
    try:
        cols_list = [y_columns] if isinstance(y_columns, str) else y_columns
        if not cols_list:
            return None
        validate_columns(dataframe, [x_column, *cols_list])
        prepared = prepare_numeric_columns(dataframe, cols_list)

        figure = px.bar(
            prepared,
            x=x_column,
            y=y_columns,
            barmode="group",
            color_discrete_sequence=DEFAULT_COLOR_SEQUENCE,
        )
        
        return apply_default_layout(
            figure,
            title=title,
            x_label=x_label or x_column,
            y_label=y_label or (cols_list[0] if len(cols_list) == 1 else "Value"),
        )
    except Exception:
        return None


def create_stacked_bar_chart(
    dataframe: pd.DataFrame,
    x_column: str,
    y_columns: list[str],
    title: str,
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure | None:
    """Create a stacked distribution bar chart representing composite loads."""
    try:
        if not y_columns:
            return None
        validate_columns(dataframe, [x_column, *y_columns])
        prepared = prepare_numeric_columns(dataframe, y_columns)

        figure = px.bar(
            prepared,
            x=x_column,
            y=y_columns,
            barmode="stack",
            color_discrete_sequence=DEFAULT_COLOR_SEQUENCE,
        )
        
        return apply_default_layout(
            figure,
            title=title,
            x_label=x_label or x_column,
            y_label=y_label or "Total Load",
        )
    except Exception:
        return None


def create_area_chart(
    dataframe: pd.DataFrame,
    x_column: str,
    y_columns: str | list[str],
    title: str,
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure | None:
    """Generate stacked area profiles representing continuous resource logs."""
    try:
        cols_list = [y_columns] if isinstance(y_columns, str) else y_columns
        if not cols_list:
            return None
        validate_columns(dataframe, [x_column, *cols_list])
        prepared = prepare_numeric_columns(dataframe, cols_list)

        figure = px.area(
            prepared,
            x=x_column,
            y=y_columns,
            color_discrete_sequence=DEFAULT_COLOR_SEQUENCE,
        )
        
        return apply_default_layout(
            figure,
            title=title,
            x_label=x_label or x_column,
            y_label=y_label or "Accumulated Value",
        )
    except Exception:
        return None


def create_pie_chart(
    dataframe: pd.DataFrame,
    names_column: str,
    values_column: str,
    title: str,
) -> go.Figure | None:
    """Generate structural distribution breakdown wheels."""
    try:
        validate_columns(dataframe, [names_column, values_column])
        prepared = prepare_numeric_columns(dataframe, [values_column]).dropna(subset=[values_column])
        if prepared.empty:
            return None

        figure = px.pie(
            prepared,
            names=names_column,
            values=values_column,
            color_discrete_sequence=DEFAULT_COLOR_SEQUENCE,
        )
        figure.update_traces(textposition="inside", textinfo="percent+label")
        
        return apply_default_layout(figure, title=title)
    except Exception:
        return None


def create_donut_chart(
    dataframe: pd.DataFrame,
    names_column: str,
    values_column: str,
    title: str,
    hole_size: float = 0.5,
) -> go.Figure | None:
    """Create a hollow donut composition tracking distribution chart."""
    try:
        validate_columns(dataframe, [names_column, values_column])
        prepared = prepare_numeric_columns(dataframe, [values_column]).dropna(subset=[values_column])
        if prepared.empty:
            return None

        figure = px.pie(
            prepared,
            names=names_column,
            values=values_column,
            hole=hole_size,
            color_discrete_sequence=DEFAULT_COLOR_SEQUENCE,
        )
        figure.update_traces(textposition="inside", textinfo="percent+label")
        
        return apply_default_layout(figure, title=title)
    except Exception:
        return None


def create_gauge_chart(
    value: float,
    title: str,
    minimum: float = 0.0,
    maximum: float = 100.0,
    warning_threshold: float | None = None,
    danger_threshold: float | None = None,
    unit: str = "",
) -> go.Figure | None:
    """Build premium operational instrumentation gauge indicators."""
    try:
        if pd.isna(value) or value is None:
            return None

        steps = []
        band_start = minimum

        if warning_threshold is not None and warning_threshold > minimum:
            steps.append({"range": [band_start, warning_threshold], "color": "rgba(46, 204, 113, 0.15)"})
            band_start = warning_threshold

        if danger_threshold is not None and danger_threshold > band_start:
            steps.append({"range": [band_start, danger_threshold], "color": "rgba(245, 166, 35, 0.15)"})
            band_start = danger_threshold

        if band_start < maximum:
            steps.append({"range": [band_start, maximum], "color": "rgba(231, 76, 60, 0.15)"})

        figure = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=value,
                number={"suffix": f" {unit}".rstrip() if unit else "", "font": {"size": 28, "color": THEME_TEXT_COLOR}},
                gauge={
                    "axis": {"range": [minimum, maximum], "tickwidth": 1, "tickcolor": THEME_TEXT_COLOR},
                    "bar": {"color": THEME_PRIMARY_COLOR, "width": 12},
                    "bgcolor": "rgba(255,255,255,0.03)",
                    "borderwidth": 1,
                    "bordercolor": "rgba(255,255,255,0.1)",
                    "steps": steps if steps else None,
                },
            )
        )

        figure.update_layout(
            title={
                "text": title,
                "font": {"size": 14, "color": THEME_TEXT_COLOR, "family": THEME_FONT},
                "y": 0.9,
                "x": 0.5,
                "xanchor": "center",
                "yanchor": "top",
            },
            template=DEFAULT_TEMPLATE,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin={"l": 30, "r": 30, "t": 50, "b": 30},
            autosize=True,
        )

        return figure
    except Exception:
        return None


def create_scatter_chart(
    dataframe: pd.DataFrame,
    x_column: str,
    y_column: str,
    title: str,
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure | None:
    """Generate cross-correlation operational telemetry scatter matrices."""
    try:
        validate_columns(dataframe, [x_column, y_column])
        prepared = prepare_numeric_columns(dataframe, [x_column, y_column]).dropna(subset=[x_column, y_column])
        if prepared.empty:
            return None

        figure = px.scatter(
            prepared,
            x=x_column,
            y=y_column,
            color_discrete_sequence=[THEME_PRIMARY_COLOR],
        )
        
        return apply_default_layout(
            figure,
            title=title,
            x_label=x_label or x_column,
            y_label=y_label or y_column,
        )
    except Exception:
        return None


def create_histogram(
    dataframe: pd.DataFrame,
    x_column: str,
    title: str,
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure | None:
    """Plot distribution profiles representing historical load frequencies."""
    try:
        validate_columns(dataframe, [x_column])
        prepared = prepare_numeric_columns(dataframe, [x_column]).dropna(subset=[x_column])
        if prepared.empty:
            return None

        figure = px.histogram(
            prepared,
            x=x_column,
            color_discrete_sequence=[THEME_PRIMARY_COLOR],
        )
        figure.update_layout(bargap=0.05)
        
        return apply_default_layout(
            figure,
            title=title,
            x_label=x_label or x_column,
            y_label=y_label or "Count",
        )
    except Exception:
        return None


def create_heatmap(
    dataframe: pd.DataFrame,
    columns: list[str] | None = None,
    title: str = "Heatmap",
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure | None:
    """Generate dense diagnostic parameter correlation matrices across profiles."""
    try:
        if not isinstance(dataframe, pd.DataFrame):
            return None

        if columns is None:
            columns = [
                col
                for col in dataframe.columns
                if pd.to_numeric(dataframe[col], errors="coerce").notna().any()
            ]

        if not columns:
            return None

        prepared = prepare_numeric_columns(dataframe, columns)
        
        figure = go.Figure(
            data=go.Heatmap(
                z=prepared[columns].to_numpy().T,
                x=list(range(len(prepared))),
                y=columns,
                colorscale="Viridis",
                showscale=True,
            )
        )

        return apply_default_layout(
            figure,
            title=title,
            x_label=x_label or "Observation Index",
            y_label=y_label or "Meter Channel",
        )
    except Exception:
        return None


def create_sparkline(
    values: pd.Series,
    line_color: str = THEME_PRIMARY_COLOR,
) -> go.Figure | None:
    """Render a clean micro-sparkline block missing margins for embedded layouts."""
    try:
        if values is None or values.empty:
            return None
            
        numeric_values = pd.to_numeric(values, errors="coerce").dropna()
        if numeric_values.empty:
            return None

        figure = go.Figure(
            data=go.Scatter(
                x=list(range(len(numeric_values))),
                y=numeric_values,
                mode="lines",
                line={"color": line_color, "width": 1.5},
                fill="tozeroy",
                fillcolor=f"rgba{tuple(list(int(line_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + [0.08])}",
            )
        )

        return apply_minimal_layout(figure)
    except Exception:
        return None


def create_kpi_trend(
    dataframe: pd.DataFrame,
    x_column: str,
    y_column: str,
    title: str,
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure | None:
    """Semantic alternate line visualization mapping rolling performance trajectories."""
    return create_line_chart(dataframe, x_column, y_column, title, x_label, y_label)
