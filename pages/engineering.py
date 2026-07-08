"""Engineering overview page for the Engineering Monitoring Dashboard.

Renders the consolidated Engineering overview, combining every
department/section discovered on the engineering overview worksheet via
``dashboard_data.build_overview_dashboard``. KPI cards come from
``services.kpi_service`` and every chart comes from ``services.chart_service``.
No KPI calculation or chart-building logic lives in this file.

Layout:
    Department selector + Meter selector
    4 KPI cards (Latest / Average / Maximum / Minimum)
    Large daily trend chart
    Multi-line department trend (when the department has >1 meter)
    Statistics table
    Latest readings table
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

import ui
from dashboard_data import build_overview_dashboard
from services import chart_service, kpi_service, page_loader
from services.dashboard_loader import load_dashboard_safe

AVAILABILITY_HEALTHY_THRESHOLD: float = 0.9
AVAILABILITY_PARTIAL_THRESHOLD: float = 0.5


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
    """Render the top-level (overview-wide) KPI row from a kpi_service summary."""
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
    """Render a status banner based on the overview's data availability."""
    availability = summary["availability"]
    if availability >= AVAILABILITY_HEALTHY_THRESHOLD:
        ui.render_success_banner("Status: Monitoring — data is healthy.")
    elif availability >= AVAILABILITY_PARTIAL_THRESHOLD:
        ui.render_info_banner("Status: Monitoring — partial data available.")
    else:
        ui.render_error_banner(
            "Status: Attention needed — low data availability."
        )


def render_department_and_meter_selectors(
    sections: list[dict],
) -> tuple[dict[str, Any], str] | None:
    """Render the department + meter selectors and return the current choice.

    No column is auto-selected on the caller's behalf: the person explicitly
    picks the department and the meter they want to inspect.

    Args:
        sections: The list of discovered department/section dicts.

    Returns:
        A ``(section, meter)`` tuple for the current selection, or None if no
        section has a plottable meter.
    """
    ui.render_section("Department & Meter")
    with st.container(border=True):
        section_names = [section["name"] for section in sections]

        col1, col2 = st.columns(2)
        with col1:
            selected_name = st.selectbox(
                "Department", section_names, key="engineering_department_select"
            )
        selected_section = next(
            section for section in sections if section["name"] == selected_name
        )

        meters = chart_service.get_department_meters(selected_section)
        if not meters:
            with col2:
                st.selectbox("Meter", ["No meters available"], disabled=True)
            ui.render_info_banner(
                f"No meters were discovered for '{selected_name}'."
            )
            return None

        with col2:
            selected_meter = st.selectbox(
                "Meter", meters, key="engineering_meter_select"
            )

    return selected_section, selected_meter


def render_meter_kpi_row(section: dict[str, Any], meter: str) -> dict[str, Any] | None:
    """Render the 4-card KPI row (Latest / Average / Maximum / Minimum) for a meter.

    Reuses ``kpi_service.build_meter_kpis`` on the section's ready DataFrame,
    so no per-meter statistics are recomputed anywhere else on this page.

    Args:
        section: The selected department/section dict.
        meter: The selected meter/column name.

    Returns:
        The full ``kpi_service.build_meter_kpis`` dict for the meter, so
        downstream sections (stats table) can reuse it without recomputing,
        or None if the meter has no data.
    """
    if not chart_service.has_ready_department_dataframe(section):
        ui.render_info_banner(f"No readings are available for '{meter}'.")
        return None

    df = section["dataframe"]
    readings = df[meter]
    dates = df[chart_service.DEFAULT_DATE_COLUMN_LABEL]

    meter_kpis = kpi_service.build_meter_kpis(readings, dates)
    unit = ""
    units_map = section.get("units")
    if isinstance(units_map, dict):
        unit = units_map.get(meter, "")

    def _fmt(value: Any) -> str:
        if value is None:
            return "—"
        try:
            return f"{float(value):,.2f} {unit}".strip()
        except (TypeError, ValueError):
            return str(value)

    cards = [
        {"title": "Latest", "value": _fmt(meter_kpis["latest_value"])},
        {"title": "Average", "value": _fmt(meter_kpis["average"])},
        {"title": "Maximum", "value": _fmt(meter_kpis["maximum"])},
        {"title": "Minimum", "value": _fmt(meter_kpis["minimum"])},
    ]
    ui.render_kpi_cards(cards)
    return meter_kpis


def render_daily_trend_chart(section: dict[str, Any], meter: str) -> None:
    """Render the large daily trend chart for the selected meter.

    Plots directly from the section's ready DataFrame (Date + meter
    columns), avoiding any re-derivation of alignment.
    """
    ui.render_section("Daily Trend")
    with st.container(border=True):
        figure = chart_service.create_department_line_chart(
            section, meter, title=f"{meter} — Daily Trend"
        )
        if figure is None:
            ui.render_info_banner("No trend data is available to chart yet.")
        else:
            figure.update_layout(height=460)
            st.plotly_chart(figure, use_container_width=True)


def render_analytics_section(section: dict[str, Any]) -> None:
    """Render the full engineering-analytics chart suite for a department.

    Builds one bundle (via `chart_service.build_department_analytics_bundle`)
    from the section's ready DataFrame and renders every chart/table it
    contains — weekly moving average, multi-meter trend, latest-day
    comparison, heatmap, distribution, radar, gauges, sparklines,
    statistics panel, and daily change table.
    """
    if not chart_service.has_ready_department_dataframe(section):
        return

    department_name = section["name"]
    ui.render_section(f"{department_name} — Engineering Analytics")

    bundle = chart_service.build_department_analytics_bundle(
        section["dataframe"], meters=section.get("meters"),
        title_prefix=department_name, date_column=chart_service.DEFAULT_DATE_COLUMN_LABEL,
    )

    if not bundle["meters"]:
        ui.render_info_banner("No meters available for analytics.")
        return

    with st.container(border=True):
        if bundle["weekly_moving_average"] is not None:
            st.plotly_chart(bundle["weekly_moving_average"], use_container_width=True)
        else:
            ui.render_info_banner("Not enough data for a moving-average trend.")

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
        ui.render_section(f"{department_name} — Live Gauges")
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
        ui.render_section(f"{department_name} — Meter Sparklines")
        spark_items = list(bundle["sparklines"].items())
        for row_start in range(0, len(spark_items), 4):
            row_items = spark_items[row_start:row_start + 4]
            columns = st.columns(len(row_items))
            for column, (meter, figure) in zip(columns, row_items):
                with column:
                    st.caption(meter)
                    if figure is not None:
                        st.plotly_chart(figure, use_container_width=True, config={"staticPlot": True})

    ui.render_section(f"{department_name} — Statistics Panel")
    with st.container(border=True):
        ui.render_dataframe(bundle["statistics_table"])

    ui.render_section(f"{department_name} — Daily Change")
    with st.container(border=True):
        ui.render_dataframe(bundle["change_table"])


def render_multi_meter_trend(section: dict[str, Any]) -> None:
    """Render a multi-line trend comparing every meter in the department.

    Only rendered when the department has more than one meter — a
    single-meter department has nothing to compare.
    """
    meters = chart_service.get_department_meters(section)
    if len(meters) <= 1:
        return

    ui.render_section(f"{section['name']} — All Meters")
    with st.container(border=True):
        figure = chart_service.create_department_multi_meter_chart(
            section, meters, title=f"{section['name']} — Meter Comparison"
        )
        if figure is None:
            ui.render_info_banner("No comparison data is available to chart yet.")
        else:
            st.plotly_chart(figure, use_container_width=True)


def render_statistics_table(meter: str, meter_kpis: dict[str, Any]) -> None:
    """Render a detailed statistics table for the selected meter.

    Reuses the already-computed ``kpi_service.build_meter_kpis`` result
    passed in from ``render_meter_kpi_row`` instead of recalculating it.
    """
    ui.render_section("Statistics")

    rows = [
        {"Statistic": "Latest Value", "Value": meter_kpis["latest_value"]},
        {"Statistic": "Previous Value", "Value": meter_kpis["previous_value"]},
        {"Statistic": "Average", "Value": meter_kpis["average"]},
        {"Statistic": "Maximum", "Value": meter_kpis["maximum"]},
        {"Statistic": "Minimum", "Value": meter_kpis["minimum"]},
        {
            "Statistic": "Trend",
            "Value": (
                f"{meter_kpis['trend_percentage']:+.2f}%"
                if meter_kpis["trend_percentage"] is not None
                else "—"
            ),
        },
        {"Statistic": "Total Readings", "Value": meter_kpis["total_readings"]},
        {"Statistic": "Missing Readings", "Value": meter_kpis["missing_readings"]},
        {
            "Statistic": "Availability",
            "Value": f"{meter_kpis['availability'] * 100:.1f}%",
        },
    ]

    with st.container(border=True):
        ui.render_dataframe(pd.DataFrame(rows))


def render_latest_readings_table(section: dict[str, Any]) -> None:
    """Render a table of the latest reading for every meter in the department."""
    ui.render_section(f"{section['name']} — Latest Readings")
    latest_values = section.get("latest_values", {})
    units_map = section.get("units", {}) if isinstance(section.get("units"), dict) else {}

    rows = [
        {
            "Meter": meter,
            "Latest Value": value,
            "Unit": units_map.get(meter, ""),
        }
        for meter, value in latest_values.items()
    ]
    with st.container(border=True):
        ui.render_dataframe(pd.DataFrame(rows))


def render_data_section(overview_dataframe: pd.DataFrame) -> None:
    """Render a preview and expandable full history of the overview data."""
    ui.render_section("Historical Data")
    with st.container(border=True):
        ui.render_dataframe(overview_dataframe.head(15))
        with st.expander("View full history"):
            ui.render_dataframe(overview_dataframe)


def render_summary_section(summary: dict) -> None:
    """Render a compact data summary table."""
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

    # TASK 6 & 7: Existing daily-trend-across-worksheet section (unchanged).
    page_loader.render_daily_trend_section(overview_dataframe)
    ui.render_divider()

    # --- Department + Meter driven layout -----------------------------
    selection = render_department_and_meter_selectors(sections)
    if selection is None:
        ui.render_divider()
        render_data_section(overview_dataframe)
        ui.render_divider()
        render_summary_section(summary)
        return

    selected_section, selected_meter = selection
    ui.render_divider()

    meter_kpis = render_meter_kpi_row(selected_section, selected_meter)
    ui.render_divider()

    render_daily_trend_chart(selected_section, selected_meter)
    ui.render_divider()

    render_multi_meter_trend(selected_section)
    ui.render_divider()

    render_analytics_section(selected_section)
    ui.render_divider()

    if meter_kpis is not None:
        render_statistics_table(selected_meter, meter_kpis)
        ui.render_divider()

    render_latest_readings_table(selected_section)
    ui.render_divider()

    render_data_section(overview_dataframe)
    ui.render_divider()

    render_summary_section(summary)
