"""Reusable Plotly chart service for the Engineering Monitoring Dashboard."""
from __future__ import annotations

import datetime
import logging
import warnings
from typing import Any, Final

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config import (
    THEME_BACKGROUND_COLOR, THEME_CHART_PALETTE, THEME_DANGER_COLOR, THEME_FONT,
    THEME_PRIMARY_COLOR, THEME_SECONDARY_BACKGROUND_COLOR, THEME_SUCCESS_COLOR,
    THEME_TEXT_COLOR, THEME_WARNING_COLOR,
)

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE: str = "plotly_white"
DEFAULT_HOVER_MODE: str = "x unified"
DEFAULT_DATE_COLUMN_LABEL: str = "Date"

SCADA_PALETTE: Final[list[str]] = [
    "#005DAA", "#E31E24", "#22C55E", "#F59E0B", "#8B5CF6", "#06B6D4", "#EC4899", "#84CC16"
]

BG_APP = "#F9FAFB"
BG_CARD = "#FFFFFF"
BG_HOVER = "#F3F4F6"
BORDER_SUBTLE = "#E5E7EB"
TEXT_PRIMARY = "#111827"
TEXT_SECONDARY = "#4B5563"
TEXT_MUTED = "#6B7280"
GRID_COLOR = "rgba(0,0,0,0.05)"
ZERO_COLOR = "rgba(0,0,0,0.1)"

FONT_FAMILY: Final[str] = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"

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
    if not isinstance(dataframe, pd.DataFrame) or dataframe.empty: return None
    for column in dataframe.columns:
        if pd.to_numeric(dataframe[column], errors="coerce").notna().any(): return column
    return None

def apply_default_layout(
    figure: go.Figure, title: str, x_label: str | None = None, y_label: str | None = None,
) -> go.Figure:
    figure.update_layout(
        title={"text": title, "font": {"size": 16, "color": TEXT_PRIMARY, "family": FONT_FAMILY, "weight": 600}, "x": 0.01, "y": 0.98, "xanchor": "left", "yanchor": "top"},
        template=DEFAULT_TEMPLATE, hovermode=DEFAULT_HOVER_MODE,
        hoverlabel={"bgcolor": "#FFFFFF", "bordercolor": "#E5E7EB", "font": {"family": FONT_FAMILY, "size": 12, "color": TEXT_PRIMARY}},
        showlegend=True, autosize=True, paper_bgcolor=BG_CARD, plot_bgcolor=BG_CARD,
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
        font={"family": FONT_FAMILY, "color": TEXT_SECONDARY, "size": 12},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0.0, "bgcolor": "rgba(0,0,0,0)", "font": {"size": 11, "color": TEXT_SECONDARY, "family": FONT_FAMILY}},
        xaxis={"gridcolor": GRID_COLOR, "zerolinecolor": ZERO_COLOR, "linecolor": "#E5E7EB", "linewidth": 1, "showline": True, "showgrid": True, "tickfont": {"size": 11, "color": TEXT_MUTED}, "title_font": {"size": 12, "color": TEXT_SECONDARY}},
        yaxis={"gridcolor": GRID_COLOR, "zerolinecolor": ZERO_COLOR, "linecolor": "#E5E7EB", "linewidth": 1, "showline": True, "showgrid": True, "tickfont": {"size": 11, "color": TEXT_MUTED}, "title_font": {"size": 12, "color": TEXT_SECONDARY}},
        colorway=SCADA_PALETTE,
    )
    if x_label is not None: figure.update_xaxes(title_text=x_label)
    if y_label is not None: figure.update_yaxes(title_text=y_label)
    return figure

def apply_minimal_layout(figure: go.Figure) -> go.Figure:
    figure.update_layout(
        template=DEFAULT_TEMPLATE, showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        xaxis={"visible": False, "showgrid": False, "fixedrange": True},
        yaxis={"visible": False, "showgrid": False, "fixedrange": True}, autosize=True,
    )
    return figure

def create_line_chart(dataframe: pd.DataFrame, x_column: str, y_column: str, title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    try:
        validate_columns(dataframe, [x_column, y_column])
        prepared = prepare_numeric_columns(dataframe, [y_column]).dropna(subset=[y_column])
        if prepared.empty: return None
        figure = go.Figure()
        figure.add_trace(go.Scatter(x=prepared[x_column], y=prepared[y_column], mode="lines", name=y_column, line={"color": SCADA_PALETTE[0], "width": 2.5}, fill="tozeroy", fillcolor="rgba(0, 93, 170, 0.05)", hovertemplate=f"<b>%{{x}}</b><br>{y_column}: %{{y:,.2f}}<extra></extra>"))
        return apply_default_layout(figure, title=title, x_label=x_label or x_column, y_label=y_label or y_column)
    except Exception as e:
        logger.error(f"Error creating line chart: {e}", exc_info=True)
        return None

def create_multi_line_chart(dataframe: pd.DataFrame, x_column: str, y_columns: list[str], title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    try:
        if not y_columns: return None
        validate_columns(dataframe, [x_column, *y_columns])
        prepared = prepare_numeric_columns(dataframe, y_columns)
        figure = go.Figure()
        for i, col in enumerate(y_columns):
            color = SCADA_PALETTE[i % len(SCADA_PALETTE)]
            figure.add_trace(go.Scatter(x=prepared[x_column], y=prepared[col], mode="lines", name=col, line={"color": color, "width": 2}, hovertemplate=f"<b>%{{x}}</b><br>{col}: %{{y:,.2f}}<extra></extra>"))
        return apply_default_layout(figure, title=title, x_label=x_label or x_column, y_label=y_label or "Readings")
    except Exception as e:
        logger.error(f"Error creating multi-line chart: {e}", exc_info=True)
        return None

def build_section_trend_chart(
    overview_dataframe: pd.DataFrame | None, section: dict[str, Any],
    date_column_label: str = DEFAULT_DATE_COLUMN_LABEL,
) -> go.Figure | None:
    """Build a trend chart using the section's own filtered dataframe."""
    try:
        if not section or "dataframe" not in section: return None
        df = section["dataframe"]
        if "Date" not in df.columns: return None
            
        numeric_cols = [c for c in df.columns if c != "Date" and pd.to_numeric(df[c], errors="coerce").notna().any()]
        meter_col = numeric_cols[0] if numeric_cols else None
        if not meter_col: return None
            
        unit_suffix = section.get("units", {}).get(meter_col, "")
        y_axis_title = f"{meter_col} ({unit_suffix})" if unit_suffix else meter_col
        
        return create_line_chart(df, x_column="Date", y_column=meter_col, title=f"{meter_col} Trend", x_label="Date", y_label=y_axis_title)
    except Exception as e:
        logger.error(f"Error building section trend chart: {e}", exc_info=True)
        return None

def create_department_multi_line_chart(
    overview_dataframe: pd.DataFrame | None, section: dict[str, Any], title: str,
    x_label: str | None = None, y_label: str | None = None,
) -> go.Figure | None:
    """Create a multi-line chart using the section's own filtered dataframe."""
    try:
        if not section or "dataframe" not in section or "meters" not in section: return None
        df = section["dataframe"]
        meters = section["meters"]
        if "Date" not in df.columns: return None
            
        numeric_meters = [col for col in meters if col in df.columns and pd.to_numeric(df[col], errors="coerce").notna().any()]
        if not numeric_meters: return None
            
        return create_multi_line_chart(dataframe=df, x_column="Date", y_columns=numeric_meters, title=title, x_label="Date", y_label=y_label or "Readings")
    except Exception as e:
        logger.error(f"Error creating department multi-line chart: {e}", exc_info=True)
        return None

def create_bar_chart(dataframe: pd.DataFrame, x_column: str, y_columns: str | list[str], title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    try:
        cols_list = [y_columns] if isinstance(y_columns, str) else y_columns
        if not cols_list: return None
        validate_columns(dataframe, [x_column, *cols_list])
        prepared = prepare_numeric_columns(dataframe, cols_list)
        figure = px.bar(prepared, x=x_column, y=y_columns, barmode="group", color_discrete_sequence=SCADA_PALETTE)
        figure.update_traces(marker_line_width=0, opacity=0.85)
        return apply_default_layout(figure, title=title, x_label=x_label or x_column, y_label=y_label or (cols_list[0] if len(cols_list) == 1 else "Value"))
    except Exception as e:
        logger.error(f"Error creating bar chart: {e}", exc_info=True)
        return None

def create_stacked_bar_chart(dataframe: pd.DataFrame, x_column: str, y_columns: list[str], title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    try:
        if not y_columns: return None
        validate_columns(dataframe, [x_column, *y_columns])
        prepared = prepare_numeric_columns(dataframe, y_columns)
        figure = px.bar(prepared, x=x_column, y=y_columns, barmode="stack", color_discrete_sequence=SCADA_PALETTE)
        figure.update_traces(marker_line_width=0, opacity=0.85)
        return apply_default_layout(figure, title=title, x_label=x_label or x_column, y_label=y_label or "Total Load")
    except Exception as e:
        logger.error(f"Error creating stacked bar chart: {e}", exc_info=True)
        return None

def create_area_chart(dataframe: pd.DataFrame, x_column: str, y_columns: str | list[str], title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    try:
        cols_list = [y_columns] if isinstance(y_columns, str) else y_columns
        if not cols_list: return None
        validate_columns(dataframe, [x_column, *cols_list])
        prepared = prepare_numeric_columns(dataframe, cols_list)
        figure = px.area(prepared, x=x_column, y=y_columns, color_discrete_sequence=SCADA_PALETTE)
        figure.update_traces(line={"width": 1.5}, opacity=0.6)
        return apply_default_layout(figure, title=title, x_label=x_label or x_column, y_label=y_label or "Accumulated Value")
    except Exception as e:
        logger.error(f"Error creating area chart: {e}", exc_info=True)
        return None

def create_pie_chart(dataframe: pd.DataFrame, names_column: str, values_column: str, title: str) -> go.Figure | None:
    try:
        validate_columns(dataframe, [names_column, values_column])
        prepared = prepare_numeric_columns(dataframe, [values_column]).dropna(subset=[values_column])
        if prepared.empty: return None
        figure = px.pie(prepared, names=names_column, values=values_column, color_discrete_sequence=SCADA_PALETTE)
        figure.update_traces(textposition="inside", textinfo="percent+label", marker={"line": {"color": BG_CARD, "width": 1}})
        return apply_default_layout(figure, title=title)
    except Exception as e:
        logger.error(f"Error creating pie chart: {e}", exc_info=True)
        return None

def create_donut_chart(dataframe: pd.DataFrame, names_column: str, values_column: str, title: str, hole_size: float = 0.6) -> go.Figure | None:
    try:
        validate_columns(dataframe, [names_column, values_column])
        prepared = prepare_numeric_columns(dataframe, [values_column]).dropna(subset=[values_column])
        if prepared.empty: return None
        figure = px.pie(prepared, names=names_column, values=values_column, hole=hole_size, color_discrete_sequence=SCADA_PALETTE)
        figure.update_traces(textposition="inside", textinfo="percent+label", marker={"line": {"color": BG_CARD, "width": 1}})
        return apply_default_layout(figure, title=title)
    except Exception as e:
        logger.error(f"Error creating donut chart: {e}", exc_info=True)
        return None

def create_gauge_chart(value: float, title: str, minimum: float = 0.0, maximum: float = 100.0, warning_threshold: float | None = None, danger_threshold: float | None = None, unit: str = "") -> go.Figure | None:
    try:
        if pd.isna(value) or value is None: return None
        steps = []
        band_start = minimum
        range_span = maximum - minimum if maximum > minimum else 1.0
        green_end = minimum + range_span * 0.60
        steps.append({"range": [band_start, green_end], "color": "rgba(34, 197, 94, 0.15)"})
        band_start = green_end
        yellow_end = minimum + range_span * 0.80
        steps.append({"range": [band_start, yellow_end], "color": "rgba(245, 158, 11, 0.15)"})
        band_start = yellow_end
        steps.append({"range": [band_start, maximum], "color": "rgba(227, 30, 36, 0.15)"})
        
        unit_suffix = f" {unit}".strip() if unit else ""
        figure = go.Figure(go.Indicator(
            mode="gauge+number", value=value,
            number={"suffix": f" {unit_suffix}" if unit_suffix else "", "font": {"size": 20, "color": TEXT_PRIMARY, "family": FONT_FAMILY}, "valueformat": ",.1f"},
            gauge={"axis": {"range": [minimum, maximum], "tickwidth": 1, "tickcolor": TEXT_MUTED, "tickfont": {"size": 8, "color": TEXT_MUTED, "family": FONT_FAMILY}, "ticklen": 4, "nticks": 6}, "bar": {"color": SCADA_PALETTE[0], "thickness": 0.15, "line": {"width": 0}}, "bgcolor": BG_CARD, "borderwidth": 1, "bordercolor": BORDER_SUBTLE, "steps": steps}
        ))
        figure.update_layout(title={"text": title, "font": {"size": 10, "color": TEXT_SECONDARY, "family": FONT_FAMILY}, "y": 0.85, "x": 0.5, "xanchor": "center", "yanchor": "top"}, template=DEFAULT_TEMPLATE, paper_bgcolor=BG_CARD, plot_bgcolor=BG_CARD, margin={"l": 20, "r": 20, "t": 35, "b": 20}, autosize=True, font={"family": FONT_FAMILY})
        return figure
    except Exception as e:
        logger.error(f"Error creating gauge chart: {e}", exc_info=True)
        return None

def create_scatter_chart(dataframe: pd.DataFrame, x_column: str, y_column: str, title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    try:
        validate_columns(dataframe, [x_column, y_column])
        prepared = prepare_numeric_columns(dataframe, [x_column, y_column]).dropna(subset=[x_column, y_column])
        if prepared.empty: return None
        figure = go.Figure(go.Scatter(x=prepared[x_column], y=prepared[y_column], mode="markers", marker={"color": SCADA_PALETTE[0], "size": 6, "opacity": 0.7, "line": {"width": 0}}))
        return apply_default_layout(figure, title=title, x_label=x_label or x_column, y_label=y_label or y_column)
    except Exception as e:
        logger.error(f"Error creating scatter chart: {e}", exc_info=True)
        return None

def create_histogram(dataframe: pd.DataFrame, x_column: str, title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    try:
        validate_columns(dataframe, [x_column])
        prepared = prepare_numeric_columns(dataframe, [x_column]).dropna(subset=[x_column])
        if prepared.empty: return None
        figure = px.histogram(prepared, x=x_column, color_discrete_sequence=[SCADA_PALETTE[0]])
        figure.update_layout(bargap=0.05)
        figure.update_traces(marker_line_width=0, opacity=0.8)
        return apply_default_layout(figure, title=title, x_label=x_label or x_column, y_label=y_label or "Count")
    except Exception as e:
        logger.error(f"Error creating histogram: {e}", exc_info=True)
        return None

def create_heatmap(dataframe: pd.DataFrame, columns: list[str] | None = None, title: str = "Heatmap", x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    try:
        if not isinstance(dataframe, pd.DataFrame): return None
        if columns is None: columns = [col for col in dataframe.columns if pd.to_numeric(dataframe[col], errors="coerce").notna().any()]
        if not columns: return None
        prepared = prepare_numeric_columns(dataframe, columns)
        figure = go.Figure(data=go.Heatmap(z=prepared[columns].to_numpy().T, x=list(range(len(prepared))), y=columns, colorscale=[[0.0, BG_CARD], [0.5, "#005DAA"], [1.0, "#E31E24"]], showscale=True, colorbar={"tickfont": {"size": 8, "color": TEXT_MUTED}, "outlinewidth": 0, "thickness": 10, "len": 0.8}))
        return apply_default_layout(figure, title=title, x_label=x_label or "Observation Index", y_label=y_label or "Meter Channel")
    except Exception as e:
        logger.error(f"Error creating heatmap: {e}", exc_info=True)
        return None

def create_sparkline(values: pd.Series, line_color: str = THEME_PRIMARY_COLOR) -> go.Figure | None:
    try:
        if values is None or values.empty: return None
        numeric_values = pd.to_numeric(values, errors="coerce").dropna()
        if numeric_values.empty: return None
        resolved_color = line_color or SCADA_PALETTE[0]
        figure = go.Figure(data=go.Scatter(x=list(range(len(numeric_values))), y=numeric_values, mode="lines", line={"color": resolved_color, "width": 1.5}, fill="tozeroy", fillcolor="rgba(0, 93, 170, 0.05)"))
        return apply_minimal_layout(figure)
    except Exception as e:
        logger.error(f"Error creating sparkline: {e}", exc_info=True)
        return None

def create_kpi_trend(dataframe: pd.DataFrame, x_column: str, y_column: str, title: str, x_label: str | None = None, y_label: str | None = None) -> go.Figure | None:
    return create_line_chart(dataframe, x_column, y_column, title, x_label, y_label)

def create_radar_chart(dataframe: pd.DataFrame, columns: list[str], title: str) -> go.Figure | None:
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
        fig = go.Figure(data=go.Scatterpolar(r=values, theta=categories, fill='toself', fillcolor='rgba(0, 93, 170, 0.1)', line=dict(color=SCADA_PALETTE[0], width=1.5), marker=dict(size=4, color=SCADA_PALETTE[0])))
        fig.update_layout(
            polar=dict(bgcolor=BG_CARD, radialaxis=dict(visible=True, range=[0, 100], gridcolor=GRID_COLOR, tickfont=dict(size=8, color=TEXT_MUTED)), angularaxis=dict(gridcolor=GRID_COLOR, tickfont=dict(size=9, color=TEXT_SECONDARY))),
            showlegend=False, title={"text": title, "font": {"size": 10, "color": TEXT_PRIMARY, "family": FONT_FAMILY}, "y": 0.95, "x": 0.5, "xanchor": "center", "yanchor": "top"},
            paper_bgcolor=BG_CARD, plot_bgcolor=BG_CARD, margin=dict(l=40, r=40, t=40, b=40), font=dict(family=FONT_FAMILY, color=TEXT_SECONDARY),
        )
        return fig
    except Exception as e:
        logger.error(f"Error creating radar chart: {e}", exc_info=True)
        return None

def create_waterfall_chart(dataframe: pd.DataFrame, x_column: str, y_column: str, title: str) -> go.Figure | None:
    try:
        validate_columns(dataframe, [x_column, y_column])
        prepared = prepare_numeric_columns(dataframe, [y_column]).dropna(subset=[y_column])
        if prepared.empty: return None
        fig = go.Figure(go.Waterfall(x=prepared[x_column], y=prepared[y_column], measure="relative", connector={"line": {"color": BORDER_SUBTLE, "width": 1}}, decreasing={"marker": {"color": SCADA_PALETTE[1]}}, increasing={"marker": {"color": SCADA_PALETTE[0]}}, totals={"marker": {"color": SCADA_PALETTE[4]}}))
        return apply_default_layout(fig, title=title, x_label=x_column, y_label=y_column)
    except Exception as e:
        logger.error(f"Error creating waterfall chart: {e}", exc_info=True)
        return None

def create_combined_line_area_chart(dataframe: pd.DataFrame, x_column: str, area_column: str, line_column: str, title: str) -> go.Figure | None:
    try:
        validate_columns(dataframe, [x_column, area_column, line_column])
        prepared = prepare_numeric_columns(dataframe, [area_column, line_column]).dropna(subset=[x_column])
        if prepared.empty: return None
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=prepared[x_column], y=prepared[area_column], fill='tozeroy', mode='lines', name=area_column, line=dict(color=SCADA_PALETTE[0], width=1), fillcolor='rgba(0, 93, 170, 0.05)'))
        fig.add_trace(go.Scatter(x=prepared[x_column], y=prepared[line_column], mode='lines', name=line_column, line=dict(color=SCADA_PALETTE[1], width=2)))
        return apply_default_layout(fig, title=title, x_label=x_column)
    except Exception as e:
        logger.error(f"Error creating combined line area chart: {e}", exc_info=True)
        return None

def create_horizontal_bar_chart(dataframe: pd.DataFrame, x_column: str, y_column: str, title: str) -> go.Figure | None:
    try:
        validate_columns(dataframe, [x_column, y_column])
        prepared = prepare_numeric_columns(dataframe, [y_column]).dropna(subset=[y_column])
        if prepared.empty: return None
        fig = px.bar(prepared, x=y_column, y=x_column, orientation='h', color_discrete_sequence=[SCADA_PALETTE[0]])
        fig.update_traces(marker_line_width=0, opacity=0.8)
        return apply_default_layout(fig, title=title, x_label=y_column, y_label=x_column)
    except Exception as e:
        logger.error(f"Error creating horizontal bar chart: {e}", exc_info=True)
        return None

def create_bullet_chart(actual: float, target: float, title: str, unit: str = "") -> go.Figure | None:
    try:
        if pd.isna(actual) or pd.isna(target): return None
        max_val = max(actual, target) * 1.2 if max(actual, target) > 0 else 100
        fig = go.Figure()
        fig.add_trace(go.Bar(x=[max_val], y=[title], orientation='h', marker=dict(color='rgba(0, 0, 0, 0.02)'), hoverinfo='skip', showlegend=False))
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
        logger.error(f"Error creating bullet chart: {e}", exc_info=True)
        return None

def create_daily_trend_chart(
    dataframe: pd.DataFrame, date_column: Any, meter_column: str, title: str = "Daily Trend"
) -> go.Figure | None:
    try:
        df = dataframe.copy()
        if isinstance(date_column, int):
            if date_column >= df.shape[1]: return None
            df["Date"] = df.iloc[:, date_column].values
            x_col = "Date"
        else:
            if date_column not in df.columns: return None
            x_col = date_column
            
        validate_columns(df, [x_col, meter_column])
        prepared = prepare_numeric_columns(df, [meter_column]).dropna(subset=[meter_column])
        if prepared.empty: return None
        
        prepared[x_col] = pd.to_datetime(prepared[x_col], errors="coerce")
        prepared = prepared.dropna(subset=[x_col])
        
        # ONLY aggregate if duplicate timestamps actually exist
        if prepared[x_col].duplicated().any():
            prepared = prepared.groupby(x_col, as_index=False)[meter_column].mean()
            
        prepared = prepared.sort_values(by=x_col)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=prepared[x_col], y=prepared[meter_column], mode="lines+markers", name=meter_column, 
            line={"color": SCADA_PALETTE[0], "width": 3, "shape": "spline"},
            marker={"size": 6, "color": "#FFFFFF", "line": {"width": 2, "color": SCADA_PALETTE[0]}},
            hovertemplate=f"<b>%{{x|%b %d, %Y}}</b><br>{meter_column}: %{{y:,.2f}}<extra></extra>"
        ))
        
        fig.update_layout(
            title={"text": title, "font": {"size": 16, "color": TEXT_PRIMARY, "family": FONT_FAMILY, "weight": 600}, "x": 0.01, "y": 0.98},
            template=DEFAULT_TEMPLATE, hovermode="x unified", showlegend=False,
            xaxis={"title": "Date", "gridcolor": GRID_COLOR, "showgrid": True},
            yaxis={"title": meter_column, "gridcolor": GRID_COLOR, "showgrid": True},
            margin={"l": 40, "r": 20, "t": 60, "b": 40}, paper_bgcolor=BG_CARD, plot_bgcolor=BG_CARD,
        )
        return fig
    except Exception as e:
        logger.error(f"Error creating daily trend chart: {e}", exc_info=True)
        return None

def calculate_daily_stats(dataframe: pd.DataFrame, meter_column: str, date_column: Any = None) -> dict[str, Any]:
    try:
        df = dataframe.copy()
        if isinstance(date_column, int):
            if date_column < df.shape[1]:
                df["Date"] = df.iloc[:, date_column].values
                x_col = "Date"
            else: x_col = None
        elif isinstance(date_column, str) and date_column in df.columns:
            x_col = date_column
        else: x_col = None
            
        if x_col:
            df[x_col] = pd.to_datetime(df[x_col], errors="coerce")
            df[meter_column] = pd.to_numeric(df[meter_column], errors="coerce")
            df = df.dropna(subset=[x_col, meter_column])
            df = df.sort_values(by=x_col)
            numeric_series = df[meter_column]
        else:
            numeric_series = pd.to_numeric(df[meter_column], errors="coerce").dropna()
            
        if numeric_series.empty:
            return {"Average": "—", "Maximum": "—", "Minimum": "—", "Latest": "—"}
        
        return {
            "Average": f"{float(numeric_series.mean()):,.2f}",
            "Maximum": f"{float(numeric_series.max()):,.2f}",
            "Minimum": f"{float(numeric_series.min()):,.2f}",
            "Latest": f"{float(numeric_series.iloc[-1]):,.2f}",
        }
    except Exception as e:
        logger.error(f"Error calculating daily stats: {e}", exc_info=True)
        return {"Average": "—", "Maximum": "—", "Minimum": "—", "Latest": "—"}

def get_daily_trend_figure_and_stats(
    dataframe: pd.DataFrame, meter_column: str, date_column: Any
) -> tuple[go.Figure | None, dict[str, Any]]:
    try:
        fig = create_daily_trend_chart(dataframe, date_column, meter_column, title=f"{meter_column} Daily Trend")
        stats = calculate_daily_stats(dataframe, meter_column, date_column)
        return fig, stats
    except Exception as e:
        logger.error(f"Error getting daily trend figure and stats: {e}", exc_info=True)
        return None, {"Average": "—", "Maximum": "—", "Minimum": "—", "Latest": "—"}
