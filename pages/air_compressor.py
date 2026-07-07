"""Air compressor monitoring page for the Engineering Monitoring Dashboard.

Renders the real Air Compressor worksheet (``dashboard["air_compressor"]``)
loaded via ``services.dashboard_loader``, with KPI cards from
``services.kpi_service``, a Plotly trend chart from
``services.chart_service``, and native Streamlit data tables. No KPI
calculation or chart-building logic lives in this file.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import ui
from dashboard_data import get_date_columns
from services import chart_service, kpi_service
from services.dashboard_loader import load_dashboard_safe

AIR_COMPRESSOR_KEY: str = "air_compressor"
"""Dashboard data key used to locate the Air Compressor worksheet."""

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
    """Render a status banner based on the worksheet's data availability.

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


def render_trend_section(dataframe: pd.DataFrame) -> None:
    """Render a multi-meter Plotly trend chart for the worksheet.

    Discovers the date column and treats every other column as a
    candidate meter series; non-numeric columns are simply ignored by
    the chart service's numeric coercion.

    Args:
        dataframe: The Air Compressor DataFrame.
    """
    ui.render_section("Trend Analysis")
    with st.container(border=True):
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
            title="Air Compressor Meters Trend",
        )
        st.plotly_chart(figure, use_container_width=True)


def render_latest_readings_table(dataframe: pd.DataFrame) -> None:
    """Render a table of the latest reading for every meter column.

    Args:
        dataframe: The Air Compressor DataFrame.
    """
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
    """Render a preview and expandable full history of the worksheet.

    Args:
        dataframe: The Air Compressor DataFrame.
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

    summary = kpi_service.build_kpi_summary(dataframe)

    render_kpi_row(summary)
    render_status_section(summary)
    ui.render_divider()

    render_trend_section(dataframe)
    ui.render_divider()

    render_latest_readings_table(dataframe)
    ui.render_divider()

    render_data_section(dataframe)
    ui.render_divider()

    render_summary_section(summary)
