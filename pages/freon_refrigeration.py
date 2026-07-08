"""Freon Refrigeration monitoring page for the Engineering Monitoring Dashboard.

Renders the real Freon Refrigeration data, preferring a dedicated Freon
worksheet (``dashboard["freon"]``) and falling back to a discovered
overview section, via ``dashboard_data.build_overview_dashboard``. KPI
cards come from ``services.kpi_service`` and the full engineering-analytics
chart suite comes from ``services.chart_service``. No KPI calculation or
chart-building logic lives in this file.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import ui
from dashboard_data import (
    build_overview_dashboard,
    find_section_by_keyword,
    get_date_columns,
)
from services import chart_service, kpi_service, page_loader
from services.dashboard_loader import load_dashboard_safe

FREON_KEY: str = "freon"
FREON_KEYWORD: str = "freon"
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
    """Render a status banner based on the data's availability."""
    availability = summary["availability"]
    if availability >= AVAILABILITY_HEALTHY_THRESHOLD:
        ui.render_success_banner("Status: Monitoring — data is healthy.")
    elif availability >= AVAILABILITY_PARTIAL_THRESHOLD:
        ui.render_info_banner("Status: Monitoring — partial data available.")
    else:
        ui.render_error_banner(
            "Status: Attention needed — low data availability."
        )


def resolve_date_column(dataframe: pd.DataFrame, section: dict | None) -> str | None:
    """Resolve the date column name for either a section or a raw worksheet.

    A discovered section's ``dataframe`` always carries a ``Date`` column
    (assembled by the business layer); a raw worksheet needs its date
    column discovered via `get_date_columns`.
    """
    if section is not None:
        return chart_service.DEFAULT_DATE_COLUMN_LABEL

    date_columns = get_date_columns(dataframe)
    if not date_columns:
        return None
    return dataframe.columns[date_columns[0]]


def render_trend_section(
    dataframe: pd.DataFrame, section: dict | None, date_column: str | None,
) -> None:
    """Render a Plotly trend chart for the Freon Refrigeration data."""
    ui.render_section("Trend Analysis")
    with st.container(border=True):
        if section is not None:
            figure = chart_service.build_section_trend_chart(
                section["overview_dataframe"], section
            )
            if figure is None:
                ui.render_info_banner("No trend data is available to chart yet.")
            else:
                st.plotly_chart(figure, use_container_width=True)
            return

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
            title="Freon Refrigeration Meters Trend",
        )
        if figure is None:
            ui.render_info_banner("No trend data is available to chart yet.")
        else:
            st.plotly_chart(figure, use_container_width=True)


def render_analytics_section(dataframe: pd.DataFrame, date_column: str | None) -> None:
    """Render the full engineering-analytics chart suite for Freon Refrigeration.

    Builds one bundle from the resolved DataFrame (auto-discovering every
    numeric meter column) and renders every chart/table it contains.
    """
    if not date_column:
        return

    ui.render_section("Freon Refrigeration — Engineering Analytics")
    bundle = chart_service.build_department_analytics_bundle(
        dataframe, title_prefix="Freon Refrigeration", date_column=date_column,
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
        ui.render_section("Freon Refrigeration — Live Gauges")
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
        ui.render_section("Freon Refrigeration — Meter Sparklines")
        spark_items = list(bundle["sparklines"].items())
        for row_start in range(0, len(spark_items), 4):
            row_items = spark_items[row_start:row_start + 4]
            columns = st.columns(len(row_items))
            for column, (meter, figure) in zip(columns, row_items):
                with column:
                    st.caption(meter)
                    if figure is not None:
                        st.plotly_chart(figure, use_container_width=True, config={"staticPlot": True})

    ui.render_section("Freon Refrigeration — Statistics Panel")
    with st.container(border=True):
        ui.render_dataframe(bundle["statistics_table"])

    ui.render_section("Freon Refrigeration — Daily Change")
    with st.container(border=True):
        ui.render_dataframe(bundle["change_table"])


def render_latest_readings_table(
    dataframe: pd.DataFrame, section: dict | None
) -> None:
    """Render a table of the latest reading for every meter."""
    ui.render_section("Latest Readings")

    if section is not None:
        latest = section["latest_values"]
    else:
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
    """Render a preview and expandable full history of the Freon data."""
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
    """Render the complete Freon Refrigeration page."""
    ui.render_page_title(
        "Freon Refrigeration",
        "Freon-based refrigeration monitoring and performance.",
    )

    with st.spinner("Loading freon data..."):
        dashboard, error = load_dashboard_safe()

    if error:
        ui.render_error_banner(error)
        return

    freon_dataframe = dashboard.get(FREON_KEY)
    section: dict | None = None

    if freon_dataframe is None or freon_dataframe.empty:
        overview_dataframe = dashboard.get("overview")
        if overview_dataframe is None or overview_dataframe.empty:
            ui.render_info_banner(
                "No Freon Refrigeration data was found in the workbook."
            )
            return

        try:
            sections = build_overview_dashboard(overview_dataframe)["sections"]
        except ValueError as build_error:
            ui.render_error_banner(f"Failed to process freon data: {build_error}")
            return

        section = find_section_by_keyword(sections, FREON_KEYWORD)
        if section is None:
            ui.render_info_banner(
                "No Freon Refrigeration data was found in the workbook."
            )
            return

        section = {**section, "overview_dataframe": overview_dataframe}
        freon_dataframe = section["dataframe"]

    date_column = resolve_date_column(freon_dataframe, section)
    summary = kpi_service.build_kpi_summary(freon_dataframe, section)

    render_kpi_row(summary)
    render_status_section(summary)
    ui.render_divider()

    # TASK 6 & 7: Added Daily Trend Section
    page_loader.render_daily_trend_section(freon_dataframe)
    ui.render_divider()

    render_trend_section(freon_dataframe, section, date_column)
    ui.render_divider()

    render_analytics_section(freon_dataframe, date_column)
    ui.render_divider()

    render_latest_readings_table(freon_dataframe, section)
    ui.render_divider()

    render_data_section(freon_dataframe)
    ui.render_divider()

    render_summary_section(summary)
