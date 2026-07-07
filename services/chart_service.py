"""Reusable Plotly chart service for the Engineering Monitoring Dashboard.

This module is responsible for creating Plotly figures from
already-loaded pandas DataFrames, and for preparing chart-ready data
(date alignment and numeric meter selection) so that pages do not need
to contain any chart-preparation logic of their own. It contains no
Streamlit code, no workbook loading, no Excel parsing, and no
engineering KPI calculation. Every dashboard page (Engineering,
Utility, Air Compressor, Freon Refrigeration, Ammonia Refrigeration,
and Home) may reuse these functions to build figures, which the calling
page is then responsible for rendering (e.g. via ``st.plotly_chart``).

No column names, meter names, department names, or worksheet names are
ever hardcoded; callers must supply the relevant column(s), title, and
axis labels, or a section dictionary from which these are discovered
dynamically. All colors are sourced from ``config.py`` rather than
hardcoded here.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config import (
    THEME_CHART_PALETTE,
    THEME_DANGER_COLOR,
    THEME_PRIMARY_COLOR,
    THEME_SUCCESS_COLOR,
    THEME_WARNING_COLOR,
)
from dashboard_data import get_date_columns

DEFAULT_TEMPLATE: str = "plotly_white"
"""Plotly template providing the clean, white-background dashboard theme."""

DEFAULT_HOVER_MODE: str = "x unified"
"""Unified hover mode used consistently across every chart."""

DEFAULT_DATE_COLUMN_LABEL: str = "Date"
"""Default column name used for the aligned date axis in trend data."""

DEFAULT_COLOR_SEQUENCE: list[str] = THEME_CHART_PALETTE
"""Ordered color sequence applied to multi-series charts, from config.py."""


# ==================================================
# DATA PREPARATION HELPERS
# ==================================================


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


# ==================================================
# SHARED STYLING
# ==================================================


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


def apply_minimal_layout(figure: go.Figure) -> go.Figure:
    """Apply a stripped-down layout for small, inline indicator charts.

    Removes axes, legends, and margins so the figure (e.g. a sparkline)
    can sit compactly inside a KPI card.

    Args:
        figure: The Plotly figure to style.

    Returns:
        The same ``figure`` instance, updated in place, for convenience
        chaining.
    """
    figure.update_layout(
        template=DEFAULT_TEMPLATE,
        showlegend=False,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        xaxis={"visible": False},
        yaxis={"visible": False},
        autosize=True,
    )
    return figure


# ==================================================
# CORE CHART BUILDERS
# ==================================================


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

    figure = px.line(
        prepared,
        x=x_column,
        y=y_column,
        color_discrete_sequence=[THEME_PRIMARY_COLOR],
    )

    return apply_default_layout(
        figure,
        title=title,
        x_label=str(x_label) if x_label is not None else str(x_column),
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

    figure = px.line(
        prepared,
        x=x_column,
        y=y_columns,
        color_discrete_sequence=DEFAULT_COLOR_SEQUENCE,
    )

    return apply_default_layout(
        figure,
        title=title,
        x_label=str(x_label or x_column),
        y_label=str(y_label or "Value"),
    )


def create_trend_comparison_chart(
    dataframe: pd.DataFrame,
    x_column: str,
    y_columns: list[str],
    title: str,
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure:
    """Create a multi-series line chart for comparing several meters' trends.

    This is a semantic wrapper around ``create_multi_line_chart`` intended
    for side-by-side comparison of two or more meters/departments over a
    shared date axis (e.g. "this year vs last year", or "compressor A vs
    compressor B").

    Args:
        dataframe: The source DataFrame.
        x_column: The column name to use for the shared x-axis.
        y_columns: The list of column names to compare as separate lines.
        title: The descriptive chart title.
        x_label: Optional custom x-axis label. Defaults to ``x_column``.
        y_label: Optional custom y-axis label. Defaults to a generic
            "Value" label.

    Returns:
        A styled Plotly ``Figure`` comparing every series in
        ``y_columns``.

    Raises:
        ValueError: If ``dataframe`` is not a valid ``pandas.DataFrame``,
            or if ``x_column`` / any of ``y_columns`` is not present in
            it.
    """
    return create_multi_line_chart(
        dataframe,
        x_column=x_column,
        y_columns=y_columns,
        title=title,
        x_label=x_label,
        y_label=y_label,
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

    figure = px.bar(
        prepared,
        x=x_column,
        y=y_columns,
        barmode="group",
        color_discrete_sequence=DEFAULT_COLOR_SEQUENCE,
    )

    default_y_label = columns_list[0] if len(columns_list) == 1 else "Value"

    return apply_default_layout(
        figure,
        title=title,
        x_label=str(x_label) if x_label is not None else str(x_column),
        y_label=y_label or default_y_label,
    )


def create_stacked_bar_chart(
    dataframe: pd.DataFrame,
    x_column: str,
    y_columns: list[str],
    title: str,
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure:
    """Create a stacked bar chart across multiple series.

    Args:
        dataframe: The source DataFrame.
        x_column: The column name to use for the x-axis categories.
        y_columns: The list of column names to stack.
        title: The descriptive chart title.
        x_label: Optional custom x-axis label. Defaults to ``x_column``.
        y_label: Optional custom y-axis label. Defaults to a generic
            "Value" label.

    Returns:
        A styled Plotly ``Figure`` containing the stacked bar chart.

    Raises:
        ValueError: If ``dataframe`` is not a valid ``pandas.DataFrame``,
            or if ``x_column`` / any of ``y_columns`` is not present in
            it.
    """
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
        x_label=str(x_label) if x_label is not None else str(x_column),
        y_label=str(y_label or "Value"),
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

    figure = px.area(
        prepared,
        x=x_column,
        y=y_columns,
        color_discrete_sequence=DEFAULT_COLOR_SEQUENCE,
    )

    default_y_label = columns_list[0] if len(columns_list) == 1 else "Value"

    return apply_default_layout(
        figure,
        title=title,
        x_label=str(x_label) if x_label is not None else str(x_column),
        y_label=y_label or default_y_label,
    )


def create_pie_chart(
    dataframe: pd.DataFrame,
    names_column: str,
    values_column: str,
    title: str,
) -> go.Figure:
    """Create a pie chart showing the share of each category.

    Args:
        dataframe: The source DataFrame.
        names_column: The column name providing each slice's label.
        values_column: The column name providing each slice's value.
        title: The descriptive chart title.

    Returns:
        A styled Plotly ``Figure`` containing the pie chart.

    Raises:
        ValueError: If ``dataframe`` is not a valid ``pandas.DataFrame``,
            or if ``names_column`` / ``values_column`` are not present
            in it.
    """
    validate_columns(dataframe, [names_column, values_column])
    prepared = prepare_numeric_columns(dataframe, [values_column])

    figure = px.pie(
        prepared,
        names=names_column,
        values=values_column,
        color_discrete_sequence=DEFAULT_COLOR_SEQUENCE,
    )

    return apply_default_layout(figure, title=title)


def create_donut_chart(
    dataframe: pd.DataFrame,
    names_column: str,
    values_column: str,
    title: str,
    hole_size: float = 0.5,
) -> go.Figure:
    """Create a donut chart showing the share of each category.

    Args:
        dataframe: The source DataFrame.
        names_column: The column name providing each slice's label.
        values_column: The column name providing each slice's value.
        title: The descriptive chart title.
        hole_size: The relative size of the center hole, between 0.0
            and 1.0. Defaults to 0.5.

    Returns:
        A styled Plotly ``Figure`` containing the donut chart.

    Raises:
        ValueError: If ``dataframe`` is not a valid ``pandas.DataFrame``,
            or if ``names_column`` / ``values_column`` are not present
            in it.
    """
    validate_columns(dataframe, [names_column, values_column])
    prepared = prepare_numeric_columns(dataframe, [values_column])

    figure = px.pie(
        prepared,
        names=names_column,
        values=values_column,
        hole=hole_size,
        color_discrete_sequence=DEFAULT_COLOR_SEQUENCE,
    )

    return apply_default_layout(figure, title=title)


def create_gauge_chart(
    value: float,
    title: str,
    minimum: float = 0.0,
    maximum: float = 100.0,
    warning_threshold: float | None = None,
    danger_threshold: float | None = None,
    unit: str = "",
) -> go.Figure:
    """Create a single-value gauge chart, e.g. for KPI cards.

    The gauge bar and threshold bands use the shared theme colors from
    ``config.py``: green for the normal range, amber from
    ``warning_threshold`` onward, and red from ``danger_threshold``
    onward. If either threshold is omitted, its corresponding band is
    skipped.

    Args:
        value: The current value to display.
        title: The descriptive chart title.
        minimum: The minimum of the gauge's scale. Defaults to 0.0.
        maximum: The maximum of the gauge's scale. Defaults to 100.0.
        warning_threshold: Optional value at which the gauge enters the
            warning color band.
        danger_threshold: Optional value at which the gauge enters the
            danger color band.
        unit: Optional unit suffix appended to the displayed number.

    Returns:
        A styled Plotly ``Figure`` containing the gauge chart.
    """
    steps = []
    band_start = minimum

    if warning_threshold is not None and warning_threshold > minimum:
        steps.append(
            {"range": [band_start, warning_threshold], "color": THEME_SUCCESS_COLOR}
        )
        band_start = warning_threshold

    if danger_threshold is not None and danger_threshold > band_start:
        steps.append(
            {"range": [band_start, danger_threshold], "color": THEME_WARNING_COLOR}
        )
        band_start = danger_threshold

    if band_start < maximum:
        steps.append({"range": [band_start, maximum], "color": THEME_DANGER_COLOR})

    figure = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"suffix": f" {unit}".rstrip() if unit else ""},
            gauge={
                "axis": {"range": [minimum, maximum]},
                "bar": {"color": THEME_PRIMARY_COLOR},
                "steps": steps or None,
            },
        )
    )

    figure.update_layout(
        title=title,
        template=DEFAULT_TEMPLATE,
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
        autosize=True,
    )

    return figure


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

    figure = px.scatter(
        prepared,
        x=x_column,
        y=y_column,
        color_discrete_sequence=[THEME_PRIMARY_COLOR],
    )

    return apply_default_layout(
        figure,
        title=title,
        x_label=str(x_label) if x_label is not None else str(x_column),
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

    figure = px.histogram(
        prepared,
        x=x_column,
        color_discrete_sequence=[THEME_PRIMARY_COLOR],
    )

    return apply_default_layout(
        figure,
        title=title,
        x_label=str(x_label) if x_label is not None else str(x_column),
        y_label=y_label or "Count",
    )


def create_heatmap(
    dataframe: pd.DataFrame,
    columns: list[str] | None = None,
    title: str = "Heatmap",
    x_label: str | None = None,
    y_label: str | None = None,
) -> go.Figure:
    """Create a heatmap of numeric values across rows and columns.

    Useful for visualizing many meters' readings at once (e.g. a
    department's full meter set, one column per meter, one row per
    day), or for a correlation matrix when ``columns`` selects several
    numeric meters.

    Args:
        dataframe: The source DataFrame.
        columns: Optional list of column names to include. Defaults to
            every column in ``dataframe`` that has at least one numeric
            value.
        title: The descriptive chart title.
        x_label: Optional custom x-axis label.
        y_label: Optional custom y-axis label.

    Returns:
        A styled Plotly ``Figure`` containing the heatmap.

    Raises:
        ValueError: If ``dataframe`` is not a valid ``pandas.DataFrame``,
            if any of ``columns`` is not present in it, or if no numeric
            columns are available to plot.
    """
    if not isinstance(dataframe, pd.DataFrame):
        raise ValueError(
            f"Expected a pandas.DataFrame, got {type(dataframe).__name__}."
        )

    if columns is None:
        columns = [
            column
            for column in dataframe.columns
            if pd.to_numeric(dataframe[column], errors="coerce").notna().any()
        ]

    if not columns:
        raise ValueError(
            "No numeric columns were found to build the heatmap."
        )

    prepared = prepare_numeric_columns(dataframe, columns)

    figure = go.Figure(
        data=go.Heatmap(
            z=prepared[columns].to_numpy().T,
            x=list(range(len(prepared))),
            y=columns,
            colorscale="Blues",
        )
    )

    return apply_default_layout(
        figure,
        title=title,
        x_label=x_label or "Index",
        y_label=y_label or "Meter",
    )


def create_sparkline(
    values: pd.Series,
    line_color: str = THEME_PRIMARY_COLOR,
) -> go.Figure:
    """Create a compact, axis-free sparkline for a single meter.

    Intended for embedding inline next to a KPI value to give a quick
    visual sense of recent trend, without the overhead of a full chart.

    Args:
        values: A Series of readings for a single meter, in
            chronological order.
        line_color: The line color to use. Defaults to the primary
            theme color from ``config.py``.

    Returns:
        A minimally-styled Plotly ``Figure`` containing the sparkline.
    """
    numeric_values = pd.to_numeric(values, errors="coerce").dropna()

    figure = go.Figure(
        data=go.Scatter(
            x=list(range(len(numeric_values))),
            y=numeric_values,
            mode="lines",
            line={"color": line_color, "width": 2},
            fill="tozeroy",
            fillcolor=line_color,
            opacity=0.9,
        )
    )

    return apply_minimal_layout(figure)
