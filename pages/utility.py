"""Utility monitoring page for the Engineering Monitoring Dashboard.

Renders the real Utility section discovered dynamically from the
workbook via ``services.page_service``, with KPI cards from
``services.kpi_service``, a Plotly trend chart from
``services.chart_service``, and native Streamlit data tables. No KPI
calculation or chart-building logic lives in this file.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import ui
from services import chart_service, kpi_service
from services.page_service import load_section

UTILITY_KEYWORD: str = "utility"
"""Keyword used to identify the Utility section among discovered sections."""

AVAILABILITY_HEALTHY_THRESHOLD: float = 0.9
"""Availability ratio at/above which data is considered healthy."""

AVAILABILITY_PARTIAL_THRESHOLD: float = 0.5
"""Availability ratio at/above which data is considered partially available."""


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
    """Render a status banner based on the section's data availability.

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


def render_trend_section(overview_dataframe: pd.DataFrame, section: dict) -> None:
    """Render the Plotly trend chart for the Utility section.

    Args:
        overview_dataframe: The engineering overview worksheet DataFrame,
            used to discover the shared date column.
        section: The discovered Utility section dictionary.
    """
    ui.render_section("Trend Analysis")
    with st.container(border=True):
        figure = chart_service.build_section_trend_chart(
            overview_dataframe, section
        )
        if figure is None:
            ui.render_info_banner("No trend data is available to chart yet.")
        else:
            st.plotly_chart(figure, use_container_width=True)


def render_latest_readings_table(section: dict) -> None:
    """Render a table of the latest reading for every meter.

    Args:
        section: The discovered Utility section dictionary.
    """
    ui.render_section("Latest Readings")
    latest_values = section["latest_values"]
    table = pd.DataFrame(
        {
            "Meter": list(latest_values.keys()),
            "Latest Value": list(latest_values.values()),
        }
    )
    with st.container(border=True):
        ui.render_dataframe(table)


def render_data_section(dataframe: pd.DataFrame) -> None:
    """Render a preview and expandable full history of the Utility data.

    Args:
        dataframe: The Utility section DataFrame.
    """
    ui.render_section("Historical Data")
    with st.container(border=True):
        ui.render_dataframe(dataframe.head(15))
        with st.expander("View full history"):
            ui.render_dataframe(dataframe)


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
    """Render the complete Utility page."""
    ui.render_page_title(
        "Utility",
        "General utility consumption and performance tracking.",
    )

    section = load_section(UTILITY_KEYWORD)
    if section is None:
        return

    summary = kpi_service.build_kpi_summary(section["dataframe"], section)

    render_kpi_row(summary)
    render_status_section(summary)
    ui.render_divider()

    render_trend_section(section["overview_dataframe"], section)
    ui.render_divider()

    render_latest_readings_table(section)
    ui.render_divider()

    render_data_section(section["dataframe"])
    ui.render_divider()

    render_summary_section(summary)
