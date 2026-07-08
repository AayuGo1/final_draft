"""Freon Refrigeration monitoring page for the Engineering Monitoring Dashboard.

Renders the real Freon Refrigeration data, preferring a dedicated Freon
worksheet (``dashboard["freon"]``) and falling back to a discovered
overview section, via ``dashboard_data.build_overview_dashboard``. KPI
cards come from ``services.kpi_service`` and the trend chart comes from
``services.chart_service``. No KPI calculation or chart-building logic
lives in this file.
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


def render_trend_section(dataframe: pd.DataFrame, section: dict | None) -> None:
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

        date_columns = get_date_columns(dataframe)
        if not date_columns:
            ui.render_info_banner("No date column was discovered to chart.")
            return

        date_column_name = dataframe.columns[date_columns[0]]
        meter_columns = [
            column for column in dataframe.columns if column != date_column_name
        ]
        if not meter_columns:
            ui.render_info_banner("No meter columns were discovered to chart.")
            return

        figure = chart_service.create_multi_line_chart(
            dataframe,
            x_column=date_column_name,
            y_columns=meter_columns,
            title="Freon Refrigeration Meters Trend",
        )
        st.plotly_chart(figure, use_container_width=True)


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

    summary = kpi_service.build_kpi_summary(freon_dataframe, section)

    render_kpi_row(summary)
    render_status_section(summary)
    ui.render_divider()

    # TASK 6 & 7: Added Daily Trend Section
    page_loader.render_daily_trend_section(freon_dataframe)
    ui.render_divider()

    render_trend_section(freon_dataframe, section)
    ui.render_divider()

    render_latest_readings_table(freon_dataframe, section)
    ui.render_divider()

    render_data_section(freon_dataframe)
    ui.render_divider()

    render_summary_section(summary)
