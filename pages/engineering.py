"""Engineering monitoring page for the Engineering Monitoring Dashboard.

This module renders the real Engineering overview, allowing selection of
any department discovered dynamically from the workbook. It reuses the
shared ``services.dashboard_loader`` service for loading dashboard data,
``dashboard_data.build_overview_dashboard`` for department discovery,
``services.kpi_service`` for all KPI calculations, and
``services.chart_service`` for building the trend chart. It performs no
KPI calculation or chart-building logic of its own, no fake data
generation, and no hardcoded department, column, or meter names.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import ui
from dashboard_data import build_overview_dashboard, get_date_columns
from services import chart_service, kpi_service
from services.dashboard_loader import load_dashboard


def load_overview_dataframe() -> pd.DataFrame | None:
    """Load dashboard data and extract the engineering overview worksheet.

    Returns:
        The overview DataFrame if it was loaded successfully, otherwise
        ``None`` after an error banner has been displayed.
    """
    try:
        dashboard_data = load_dashboard()
    except TimeoutError as exc:
        ui.render_error_banner(f"The workbook source timed out: {exc}")
        return None
    except ConnectionError as exc:
        ui.render_error_banner(
            f"Could not connect to the workbook source: {exc}"
        )
        return None
    except FileNotFoundError as exc:
        ui.render_error_banner(f"Workbook not found: {exc}")
        return None
    except ValueError as exc:
        ui.render_error_banner(f"The workbook data is invalid: {exc}")
        return None
    except RuntimeError as exc:
        ui.render_error_banner(
            f"An error occurred while loading the workbook: {exc}"
        )
        return None

    overview_dataframe = dashboard_data["overview"]

    if overview_dataframe is None:
        ui.render_info_banner(
            "No engineering overview worksheet was found in the workbook."
        )
        return None

    return overview_dataframe


def get_department_sections(overview_dataframe: pd.DataFrame) -> list[dict]:
    """Discover every engineering department section from the overview sheet.

    Args:
        overview_dataframe: The engineering overview worksheet DataFrame.

    Returns:
        A list of section dictionaries as produced by
        ``dashboard_data.build_overview_dashboard``, each with keys
        ``name``, ``meters``, ``latest_values``, and ``dataframe``.
    """
    overview_dashboard = build_overview_dashboard(overview_dataframe)
    return overview_dashboard["sections"]


def render_department_selector(sections: list[dict]) -> dict:
    """Render a department selector and return the selected section.

    Args:
        sections: The list of discovered department sections.

    Returns:
        The section dictionary corresponding to the selected department.
    """
    department_names = [section["name"] for section in sections]
    selected_name = st.selectbox("Department", department_names)
    return next(
        section for section in sections if section["name"] == selected_name
    )


def render_kpi_row(section: dict, overview_dataframe: pd.DataFrame) -> None:
    """Render the top KPI row derived from the selected department section.

    All KPI values are obtained from ``services.kpi_service`` rather than
    being calculated in this page.

    Args:
        section: The selected department section dictionary.
        overview_dataframe: The engineering overview worksheet DataFrame,
            used to discover the latest available timestamp.
    """
    summary = kpi_service.build_kpi_summary(section["dataframe"], section)
    latest_timestamp = kpi_service.get_latest_timestamp(overview_dataframe)

    cards = [
        {"title": "Number of Meters", "value": summary["meters"]},
        {
            "title": "Available Readings",
            "value": summary["available_readings"],
        },
        {"title": "Latest Timestamp", "value": latest_timestamp},
        {"title": "Status", "value": "Monitoring"},
    ]
    ui.render_kpi_cards(cards)


def render_data_section(dataframe: pd.DataFrame) -> None:
    """Render the department data table, limited to the first 15 rows.

    Args:
        dataframe: The selected department DataFrame.
    """
    ui.render_section("Data")
    with st.container(border=True):
        ui.render_dataframe(dataframe.head(15))


def build_trend_dataframe(
    overview_dataframe: pd.DataFrame, section: dict
) -> tuple[pd.DataFrame, str, str] | None:
    """Build a chart-ready DataFrame for the trend chart, if possible.

    Discovers the date column dynamically from the overview worksheet
    and the first meter with usable numeric readings from the selected
    department section, then aligns the two into a single DataFrame
    ready for charting.

    Args:
        overview_dataframe: The engineering overview worksheet DataFrame.
        section: The selected department section dictionary.

    Returns:
        A tuple of ``(trend_dataframe, date_column_name, meter_column_name)``
        if a valid date column and meter could be discovered, otherwise
        ``None``.
    """
    date_columns = get_date_columns(overview_dataframe)
    if not date_columns:
        return None

    meters_dataframe = section["dataframe"]
    if meters_dataframe.empty:
        return None

    meter_column_name = next(
        (
            column
            for column in meters_dataframe.columns
            if pd.to_numeric(
                meters_dataframe[column], errors="coerce"
            ).notna().any()
        ),
        None,
    )
    if meter_column_name is None:
        return None

    date_column_index = date_columns[0]
    date_column_name = "Date"

    date_values = (
        overview_dataframe.iloc[2:, date_column_index]
        .reset_index(drop=True)
    )

    row_count = min(len(date_values), len(meters_dataframe))
    if row_count == 0:
        return None

    trend_dataframe = pd.DataFrame(
        {
            date_column_name: date_values.iloc[:row_count].values,
            meter_column_name: meters_dataframe[meter_column_name]
            .iloc[:row_count]
            .values,
        }
    ).dropna()

    if trend_dataframe.empty:
        return None

    return trend_dataframe, date_column_name, meter_column_name


def render_trend_section(overview_dataframe: pd.DataFrame, section: dict) -> None:
    """Render the Trend Analysis section with a real Plotly chart.

    Discovers a date column and a numeric meter column dynamically and
    builds a line chart via ``services.chart_service``. If no valid
    chart can be generated, an informative message is shown instead of
    raising an exception.

    Args:
        overview_dataframe: The engineering overview worksheet DataFrame.
        section: The selected department section dictionary.
    """
    with st.container(border=True):
        st.write("**Trend Analysis**")

        trend_data = build_trend_dataframe(overview_dataframe, section)
        if trend_data is None:
            st.caption(
                "No date column or numeric meter readings were found "
                "for this department, so a trend chart could not be "
                "generated."
            )
            return

        trend_dataframe, date_column_name, meter_column_name = trend_data

        figure = chart_service.create_line_chart(
            trend_dataframe,
            x_column=date_column_name,
            y_column=meter_column_name,
            title=f"{meter_column_name} Trend",
            x_label=date_column_name,
            y_label=meter_column_name,
        )
        st.plotly_chart(figure, use_container_width=True)


def render() -> None:
    """Render the complete Engineering page."""
    ui.render_page_title(
        "Engineering",
        "Overall engineering performance and asset health.",
    )

    overview_dataframe = load_overview_dataframe()
    if overview_dataframe is None:
        return

    sections = get_department_sections(overview_dataframe)
    if not sections:
        ui.render_info_banner(
            "No engineering departments were discovered in the workbook."
        )
        return

    selected_section = render_department_selector(sections)
    ui.render_divider()

    render_kpi_row(selected_section, overview_dataframe)
    ui.render_divider()

    render_data_section(selected_section["dataframe"])
    ui.render_divider()

    render_trend_section(overview_dataframe, selected_section)
