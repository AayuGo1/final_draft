"""Reusable Plotly chart service for the Engineering Monitoring Dashboard.

This module acts as the definitive data visualization layer for the dashboard.
It consumes structured datasets exposed by ``dashboard_data.py`` and processes
them into production-grade Plotly figures. It adheres to an industrial dark 
theme optimized for premium Power BI style executive reporting.
"""

from __future__ import annotations

import datetime
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

# ==============================================================================
# PREMIUM SCADA VISUALIZATION CONSTANTS
# ==============================================================================

DEFAULT_TEMPLATE: str = "plotly_dark"
DEFAULT_HOVER_MODE: str = "x unified"
DEFAULT_DATE_COLUMN_LABEL: str = "Date"
DEFAULT_COLOR_SEQUENCE: list[str] = THEME_CHART_PALETTE

SCADA_PALETTE: Final[list[str]] = [
    "#00D4FF", "#7B61FF", "#00E676", "#FFB300", "#FF5252",
    "#36A2EB", "#FF6384", "#4BC0C0", "#9966FF", "#FF9F40",
]

FONT_FAMILY: Final[str] = THEME_FONT or "'Inter', 'Segoe UI', system-ui, sans-serif"
FONT_COLOR: Final[str] = THEME_TEXT_COLOR or "#E2E8F0"
FONT_MUTED: Final[str] = "#64748B"
FONT_BRIGHT: Final[str] = "#F8FAFC"

GRID_COLOR: Final[str] = "rgba(148, 163, 184, 0.08)"
ZEROLINE_COLOR: Final[str] = "rgba(148, 163, 184, 0.15)"
AXIS_LINE_COLOR: Final[str] = "rgba(148, 163, 184, 0.12)"

CHART_BG: Final[str] = "rgba(0,0,0,0)"
PAPER_BG: Final[str] = "rgba(0,0,0,0)"


# ==============================================================================
# DATA PREPARATION & SANITIZATION HELPERS
# ==============================================================================

def validate_columns(dataframe: pd.DataFrame, columns: list[str]) -> None:
    if not isinstance(dataframe, pd.DataFrame):
        raise ValueError(f"Expected pandas.DataFrame, got {type(dataframe).__name__}.")
    missing = [col for col in columns if col not in dataframe.columns]
    if missing:
        raise ValueError(f"Columns not found in the matrix workspace: {missing}.")

def prepare_numeric_columns(dataframe: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    validate_columns(dataframe, columns)
    prepared = dataframe.copy()
    for column in columns:
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    return prepared

def find_first_numeric_column(dataframe: pd.DataFrame) -> str | None:
    if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
        return None
    for column in dataframe.columns:
        if pd.to_numeric(dataframe[column], errors="coerce").notna().any():
            return column
    return None

def align_dates_with_meter(
    overview_dataframe: pd.DataFrame, meter_series: pd.Series,
    date_column_label: str = DEFAULT_DATE_COLUMN_LABEL,
) -> pd.DataFrame | None:
    if not isinstance(overview_dataframe, pd.DataFrame) or overview_dataframe.empty:
        return None
    if meter_series is None or meter_series.dropna().empty:
        return None

    date_cols = get_date_columns(overview_dataframe)
    if not date_cols:
        return None

    date_values = overview_dataframe.iloc[3:, date_cols[0]].reset_index(drop=True)
    meter_values = meter_series.reset_index(drop=True)
    row_count = min(len(date_values), len(meter_values))
    if row_count == 0:
        return None

    meter_name = meter_series.name or "Value"
    trend_df = pd.DataFrame({
        date_column_label: date_values.iloc[:row_count].values,
        meter_name: meter_values.iloc[:row_count].values,
    })
    trend_df[meter_name] = pd.to_numeric(trend_df[meter_name], errors="coerce")
    trend_df = trend_df.dropna(subset=[date_column_label, meter_name])
    return trend_df if not trend_df.empty else None

def _align_dates_with_multiple_meters(
    overview_dataframe: pd.DataFrame, dataframe_block: pd.DataFrame,
    columns: list[str], date_column_label: str = DEFAULT_DATE_COLUMN_LABEL,
) -> pd.DataFrame | None:
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
            compiled_df[col] = pd.to_numeric(
                dataframe_block[col].iloc[:row_count].reset_index(drop=True), errors="coerce"
            )
    compiled_df = compiled_df.dropna(subset=[date_column_label])
    return compiled_df if not compiled_df.empty else None

def build_section_trend_data(
    overview_dataframe: pd.DataFrame, section: dict[str, Any],
    date_column_label: str = DEFAULT_DATE_COLUMN_LABEL,
) -> tuple[pd.DataFrame, str, str] | None:
    if not section or "dataframe" not in section:
        return None
    meters_df = section["dataframe"]
    if not isinstance(meters_df, pd.DataFrame) or meters_df.empty:
        return None
    meter_col = find_first_numeric_column(meters_df)
    if meter_col is None:
        return None
    trend_df = align_dates_with_meter(
        overview_dataframe, meters_df[meter_col], date_column_label=date_column_label,
    )
    return (trend_df, date_column_label, meter_col) if trend_df is not None else None

def build_section_trend_chart(
    overview_dataframe: pd.DataFrame, section: dict[str, Any],
    date_column_label: str = DEFAULT_DATE_COLUMN_LABEL,
) -> go.Figure | None:
    try:
        trend_data = build_section_trend_data(overview_dataframe, section, date_column_label=date_column_label)
        if trend_data is None:
            return None
        trend_df, date_col, meter_col = trend_data
        unit_suffix = section.get("units", {}).get(meter_col, "")
        y_axis_title = f"{meter_col} ({unit_suffix})" if unit_suffix else meter_col
        return create_line_chart(
            trend_df, x_column=date_col, y_column=meter_col,
            title=f"{section.get('name', 'Department')} — {meter_col} Trend",
            x_label=date_col, y_label=y_axis_title,
        )
    except Exception:
        return None

def create_department_multi_line_chart(
    overview_dataframe: pd.DataFrame, section: dict[str, Any], title: str,
    x_label: str | None = None, y_label: str | None = None,
) -> go.Figure | None:
    if not section or "dataframe" not in section or "meters" not in section:
        return None
    dept_df = section["dataframe"]
    meters = section["meters"]
    if not isinstance(dept_df, pd.DataFrame) or dept_df.empty or not meters:
        return None
    numeric_meters = [
        col for col in meters
        if col in dept_df.columns and pd.to_numeric(dept_df[col], errors="coerce").notna().any()
    ]
    if not numeric_meters:
        return None
    aligned_df = _align_dates_with_multiple_meters(
        overview_dataframe=overview_dataframe, dataframe_block=dept_df,
        columns=numeric_meters, date_column_label=DEFAULT_DATE_COLUMN_LABEL,
    )
    if aligned_df is None or aligned_df.empty:
        return None
    return create_multi_line_chart(
        dataframe=aligned_df, x_column=DEFAULT_DATE_COLUMN_LABEL,
        y_columns=numeric_meters, title=title, x_label=x_label, y_label=y_label,
    )


# ==============================================================================
# PREMIUM DARK SCADA THEME LAYOUTS
# ==============================================================================

def apply_default_layout(
    figure: go.Figure, title: str, x_label: str | None = None, y_label: str | None = None,
) -> go.Figure:
    figure.update_layout(
        title={"text": title, "font": {"size": 15, "color": FONT_BRIGHT, "family": FONT_FAMILY, "weight": "bold"}, "y": 0.97, "x": 0.015, "xanchor": "left", "yanchor": "top"},
        template=DEFAULT_TEMPLATE, hovermode=DEFAULT_HOVER_MODE,
        hoverlabel={"bgcolor": "rgba(15, 23, 42, 0.95)", "bordercolor": "rgba(0, 212, 255, 0.3)", "font": {"family": FONT_FAMILY, "size": 12, "color": FONT_BRIGHT}, "namelength": -1},
        showlegend=True, autosize=True, paper_bgcolor=PAPER_BG, plot_bgcolor=CHART_BG,
        margin={"l": 55, "r": 25, "t": 75, "b": 55},
        font={"family": FONT_FAMILY, "color": FONT_COLOR, "size": 11},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0.0, "bgcolor": "rgba(0,0,0,0)", "bordercolor": "rgba(0,0,0,0)", "font": {"size": 11, "color": FONT_COLOR, "family": FONT_FAMILY}, "itemsizing": "constant", "itemwidth": 40},
        xaxis={"gridcolor": GRID_COLOR, "zerolinecolor": ZEROLINE_COLOR, "linecolor": AXIS_LINE_COLOR, "linewidth": 1, "showline": True, "showgrid": True, "tickfont": {"size": 10, "color": FONT_MUTED}, "title_font": {"size": 11, "color": FONT_COLOR}, "hoverformat": "%b %d, %Y"},
        yaxis={"gridcolor": GRID_COLOR, "zerolinecolor": ZEROLINE_COLOR, "linecolor": AXIS_LINE_COLOR, "linewidth": 1, "showline": True, "showgrid": True, "tickfont": {"size": 10, "color": FONT_MUTED}, "title_font": {"size": 11, "color": FONT_COLOR}},
        colorway=SCADA_PALETTE,
    )
    if x_label is not None: figure.update_xaxes(title_text=x_label)
    if y_label is not None: figure.update_yaxes(title_text=y_label)
    return figure

def apply_minimal_layout(figure: go.Figure) -> go.Figure:
    figure.update_layout(
        template=DEFAULT_TEMPLATE, showlegend=False, paper_bgcolor=PAPER_BG, plot_bgcolor=CHART_BG,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        xaxis={"visible": False, "showgrid": False, "fixedrange": True},
        yaxis={"visible": False, "showgrid": False, "fixedrange": True}, autosize=True,
    )
    return figure


# ==============================================================================
# CORE REUSABLE CHART INTERFACES
# ==============================================================================

def create_line_chart(dataframe: pd.DataFrame, x_column: str, y_column: str, title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    try:
        validate_columns(dataframe, [x_column, y_column])
        prepared = prepare_numeric_columns(dataframe, [y_column]).dropna(subset=[y_column])
        if prepared.empty: return None
        figure = go.Figure()
        figure.add_trace(go.Scatter(x=prepared[x_column], y=prepared[y_column], mode="lines", name=y_column, line={"color": SCADA_PALETTE[0], "width": 2.5, "shape": "spline", "smoothing": 1.1}, fill="tozeroy", fillcolor="rgba(0, 212, 255, 0.06)", hovertemplate=f"<b>%{{x}}</b><br>{y_column}: %{{y:,.2f}}<extra></extra>"))
        figure.add_trace(go.Scatter(x=prepared[x_column], y=prepared[y_column], mode="markers", name=y_column, marker={"color": SCADA_PALETTE[0], "size": 4, "opacity": 0.5, "line": {"width": 0}}, showlegend=False, hoverinfo="skip"))
        return apply_default_layout(figure, title=title, x_label=x_label or x_column, y_label=y_label or y_column)
    except Exception: return None

def create_multi_line_chart(dataframe: pd.DataFrame, x_column: str, y_columns: list[str], title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    try:
        if not y_columns: return None
        validate_columns(dataframe, [x_column, *y_columns])
        prepared = prepare_numeric_columns(dataframe, y_columns)
        figure = go.Figure()
        for i, col in enumerate(y_columns):
            color = SCADA_PALETTE[i % len(SCADA_PALETTE)]
            figure.add_trace(go.Scatter(x=prepared[x_column], y=prepared[col], mode="lines", name=col, line={"color": color, "width": 2.0, "shape": "spline", "smoothing": 1.0}, hovertemplate=f"<b>%{{x}}</b><br>{col}: %{{y:,.2f}}<extra></extra>", connectgaps=True))
        fig = apply_default_layout(figure, title=title, x_label=x_label or x_column, y_label=y_label or "Readings")
        fig.update_xaxes(rangeslider={"visible": False}, rangeselector=dict(buttons=list([dict(count=7, label="1W", step="day", stepmode="backward"), dict(count=1, label="1M", step="month", stepmode="backward"), dict(count=3, label="3M", step="month", stepmode="backward"), dict(step="all", label="ALL")]), bgcolor="rgba(30, 41, 59, 0.5)", activecolor="rgba(0, 212, 255, 0.2)", bordercolor="rgba(148, 163, 184, 0.15)", borderwidth=1, font={"color": FONT_COLOR, "size": 10, "family": FONT_FAMILY}, x=0.0, y=1.14))
        return fig
    except Exception: return None

def create_bar_chart(dataframe: pd.DataFrame, x_column: str, y_columns: str | list[str], title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    try:
        cols_list = [y_columns] if isinstance(y_columns, str) else y_columns
        if not cols_list: return None
        validate_columns(dataframe, [x_column, *cols_list])
        prepared = prepare_numeric_columns(dataframe, cols_list)
        figure = px.bar(prepared, x=x_column, y=y_columns, barmode="group", color_discrete_sequence=SCADA_PALETTE)
        figure.update_traces(marker_line_width=0, opacity=0.9, hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y:,.2f}<extra></extra>")
        return apply_default_layout(figure, title=title, x_label=x_label or x_column, y_label=y_label or (cols_list[0] if len(cols_list) == 1 else "Value"))
    except Exception: return None

def create_stacked_bar_chart(dataframe: pd.DataFrame, x_column: str, y_columns: list[str], title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    try:
        if not y_columns: return None
        validate_columns(dataframe, [x_column, *y_columns])
        prepared = prepare_numeric_columns(dataframe, y_columns)
        figure = px.bar(prepared, x=x_column, y=y_columns, barmode="stack", color_discrete_sequence=SCADA_PALETTE)
        figure.update_traces(marker_line_width=0, opacity=0.9, hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y:,.2f}<extra></extra>")
        return apply_default_layout(figure, title=title, x_label=x_label or x_column, y_label=y_label or "Total Load")
    except Exception: return None

def create_area_chart(dataframe: pd.DataFrame, x_column: str, y_columns: str | list[str], title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    try:
        cols_list = [y_columns] if isinstance(y_columns, str) else y_columns
        if not cols_list: return None
        validate_columns(dataframe, [x_column, *cols_list])
        prepared = prepare_numeric_columns(dataframe, cols_list)
        figure = px.area(prepared, x=x_column, y=y_columns, color_discrete_sequence=SCADA_PALETTE)
        figure.update_traces(line={"width": 1.5}, opacity=0.7, hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y:,.2f}<extra></extra>")
        return apply_default_layout(figure, title=title, x_label=x_label or x_column, y_label=y_label or "Accumulated Value")
    except Exception: return None

def create_pie_chart(dataframe: pd.DataFrame, names_column: str, values_column: str, title: str) -> go.Figure | None:
    try:
        validate_columns(dataframe, [names_column, values_column])
        prepared = prepare_numeric_columns(dataframe, [values_column]).dropna(subset=[values_column])
        if prepared.empty: return None
        figure = px.pie(prepared, names=names_column, values=values_column, color_discrete_sequence=SCADA_PALETTE)
        figure.update_traces(textposition="inside", textinfo="percent+label", marker={"line": {"color": "rgba(15, 23, 42, 0.8)", "width": 2}}, hovertemplate="<b>%{label}</b><br>Value: %{value:,.2f}<br>Share: %{percent}<extra></extra>")
        return apply_default_layout(figure, title=title)
    except Exception: return None

def create_donut_chart(dataframe: pd.DataFrame, names_column: str, values_column: str, title: str, hole_size: float = 0.5) -> go.Figure | None:
    try:
        validate_columns(dataframe, [names_column, values_column])
        prepared = prepare_numeric_columns(dataframe, [values_column]).dropna(subset=[values_column])
        if prepared.empty: return None
        figure = px.pie(prepared, names=names_column, values=values_column, hole=hole_size, color_discrete_sequence=SCADA_PALETTE)
        figure.update_traces(textposition="inside", textinfo="percent+label", marker={"line": {"color": "rgba(15, 23, 42, 0.8)", "width": 2}}, hovertemplate="<b>%{label}</b><br>Value: %{value:,.2f}<br>Share: %{percent}<extra></extra>")
        return apply_default_layout(figure, title=title)
    except Exception: return None

def create_gauge_chart(value: float, title: str, minimum: float = 0.0, maximum: float = 100.0, warning_threshold: float | None = None, danger_threshold: float | None = None, unit: str = "") -> go.Figure | None:
    try:
        if pd.isna(value) or value is None: return None
        steps = []
        band_start = minimum
        range_span = maximum - minimum if maximum > minimum else 1.0
        green_end = minimum + range_span * 0.60
        steps.append({"range": [band_start, green_end], "color": "rgba(0, 230, 118, 0.12)"})
        band_start = green_end
        yellow_end = minimum + range_span * 0.80
        steps.append({"range": [band_start, yellow_end], "color": "rgba(255, 179, 0, 0.12)"})
        band_start = yellow_end
        steps.append({"range": [band_start, maximum], "color": "rgba(255, 82, 82, 0.12)"})
        if warning_threshold is not None and danger_threshold is not None:
            steps = []
            if warning_threshold > minimum: steps.append({"range": [minimum, warning_threshold], "color": "rgba(0, 230, 118, 0.12)"})
            if danger_threshold > warning_threshold: steps.append({"range": [warning_threshold, danger_threshold], "color": "rgba(255, 179, 0, 0.12)"})
            if maximum > danger_threshold: steps.append({"range": [danger_threshold, maximum], "color": "rgba(255, 82, 82, 0.12)"})
        unit_suffix = f" {unit}".strip() if unit else ""
        figure = go.Figure(go.Indicator(mode="gauge+number+delta", value=value, delta={"reference": value * 0.95 if value else 0, "position": "bottom", "font": {"size": 12, "color": FONT_MUTED, "family": FONT_FAMILY}, "valueformat": ".1f", "increasing": {"color": THEME_SUCCESS_COLOR or "#00E676"}, "decreasing": {"color": THEME_DANGER_COLOR or "#FF5252"}}, number={"suffix": f" {unit_suffix}" if unit_suffix else "", "font": {"size": 30, "color": FONT_BRIGHT, "family": FONT_FAMILY}, "valueformat": ",.1f"}, gauge={"axis": {"range": [minimum, maximum], "tickwidth": 1, "tickcolor": FONT_MUTED, "tickfont": {"size": 9, "color": FONT_MUTED, "family": FONT_FAMILY}, "ticklen": 6, "nticks": 8}, "bar": {"color": SCADA_PALETTE[0], "thickness": 0.18, "line": {"color": "rgba(0, 212, 255, 0.4)", "width": 1}}, "bgcolor": "rgba(255,255,255,0.02)", "borderwidth": 1, "bordercolor": "rgba(148, 163, 184, 0.1)", "steps": steps, "threshold": {"line": {"color": SCADA_PALETTE[0], "width": 3}, "thickness": 0.8, "value": value}}))
        figure.update_layout(title={"text": title, "font": {"size": 13, "color": FONT_COLOR, "family": FONT_FAMILY}, "y": 0.92, "x": 0.5, "xanchor": "center", "yanchor": "top"}, template=DEFAULT_TEMPLATE, paper_bgcolor=PAPER_BG, plot_bgcolor=CHART_BG, margin={"l": 25, "r": 25, "t": 55, "b": 20}, autosize=True, font={"family": FONT_FAMILY})
        return figure
    except Exception: return None

def create_scatter_chart(dataframe: pd.DataFrame, x_column: str, y_column: str, title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    try:
        validate_columns(dataframe, [x_column, y_column])
        prepared = prepare_numeric_columns(dataframe, [x_column, y_column]).dropna(subset=[x_column, y_column])
        if prepared.empty: return None
        figure = go.Figure(go.Scatter(x=prepared[x_column], y=prepared[y_column], mode="markers", marker={"color": SCADA_PALETTE[0], "size": 7, "opacity": 0.7, "line": {"width": 1, "color": "rgba(0, 212, 255, 0.3)"}}, hovertemplate=f"{x_column}: %{{x:,.2f}}<br>{y_column}: %{{y:,.2f}}<extra></extra>"))
        return apply_default_layout(figure, title=title, x_label=x_label or x_column, y_label=y_label or y_column)
    except Exception: return None

def create_histogram(dataframe: pd.DataFrame, x_column: str, title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    try:
        validate_columns(dataframe, [x_column])
        prepared = prepare_numeric_columns(dataframe, [x_column]).dropna(subset=[x_column])
        if prepared.empty: return None
        figure = px.histogram(prepared, x=x_column, color_discrete_sequence=[SCADA_PALETTE[0]])
        figure.update_layout(bargap=0.04)
        figure.update_traces(marker_line_width=0, opacity=0.85, hovertemplate="Range: %{x}<br>Count: %{y}<extra></extra>")
        return apply_default_layout(figure, title=title, x_label=x_label or x_column, y_label=y_label or "Count")
    except Exception: return None

def create_heatmap(dataframe: pd.DataFrame, columns: list[str] | None = None, title: str = "Heatmap", x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    try:
        if not isinstance(dataframe, pd.DataFrame): return None
        if columns is None: columns = [col for col in dataframe.columns if pd.to_numeric(dataframe[col], errors="coerce").notna().any()]
        if not columns: return None
        prepared = prepare_numeric_columns(dataframe, columns)
        figure = go.Figure(data=go.Heatmap(z=prepared[columns].to_numpy().T, x=list(range(len(prepared))), y=columns, colorscale=[[0.0, "rgba(15, 23, 42, 0.9)"], [0.25, "rgba(0, 100, 180, 0.6)"], [0.5, "rgba(0, 212, 255, 0.7)"], [0.75, "rgba(255, 179, 0, 0.7)"], [1.0, "rgba(255, 82, 82, 0.8)"]], showscale=True, colorbar={"tickfont": {"size": 9, "color": FONT_MUTED}, "outlinewidth": 0, "thickness": 12, "len": 0.8}, hovertemplate="Index: %{x}<br>Channel: %{y}<br>Value: %{z:,.2f}<extra></extra>"))
        return apply_default_layout(figure, title=title, x_label=x_label or "Observation Index", y_label=y_label or "Meter Channel")
    except Exception: return None

def create_sparkline(values: pd.Series, line_color: str = THEME_PRIMARY_COLOR) -> go.Figure | None:
    try:
        if values is None or values.empty: return None
        numeric_values = pd.to_numeric(values, errors="coerce").dropna()
        if numeric_values.empty: return None
        resolved_color = line_color or SCADA_PALETTE[0]
        try:
            r = int(resolved_color.lstrip("#")[0:2], 16); g = int(resolved_color.lstrip("#")[2:4], 16); b = int(resolved_color.lstrip("#")[4:6], 16)
            fill_rgba = f"rgba({r}, {g}, {b}, 0.10)"
        except Exception: fill_rgba = "rgba(0, 212, 255, 0.10)"
        figure = go.Figure(data=go.Scatter(x=list(range(len(numeric_values))), y=numeric_values, mode="lines", line={"color": resolved_color, "width": 1.8, "shape": "spline", "smoothing": 1.2}, fill="tozeroy", fillcolor=fill_rgba))
        return apply_minimal_layout(figure)
    except Exception: return None

def create_kpi_trend(dataframe: pd.DataFrame, x_column: str, y_column: str, title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    return create_line_chart(dataframe, x_column, y_column, title, x_label, y_label)


# ==============================================================================
# NEW ENTERPRISE CHART INTERFACES
# ==============================================================================

def create_radar_chart(dataframe: pd.DataFrame, columns: list[str], title: str) -> go.Figure | None:
    """Create a radar/spider chart for multi-metric comparison."""
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
        categories = list(columns) + [columns[0]]
        values = normalized + [normalized[0]]
        fig = go.Figure(data=go.Scatterpolar(r=values, theta=categories, fill='toself', fillcolor='rgba(0, 212, 255, 0.15)', line=dict(color=SCADA_PALETTE[0], width=2), marker=dict(size=6, color=SCADA_PALETTE[0])))
        fig.update_layout(
            polar=dict(bgcolor='rgba(0,0,0,0)', radialaxis=dict(visible=True, range=[0, 100], gridcolor=GRID_COLOR, tickfont=dict(size=9, color=FONT_MUTED)), angularaxis=dict(gridcolor=GRID_COLOR, tickfont=dict(size=10, color=FONT_COLOR))),
            showlegend=False, title={"text": title, "font": {"size": 14, "color": FONT_BRIGHT, "family": FONT_FAMILY}, "y": 0.95, "x": 0.5, "xanchor": "center", "yanchor": "top"},
            paper_bgcolor=PAPER_BG, plot_bgcolor=CHART_BG, margin=dict(l=60, r=60, t=60, b=60), font=dict(family=FONT_FAMILY, color=FONT_COLOR),
        )
        return fig
    except Exception: return None

def create_waterfall_chart(dataframe: pd.DataFrame, x_column: str, y_column: str, title: str) -> go.Figure | None:
    """Create a waterfall chart for cumulative/step data."""
    try:
        validate_columns(dataframe, [x_column, y_column])
        prepared = prepare_numeric_columns(dataframe, [y_column]).dropna(subset=[y_column])
        if prepared.empty: return None
        fig = go.Figure(go.Waterfall(x=prepared[x_column], y=prepared[y_column], measure="relative", connector={"line": {"color": "rgba(148, 163, 184, 0.2)", "width": 1}}, decreasing={"marker": {"color": SCADA_PALETTE[4]}}, increasing={"marker": {"color": SCADA_PALETTE[0]}}, totals={"marker": {"color": SCADA_PALETTE[1]}}, hovertemplate="<b>%{x}</b><br>Value: %{y:,.2f}<extra></extra>"))
        return apply_default_layout(fig, title=title, x_label=x_column, y_label=y_column)
    except Exception: return None

def create_combined_line_area_chart(dataframe: pd.DataFrame, x_column: str, area_column: str, line_column: str, title: str) -> go.Figure | None:
    """Create a combined line and area chart."""
    try:
        validate_columns(dataframe, [x_column, area_column, line_column])
        prepared = prepare_numeric_columns(dataframe, [area_column, line_column]).dropna(subset=[x_column])
        if prepared.empty: return None
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=prepared[x_column], y=prepared[area_column], fill='tozeroy', mode='lines', name=area_column, line=dict(color=SCADA_PALETTE[0], width=1), fillcolor='rgba(0, 212, 255, 0.1)'))
        fig.add_trace(go.Scatter(x=prepared[x_column], y=prepared[line_column], mode='lines+markers', name=line_column, line=dict(color=SCADA_PALETTE[1], width=2.5, shape='spline'), marker=dict(size=5, color=SCADA_PALETTE[1])))
        return apply_default_layout(fig, title=title, x_label=x_column)
    except Exception: return None

def create_horizontal_bar_chart(dataframe: pd.DataFrame, x_column: str, y_column: str, title: str) -> go.Figure | None:
    """Create a horizontal bar chart."""
    try:
        validate_columns(dataframe, [x_column, y_column])
        prepared = prepare_numeric_columns(dataframe, [y_column]).dropna(subset=[y_column])
        if prepared.empty: return None
        fig = px.bar(prepared, x=y_column, y=x_column, orientation='h', color_discrete_sequence=[SCADA_PALETTE[0]])
        fig.update_traces(marker_line_width=0, opacity=0.85, hovertemplate="<b>%{y}</b><br>%{x:,.2f}<extra></extra>")
        return apply_default_layout(fig, title=title, x_label=y_column, y_label=x_column)
    except Exception: return None

def create_bullet_chart(actual: float, target: float, title: str, unit: str = "") -> go.Figure | None:
    """Create a bullet chart for target vs actual."""
    try:
        if pd.isna(actual) or pd.isna(target): return None
        max_val = max(actual, target) * 1.2 if max(actual, target) > 0 else 100
        fig = go.Figure()
        fig.add_trace(go.Bar(x=[max_val], y=[title], orientation='h', marker=dict(color='rgba(255, 255, 255, 0.03)'), hoverinfo='skip', showlegend=False))
        fig.add_trace(go.Scatter(x=[target, target], y=[title, title], mode='lines', line=dict(color=SCADA_PALETTE[3], width=3), name='Target', hoverinfo='name+x'))
        fig.add_trace(go.Bar(x=[actual], y=[title], orientation='h', marker=dict(color=SCADA_PALETTE[0], opacity=0.8), name='Actual', hovertemplate=f"Actual: %{{x:,.2f}} {unit}<extra></extra>"))
        fig.update_layout(barmode='overlay', title={"text": title, "font": {"size": 14, "color": FONT_BRIGHT, "family": FONT_FAMILY}, "y": 0.9, "x": 0.5, "xanchor": "center", "yanchor": "top"}, xaxis=dict(range=[0, max_val], gridcolor=GRID_COLOR, zerolinecolor=ZEROLINE_COLOR, tickfont=dict(size=10, color=FONT_MUTED)), yaxis=dict(showticklabels=False, showgrid=False, zeroline=False), showlegend=False, paper_bgcolor=PAPER_BG, plot_bgcolor=CHART_BG, margin=dict(l=20, r=20, t=50, b=30), font=dict(family=FONT_FAMILY, color=FONT_COLOR))
        return fig
    except Exception: return None

def create_sparkline_card(series: pd.Series, title: str, value: Any, unit: str = "") -> str:
    """Generate HTML for a mini sparkline KPI card."""
    try:
        numeric_series = pd.to_numeric(series, errors='coerce').dropna()
        if numeric_series.empty:
            val_display = "N/A"
            spark_html = ""
        else:
            val_display = f"{numeric_series.iloc[-1]:,.2f}"
            min_v = numeric_series.min()
            max_v = numeric_series.max()
            range_v = max_v - min_v if max_v > min_v else 1
            points = []
            width = 100
            height = 30
            step = width / (len(numeric_series) - 1) if len(numeric_series) > 1 else width
            for i, v in enumerate(numeric_series):
                x = i * step
                y = height - ((v - min_v) / range_v * height)
                points.append(f"{x:.1f},{y:.1f}")
            path_d = "M" + " L".join(points)
            spark_html = f"""
            <svg width="100%" height="40" viewBox="0 0 {width} {height}" preserveAspectRatio="none" style="margin-top: 8px;">
                <path d="{path_d}" fill="none" stroke="{SCADA_PALETTE[0]}" stroke-width="1.5" opacity="0.8"/>
                <path d="{path_d} L{width},{height} L0,{height} Z" fill="url(#sparkGrad)" opacity="0.2"/>
                <defs><linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="{SCADA_PALETTE[0]}"/><stop offset="100%" stop-color="transparent"/></linearGradient></defs>
            </svg>"""
        return f"""<div class="metric-card-container" style="padding: 12px 16px;"><p class="metric-card-title">{title}</p><p class="metric-card-value" style="font-size: 1.2rem;">{val_display} <span style="font-size: 0.7rem; color: #64748B;">{unit}</span></p>{spark_html}</div>"""
    except Exception: return ""
