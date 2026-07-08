"""Reusable Plotly chart service for the Engineering Monitoring Dashboard.
ARCHITECTURE NOTE: This service ONLY plots. It assumes input DataFrames are
already cleaned, aligned, and validated by the caller.

VISUALIZATION LAYER v2 — "Industrial HMI" design system
---------------------------------------------------------
This module keeps every public function signature used by app.py identical,
so no caller needs to change. Internally, every chart has been rebuilt on a
shared theming engine (`_Theme` / `_Layout`) so the dashboard reads like a
Grafana / Ignition / WinCC style industrial HMI instead of default Plotly:

  - unified hover with spike lines, rounded "cards", monospace numerics
  - spline curves + soft gradient fills on trends
  - engineering-grade annotations (max/min/current/target markers)
  - consistent 8px-grid spacing, hairline borders, no default Plotly chrome
  - zoom/pan enabled everywhere sensible, modebar hidden (app.py already
    hides it via CSS + config, this module just makes sure drag/zoom works)
  - each metric type gets the *right* chart (gauge for status, bullet for
    target-vs-actual, heatmap for multi-channel intensity, donut for share,
    ranked horizontal bars for comparison, histogram for distribution)
  - automatic y-axis padding so trend lines never hug the plot edges
  - explicit date-aware x-axis tick formatting on time-series charts

Nothing here touches data loading, alignment, or business logic — those
helpers (validate_columns, prepare_numeric_columns, find_first_numeric_column,
align_dates_with_meter, _align_dates_with_multiple_meters,
build_section_trend_data) are preserved byte-for-byte in behavior.

PERFORMANCE NOTE: whenever a caller already has a "ready" DataFrame (a Date
column plus one column per meter — exactly what the business layer's
department ``dataframe`` payload provides), prefer the direct-dataframe
helpers below (`create_department_line_chart`,
`create_department_multi_meter_chart`) over the data-rebuilding path
(`build_section_trend_chart` / `create_department_multi_line_chart`), which
re-derives alignment via `align_dates_with_meter` /
`_align_dates_with_multiple_meters` even when it isn't necessary. Both paths
are kept for backward compatibility.
"""
from __future__ import annotations

import datetime
import logging
import warnings
from typing import Any, Final

import numpy as np
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

logger = logging.getLogger(__name__)

# ==================================================================
# THEME / DESIGN TOKENS — single source of truth for every chart
# ==================================================================

DEFAULT_TEMPLATE: str = "plotly_dark"
DEFAULT_HOVER_MODE: str = "x unified"
DEFAULT_DATE_COLUMN_LABEL: str = "Date"

# Industrial HMI palette — chosen for contrast on dark SCADA backgrounds
SCADA_PALETTE: Final[list[str]] = [
    "#3B82F6", "#22C55E", "#F59E0B", "#EF4444",
    "#8B5CF6", "#06B6D4", "#EC4899", "#84CC16",
]

BG_APP = "#0B1220"
BG_CARD = "#111827"
BG_HOVER = "#1F2937"
BORDER_SUBTLE = "rgba(255,255,255,0.07)"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#94A3B8"
TEXT_MUTED = "#64748B"
GRID_COLOR = "rgba(255,255,255,0.045)"
ZERO_COLOR = "rgba(255,255,255,0.08)"
SPIKE_COLOR = "rgba(148,163,184,0.55)"

GOOD_COLOR = "#22C55E"
WARN_COLOR = "#F59E0B"
BAD_COLOR = "#EF4444"

FONT_FAMILY: Final[str] = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
MONO_FAMILY: Final[str] = "'JetBrains Mono', 'SF Mono', 'Roboto Mono', monospace"

# Fraction of the observed data range added above/below a trend line so it
# never touches the plot edges.
Y_AXIS_PADDING_RATIO: Final[float] = 0.12


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Convert a #RRGGBB color into an rgba() string with the given alpha."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r}, {g}, {b}, {alpha})"
    except Exception:
        return f"rgba(59, 130, 246, {alpha})"


def _status_color(ratio: float) -> str:
    """Map a 0..1+ utilization ratio to a semantic SCADA status color."""
    if ratio >= 0.85:
        return BAD_COLOR
    if ratio >= 0.65:
        return WARN_COLOR
    return GOOD_COLOR


def _padded_y_range(*series: pd.Series) -> list[float] | None:
    """Compute a y-axis range padded by ``Y_AXIS_PADDING_RATIO`` so trend
    lines/markers never hug the top or bottom of the plot area.

    Args:
        *series: One or more numeric Series to consider together.

    Returns:
        A ``[low, high]`` list, or ``None`` if no numeric data is available.
    """
    values = pd.concat([pd.to_numeric(s, errors="coerce") for s in series if s is not None])
    values = values.dropna()
    if values.empty:
        return None

    lo, hi = float(values.min()), float(values.max())
    span = hi - lo
    if span <= 0:
        # Flat series — pad by a fixed proportion of the value itself (or a
        # small absolute amount if the value is zero) so it isn't a flat
        # line glued to the axis.
        pad = abs(hi) * Y_AXIS_PADDING_RATIO if hi != 0 else 1.0
        return [lo - pad, hi + pad]

    pad = span * Y_AXIS_PADDING_RATIO
    return [lo - pad, hi + pad]


class _HMI:
    """Shared layout engine — every chart routes through here so the whole
    dashboard reads as one coherent industrial product instead of a pile of
    ad-hoc Plotly calls."""

    BASE_FONT = {"family": FONT_FAMILY, "color": TEXT_SECONDARY, "size": 11}

    @staticmethod
    def title_block(title: str, subtitle: str | None = None) -> dict[str, Any]:
        text = f"<b>{title}</b>"
        if subtitle:
            text += f"<br><span style='font-size:10px;color:{TEXT_MUTED}'>{subtitle}</span>"
        return {
            "text": text,
            "font": {"size": 13, "color": TEXT_PRIMARY, "family": FONT_FAMILY},
            "x": 0.02, "y": 0.96, "xanchor": "left", "yanchor": "top",
        }

    @staticmethod
    def apply(
        figure: go.Figure,
        title: str,
        x_label: str | None = None,
        y_label: str | None = None,
        subtitle: str | None = None,
        show_legend: bool = True,
        hovermode: str = DEFAULT_HOVER_MODE,
        x_is_date: bool = False,
        y_range: list[float] | None = None,
    ) -> go.Figure:
        figure.update_layout(
            title=_HMI.title_block(title, subtitle),
            template=DEFAULT_TEMPLATE,
            hovermode=hovermode,
            hoverlabel={
                "bgcolor": BG_HOVER,
                "bordercolor": BORDER_SUBTLE,
                "font": {"family": MONO_FAMILY, "size": 11, "color": TEXT_PRIMARY},
                "namelength": -1,
                "align": "left",
            },
            showlegend=show_legend,
            autosize=True,
            paper_bgcolor=BG_CARD,
            plot_bgcolor=BG_CARD,
            margin={"l": 54, "r": 24, "t": 54, "b": 44},
            font=_HMI.BASE_FONT,
            legend={
                "orientation": "h", "yanchor": "bottom", "y": 1.05, "xanchor": "left", "x": 0.0,
                "bgcolor": "rgba(0,0,0,0)", "font": {"size": 10, "color": TEXT_SECONDARY, "family": FONT_FAMILY},
                "itemwidth": 40, "traceorder": "normal",
                "bordercolor": "rgba(0,0,0,0)",
            },
            xaxis={
                "gridcolor": GRID_COLOR, "zerolinecolor": ZERO_COLOR, "linecolor": BORDER_SUBTLE,
                "linewidth": 1, "showline": True, "showgrid": True,
                "tickfont": {"size": 10, "color": TEXT_MUTED, "family": MONO_FAMILY},
                "title_font": {"size": 11, "color": TEXT_SECONDARY},
                "showspikes": True, "spikemode": "across", "spikesnap": "cursor",
                "spikecolor": SPIKE_COLOR, "spikethickness": 1, "spikedash": "dot",
                "rangeslider": {"visible": False},
                **({"tickformat": "%d %b", "hoverformat": "%d %b %Y"} if x_is_date else {}),
            },
            yaxis={
                "gridcolor": GRID_COLOR, "zerolinecolor": ZERO_COLOR, "linecolor": BORDER_SUBTLE,
                "linewidth": 1, "showline": True, "showgrid": True,
                "tickfont": {"size": 10, "color": TEXT_MUTED, "family": MONO_FAMILY},
                "title_font": {"size": 11, "color": TEXT_SECONDARY},
                "showspikes": True, "spikemode": "across", "spikecolor": SPIKE_COLOR, "spikethickness": 1,
                **({"range": y_range} if y_range is not None else {}),
            },
            colorway=SCADA_PALETTE,
            transition={"duration": 350, "easing": "cubic-in-out"},
            dragmode="pan",
        )
        if x_label is not None:
            figure.update_xaxes(title_text=x_label)
        if y_label is not None:
            figure.update_yaxes(title_text=y_label)
        return figure

    @staticmethod
    def minimal(figure: go.Figure) -> go.Figure:
        figure.update_layout(
            template=DEFAULT_TEMPLATE, showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            margin={"l": 0, "r": 0, "t": 0, "b": 0},
            xaxis={"visible": False, "showgrid": False, "fixedrange": True},
            yaxis={"visible": False, "showgrid": False, "fixedrange": True},
            autosize=True,
            transition={"duration": 300, "easing": "cubic-in-out"},
        )
        return figure

    @staticmethod
    def indicator_shell(figure: go.Figure, title: str) -> go.Figure:
        figure.update_layout(
            title={
                "text": f"<b>{title}</b>",
                "font": {"size": 12, "color": TEXT_SECONDARY, "family": FONT_FAMILY},
                "y": 0.88, "x": 0.5, "xanchor": "center", "yanchor": "top",
            },
            template=DEFAULT_TEMPLATE,
            paper_bgcolor=BG_CARD, plot_bgcolor=BG_CARD,
            margin={"l": 24, "r": 24, "t": 42, "b": 20},
            autosize=True,
            font=_HMI.BASE_FONT,
            transition={"duration": 400, "easing": "elastic"},
        )
        return figure


# Backwards-compatible aliases (kept in case other modules import these names)
apply_default_layout = lambda figure, title, x_label=None, y_label=None: _HMI.apply(figure, title, x_label, y_label)
apply_minimal_layout = lambda figure: _HMI.minimal(figure)


# ==================================================================
# DATA HELPERS — unchanged behavior (alignment / validation only)
# ==================================================================

def validate_columns(dataframe: pd.DataFrame, columns: list[str]) -> None:
    """Validate that the specified columns exist in the dataframe."""
    if not isinstance(dataframe, pd.DataFrame):
        raise ValueError(f"Expected pandas.DataFrame, got {type(dataframe).__name__}.")
    if dataframe.empty:
        raise ValueError("DataFrame is empty.")

    actual_cols = [str(c) for c in dataframe.columns]
    missing = [col for col in columns if str(col) not in actual_cols]

    if missing:
        raise ValueError(f"Columns not found in the dataframe: {missing}. Available: {list(dataframe.columns)}")


def prepare_numeric_columns(dataframe: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Convert specified columns to numeric types."""
    validate_columns(dataframe, columns)
    prepared = dataframe.copy()
    for column in columns:
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
        else:
            for col in prepared.columns:
                if str(col) == str(column):
                    prepared[col] = pd.to_numeric(prepared[col], errors="coerce")
                    break
    return prepared


def find_first_numeric_column(dataframe: pd.DataFrame) -> str | None:
    """Find the first column in the dataframe that contains numeric data."""
    if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
        return None

    date_keywords = {"date", "time", "timestamp", "datetime"}

    for column in dataframe.columns:
        try:
            col_str = str(column).lower().strip()
            if any(keyword in col_str for keyword in date_keywords):
                continue
            numeric_series = pd.to_numeric(dataframe[column], errors="coerce")
            if numeric_series.notna().any():
                return column
        except Exception as e:
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

        date_col_name = date_cols[0]

        if date_col_name not in overview_dataframe.columns:
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

        trend_df[date_column_label] = pd.to_datetime(trend_df[date_column_label], errors="coerce")
        trend_df[meter_name] = pd.to_numeric(trend_df[meter_name], errors="coerce")

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
                for c in dataframe_block.columns:
                    if str(c) == str(col):
                        compiled_df[col] = pd.to_numeric(
                            dataframe_block[c].iloc[:min_len].reset_index(drop=True), errors="coerce"
                        )
                        break

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


# ==================================================================
# DIRECT-DATAFRAME HELPERS (preferred, avoid rebuilding chart data)
# ==================================================================
#
# The business layer's department payload already provides a ready-to-plot
# DataFrame with a "Date" column plus one column per meter (see
# `build_dashboard` in dashboard_data.py). These helpers plot that
# DataFrame directly — no re-derivation of dates, no `find_first_numeric_column`
# guessing, no realignment. Callers choose *which* meter to plot (e.g. via a
# Streamlit selectbox) instead of the chart layer silently picking one.

def has_ready_department_dataframe(section: dict[str, Any]) -> bool:
    """Check whether a section already carries a plot-ready DataFrame.

    A "ready" DataFrame has a ``Date`` column plus at least one meter
    column, meaning no realignment via `align_dates_with_meter` is needed.

    Args:
        section: A department/section dict as produced by the business layer.

    Returns:
        True if `section["dataframe"]` can be plotted directly.
    """
    df = section.get("dataframe") if section else None
    return (
        isinstance(df, pd.DataFrame)
        and not df.empty
        and DEFAULT_DATE_COLUMN_LABEL in df.columns
        and df.shape[1] > 1
    )


def get_department_meters(section: dict[str, Any]) -> list[str]:
    """Return the list of meter column names available for a section.

    Prefers the explicit ``section["meters"]`` list (authoritative, in
    business-layer order); falls back to every non-Date column of the
    section's DataFrame.

    Args:
        section: A department/section dict as produced by the business layer.

    Returns:
        A list of meter names available to plot for this section.
    """
    if not section:
        return []

    meters = section.get("meters")
    if meters:
        return list(meters)

    df = section.get("dataframe")
    if isinstance(df, pd.DataFrame):
        return [c for c in df.columns if c != DEFAULT_DATE_COLUMN_LABEL]

    return []


def create_department_line_chart(
    section: dict[str, Any], meter: str, title: str | None = None,
) -> go.Figure | None:
    """Plot a single meter directly from a section's ready DataFrame.

    This is the preferred path for department trend charts: it uses the
    ``Date`` + meter columns already assembled by the business layer
    instead of rebuilding alignment via `align_dates_with_meter`.

    Args:
        section: A department/section dict with a ready ``dataframe``.
        meter: The meter/column name to plot.
        title: Optional chart title; defaults to "{meter} Trend".

    Returns:
        A Plotly Figure, or None if the section/meter has no plottable data.
    """
    if not has_ready_department_dataframe(section):
        return None

    df = section["dataframe"]
    if meter not in df.columns:
        return None

    unit = ""
    units_map = section.get("units")
    if isinstance(units_map, dict):
        unit = units_map.get(meter, "")

    y_label = f"{meter} ({unit})" if unit else meter
    chart_title = title or f"{meter} Trend"

    return create_line_chart(
        df, x_column=DEFAULT_DATE_COLUMN_LABEL, y_column=meter,
        title=chart_title, x_label=DEFAULT_DATE_COLUMN_LABEL, y_label=y_label,
    )


def create_department_multi_meter_chart(
    section: dict[str, Any], meters: list[str] | None, title: str,
    x_label: str | None = None, y_label: str | None = None,
) -> go.Figure | None:
    """Plot several meters directly from a section's ready DataFrame.

    Args:
        section: A department/section dict with a ready ``dataframe``.
        meters: Meter names to plot; defaults to every meter in the section.
        title: Chart title.
        x_label: Optional x-axis label override.
        y_label: Optional y-axis label override.

    Returns:
        A Plotly Figure (multi-line, or a heatmap if there are many
        channels), or None if there's no plottable data.
    """
    if not has_ready_department_dataframe(section):
        return None

    df = section["dataframe"]
    candidate_meters = meters or get_department_meters(section)
    numeric_meters = [m for m in candidate_meters if m in df.columns]
    if not numeric_meters:
        return None

    if len(numeric_meters) > 8:
        return create_heatmap(
            df, columns=numeric_meters, title=title,
            x_label=x_label or DEFAULT_DATE_COLUMN_LABEL, y_label=y_label or "Channel",
        )

    return create_multi_line_chart(
        df, x_column=DEFAULT_DATE_COLUMN_LABEL, y_columns=numeric_meters,
        title=title, x_label=x_label, y_label=y_label,
    )


# ==================================================================
# CHART BUILDERS — the redesigned visualization layer
# ==================================================================

def build_section_trend_chart(
    overview_dataframe: pd.DataFrame, section: dict[str, Any],
    date_column_label: str = DEFAULT_DATE_COLUMN_LABEL,
) -> go.Figure | None:
    """Build a trend chart for a specific section (spline area, annotated).

    Kept for backward compatibility. When the section already carries a
    ready DataFrame, prefer `create_department_line_chart` with an
    explicit, user-chosen meter instead of this auto-selecting path.
    """
    try:
        trend_data = build_section_trend_data(overview_dataframe, section, date_column_label=date_column_label)
        if trend_data is None:
            return None

        trend_df, date_col, meter_col = trend_data

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
    """Create an interactive multiline chart for all meters in a department.

    Kept for backward compatibility with callers that only have the
    overview dataframe. When the section already carries a ready
    DataFrame (Date + meter columns), prefer
    `create_department_multi_meter_chart`, which skips realignment.
    """
    try:
        if has_ready_department_dataframe(section):
            return create_department_multi_meter_chart(
                section, section.get("meters"), title, x_label=x_label, y_label=y_label,
            )

        if not section or "dataframe" not in section or "meters" not in section:
            logger.warning("Section is invalid or missing required keys.")
            return None

        dept_df = section["dataframe"]
        meters = section["meters"]

        if not isinstance(dept_df, pd.DataFrame) or dept_df.empty or not meters:
            logger.warning("Department dataframe is invalid/empty or no meters provided.")
            return None

        numeric_meters = []
        for col in meters:
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
                except Exception:
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

        # Auto-select the right chart type based on cardinality:
        # a handful of channels -> interactive multiline; a lot of channels
        # -> heatmap communicates "hourly/multi-channel intensity" far better.
        if len(numeric_meters) > 8:
            return create_heatmap(
                aligned_df, columns=numeric_meters, title=title,
                x_label=x_label or DEFAULT_DATE_COLUMN_LABEL, y_label=y_label or "Channel",
            )

        return create_multi_line_chart(
            dataframe=aligned_df, x_column=DEFAULT_DATE_COLUMN_LABEL,
            y_columns=numeric_meters, title=title, x_label=x_label, y_label=y_label,
        )
    except Exception as e:
        logger.error(f"Error in create_department_multi_line_chart: {e}", exc_info=True)
        return None


def create_line_chart(
    dataframe: pd.DataFrame, x_column: str, y_column: str, title: str,
    x_label: str | None = None, y_label: str | None = None,
) -> go.Figure | None:
    """Premium smooth-spline area trend chart with max/min/current annotations."""
    try:
        validate_columns(dataframe, [x_column, y_column])
        prepared = prepare_numeric_columns(dataframe, [y_column]).dropna(subset=[y_column])

        if prepared.empty:
            logger.warning(f"No data to plot for {y_column}")
            return None

        max_idx = prepared[y_column].idxmax()
        min_idx = prepared[y_column].idxmin()
        last_idx = prepared.index[-1]

        max_val = prepared.loc[max_idx, y_column]
        min_val = prepared.loc[min_idx, y_column]
        last_val = prepared.loc[last_idx, y_column]

        max_date = prepared.loc[max_idx, x_column]
        min_date = prepared.loc[min_idx, x_column]
        last_date = prepared.loc[last_idx, x_column]

        accent = SCADA_PALETTE[0]
        figure = go.Figure()

        # Soft gradient area under a thick smooth spline
        figure.add_trace(go.Scatter(
            x=prepared[x_column], y=prepared[y_column],
            mode="lines", name=str(y_column),
            line={"color": accent, "width": 3, "shape": "spline", "smoothing": 0.65},
            fill="tozeroy", fillcolor=_hex_to_rgba(accent, 0.16),
            hovertemplate=f"<b>%{{x|%d %b, %H:%M}}</b><br>{y_column}: <b>%{{y:,.2f}}</b><extra></extra>",
        ))

        # Current point — glowing marker
        figure.add_trace(go.Scatter(
            x=[last_date], y=[last_val], mode="markers", name="Current",
            marker={"size": 10, "color": accent, "line": {"width": 2, "color": BG_CARD},
                    "symbol": "circle"},
            hovertemplate=f"<b>Current</b><br>%{{x|%d %b, %H:%M}}<br>{y_column}: <b>%{{y:,.2f}}</b><extra></extra>",
            showlegend=False,
        ))

        # Max / Min annotated markers
        figure.add_trace(go.Scatter(
            x=[max_date], y=[max_val], mode="markers+text", name="Peak",
            text=["▲ PEAK"], textposition="top center",
            textfont={"size": 9, "color": GOOD_COLOR, "family": FONT_FAMILY},
            marker={"size": 7, "color": GOOD_COLOR, "line": {"width": 1, "color": BG_CARD}},
            hovertemplate=f"<b>Peak</b><br>%{{x|%d %b}}<br>{y_column}: <b>%{{y:,.2f}}</b><extra></extra>",
            showlegend=False,
        ))
        figure.add_trace(go.Scatter(
            x=[min_date], y=[min_val], mode="markers+text", name="Low",
            text=["▼ LOW"], textposition="bottom center",
            textfont={"size": 9, "color": BAD_COLOR, "family": FONT_FAMILY},
            marker={"size": 7, "color": BAD_COLOR, "line": {"width": 1, "color": BG_CARD}},
            hovertemplate=f"<b>Low</b><br>%{{x|%d %b}}<br>{y_column}: <b>%{{y:,.2f}}</b><extra></extra>",
            showlegend=False,
        ))

        is_date_axis = pd.api.types.is_datetime64_any_dtype(prepared[x_column]) or "date" in str(x_column).lower()
        y_range = _padded_y_range(prepared[y_column])

        figure = _HMI.apply(
            figure, title=title, x_label=x_label or str(x_column), y_label=y_label or str(y_column),
            x_is_date=is_date_axis, y_range=y_range,
        )
        figure.update_xaxes(rangeslider_visible=False)
        figure.update_layout(dragmode="zoom")
        return figure
    except Exception as e:
        logger.error(f"Error in create_line_chart: {e}", exc_info=True)
        return None


def create_multi_line_chart(
    dataframe: pd.DataFrame, x_column: str, y_columns: list[str], title: str,
    x_label: str | None = None, y_label: str | None = None,
) -> go.Figure | None:
    """Interactive multiline chart — clean overlay with unified hover card."""
    try:
        if not y_columns:
            return None
        validate_columns(dataframe, [x_column, *y_columns])
        prepared = prepare_numeric_columns(dataframe, y_columns)

        figure = go.Figure()
        plotted_series: list[pd.Series] = []
        for i, col in enumerate(y_columns):
            if prepared[col].dropna().empty:
                continue

            color = SCADA_PALETTE[i % len(SCADA_PALETTE)]
            figure.add_trace(go.Scatter(
                x=prepared[x_column], y=prepared[col],
                mode="lines", name=str(col),
                line={"color": color, "width": 2.5, "shape": "spline", "smoothing": 0.55},
                hovertemplate=f"<b>{col}</b>: %{{y:,.2f}}<extra></extra>",
            ))
            plotted_series.append(prepared[col])

        if not figure.data:
            logger.warning("No data traces added to multi-line chart.")
            return None

        is_date_axis = pd.api.types.is_datetime64_any_dtype(prepared[x_column]) or "date" in str(x_column).lower()
        y_range = _padded_y_range(*plotted_series)

        figure = _HMI.apply(
            figure, title=title, x_label=x_label or str(x_column), y_label=y_label or "Readings",
            x_is_date=is_date_axis, y_range=y_range,
        )
        figure.update_layout(dragmode="zoom")
        return figure
    except Exception as e:
        logger.error(f"Error in create_multi_line_chart: {e}", exc_info=True)
        return None


def create_bar_chart(
    dataframe: pd.DataFrame, x_column: str, y_columns: str | list[str], title: str,
    x_label: str | None = None, y_label: str | None = None,
) -> go.Figure | None:
    """Ranked comparison bars — auto-orients horizontal for readable labels."""
    try:
        cols_list = [y_columns] if isinstance(y_columns, str) else y_columns
        if not cols_list:
            return None
        validate_columns(dataframe, [x_column, *cols_list])
        prepared = prepare_numeric_columns(dataframe, cols_list)

        # Single series comparison -> ranked horizontal bars (Grafana style)
        if len(cols_list) == 1:
            return create_horizontal_bar_chart(prepared, x_column=x_column, y_column=cols_list[0], title=title)

        figure = go.Figure()
        for i, col in enumerate(cols_list):
            color = SCADA_PALETTE[i % len(SCADA_PALETTE)]
            figure.add_trace(go.Bar(
                x=prepared[x_column], y=prepared[col], name=str(col),
                marker={"color": color, "line": {"width": 0}, "opacity": 0.92,
                        "cornerradius": 4},
                hovertemplate=f"<b>%{{x}}</b><br>{col}: <b>%{{y:,.2f}}</b><extra></extra>",
            ))

        figure.update_layout(bargap=0.28, bargroupgap=0.08)
        return _HMI.apply(
            figure, title=title, x_label=x_label or str(x_column),
            y_label=y_label or (str(cols_list[0]) if len(cols_list) == 1 else "Value"),
        )
    except Exception as e:
        logger.error(f"Error in create_bar_chart: {e}", exc_info=True)
        return None


def create_stacked_bar_chart(
    dataframe: pd.DataFrame, x_column: str, y_columns: list[str], title: str,
    x_label: str | None = None, y_label: str | None = None,
) -> go.Figure | None:
    """Stacked contribution bars with rounded corners."""
    try:
        if not y_columns:
            return None
        validate_columns(dataframe, [x_column, *y_columns])
        prepared = prepare_numeric_columns(dataframe, y_columns)

        figure = go.Figure()
        for i, col in enumerate(y_columns):
            color = SCADA_PALETTE[i % len(SCADA_PALETTE)]
            figure.add_trace(go.Bar(
                x=prepared[x_column], y=prepared[col], name=str(col),
                marker={"color": color, "opacity": 0.92, "cornerradius": 3, "line": {"width": 0}},
                hovertemplate=f"<b>{col}</b>: %{{y:,.2f}}<extra></extra>",
            ))
        figure.update_layout(barmode="stack", bargap=0.25)
        return _HMI.apply(figure, title=title, x_label=x_label or str(x_column), y_label=y_label or "Total Load")
    except Exception as e:
        logger.error(f"Error in create_stacked_bar_chart: {e}", exc_info=True)
        return None


def create_area_chart(
    dataframe: pd.DataFrame, x_column: str, y_columns: str | list[str], title: str,
    x_label: str | None = None, y_label: str | None = None,
) -> go.Figure | None:
    """Smooth layered area chart for accumulation-style metrics."""
    try:
        cols_list = [y_columns] if isinstance(y_columns, str) else y_columns
        if not cols_list:
            return None
        validate_columns(dataframe, [x_column, *cols_list])
        prepared = prepare_numeric_columns(dataframe, cols_list)

        figure = go.Figure()
        for i, col in enumerate(cols_list):
            color = SCADA_PALETTE[i % len(SCADA_PALETTE)]
            figure.add_trace(go.Scatter(
                x=prepared[x_column], y=prepared[col], mode="lines", name=str(col),
                line={"color": color, "width": 2, "shape": "spline", "smoothing": 0.5},
                stackgroup="one" if len(cols_list) > 1 else None,
                fill="tonexty" if len(cols_list) > 1 else "tozeroy",
                fillcolor=_hex_to_rgba(color, 0.22),
                hovertemplate=f"<b>{col}</b>: %{{y:,.2f}}<extra></extra>",
            ))
        return _HMI.apply(figure, title=title, x_label=x_label or str(x_column), y_label=y_label or "Accumulated Value")
    except Exception as e:
        logger.error(f"Error in create_area_chart: {e}", exc_info=True)
        return None


def create_pie_chart(dataframe: pd.DataFrame, names_column: str, values_column: str, title: str) -> go.Figure | None:
    """Share-of-total chart — routed to the donut renderer for a premium look."""
    return create_donut_chart(dataframe, names_column, values_column, title)


def create_donut_chart(
    dataframe: pd.DataFrame, names_column: str, values_column: str, title: str, hole_size: float = 0.68,
) -> go.Figure | None:
    """Modern donut with a live center total — used for contribution/share metrics."""
    try:
        validate_columns(dataframe, [names_column, values_column])
        prepared = prepare_numeric_columns(dataframe, [values_column]).dropna(subset=[values_column])
        if prepared.empty:
            return None

        total_val = prepared[values_column].sum()

        figure = px.pie(
            prepared, names=names_column, values=values_column, hole=hole_size,
            color_discrete_sequence=SCADA_PALETTE,
        )
        figure.update_traces(
            textposition="outside", textinfo="percent+label",
            textfont={"size": 10, "color": TEXT_SECONDARY, "family": FONT_FAMILY},
            marker={"line": {"color": BG_CARD, "width": 3}},
            pull=[0.02] * len(prepared),
            hovertemplate="<b>%{label}</b><br>%{value:,.2f} (%{percent})<extra></extra>",
        )

        figure.add_annotation(
            text=f"<span style='font-size:18px;font-weight:700;color:{TEXT_PRIMARY}'>{total_val:,.0f}</span>"
                 f"<br><span style='font-size:9px;color:{TEXT_MUTED};letter-spacing:0.5px'>TOTAL</span>",
            x=0.5, y=0.5, showarrow=False, font={"family": FONT_FAMILY},
        )

        return _HMI.apply(figure, title=title, show_legend=True, hovermode="closest")
    except Exception as e:
        logger.error(f"Error in create_donut_chart: {e}", exc_info=True)
        return None


def create_gauge_chart(
    value: float, title: str, minimum: float = 0.0, maximum: float = 100.0,
    warning_threshold: float | None = None, danger_threshold: float | None = None, unit: str = "",
) -> go.Figure | None:
    """Radial SCADA-style gauge for a single live status metric."""
    try:
        if pd.isna(value) or value is None:
            return None

        range_span = maximum - minimum if maximum > minimum else 1.0
        normalized_val = (value - minimum) / range_span
        needle_color = _status_color(normalized_val)

        warn_pt = warning_threshold if warning_threshold is not None else minimum + range_span * 0.6
        danger_pt = danger_threshold if danger_threshold is not None else minimum + range_span * 0.8

        steps = [
            {"range": [minimum, warn_pt], "color": _hex_to_rgba(GOOD_COLOR, 0.10)},
            {"range": [warn_pt, danger_pt], "color": _hex_to_rgba(WARN_COLOR, 0.12)},
            {"range": [danger_pt, maximum], "color": _hex_to_rgba(BAD_COLOR, 0.14)},
        ]

        figure = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=value,
            number={
                "suffix": f" {unit}".rstrip() if unit else "",
                "font": {"size": 26, "color": TEXT_PRIMARY, "family": MONO_FAMILY},
                "valueformat": ",.1f",
            },
            delta={
                "reference": (minimum + maximum) / 2, "relative": False,
                "increasing": {"color": WARN_COLOR}, "decreasing": {"color": GOOD_COLOR},
                "font": {"size": 11},
            },
            gauge={
                "axis": {
                    "range": [minimum, maximum], "tickwidth": 1, "tickcolor": TEXT_MUTED,
                    "tickfont": {"size": 9, "color": TEXT_MUTED, "family": MONO_FAMILY},
                    "ticklen": 5, "nticks": 8,
                },
                "bar": {"color": needle_color, "thickness": 0.24, "line": {"width": 0}},
                "bgcolor": BG_CARD,
                "borderwidth": 1,
                "bordercolor": BORDER_SUBTLE,
                "steps": steps,
                "threshold": {"line": {"color": needle_color, "width": 3}, "thickness": 0.82, "value": value},
            },
        ))

        figure = _HMI.indicator_shell(figure, title)
        return figure
    except Exception as e:
        logger.error(f"Error in create_gauge_chart: {e}", exc_info=True)
        return None


def create_scatter_chart(
    dataframe: pd.DataFrame, x_column: str, y_column: str, title: str,
    x_label: str | None = None, y_label: str | None = None,
) -> go.Figure | None:
    """Correlation scatter with soft glow markers."""
    try:
        validate_columns(dataframe, [x_column, y_column])
        prepared = prepare_numeric_columns(dataframe, [x_column, y_column]).dropna(subset=[x_column, y_column])
        if prepared.empty:
            return None
        accent = SCADA_PALETTE[0]
        figure = go.Figure(go.Scatter(
            x=prepared[x_column], y=prepared[y_column], mode="markers",
            marker={
                "color": accent, "size": 9, "opacity": 0.75,
                "line": {"width": 1, "color": BG_CARD},
            },
            hovertemplate=f"{x_column}: %{{x:,.2f}}<br>{y_column}: %{{y:,.2f}}<extra></extra>",
        ))
        return _HMI.apply(
            figure, title=title, x_label=x_label or str(x_column), y_label=y_label or str(y_column),
            hovermode="closest",
        )
    except Exception as e:
        logger.error(f"Error in create_scatter_chart: {e}", exc_info=True)
        return None


def create_histogram(
    dataframe: pd.DataFrame, x_column: str, title: str,
    x_label: str | None = None, y_label: str | None = None,
) -> go.Figure | None:
    """Distribution histogram with mean/median reference lines."""
    try:
        validate_columns(dataframe, [x_column])
        prepared = prepare_numeric_columns(dataframe, [x_column]).dropna(subset=[x_column])
        if prepared.empty:
            return None

        mean_val = prepared[x_column].mean()
        median_val = prepared[x_column].median()

        figure = px.histogram(prepared, x=x_column, color_discrete_sequence=[SCADA_PALETTE[0]])
        figure.update_traces(marker_line_width=0, opacity=0.85, marker_cornerradius=3)
        figure.add_vline(x=mean_val, line_dash="dash", line_color=WARN_COLOR, line_width=1.5,
                          annotation_text=f"Mean {mean_val:,.1f}", annotation_font_size=9,
                          annotation_font_color=WARN_COLOR)
        figure.add_vline(x=median_val, line_dash="dot", line_color=SCADA_PALETTE[0], line_width=1.5,
                          annotation_text=f"Median {median_val:,.1f}", annotation_font_size=9,
                          annotation_font_color=SCADA_PALETTE[0])

        figure.update_layout(bargap=0.08)
        return _HMI.apply(figure, title=title, x_label=x_label or str(x_column), y_label=y_label or "Count",
                           hovermode="closest")
    except Exception as e:
        logger.error(f"Error in create_histogram: {e}", exc_info=True)
        return None


def create_heatmap(
    dataframe: pd.DataFrame, columns: list[str] | None = None, title: str = "Heatmap",
    x_label: str | None = None, y_label: str | None = None,
) -> go.Figure | None:
    """Multi-channel intensity heatmap — used whenever there are too many
    channels for a legible multiline chart."""
    try:
        if not isinstance(dataframe, pd.DataFrame):
            return None
        if columns is None:
            columns = [col for col in dataframe.columns if pd.to_numeric(dataframe[col], errors="coerce").notna().any()]
        if not columns:
            return None

        x_values = list(range(len(dataframe)))
        if "Date" in dataframe.columns:
            x_values = dataframe["Date"].tolist()
        elif isinstance(dataframe.index, pd.DatetimeIndex):
            x_values = dataframe.index.tolist()

        prepared = prepare_numeric_columns(dataframe, columns)

        colorscale = [
            [0.0, "#0B1220"],
            [0.25, "#1E3A8A"],
            [0.5, "#06B6D4"],
            [0.75, "#22C55E"],
            [1.0, "#F59E0B"],
        ]

        figure = go.Figure(data=go.Heatmap(
            z=prepared[columns].to_numpy().T, x=x_values, y=[str(c) for c in columns],
            colorscale=colorscale, showscale=True, zsmooth=False,
            colorbar={
                "tickfont": {"size": 9, "color": TEXT_MUTED, "family": MONO_FAMILY},
                "outlinewidth": 0, "thickness": 10, "len": 0.85, "ticks": "outside",
            },
            hovertemplate="<b>%{y}</b><br>%{x}<br>Value: <b>%{z:,.2f}</b><extra></extra>",
        ))

        return _HMI.apply(
            figure, title=title, x_label=x_label or "Date", y_label=y_label or "Meter Channel",
            show_legend=False, hovermode="closest",
        )
    except Exception as e:
        logger.error(f"Error in create_heatmap: {e}", exc_info=True)
        return None


def create_sparkline(values: pd.Series, line_color: str = THEME_PRIMARY_COLOR) -> go.Figure | None:
    """Compact KPI sparkline with gradient fill and glowing latest point."""
    try:
        if values is None or values.empty:
            return None
        numeric_values = pd.to_numeric(values, errors="coerce").dropna()
        if numeric_values.empty:
            return None

        resolved_color = line_color or SCADA_PALETTE[0]
        last_idx = len(numeric_values) - 1
        last_val = numeric_values.iloc[-1]

        figure = go.Figure()
        figure.add_trace(go.Scatter(
            x=list(range(len(numeric_values))), y=numeric_values, mode="lines",
            line={"color": resolved_color, "width": 2, "shape": "spline", "smoothing": 0.6},
            fill="tozeroy", fillcolor=_hex_to_rgba(resolved_color, 0.15),
            hoverinfo="skip",
        ))
        figure.add_trace(go.Scatter(
            x=[last_idx], y=[last_val], mode="markers",
            marker={"size": 7, "color": resolved_color, "line": {"width": 2, "color": BG_CARD}},
            hoverinfo="skip",
        ))

        return _HMI.minimal(figure)
    except Exception as e:
        logger.error(f"Error in create_sparkline: {e}", exc_info=True)
        return None


def create_kpi_trend(
    dataframe: pd.DataFrame, x_column: str, y_column: str, title: str,
    x_label: str | None = None, y_label: str | None = None,
) -> go.Figure | None:
    """Create a KPI trend chart (alias for line chart)."""
    return create_line_chart(dataframe, x_column, y_column, title, x_label, y_label)


def create_radar_chart(dataframe: pd.DataFrame, columns: list[str], title: str) -> go.Figure | None:
    """Normalized channel-profile radar — good for comparing several meters
    on a common 0-100 scale at a glance."""
    try:
        if not columns:
            return None
        normalized = []
        for col in columns:
            series = pd.to_numeric(dataframe[col], errors="coerce").dropna()
            if series.empty:
                normalized.append(0)
            else:
                max_val = series.max()
                latest_val = series.iloc[-1]
                norm_val = (latest_val / max_val * 100) if max_val > 0 else 0
                normalized.append(norm_val)

        categories = [str(c) for c in columns] + [str(columns[0])]
        values = normalized + [normalized[0]]
        accent = SCADA_PALETTE[0]

        fig = go.Figure(data=go.Scatterpolar(
            r=values, theta=categories, fill="toself",
            fillcolor=_hex_to_rgba(accent, 0.16),
            line={"color": accent, "width": 2, "shape": "spline"},
            marker={"size": 6, "color": accent, "line": {"width": 1, "color": BG_CARD}},
            hovertemplate="<b>%{theta}</b><br>%{r:.0f}% of peak<extra></extra>",
        ))
        fig.update_layout(
            polar={
                "bgcolor": BG_CARD,
                "radialaxis": {
                    "visible": True, "range": [0, 100], "gridcolor": GRID_COLOR,
                    "tickfont": {"size": 9, "color": TEXT_MUTED, "family": MONO_FAMILY},
                },
                "angularaxis": {"gridcolor": GRID_COLOR, "tickfont": {"size": 10, "color": TEXT_SECONDARY}},
            },
            showlegend=False,
            title=_HMI.title_block(title),
            paper_bgcolor=BG_CARD, plot_bgcolor=BG_CARD,
            margin={"l": 40, "r": 40, "t": 46, "b": 40},
            font=_HMI.BASE_FONT,
            hovermode="closest",
        )
        return fig
    except Exception as e:
        logger.error(f"Error in create_radar_chart: {e}", exc_info=True)
        return None


def create_waterfall_chart(dataframe: pd.DataFrame, x_column: str, y_column: str, title: str) -> go.Figure | None:
    """Waterfall for cumulative build-up/drawdown metrics."""
    try:
        validate_columns(dataframe, [x_column, y_column])
        prepared = prepare_numeric_columns(dataframe, [y_column]).dropna(subset=[y_column])
        if prepared.empty:
            return None
        fig = go.Figure(go.Waterfall(
            x=prepared[x_column], y=prepared[y_column], measure="relative",
            connector={"line": {"color": BORDER_SUBTLE, "width": 1}},
            decreasing={"marker": {"color": BAD_COLOR}},
            increasing={"marker": {"color": SCADA_PALETTE[0]}},
            totals={"marker": {"color": SCADA_PALETTE[4]}},
            hovertemplate=f"<b>%{{x}}</b><br>{y_column}: %{{y:,.2f}}<extra></extra>",
        ))
        return _HMI.apply(fig, title=title, x_label=str(x_column), y_label=str(y_column), show_legend=False)
    except Exception as e:
        logger.error(f"Error in create_waterfall_chart: {e}", exc_info=True)
        return None


def create_combined_line_area_chart(
    dataframe: pd.DataFrame, x_column: str, area_column: str, line_column: str, title: str,
) -> go.Figure | None:
    """Combined area (context) + line (signal) chart."""
    try:
        validate_columns(dataframe, [x_column, area_column, line_column])
        prepared = prepare_numeric_columns(dataframe, [area_column, line_column]).dropna(subset=[x_column])
        if prepared.empty:
            return None
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=prepared[x_column], y=prepared[area_column], fill="tozeroy", mode="lines",
            name=str(area_column), line={"color": SCADA_PALETTE[0], "width": 1.5, "shape": "spline"},
            fillcolor=_hex_to_rgba(SCADA_PALETTE[0], 0.14),
            hovertemplate=f"{area_column}: %{{y:,.2f}}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=prepared[x_column], y=prepared[line_column], mode="lines",
            name=str(line_column), line={"color": SCADA_PALETTE[2], "width": 2.2, "shape": "spline"},
            hovertemplate=f"{line_column}: %{{y:,.2f}}<extra></extra>",
        ))
        return _HMI.apply(fig, title=title, x_label=str(x_column))
    except Exception as e:
        logger.error(f"Error in create_combined_line_area_chart: {e}", exc_info=True)
        return None


def create_horizontal_bar_chart(dataframe: pd.DataFrame, x_column: str, y_column: str, title: str) -> go.Figure | None:
    """Ranked horizontal bars — the go-to for department/channel comparison."""
    try:
        validate_columns(dataframe, [x_column, y_column])
        prepared = prepare_numeric_columns(dataframe, [y_column]).dropna(subset=[y_column])
        if prepared.empty:
            return None

        prepared = prepared.sort_values(by=y_column, ascending=True)
        max_val = prepared[y_column].max() or 1.0
        colors = [
            _status_color(v / max_val) if max_val else SCADA_PALETTE[0]
            for v in prepared[y_column]
        ]

        fig = go.Figure(go.Bar(
            x=prepared[y_column], y=prepared[x_column].astype(str), orientation="h",
            marker={"color": colors, "opacity": 0.9, "cornerradius": 4, "line": {"width": 0}},
            text=[f"{v:,.1f}" for v in prepared[y_column]],
            textposition="outside",
            textfont={"size": 10, "color": TEXT_SECONDARY, "family": MONO_FAMILY},
            hovertemplate=f"<b>%{{y}}</b><br>{y_column}: <b>%{{x:,.2f}}</b><extra></extra>",
        ))
        fig.update_layout(bargap=0.32)
        return _HMI.apply(fig, title=title, x_label=str(y_column), y_label=str(x_column), show_legend=False,
                           hovermode="closest")
    except Exception as e:
        logger.error(f"Error in create_horizontal_bar_chart: {e}", exc_info=True)
        return None


def create_bullet_chart(actual: float, target: float, title: str, unit: str = "") -> go.Figure | None:
    """Target-vs-actual bullet chart — the standard industrial KPI widget."""
    try:
        if pd.isna(actual) or pd.isna(target):
            return None
        max_val = max(actual, target) * 1.25 if max(actual, target) > 0 else 100

        ratio = actual / max_val if max_val else 0
        actual_color = _status_color(ratio)

        steps = [
            {"range": [0, max_val * 0.6], "color": _hex_to_rgba(GOOD_COLOR, 0.08)},
            {"range": [max_val * 0.6, max_val * 0.8], "color": _hex_to_rgba(WARN_COLOR, 0.10)},
            {"range": [max_val * 0.8, max_val], "color": _hex_to_rgba(BAD_COLOR, 0.12)},
        ]

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=[max_val], y=[title], orientation="h",
            marker={"color": "rgba(255,255,255,0.02)"}, hoverinfo="skip", showlegend=False, width=0.5,
        ))

        for step in steps:
            fig.add_shape(
                type="rect", x0=step["range"][0], x1=step["range"][1], y0=-0.25, y1=0.25,
                fillcolor=step["color"], line_width=0, layer="below",
            )

        fig.add_trace(go.Bar(
            x=[actual], y=[title], orientation="h", width=0.32,
            marker={"color": actual_color, "opacity": 0.95, "cornerradius": 3},
            name="Actual",
            hovertemplate=f"<b>Actual</b>: %{{x:,.2f}} {unit}<extra></extra>",
        ))

        fig.add_shape(
            type="line", x0=target, x1=target, y0=-0.36, y1=0.36,
            line={"color": TEXT_PRIMARY, "width": 3},
        )
        fig.add_trace(go.Scatter(
            x=[target], y=[title], mode="markers", marker={"opacity": 0}, showlegend=False,
            name="Target", hovertemplate=f"<b>Target</b>: %{{x:,.2f}} {unit}<extra></extra>",
        ))

        gap_pct = ((actual - target) / target * 100) if target else 0
        gap_color = GOOD_COLOR if gap_pct >= 0 else BAD_COLOR
        fig.add_annotation(
            x=1, y=1.35, xref="paper", yref="paper", showarrow=False, xanchor="right",
            text=f"<span style='color:{gap_color};font-family:{MONO_FAMILY}'>{gap_pct:+.1f}%</span> vs target",
            font={"size": 10, "color": TEXT_MUTED},
        )

        fig.update_layout(
            barmode="overlay",
            title={
                "text": f"<b>{title}</b>", "font": {"size": 12, "color": TEXT_PRIMARY, "family": FONT_FAMILY},
                "y": 0.92, "x": 0.02, "xanchor": "left", "yanchor": "top",
            },
            xaxis={
                "range": [0, max_val], "gridcolor": GRID_COLOR, "zerolinecolor": ZERO_COLOR,
                "tickfont": {"size": 9, "color": TEXT_MUTED, "family": MONO_FAMILY},
            },
            yaxis={"showticklabels": False, "showgrid": False, "zeroline": False},
            showlegend=False,
            paper_bgcolor=BG_CARD, plot_bgcolor=BG_CARD,
            margin={"l": 20, "r": 20, "t": 44, "b": 20},
            font=_HMI.BASE_FONT,
            hovermode="closest",
        )
        return fig
    except Exception as e:
        logger.error(f"Error in create_bullet_chart: {e}", exc_info=True)
        return None


# ==================================================================
# Daily Trend Chart & Statistics Helpers
# ==================================================================

def create_daily_trend_chart(
    dataframe: pd.DataFrame, date_column: str, meter_column: str, title: str = "Daily Trend",
) -> go.Figure | None:
    """Smooth spline area daily trend with unified hover — matches the
    rest of the dashboard's premium trend styling."""
    try:
        validate_columns(dataframe, [date_column, meter_column])
        prepared = prepare_numeric_columns(dataframe, [meter_column]).dropna(subset=[meter_column])
        if prepared.empty:
            return None

        accent = SCADA_PALETTE[0]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=prepared[date_column], y=prepared[meter_column], mode="lines",
            name=str(meter_column),
            line={"color": accent, "width": 3, "shape": "spline", "smoothing": 0.65},
            fill="tozeroy", fillcolor=_hex_to_rgba(accent, 0.15),
            hovertemplate=f"<b>%{{x|%d %b, %H:%M}}</b><br>{meter_column}: <b>%{{y:,.2f}}</b><extra></extra>",
        ))

        last_val = prepared[meter_column].iloc[-1]
        last_date = prepared[date_column].iloc[-1]
        fig.add_trace(go.Scatter(
            x=[last_date], y=[last_val], mode="markers", showlegend=False,
            marker={"size": 9, "color": accent, "line": {"width": 2, "color": BG_CARD}},
            hovertemplate=f"<b>Current</b>: %{{y:,.2f}}<extra></extra>",
        ))

        is_date_axis = pd.api.types.is_datetime64_any_dtype(prepared[date_column]) or "date" in str(date_column).lower()
        y_range = _padded_y_range(prepared[meter_column])

        return _HMI.apply(
            fig, title=title, x_label="Date", y_label=str(meter_column),
            x_is_date=is_date_axis, y_range=y_range,
        )
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
    dataframe: pd.DataFrame, meter_column: str, date_column: str,
) -> tuple[go.Figure | None, dict[str, Any]]:
    """Get the daily trend figure and stats for a specific meter."""
    fig = create_daily_trend_chart(dataframe, date_column, meter_column, title=f"{meter_column} Daily Trend")
    stats = calculate_daily_stats(dataframe, meter_column)
    return fig, stats
