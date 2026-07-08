"""Air compressor monitoring page for the Engineering Monitoring Dashboard.

Renders the real Air Compressor worksheet (``dashboard["air_compressor"]``)
loaded via ``services.dashboard_loader``, with KPI cards from
``services.kpi_service``, a full engineering-analytics chart suite from
``services.chart_service``, and native Streamlit data tables. No KPI
calculation or chart-building logic lives in this file.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import ui
from dashboard_data import get_date_columns
from services import chart_service, kpi_service, page_loader
from services.dashboard_loader import load_dashboard_safe

AIR_COMPRESSOR_KEY: str = "air_compressor"
AVAILABILITY_HEALTHY_THRESHOLD: float = 0.9
AVAILABILITY_PARTIAL_THRESHOLD: float = 0.5


def render_kpi_row(summary: dict) -> None:
    """Render the top KPI row from a kpi_service summary."""
    cards = [
        {"title": "Number of Meters", "value": summary["meters"]},
        {"title": "Available Readings", "value": summary["available_readings"]},
        {"title": "Latest Timestamp", "value": summary["latest_timestamp"]},
        {
            "title": "Data Availability",
            "value": f"{summary['availability'] * 100:.1f}%",
        },
    ]
    ui.render_kpi_cards(cards)


def render_status_section(summary: dict) -> None:
    """Render a status banner based on the worksheet's data availability."""
    availability = summary["availability"]
    if availability >= AVAILABILITY_HEALTHY_THRESHOLD:
        ui.render_success_banner("Status: Monitoring — data is healthy.")
    elif availability >= AVAILABILITY_PARTIAL_THRESHOLD:
        ui.render_info_banner("Status: Monitoring — partial data available.")
    else:
        ui.render_error_banner(
            "Status: Attention needed — low data availability."
        )


def resolve_date_column(dataframe: pd.DataFrame) -> str | None:
    """Resolve the worksheet's date column name via `get_date_columns`."""
    date_columns = get_date_columns(dataframe)
    if not date_columns:
        return None
    return dataframe.columns[date_columns[0]]


def render_trend_section(dataframe: pd.DataFrame, date_column: str | None) -> None:
    """Render a multi-meter Plotly trend chart for the worksheet."""
    ui.render_section("Trend Analysis")
    with st.container(border=True):
        if not date_column:
            ui.render_info_banner("No date column was discovered to chart.")
            return

        meter_columns = chart_service.discover_numeric_meters(dataframe, date_column=date_column)
        if not meter_columns:
            ui.render_info_banner("No meter columns were discovered to chart.")
            return

        figure = chart_service.create_multi_line_chart(
            dataframe,
            x_column=date_column,
            y_columns=meter_columns,
            title="Air Compressor Meters Trend",
        )
        if figure is None:
            ui.render_info_banner("No trend data is available to chart yet.")
        else:
            st.plotly_chart(figure, use_container_width=True)


def render_analytics_section(dataframe: pd.DataFrame, date_column: str | None) -> None:
    """Render the full engineering-analytics chart suite for Air Compressor.

    Builds one bundle from the worksheet DataFrame (auto-discovering every
    numeric meter column) and renders every chart/table it contains.
    """
    if not date_column:
        return

    ui.render_section("Air Compressor — Engineering Analytics")
    bundle = chart_service.build_department_analytics_bundle(
        dataframe, title_prefix="Air Compressor", date_column=date_column,
    )

    if not bundle["meters"]:
        ui.render_info_banner("No meters available for analytics.")
        return

    with st.container(border=True):
        if bundle["daily_trend"] is not None:
            st.plotly_chart(bundle["daily_trend"], use_container_width=True)

    with st.container(border=True):
        if bundle["weekly_moving_average"] is not None:
            st.plotly_chart(bundle["weekly_moving_average"], use_container_width=True)

    if bundle["multi_line"] is not None:
        with st.container(border=True):
            st.plotly_chart(bundle["multi_line"], use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            if bundle["comparison_bar"] is not None:
                st.plotly_chart(bundle["comparison_bar"], use_container_width=True)
    with col2:
        with st.container(border=True):
            if bundle["top_bottom_chart"] is not None:
                st.plotly_chart(bundle["top_bottom_chart"], use_container_width=True)

    if bundle["heatmap"] is not None:
        with st.container(border=True):
            st.plotly_chart(bundle["heatmap"], use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        with st.container(border=True):
            if bundle["histogram"] is not None:
                st.plotly_chart(bundle["histogram"], use_container_width=True)
    with col4:
        with st.container(border=True):
            if bundle["radar"] is not None:
                st.plotly_chart(bundle["radar"], use_container_width=True)
            else:
                ui.render_info_banner("Radar needs at least 3 meters to compare.")

    if bundle["gauges"]:
        ui.render_section("Air Compressor — Live Gauges")
        gauge_items = list(bundle["gauges"].items())
        for row_start in range(0, len(gauge_items), 3):
            row_items = gauge_items[row_start:row_start + 3]
            columns = st.columns(len(row_items))
            for column, (meter, figure) in zip(columns, row_items):
                with column:
                    with st.container(border=True):
                        if figure is not None:
                            st.plotly_chart(figure, use_container_width=True)

    if bundle["sparklines"]:
        ui.render_section("Air Compressor — Meter Sparklines")
        spark_items = list(bundle["sparklines"].items())
        for row_start in range(0, len(spark_items), 4):
            row_items = spark_items[row_start:row_start + 4]
            columns = st.columns(len(row_items))
            for column, (meter, figure) in zip(columns, row_items):
                with column:
                    st.caption(meter)
                    if figure is not None:
                        st.plotly_chart(figure, use_container_width=True, config={"staticPlot": True})

    ui.render_section("Air Compressor — Statistics Panel")
    with st.container(border=True):
        ui.render_dataframe(bundle["statistics_table"])

    ui.render_section("Air Compressor — Daily Change")
    with st.container(border=True):
        ui.render_dataframe(bundle["change_table"])


def render_latest_readings_table(dataframe: pd.DataFrame) -> None:
    """Render a table of the latest reading for every meter column."""
    ui.render_section("Latest Readings")
    latest = {
        str(column): (
            dataframe[column].dropna().iloc[-1]
            if not dataframe[column].dropna().empty
            else None
        )
        for column in dataframe.columns
    }
    table = pd.DataFrame(
        {"Meter": list(latest.keys()), "Latest Value": list(latest.values())}
    )
    with st.container(border=True):
        ui.render_dataframe(table)


def render_data_section(dataframe: pd.DataFrame) -> None:
    """Render a preview and expandable full history of the worksheet."""
    ui.render_section("Historical Data")
    with st.container(border=True):
        ui.render_dataframe(dataframe.head(15))
        with st.expander("View full history"):
            ui.render_dataframe(dataframe)


def render_summary_section(summary: dict) -> None:
    """Render a compact data summary table."""
    ui.render_section("Data Summary")
    with st.container(border=True):
        ui.render_dataframe(pd.DataFrame([summary]))


def render() -> None:
    """Render the complete Air Compressor page."""
    ui.render_page_title(
        "Air Compressor",
        "Air compressor load, output, and efficiency tracking.",
    )

    with st.spinner("Loading air compressor data..."):
        dashboard, error = load_dashboard_safe()

    if error:
        ui.render_error_banner(error)
        return

    dataframe = dashboard.get(AIR_COMPRESSOR_KEY)
    if dataframe is None or dataframe.empty:
        ui.render_info_banner(
            "No Air Compressor worksheet was found in the workbook."
        )
        return

    date_column = resolve_date_column(dataframe)
    summary = kpi_service.build_kpi_summary(dataframe)

    render_kpi_row(summary)
    render_status_section(summary)
    ui.render_divider()

    # TASK 6 & 7: Added Daily Trend Section
    page_loader.render_daily_trend_section(dataframe)
    ui.render_divider()

    render_trend_section(dataframe, date_column)
    ui.render_divider()

    render_analytics_section(dataframe, date_column)
    ui.render_divider()

    render_latest_readings_table(dataframe)
    ui.render_divider()

    render_data_section(dataframe)
    ui.render_divider()

    render_summary_section(summary)
