"""Reusable Plotly chart service for the Engineering Monitoring Dashboard.

This module is responsible for creating Plotly figures from
already-loaded pandas DataFrames, and for preparing chart-ready data
(date alignment and numeric meter selection) so that pages do not need
to contain any chart-preparation logic of their own. It contains no
Streamlit code, no workbook loading, and no Excel parsing. Every
dashboard page (Engineering, Utility, Air Compressor, Freon
Refrigeration, Ammonia Refrigeration, and Home) may reuse these
functions to build figures, which the calling page is then responsible
for rendering (e.g. via ``st.plotly_chart``).

No column names, meter names, department names, or worksheet names are
ever hardcoded; callers must supply the relevant column(s), title, and
axis labels, or a section dictionary from which these are discovered
dynamically.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from dashboard_data import get_date_columns

DEFAULT_TEMPLATE: str = "plotly_white"
"""Plotly template providing the clean, white-background dashboard theme."""

DEFAULT_HOVER_MODE: str = "x unified"
"""Unified hover mode used consistently across every chart."""

DEFAULT_DATE_COLUMN_LABEL: str = "Date"
"""Default column name used for the aligned date axis in trend data."""


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


def find_first_numeric_column(dataframe: pd.DataFrame) -> str | None:
    """Find the first column in a DataFrame with usable numeric readings.

    A column is considered usable when at least one of its values can
    be coerced to a number. Column order is preserved, so the first
    match in workbook order is returned.

    Args:
        dataframe: The DataFrame to inspect.

    Returns:
        The name of the first column with at least one numeric value,
        or ``None`` if no such column exists (including when
        ``dataframe`` is empty).
    """
    if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
        return None

    return next(
        (
            column
            for column in dataframe.columns
            if pd.to_numeric(dataframe[column], errors="coerce").notna().any()
        ),
        None,
    )


def align_dates_with_meter(
    overview_dataframe: pd.DataFrame,
    meter_series: pd.Series,
    date_column_label: str = DEFAULT_DATE_COLUMN_LABEL,
) -> pd.DataFrame | None:
    """Align a discovered date column with a single meter's readings.

    Discovers a date column dynamically from ``overview_dataframe`` via
    ``dashboard_data.get_date_columns``, skips the department/meter
    header rows (the first two rows), and pairs each date with the
    corresponding position in ``meter_series``. Rows with a missing date
    or a missing reading are dropped.

    Args:
        overview_dataframe: The overview worksheet DataFrame, used only
            to discover the date column.
        meter_series: The single meter's readings to align against the
            discovered dates.
        date_column_label: The column name to use for the aligned date
            axis in the returned DataFrame.

    Returns:
        A two-column DataFrame with ``date_column_label`` and the
        original name of ``meter_series``, or ``None`` if no date
        column could be discovered or no aligned rows remain.
    """
    if not isinstance(overview_dataframe, pd.DataFrame) or overview_dataframe.empty:
        return None
    if meter_series is None or meter_series.dropna().empty:
        return None

    date_columns = get_date_columns(overview_dataframe)
    if not date_columns:
        return None

    date_column_index = date_columns[0]
    date_values = (
        overview_dataframe.iloc[2:, date_column_index].reset_index(drop=True)
    )
    meter_values = meter_series.reset_index(drop=True)

    row_count = min(len(date_values), len(meter_values))
    if row_count == 0:
        return None

    meter_name = meter_series.name or "Value"

    trend_dataframe = pd.DataFrame(
        {
            date_column_label: date_values.iloc[:row_count].values,
            meter_name: meter_values.iloc[:row_count].values,
        }
    ).dropna()

    return trend_dataframe if not trend_dataframe.empty else None


def build_section_trend_data(
    overview_dataframe: pd.DataFrame,
    section: dict,
    date_column_label: str = DEFAULT_DATE_COLUMN_LABEL,
) -> tuple[pd.DataFrame, str, str] | None:
    """Build chart-ready trend data for a discovered department section.

    Combines dynamic date-column discovery with dynamic selection of the
    first meter that has usable numeric readings, then aligns the two
    into a single DataFrame ready for ``create_line_chart``.

    Args:
        overview_dataframe: The overview worksheet DataFrame, used to
            discover the date column.
        section: A section dictionary (as produced by
            ``dashboard_data.build_overview_dashboard``) containing a
            ``"dataframe"`` key with one column per meter.
        date_column_label: The column name to use for the aligned date
            axis in the returned trend DataFrame.

    Returns:
        A tuple of ``(trend_dataframe, date_column_name, meter_column_name)``
        if a valid date column and meter could be discovered and
        aligned, otherwise ``None``.
    """
    if not section or "dataframe" not in section:
        return None

    meters_dataframe = section["dataframe"]
    if not isinstance(meters_dataframe, pd.DataFrame) or meters_dataframe.empty:
        return None

    meter_column_name = find_first_numeric_column(meters_dataframe)
    if meter_column_name is None:
        return None

    trend_dataframe = align_dates_with_meter(
        overview_dataframe,
        meters_dataframe[meter_column_name],
        date_column_label=date_column_label,
    )
    if trend_dataframe is None:
        return None

    return trend_dataframe, date_column_label, meter_column_name


def build_section_trend_chart(
    overview_dataframe: pd.DataFrame,
    section: dict,
    date_column_label: str = DEFAULT_DATE_COLUMN_LABEL,
) -> go.Figure | None:
    """Build a ready-to-render trend chart for a discovered department section.

    Discovers a date column and the first numeric meter dynamically via
    ``build_section_trend_data``, then builds a styled line chart. Pages
    calling this function need no chart-preparation logic of their own;
    they only need to render the returned figure, or show a fallback
    message when ``None`` is returned.

    Args:
        overview_dataframe: The overview worksheet DataFrame, used to
            discover the date column.
        section: A section dictionary (as produced by
            ``dashboard_data.build_overview_dashboard``) containing a
            ``"dataframe"`` key with one column per meter.
        date_column_label: The column name to use for the aligned date
            axis.

    Returns:
        A styled Plotly ``Figure`` for the discovered meter's trend, or
        ``None`` if no valid date column or numeric meter could be
        discovered.
    """
    trend_data = build_section_trend_data(
        overview_dataframe, section, date_column_label=date_column_label
    )
    if trend_data is None:
        return None

    trend_dataframe, date_column_name, meter_column_name = trend_data

    return create_line_chart(
        trend_dataframe,
        x_column=date_column_name,
        y_column=meter_column_name,
        title=f"{meter_column_name} Trend",
        x_label=date_column_name,
        y_label=meter_column_name,
    )


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
        x_label=str(x_label or x_column),
        y_label=str(y_label or "Value"),
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
