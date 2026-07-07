"""Ammonia Refrigeration monitoring page for the Engineering Monitoring
Dashboard.

Renders the real Ammonia Refrigeration data, preferring a dedicated
Ammonia worksheet and falling back to a discovered overview section, via
``services.page_service``. KPI cards come from ``services.kpi_service``
and the trend chart comes from ``services.chart_service``. No KPI
calculation or chart-building logic lives in this file.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import ui
from dashboard_data import get_date_columns
from services import chart_service, kpi_service
from services.page_service import load_dedicated_sheet

AMMONIA_KEY: str = "ammonia"
"""Dashboard data key used to locate a dedicated Ammonia worksheet."""

AMMONIA_KEYWORD: str = "ammonia"
"""Keyword used to identify the Ammonia Refrigeration section among
discovered sections."""

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
    """Render a status banner based on the data's availability.

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


def render_trend_section(dataframe: pd.DataFrame, section: dict | None) -> None:
    """Render a Plotly trend chart for the Ammonia Refrigeration data.

    When a discovered overview ``section`` is available, reuses
    ``chart_service.build_section_trend_chart`` (which aligns the
    section's meters against the overview worksheet's date column).
    Otherwise, for a dedicated worksheet, discovers the date column
    directly and treats every other column as a candidate meter series.

    Args:
        dataframe: The Ammonia Refrigeration DataFrame.
        section: The discovered overview section dictionary, or ``None``
            when a dedicated Ammonia worksheet is used.
    """
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
            title="Ammonia Refrigeration Meters Trend",
        )
        st.plotly_chart(figure, use_container_width=True)


def render_latest_readings_table(
    dataframe: pd.DataFrame, section: dict | None
) -> None:
    """Render a table of the latest reading for every meter.

    Args:
        dataframe: The Ammonia Refrigeration DataFrame.
        section: The discovered overview section dictionary, or ``None``
            when a dedicated Ammonia worksheet is used.
    """
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
    """Render a preview and expandable full history of the Ammonia data.

    Args:
        dataframe: The Ammonia Refrigeration DataFrame.
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
    """Render the complete Ammonia Refrigeration page."""
    ui.render_page_title(
        "Ammonia Refrigeration",
        "Ammonia refrigeration monitoring and performance.",
    )

    ammonia_dataframe, section = load_dedicated_sheet(
        AMMONIA_KEY, fallback_keyword=AMMONIA_KEYWORD
    )
    if ammonia_dataframe is None:
        return

    summary = kpi_service.build_kpi_summary(ammonia_dataframe, section)

    render_kpi_row(summary)
    render_status_section(summary)
    ui.render_divider()

    render_trend_section(ammonia_dataframe, section)
    ui.render_divider()

    render_latest_readings_table(ammonia_dataframe, section)
    ui.render_divider()

    render_data_section(ammonia_dataframe)
    ui.render_divider()

    render_summary_section(summary)
