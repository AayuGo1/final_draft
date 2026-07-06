"""Reusable Plotly chart service for the Engineering Monitoring Dashboard.

This module is responsible ONLY for creating Plotly figures from
already-loaded pandas DataFrames. It contains no Streamlit code, no
workbook loading, no Excel parsing, no KPI calculations, and no
dashboard rendering. Every dashboard page (Engineering, Utility, Air
Compressor, Freon Refrigeration, Ammonia Refrigeration, and Home) may
reuse these functions to build figures, which the calling page is then
responsible for rendering (e.g. via ``st.plotly_chart``).

No column names, meter names, department names, or worksheet names are
ever hardcoded; callers must supply the relevant column(s), title, and
axis labels.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

DEFAULT_TEMPLATE: str = "plotly_white"
"""Plotly template providing the clean, white-background dashboard theme."""

DEFAULT_HOVER_MODE: str = "x unified"
"""Unified hover mode used consistently across every chart."""


def validate_columns(dataframe: pd.DataFrame, columns: list[str]) -> None:
    """Validate that the given columns exist in a DataFrame.

    Args:
        dataframe: The DataFrame to check.
        columns: The list of column names that must be present.

    Raises:
        ValueError: If ``dataframe`` is not a valid ``pandas.DataFrame``,
            or if any of ``columns`` is not present in it.
    """
    if not isinstance(dataframe, pd.DataFrame):
        raise ValueError(
            f"Expected a pandas.DataFrame, got {type(dataframe).__name__}."
        )

    missing_columns = [
        column for column in columns if column not in dataframe.columns
    ]
    if missing_columns:
        raise ValueError(
            f"The following columns were not found in the DataFrame: "
            f"{missing_columns}."
        )


def prepare_numeric_columns(
    dataframe: pd.DataFrame, columns: list[str]
) -> pd.DataFrame:
    """Coerce the given columns of a DataFrame to numeric values.

    Non-numeric values are converted to ``NaN`` rather than raising, so
    that charts can be built even from worksheets containing stray text
    or blank cells within otherwise-numeric columns.

    Args:
        dataframe: The source DataFrame.
        columns: The column names to coerce to numeric.

    Returns:
        A copy of ``dataframe`` with ``columns`` coerced to numeric
        dtypes via ``pandas.to_numeric`` (invalid values become
        ``NaN``).

    Raises:
        ValueError: If ``dataframe`` is not a valid ``pandas.DataFrame``,
            or if any of ``columns`` is not present in it.
    """
    validate_columns(dataframe, columns)

    prepared = dataframe.copy()
    for column in columns:
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")

    return prepared


def apply_default_layout(
    figure: go.Figure,
    title: str,
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure:
    """Apply the shared engineering dashboard theme to a Plotly figure.

    Applies a white background template, unified hover mode, an enabled
    legend, responsive sizing, and consistent axis/title styling.

    Args:
        figure: The Plotly figure to style.
        title: The descriptive chart title.
        x_label: Optional label for the x-axis. Defaults to the axis's
            existing label if not provided.
        y_label: Optional label for the y-axis. Defaults to the axis's
            existing label if not provided.

    Returns:
        The same ``figure`` instance, updated in place, for convenience
        chaining.
    """
    figure.update_layout(
        title=title,
        template=DEFAULT_TEMPLATE,
        hovermode=DEFAULT_HOVER_MODE,
        showlegend=True,
        autosize=True,
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
    )

    if x_label is not None:
        figure.update_xaxes(title_text=x_label)
    if y_label is not None:
        figure.update_yaxes(title_text=y_label)

    return figure


def create_line_chart(
    dataframe: pd.DataFrame,
    x_column: str,
    y_column: str,
    title: str,
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure:
    """Create a single-series line chart.

    Args:
        dataframe: The source DataFrame.
        x_column: The column name to use for the x-axis.
        y_column: The column name to use for the y-axis (single series).
        title: The descriptive chart title.
        x_label: Optional custom x-axis label. Defaults to ``x_column``.
        y_label: Optional custom y-axis label. Defaults to ``y_column``.

    Returns:
        A styled Plotly ``Figure`` containing the line chart.

    Raises:
        ValueError: If ``dataframe`` is not a valid ``pandas.DataFrame``,
            or if ``x_column`` / ``y_column`` are not present in it.
    """
    validate_columns(dataframe, [x_column, y_column])
    prepared = prepare_numeric_columns(dataframe, [y_column])

    figure = px.line(prepared, x=x_column, y=y_column)

    return apply_default_layout(
        figure,
        title=title,
        x_label=x_label or x_column,
        y_label=y_label or y_column,
    )


def create_multi_line_chart(
    dataframe: pd.DataFrame,
    x_column: str,
    y_columns: list[str],
    title: str,
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure:
    """Create a multi-series line chart.

    Args:
        dataframe: The source DataFrame.
        x_column: The column name to use for the x-axis.
        y_columns: The list of column names to plot as separate lines.
        title: The descriptive chart title.
        x_label: Optional custom x-axis label. Defaults to ``x_column``.
        y_label: Optional custom y-axis label. Defaults to a generic
            "Value" label.

    Returns:
        A styled Plotly ``Figure`` containing one line per entry in
        ``y_columns``.

    Raises:
        ValueError: If ``dataframe`` is not a valid ``pandas.DataFrame``,
            or if ``x_column`` / any of ``y_columns`` is not present in
            it.
    """
    validate_columns(dataframe, [x_column, *y_columns])
    prepared = prepare_numeric_columns(dataframe, y_columns)

    figure = px.line(prepared, x=x_column, y=y_columns)

    return apply_default_layout(
        figure,
        title=title,
        x_label=x_label or x_column,
        y_label=y_label or "Value",
    )


def create_bar_chart(
    dataframe: pd.DataFrame,
    x_column: str,
    y_columns: str | list[str],
    title: str,
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure:
    """Create a bar chart, supporting single or grouped series.

    Args:
        dataframe: The source DataFrame.
        x_column: The column name to use for the x-axis categories.
        y_columns: A single column name, or a list of column names for
            grouped bars.
        title: The descriptive chart title.
        x_label: Optional custom x-axis label. Defaults to ``x_column``.
        y_label: Optional custom y-axis label. Defaults to a generic
            "Value" label, or the single column name if only one is
            given.

    Returns:
        A styled Plotly ``Figure`` containing the bar chart.

    Raises:
        ValueError: If ``dataframe`` is not a valid ``pandas.DataFrame``,
            or if ``x_column`` / any of ``y_columns`` is not present in
            it.
    """
    columns_list = [y_columns] if isinstance(y_columns, str) else y_columns
    validate_columns(dataframe, [x_column, *columns_list])
    prepared = prepare_numeric_columns(dataframe, columns_list)

    figure = px.bar(prepared, x=x_column, y=y_columns, barmode="group")

    default_y_label = columns_list[0] if len(columns_list) == 1 else "Value"

    return apply_default_layout(
        figure,
        title=title,
        x_label=x_label or x_column,
        y_label=y_label or default_y_label,
    )


def create_area_chart(
    dataframe: pd.DataFrame,
    x_column: str,
    y_columns: str | list[str],
    title: str,
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure:
    """Create an area chart, supporting single or stacked series.

    Args:
        dataframe: The source DataFrame.
        x_column: The column name to use for the x-axis.
        y_columns: A single column name, or a list of column names to
            stack as separate areas.
        title: The descriptive chart title.
        x_label: Optional custom x-axis label. Defaults to ``x_column``.
        y_label: Optional custom y-axis label. Defaults to a generic
            "Value" label, or the single column name if only one is
            given.

    Returns:
        A styled Plotly ``Figure`` containing the area chart.

    Raises:
        ValueError: If ``dataframe`` is not a valid ``pandas.DataFrame``,
            or if ``x_column`` / any of ``y_columns`` is not present in
            it.
    """
    columns_list = [y_columns] if isinstance(y_columns, str) else y_columns
    validate_columns(dataframe, [x_column, *columns_list])
    prepared = prepare_numeric_columns(dataframe, columns_list)

    figure = px.area(prepared, x=x_column, y=y_columns)

    default_y_label = columns_list[0] if len(columns_list) == 1 else "Value"

    return apply_default_layout(
        figure,
        title=title,
        x_label=x_label or x_column,
        y_label=y_label or default_y_label,
    )


def create_scatter_chart(
    dataframe: pd.DataFrame,
    x_column: str,
    y_column: str,
    title: str,
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure:
    """Create a scatter chart comparing two columns.

    Args:
        dataframe: The source DataFrame.
        x_column: The column name to use for the x-axis.
        y_column: The column name to use for the y-axis.
        title: The descriptive chart title.
        x_label: Optional custom x-axis label. Defaults to ``x_column``.
        y_label: Optional custom y-axis label. Defaults to ``y_column``.

    Returns:
        A styled Plotly ``Figure`` containing the scatter chart.

    Raises:
        ValueError: If ``dataframe`` is not a valid ``pandas.DataFrame``,
            or if ``x_column`` / ``y_column`` are not present in it.
    """
    validate_columns(dataframe, [x_column, y_column])
    prepared = prepare_numeric_columns(dataframe, [x_column, y_column])

    figure = px.scatter(prepared, x=x_column, y=y_column)

    return apply_default_layout(
        figure,
        title=title,
        x_label=x_label or x_column,
        y_label=y_label or y_column,
    )


def create_histogram(
    dataframe: pd.DataFrame,
    x_column: str,
    title: str,
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure:
    """Create a histogram of a single column's distribution.

    Args:
        dataframe: The source DataFrame.
        x_column: The column name whose distribution to plot.
        title: The descriptive chart title.
        x_label: Optional custom x-axis label. Defaults to ``x_column``.
        y_label: Optional custom y-axis label. Defaults to "Count".

    Returns:
        A styled Plotly ``Figure`` containing the histogram.

    Raises:
        ValueError: If ``dataframe`` is not a valid ``pandas.DataFrame``,
            or if ``x_column`` is not present in it.
    """
    validate_columns(dataframe, [x_column])
    prepared = prepare_numeric_columns(dataframe, [x_column])

    figure = px.histogram(prepared, x=x_column)

    return apply_default_layout(
        figure,
        title=title,
        x_label=x_label or x_column,
        y_label=y_label or "Count",
    )
