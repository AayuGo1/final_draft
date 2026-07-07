"""Engineering overview page for the Engineering Monitoring Dashboard.

Renders the consolidated Engineering overview, combining every
department/section discovered on the engineering overview worksheet via
``dashboard_data.build_overview_dashboard``. KPI cards come from
``services.kpi_service`` and the trend chart comes from
``services.chart_service``. No KPI calculation or chart-building logic
lives in this file.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import ui
from dashboard_data import build_overview_dashboard
from services import chart_service, kpi_service
from services.dashboard_loader import load_dashboard_safe

AVAILABILITY_HEALTHY_THRESHOLD: float = 0.9
"""Availability ratio at/above which data is considered healthy."""

AVAILABILITY_PARTIAL_THRESHOLD: float = 0.5
"""Availability ratio at/above which data is considered partially available."""


def load_overview_dataframe() -> pd.DataFrame | None:
    """Load the dashboard workbook and return the engineering overview sheet."""

    with st.spinner("Loading engineering data..."):
        dashboard, error = load_dashboard_safe()

    if error:
        ui.render_error_banner(error)
        return None

    overview_dataframe = dashboard.get("overview")

    if overview_dataframe is None or overview_dataframe.empty:
        ui.render_info_banner(
            "No engineering overview data is available in the workbook."
        )
        return None

    return overview_dataframe


def render_kpi_row(summary: dict) -> None:
    """Render the top KPI row from a kpi_service summary.

    Args:
        summary: The KPI summary dictionary from
            ``kpi_service.build_kpi_summary``.
    """
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
    """Render a status banner based on the overview's data availability.

    Args:
        summary: The KPI summary dictionary from
            ``kpi_service.build_kpi_summary``.
    """
    availability = summary["availability"]
    if availability >= AVAILABILITY_HEALTHY_THRESHOLD:
        ui.render_success_banner("Status: Monitoring — data is healthy.")
    elif availability >= AVAILABILITY_PARTIAL_THRESHOLD:
        ui.render_info_banner("Status: Monitoring — partial data available.")
    else:
        ui.render_error_banner(
            "Status: Attention needed — low data availability."
        )


def render_trend_section(
    overview_dataframe: pd.DataFrame, sections: list[dict]
) -> None:
    """Render a Plotly trend chart for a user-selected department section.

    Args:
        overview_dataframe: The engineering overview worksheet DataFrame.
        sections: The list of discovered section dictionaries.
    """
    ui.render_section("Trend Analysis")
    with st.container(border=True):
        section_names = [section["name"] for section in sections]
        selected_name = st.selectbox("Select a department", section_names)
        selected_section = next(
            section for section in sections if section["name"] == selected_name
        )

        figure = chart_service.build_section_trend_chart(
            overview_dataframe, selected_section
        )
        if figure is None:
            ui.render_info_banner("No trend data is available to chart yet.")
        else:
            st.plotly_chart(figure, use_container_width=True)


def render_latest_readings_table(sections: list[dict]) -> None:
    """Render a table of the latest reading for every meter, by department.

    Args:
        sections: The list of discovered section dictionaries.
    """
    ui.render_section("Latest Readings")
    rows = [
        {"Department": section["name"], "Meter": meter, "Latest Value": value}
        for section in sections
        for meter, value in section["latest_values"].items()
    ]
    with st.container(border=True):
        ui.render_dataframe(pd.DataFrame(rows))


def render_data_section(overview_dataframe: pd.DataFrame) -> None:
    """Render a preview and expandable full history of the overview data.

    Args:
        overview_dataframe: The engineering overview worksheet DataFrame.
    """
    ui.render_section("Historical Data")
    with st.container(border=True):
        ui.render_dataframe(overview_dataframe.head(15))
        with st.expander("View full history"):
            ui.render_dataframe(overview_dataframe)


def render_summary_section(summary: dict) -> None:
    """Render a compact data summary table.

    Args:
        summary: The KPI summary dictionary from
            ``kpi_service.build_kpi_summary``.
    """
    ui.render_section("Data Summary")
    with st.container(border=True):
        ui.render_dataframe(pd.DataFrame([summary]))


def render() -> None:
    """Render the complete Engineering overview page."""
    ui.render_page_title(
        "Engineering",
        "Consolidated engineering overview across all departments.",
    )

    overview_dataframe = load_overview_dataframe()
    if overview_dataframe is None:
        return

    try:
        sections = build_overview_dashboard(overview_dataframe)["sections"]
    except ValueError as error:
        ui.render_error_banner(f"Failed to process engineering data: {error}")
        return

    if not sections:
        ui.render_info_banner(
            "No departments were discovered in the engineering overview "
            "worksheet."
        )
        return

    summary = kpi_service.build_kpi_summary(overview_dataframe)

    render_kpi_row(summary)
    render_status_section(summary)
    ui.render_divider()

    render_trend_section(overview_dataframe, sections)
    ui.render_divider()

    render_latest_readings_table(sections)
    ui.render_divider()

    render_data_section(overview_dataframe)
    ui.render_divider()

    render_summary_section(summary)
