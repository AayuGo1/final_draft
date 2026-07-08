"""Main Entry Point for the Engineering Monitoring Dashboard.

This module serves as the production presentation and UI/UX orchestration layer
for the Engineering Monitoring Dashboard. It interfaces directly with validated
domain logic services to render an enterprise dark SCADA interface.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Final

import pandas as pd
import streamlit as st

from config import (
    APP_ICON,
    APP_NAME,
    APP_VERSION,
    GITHUB_BRANCH,
    GITHUB_OWNER,
    GITHUB_REPO,
    PAGE_CONFIG,
    THEME_DANGER_COLOR,
    THEME_PRIMARY_COLOR,
    THEME_SUCCESS_COLOR,
)
import services.chart_service as chart_service
import services.kpi_service as kpi_service
from services.dashboard_loader import load_dashboard_safe

st.set_page_config(
    page_title=PAGE_CONFIG.get("page_title", APP_NAME),
    page_icon=PAGE_CONFIG.get("page_icon", "⚙️"),
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Layout constants
GRID_COLUMNS: Final[int] = 4

def get_dashboard() -> tuple[dict[str, Any] | None, str | None]:
    """Retrieve the cached dashboard session payload framework context safely.

    Returns:
        A tuple of (dashboard_dict, error_message).
    """
    if "dashboard_data" not in st.session_state:
        dashboard, error = load_dashboard_safe()
        st.session_state["dashboard_data"] = dashboard
        st.session_state["dashboard_error"] = error
        st.session_state["last_refresh"] = dt.datetime.now()

    return st.session_state.get("dashboard_data"), st.session_state.get("dashboard_error")


def refresh_dashboard() -> None:
    """Evict structural context references from active session state layers and clear caches."""
    st.cache_data.clear()
    st.cache_resource.clear()
    for key in ("dashboard_data", "dashboard_error", "last_refresh"):
        st.session_state.pop(key, None)


def inject_global_styles() -> None:
    """Inject customized production glassmorphism responsive layout rules."""
    st.markdown(
        f"""
        <style>
            #MainMenu {{visibility: hidden;}}
            footer {{visibility: hidden;}}
            header[data-testid="stHeader"] {{background: transparent;}}

            .block-container {{
                padding-top: 1.0rem;
                padding-bottom: 2.0rem;
                max-width: 1550px;
            }}

            .scada-header {{
                background: linear-gradient(135deg, rgba(108, 99, 255, 0.12), rgba(22, 26, 37, 0.95));
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                padding: 16px 20px;
                margin-bottom: 16px;
            }}

            .scada-title-block {{
                display: flex;
                align-items: center;
                gap: 14px;
            }}

            .scada-logo {{
                width: 44px;
                height: 44px;
                border-radius: 8px;
                background: linear-gradient(135deg, {THEME_PRIMARY_COLOR}, #3a34a1);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 22px;
                box-shadow: 0 4px 12px rgba(108, 99, 255, 0.3);
            }}

            .scada-main-title {{
                font-size: 1.25rem;
                font-weight: 700;
                color: #FAFAFA;
                margin: 0;
            }}

            .status-pill {{
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 3px 10px;
                border-radius: 12px;
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.06);
                font-size: 0.72rem;
                color: #CBD5E1;
            }}

            .status-dot {{
                width: 7px;
                height: 7px;
                border-radius: 50%;
                display: inline-block;
            }}

            .metric-card-container {{
                background: linear-gradient(145deg, rgba(30, 41, 59, 0.35), rgba(15, 23, 42, 0.75));
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 10px;
                padding: 14px 18px;
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
            }}

            .metric-card-title {{
                font-size: 0.75rem;
                color: #94A3B8;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin: 0 0 4px 0;
            }}

            .metric-card-value {{
                font-size: 1.5rem;
                font-weight: 700;
                color: #F8FAFC;
                margin: 0;
            }}

            .metric-card-footer {{
                font-size: 0.7rem;
                color: #64748B;
                margin-top: 4px;
            }}

            .section-panel-title {{
                font-size: 0.9rem;
                font-weight: 700;
                color: #F1F5F9;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin: 16px 0 10px 2px;
            }}

            .scada-asset-card {{
                background: linear-gradient(145deg, rgba(30, 41, 59, 0.45), rgba(15, 23, 42, 0.85));
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 12px;
                padding: 18px;
                box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
                transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
                min-height: 250px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                box-sizing: border-box;
                margin-bottom: 16px;
            }}

            .scada-asset-card:hover {{
                transform: translateY(-2px);
                box-shadow: 0 10px 24px rgba(108, 99, 255, 0.15);
                border-color: {THEME_PRIMARY_COLOR}55;
            }}

            .scada-asset-title {{
                font-size: 1.05rem;
                font-weight: 700;
                color: #FAFAFA;
                margin: 0 0 12px 0;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}

            .scada-asset-data-row {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin: 4px 0;
                font-size: 0.82rem;
            }}

            .scada-asset-label {{
                color: #94A3B8;
                font-weight: 500;
            }}

            .scada-asset-value {{
                color: #F8FAFC;
                font-weight: 700;
                text-align: right;
                white-space: nowrap;
            }}

            .scada-asset-status {{
                display: flex;
                align-items: center;
                gap: 6px;
                font-size: 0.75rem;
                color: #CBD5E1;
                margin-top: 10px;
                margin-bottom: 12px;
            }}

            div[data-testid="stButton"] > button {{
                width: 100%;
                border-radius: 8px !important;
                border: 1px solid rgba(255, 255, 255, 0.05) !important;
                background: linear-gradient(145deg, rgba(30, 41, 59, 0.3), rgba(15, 23, 42, 0.7)) !important;
                padding: 10px 12px !important;
                text-align: left !important;
                transition: all 0.15s ease-in-out !important;
            }}

            div[data-testid="stButton"] > button:hover {{
                transform: translateY(-1px);
                border-color: {THEME_PRIMARY_COLOR}66 !important;
                box-shadow: 0 4px 12px rgba(108, 99, 255, 0.12) !important;
            }}

            .tile-active > div[data-testid="stButton"] > button {{
                border-color: {THEME_PRIMARY_COLOR} !important;
                background: linear-gradient(145deg, rgba(108, 99, 255, 0.15), rgba(15, 23, 42, 0.85)) !important;
                box-shadow: 0 4px 12px rgba(108, 99, 255, 0.18) !important;
            }}

            .scada-action-btn > div[data-testid="stButton"] > button {{
                text-align: center !important;
                background: linear-gradient(145deg, {THEME_PRIMARY_COLOR}22, rgba(15, 23, 42, 0.8)) !important;
                border: 1px solid rgba(108, 99, 255, 0.2) !important;
                font-weight: 600 !important;
                color: #E2E8F0 !important;
            }}

            .scada-action-btn > div[data-testid="stButton"] > button:hover {{
                background: linear-gradient(145deg, {THEME_PRIMARY_COLOR}44, rgba(15, 23, 42, 0.9)) !important;
                border-color: {THEME_PRIMARY_COLOR} !important;
                color: #FAFAFA !important;
            }}

            .tile-dept-name {{
                font-size: 0.82rem;
                font-weight: 700;
                color: #F8FAFC;
                margin: 0 0 4px 0;
            }}

            .tile-meta-row {{
                display: flex;
                justify-content: space-between;
                font-size: 0.7rem;
                color: #94A3B8;
                margin-top: 2px;
            }}

            .panel-container {{
                background: rgba(22, 26, 37, 0.45);
                border: 1px solid rgba(255, 255, 255, 0.04);
                border-radius: 12px;
                padding: 18px;
                margin-top: 14px;
            }}

            .scada-footer {{
                margin-top: 28px;
                padding: 12px;
                border-radius: 8px;
                background: rgba(255, 255, 255, 0.01);
                border: 1px solid rgba(255, 255, 255, 0.03);
                font-size: 0.7rem;
                color: #475569;
                text-align: center;
            }}

            /* ===================== WORKSPACE-SPECIFIC STYLES ===================== */
            /* These rules are additive and scoped to the Department Workspace only.
               No pre-existing selectors above were modified. */

            .ws-header-panel {{
                background: linear-gradient(135deg, rgba(108, 99, 255, 0.10), rgba(15, 23, 42, 0.92));
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 14px;
                padding: 18px 22px;
                margin-top: 4px;
                margin-bottom: 18px;
                box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
            }}

            .ws-header-top-row {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                flex-wrap: wrap;
                gap: 14px;
            }}

            .ws-dept-name {{
                font-size: 1.35rem;
                font-weight: 800;
                color: #FAFAFA;
                margin: 0 0 4px 0;
                letter-spacing: 0.2px;
            }}

            .ws-dept-subtitle {{
                font-size: 0.78rem;
                color: #94A3B8;
                font-weight: 500;
                margin: 0;
            }}

            .ws-meta-grid {{
                display: flex;
                gap: 22px;
                flex-wrap: wrap;
                align-items: center;
            }}

            .ws-meta-item {{
                display: flex;
                flex-direction: column;
                gap: 2px;
                min-width: 110px;
            }}

            .ws-meta-label {{
                font-size: 0.65rem;
                color: #64748B;
                text-transform: uppercase;
                letter-spacing: 0.6px;
                font-weight: 600;
            }}

            .ws-meta-value {{
                font-size: 0.88rem;
                color: #F1F5F9;
                font-weight: 700;
            }}

            .ws-status-chip {{
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 5px 12px;
                border-radius: 14px;
                font-size: 0.72rem;
                font-weight: 700;
                letter-spacing: 0.3px;
            }}

            .ws-kpi-strip {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 14px;
                margin-bottom: 18px;
            }}

            .ws-kpi-card {{
                background: linear-gradient(145deg, rgba(30, 41, 59, 0.5), rgba(15, 23, 42, 0.9));
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-left: 3px solid {THEME_PRIMARY_COLOR};
                border-radius: 10px;
                padding: 14px 16px;
                box-shadow: 0 4px 14px rgba(0, 0, 0, 0.22);
            }}

            .ws-kpi-card .metric-card-title {{
                margin-bottom: 6px;
            }}

            .ws-panel {{
                background: rgba(22, 26, 37, 0.5);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 12px;
                padding: 16px 18px 18px 18px;
                margin-bottom: 18px;
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
                height: 100%;
                box-sizing: border-box;
            }}

            .ws-panel-title {{
                font-size: 0.8rem;
                font-weight: 700;
                color: #E2E8F0;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin: 0 0 12px 0;
                padding-bottom: 8px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.06);
                display: flex;
                align-items: center;
                gap: 8px;
            }}

            .ws-empty-note {{
                font-size: 0.78rem;
                color: #64748B;
                font-style: italic;
                padding: 10px 2px;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_top_header(dashboard: dict[str, Any] | None) -> tuple[str, str]:
    """Render the simplified global system supervision header and time controls."""
    now = dt.datetime.now()
    summary = (dashboard or {}).get("summary", {})
    filters_data = (dashboard or {}).get("filters", {})
    departments = (dashboard or {}).get("departments", {})
    
    plant_ok = bool(departments)
    plant_color = THEME_SUCCESS_COLOR if plant_ok else THEME_DANGER_COLOR
    plant_text = "ONLINE" if plant_ok else "OFFLINE"
    
    wb_color = THEME_SUCCESS_COLOR if dashboard else THEME_DANGER_COLOR
    wb_text = "CONNECTED" if dashboard else "DISCONNECTED"
    
    last_refresh = st.session_state.get("last_refresh", now)

    st.markdown(
        f"""
        <div class="scada-header">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                <div class="scada-title-block">
                    <div class="scada-logo">{APP_ICON}</div>
                    <div>
                        <h1 class="scada-main-title">{APP_NAME}</h1>
                        <div style="display: flex; gap: 8px; margin-top: 2px; flex-wrap: wrap;">
                            <div class="status-pill"><span class="status-dot" style="background:{plant_color};"></span>PLANT: {plant_text}</div>
                            <div class="status-pill"><span class="status-dot" style="background:{wb_color};"></span>WORKBOOK: {wb_text}</div>
                            <div class="status-pill">📅 {now.strftime("%d %b %Y")}</div>
                            <div class="status-pill">🕒 {now.strftime("%H:%M:%S")}</div>
                            <div class="status-pill">🔁 LAST REFRESH: {last_refresh.strftime("%H:%M:%S")}</div>
                            <div class="status-pill">🐙 GITHUB: {GITHUB_OWNER}/{GITHUB_REPO}@{GITHUB_BRANCH}</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    h_col1, h_col2, h_col3 = st.columns([2.5, 2.5, 5])
    with h_col1:
        st.selectbox(
            "Month Sync Context",
            options=filters_data.get("months", ["N/A"]),
            index=0,
            key="header_month_select",
            disabled=True,
            help="Filtering by date is managed at downstream visualization layer levels."
        )
    with h_col2:
        st.selectbox(
            "Date Sync Context",
            options=filters_data.get("dates", ["N/A"]),
            index=0,
            key="header_date_select",
            disabled=True,
            help="Filtering by date is managed at downstream visualization layer levels."
        )
    with h_col3:
        st.markdown("<div style='padding-top: 24px;'></div>", unsafe_allow_html=True)
        if st.button("🔄 Sync Live Remote Ingestion Buffer", key="btn_manual_header_sync"):
            refresh_dashboard()
            st.rerun()

    return "N/A", "N/A"


def render_executive_kpi_strip(dashboard: dict[str, Any]) -> None:
    """Compile and render industrial engineering KPIs cleanly across node telemetry states."""
    summary = dashboard.get("summary", {})
    departments = dashboard.get("departments", {})

    total_consumption = 0.0
    active_depts_count = 0
    total_reporting_meters = 0

    for dept_obj in departments.values():
        latest_map = dept_obj.get("latest_values", {})
        valid_dept_vals = [v for v in latest_map.values() if isinstance(v, (int, float))]
        if valid_dept_vals:
            total_consumption += sum(valid_dept_vals)
            active_depts_count += 1
        total_reporting_meters += len(valid_dept_vals)

    flat_averages = [
        v for dept in summary.get("average_values", {}).values() if isinstance(dept, dict)
        for v in dept.values() if isinstance(v, (int, float))
    ]
    global_average = sum(flat_averages) / len(flat_averages) if flat_averages else 0.0
    
    latest_ts_raw = summary.get("latest_timestamp", "N/A")
    if isinstance(latest_ts_raw, str):
        latest_ts_display = latest_ts_raw.split()[0] if " " in latest_ts_raw else latest_ts_raw
    elif hasattr(latest_ts_raw, "strftime"):
        latest_ts_display = latest_ts_raw.strftime("%Y-%m-%d")
    else:
        latest_ts_display = "N/A"

    meter_count = summary.get("meter_count", 0)

    st.markdown('<p class="section-panel-title">📈 Corporate Operations KPI Infrastructure</p>', unsafe_allow_html=True)
    k_col1, k_col2, k_col3, k_col4, k_col5, k_col6 = st.columns(6)

    with k_col1:
        st.markdown(
            f"""<div class="metric-card-container">
                <p class="metric-card-title">Total Consumption</p>
                <p class="metric-card-value">{total_consumption:,.1f}</p>
                <div class="metric-card-footer">Sum Active Channels</div>
            </div>""", unsafe_allow_html=True
        )
    with k_col2:
        st.markdown(
            f"""<div class="metric-card-container">
                <p class="metric-card-title">Average Consumption</p>
                <p class="metric-card-value">{global_average:,.1f}</p>
                <div class="metric-card-footer">Channel Array Average</div>
            </div>""", unsafe_allow_html=True
        )
    with k_col3:
        st.markdown(
            f"""<div class="metric-card-container">
                <p class="metric-card-title">Latest Reading</p>
                <p class="metric-card-value">{total_consumption / max(total_reporting_meters, 1):,.1f}</p>
                <div class="metric-card-footer">Mean Vector Output</div>
            </div>""", unsafe_allow_html=True
        )
    with k_col4:
        st.markdown(
            f"""<div class="metric-card-container">
                <p class="metric-card-title">Depts Reporting</p>
                <p class="metric-card-value">{active_depts_count}</p>
                <div class="metric-card-footer">Functional Systems Feed</div>
            </div>""", unsafe_allow_html=True
        )
    with k_col5:
        st.markdown(
            f"""<div class="metric-card-container">
                <p class="metric-card-title">Meters Reporting</p>
                <p class="metric-card-value">{total_reporting_meters} / {meter_count}</p>
                <div class="metric-card-footer">Active Subnodes Trace</div>
            </div>""", unsafe_allow_html=True
        )
    with k_col6:
        st.markdown(
            f"""<div class="metric-card-container">
                <p class="metric-card-title">Last Updated</p>
                <p class="metric-card-value" style="font-size: 1.3rem; font-weight: 700; padding-top: 3px;">{latest_ts_display}</p>
                <div class="metric-card-footer">Chronological Base Target</div>
            </div>""", unsafe_allow_html=True
        )


def _get_representative_meter(dept_obj: dict[str, Any]) -> str:
    """Safely select the first valid numeric column within a department context."""
    meters = dept_obj.get("meters", [])
    latest_values = dept_obj.get("latest_values", {})
    for m in meters:
        if isinstance(latest_values.get(m), (int, float)):
            return m
    return ""


def render_department_grid(dashboard: dict[str, Any]) -> str:
    """Render specialized structural matrix navigation system grids with modern SCADA-style cards."""
    departments: dict[str, dict[str, Any]] = dashboard.get("departments", {})

    critical_assets = [
        "NPCL",
        "Dough",
        "Traywasher",
        "Air compressor",
        "Freon Refrigeration",
        "DG",
        "GG",
    ]

    dept_names = [name for name in critical_assets if name in departments]

    st.markdown('<p class="section-panel-title">🏭 Critical Plant Assets</p>', unsafe_allow_html=True)

    if not dept_names:
        return ""

    if "selected_department" not in st.session_state or st.session_state["selected_department"] not in dept_names:
        st.session_state["selected_department"] = dept_names[0]
    current_selection = st.session_state["selected_department"]

    # Desktop Layout Optimization splitting rows exactly 4 then 3 dynamically
    first_row = dept_names[0:4]
    second_row = dept_names[4:7]

    for row_slice in (first_row, second_row):
        if not row_slice:
            continue
        cols = st.columns(len(row_slice)) if len(row_slice) < GRID_COLUMNS else st.columns(GRID_COLUMNS)

        for col, d_name in zip(cols, row_slice):
            dept_obj = departments[d_name]
            meters = dept_obj.get("meters", [])
            rep_m = _get_representative_meter(dept_obj)
            
            latest_value = dept_obj.get("latest_values", {}).get(rep_m) if rep_m else None
            average_value = dept_obj.get("average_values", {}).get(rep_m) if rep_m else None
            total_value = dept_obj.get("total_values", {}).get(rep_m) if rep_m else None
            unit_label = dept_obj.get("units", {}).get(rep_m, "") if rep_m else ""

            meter_count = len(meters)
            is_active = (d_name == current_selection)

            latest_display = f"{latest_value:,.2f} {unit_label}".strip() if isinstance(latest_value, (int, float)) else "N/A"
            average_display = f"{average_value:,.2f}" if isinstance(average_value, (int, float)) else "N/A"
            total_display = f"{total_value:,.2f}" if isinstance(total_value, (int, float)) else "N/A"

            # Nest the Streamlit button cleanly INSIDE the asset card layout framework
            with col:
                st.markdown(
                    f"""
                    <div class="scada-asset-card" style="border-color: {THEME_PRIMARY_COLOR if is_active else 'rgba(255,255,255,0.06)'}; margin-bottom: 0px;">
                        <div>
                            <div class="scada-asset-title">⚡ {d_name}</div>
                            <div class="scada-asset-data-row">
                                <span class="scada-asset-label">Latest</span>
                                <span class="scada-asset-value">{latest_display}</span>
                            </div>
                            <div class="scada-asset-data-row">
                                <span class="scada-asset-label">Average</span>
                                <span class="scada-asset-value">{average_display}</span>
                            </div>
                            <div class="scada-asset-data-row">
                                <span class="scada-asset-label">Total</span>
                                <span class="scada-asset-value">{total_display}</span>
                            </div>
                        </div>
                        <div>
                            <div class="scada-asset-status" style="margin-bottom: 0px;">
                                <span class="status-dot" style="background: {THEME_SUCCESS_COLOR};"></span>
                                Meters : {meter_count}
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                st.markdown('<div class="scada-action-btn" style="margin-top: -12px; margin-bottom: 16px;">', unsafe_allow_html=True)
                if st.button("Open Dashboard", key=f"nav_tile_{d_name}"):
                    st.session_state["selected_department"] = d_name
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    return st.session_state["selected_department"]


def render_subsystem_workspace(dashboard: dict[str, Any], active_dept: str) -> None:
    """Render the Department Workspace as a premium SCADA-style analytical console.

    Layout (top to bottom):
        - Department header (name, representative meter, unit, latest timestamp, status)
        - Row 1: Latest / Average / Total / Active Meter Count KPI strip
        - Row 2: Primary trend chart + gauge
        - Row 3: Multi-line comparison chart (full width)
        - Row 4: Meter summary table
        - Row 5: Historical data table (sortable, full width)

    All values are sourced from the existing validated department object with
    zero new calculations, zero new engineering logic, and no changes to the
    representative meter selection or gauge scaling logic.
    """
    dept_obj: dict[str, Any] = dashboard.get("departments", {}).get(active_dept, {})
    overview_df: pd.DataFrame = dashboard.get("overview", pd.DataFrame())

    if not dept_obj:
        return

    meters = dept_obj.get("meters", [])
    df_block = dept_obj.get("dataframe", pd.DataFrame())
    rep_m = _get_representative_meter(dept_obj)

    latest_values = dept_obj.get("latest_values", {})
    average_values = dept_obj.get("average_values", {})
    total_values = dept_obj.get("total_values", {})
    units_map = dept_obj.get("units", {})

    rep_unit = units_map.get(rep_m, "") if rep_m else ""
    rep_latest = latest_values.get(rep_m) if rep_m else None
    rep_average = average_values.get(rep_m) if rep_m else None
    rep_total = total_values.get(rep_m) if rep_m else None

    active_meter_count = sum(1 for m in meters if isinstance(latest_values.get(m), (int, float)))
    total_meter_count = len(meters)
    is_reporting = active_meter_count > 0

    # -------- Determine latest timestamp for this department's data block --------
    latest_ts_display = "N/A"
    if isinstance(df_block, pd.DataFrame) and not df_block.empty:
        ts_col = None
        for candidate in ("Timestamp", "Date", "timestamp", "date"):
            if candidate in df_block.columns:
                ts_col = candidate
                break
        if ts_col is not None:
            try:
                last_ts = df_block[ts_col].iloc[-1]
                if hasattr(last_ts, "strftime"):
                    latest_ts_display = last_ts.strftime("%d %b %Y, %H:%M")
                else:
                    latest_ts_display = str(last_ts)
            except Exception:
                latest_ts_display = "N/A"

    status_color = THEME_SUCCESS_COLOR if is_reporting else THEME_DANGER_COLOR
    status_text = "REPORTING" if is_reporting else "NO SIGNAL"

    # ===================== DEPARTMENT HEADER =====================
    st.markdown(
        f"""
        <div class="ws-header-panel">
            <div class="ws-header-top-row">
                <div>
                    <p class="ws-dept-name">🛡️ {active_dept}</p>
                    <p class="ws-dept-subtitle">Engineering Supervisory System &middot; Department Workspace</p>
                </div>
                <div class="ws-meta-grid">
                    <div class="ws-meta-item">
                        <span class="ws-meta-label">Representative Meter</span>
                        <span class="ws-meta-value">{rep_m if rep_m else "N/A"}</span>
                    </div>
                    <div class="ws-meta-item">
                        <span class="ws-meta-label">Engineering Unit</span>
                        <span class="ws-meta-value">{rep_unit if rep_unit else "N/A"}</span>
                    </div>
                    <div class="ws-meta-item">
                        <span class="ws-meta-label">Latest Timestamp</span>
                        <span class="ws-meta-value">{latest_ts_display}</span>
                    </div>
                    <div class="ws-meta-item">
                        <span class="ws-meta-label">Reporting Status</span>
                        <span class="ws-status-chip" style="background: {status_color}22; color: {status_color}; border: 1px solid {status_color}55;">
                            <span class="status-dot" style="background:{status_color};"></span>{status_text}
                        </span>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ===================== ROW 1: KPI STRIP =====================
    r1_col1, r1_col2, r1_col3, r1_col4 = st.columns(4)

    with r1_col1:
        st.markdown(
            f"""<div class="ws-kpi-card">
                <p class="metric-card-title">Latest</p>
                <p class="metric-card-value">{f"{rep_latest:,.2f}" if isinstance(rep_latest, (int, float)) else "N/A"}</p>
                <div class="metric-card-footer">{rep_unit if rep_unit else "&nbsp;"}</div>
            </div>""", unsafe_allow_html=True
        )
    with r1_col2:
        st.markdown(
            f"""<div class="ws-kpi-card">
                <p class="metric-card-title">Average</p>
                <p class="metric-card-value">{f"{rep_average:,.2f}" if isinstance(rep_average, (int, float)) else "N/A"}</p>
                <div class="metric-card-footer">{rep_unit if rep_unit else "&nbsp;"}</div>
            </div>""", unsafe_allow_html=True
        )
    with r1_col3:
        st.markdown(
            f"""<div class="ws-kpi-card">
                <p class="metric-card-title">Total</p>
                <p class="metric-card-value">{f"{rep_total:,.2f}" if isinstance(rep_total, (int, float)) else "N/A"}</p>
                <div class="metric-card-footer">{rep_unit if rep_unit else "&nbsp;"}</div>
            </div>""", unsafe_allow_html=True
        )
    with r1_col4:
        st.markdown(
            f"""<div class="ws-kpi-card">
                <p class="metric-card-title">Active Meter Count</p>
                <p class="metric-card-value">{active_meter_count} / {total_meter_count}</p>
                <div class="metric-card-footer">Channels Online</div>
            </div>""", unsafe_allow_html=True
        )

    # ===================== ROW 2: PRIMARY TREND + GAUGE =====================
    r2_col1, r2_col2 = st.columns([6.5, 3.5])

    with r2_col1:
        st.markdown(
            '<div class="ws-panel"><p class="ws-panel-title">📉 Primary Trend Chart</p>',
            unsafe_allow_html=True,
        )
        fig_primary = chart_service.build_section_trend_chart(overview_df, dept_obj)
        if fig_primary:
            st.plotly_chart(fig_primary, use_container_width=True)
        else:
            st.markdown('<p class="ws-empty-note">Primary chronological metric profile logs absent or structurally misaligned.</p>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with r2_col2:
        st.markdown(
            '<div class="ws-panel"><p class="ws-panel-title">🧭 Gauge</p>',
            unsafe_allow_html=True,
        )
        if rep_m:
            latest_val = latest_values.get(rep_m, 0.0)
            avg_val = average_values.get(rep_m, 100.0)
            total_val = total_values.get(rep_m, 500.0)
            unit_lbl = units_map.get(rep_m, "")

            max_ceiling = 100.0
            for potential_max in (total_val, avg_val, latest_val):
                if isinstance(potential_max, (int, float)) and potential_max > 0:
                    max_ceiling = float(potential_max)
                    break

            fig_gauge = chart_service.create_gauge_chart(
                value=float(latest_val) if isinstance(latest_val, (int, float)) else 0.0,
                title=f"Gauge: {rep_m[:18]}",
                maximum=max_ceiling if max_ceiling > float(latest_val or 0) else float((latest_val or 0) * 1.5),
                unit=str(unit_lbl)
            )
            if fig_gauge:
                st.plotly_chart(fig_gauge, use_container_width=True)
            else:
                st.markdown('<p class="ws-empty-note">Gauge visualization failed.</p>', unsafe_allow_html=True)
        else:
            st.markdown('<p class="ws-empty-note">No representative meter available for gauge display.</p>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # ===================== ROW 3: MULTI-LINE COMPARISON (FULL WIDTH) =====================
    st.markdown(
        '<div class="ws-panel"><p class="ws-panel-title">📊 Multi-Variable Process Cross-Channel Analysis</p>',
        unsafe_allow_html=True,
    )
    if len(meters) > 1:
        fig_compare = chart_service.create_department_multi_line_chart(
            overview_dataframe=overview_df,
            section=dept_obj,
            title="Parallel Operations Diagnostic Load Profiles",
        )
        if fig_compare:
            st.plotly_chart(fig_compare, use_container_width=True)
        else:
            st.markdown('<p class="ws-empty-note">Comparison chart unavailable for this data set.</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p class="ws-empty-note">Multi-channel comparison requires more than one active meter.</p>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # ===================== ROW 4: METER SUMMARY TABLE =====================
    st.markdown(
        '<div class="ws-panel"><p class="ws-panel-title">📑 Meter Summary Table</p>',
        unsafe_allow_html=True,
    )

    summary_records = []
    for m in meters:
        l_v = latest_values.get(m)
        a_v = average_values.get(m)
        t_v = total_values.get(m)
        u = units_map.get(m)
        status_string = "🟢 Active" if l_v is not None else "⚪ Idle"

        summary_records.append({
            "Meter": m,
            "Latest": round(l_v, 2) if isinstance(l_v, (int, float)) else "N/A",
            "Average": round(a_v, 2) if isinstance(a_v, (int, float)) else "N/A",
            "Total": round(t_v, 2) if isinstance(t_v, (int, float)) else "N/A",
            "Unit": u if (u and str(u).strip()) else "N/A",
            "Status": status_string,
        })

    if summary_records:
        st.dataframe(pd.DataFrame(summary_records), use_container_width=True, hide_index=True)
    else:
        st.markdown('<p class="ws-empty-note">No meter channels registered for this department.</p>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # ===================== ROW 5: HISTORICAL DATA (SORTABLE, FULL WIDTH) =====================
    st.markdown(
        '<div class="ws-panel"><p class="ws-panel-title">🗂️ Historical Data</p>',
        unsafe_allow_html=True,
    )
    if isinstance(df_block, pd.DataFrame) and not df_block.empty:
        # st.dataframe natively supports interactive column-header sorting;
        # no data transformation or logic change is applied to df_block.
        st.dataframe(df_block, use_container_width=True, hide_index=True)
    else:
        st.markdown('<p class="ws-empty-note">No historical dataframe records available for this department.</p>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_footer(dashboard: dict[str, Any] | None) -> None:
    """Render a minimal presentation bottom block containing deployment indicators."""
    last_refresh = st.session_state.get("last_refresh")
    refresh_text = last_refresh.strftime("%d %b %Y, %H:%M:%S") if last_refresh else "N/A"
    
    meta = (dashboard or {}).get("metadata", {})
    sheet_names = meta.get("sheet_names", ["Data Source Unlinked"])
    active_workbook = sheet_names[0] if sheet_names else "N/A"

    st.markdown(
        f"""
        <div class="scada-footer">
            Workbook Context: {active_workbook} · 
            Last Refresh: {refresh_text} · 
            Dashboard Baseline Version Suite v{APP_VERSION}
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    """Orchestrate layout render workflows safely utilizing session cache resources."""
    inject_global_styles()

    dashboard, error_msg = get_dashboard()

    render_top_header(dashboard)

    if error_msg is not None or dashboard is None:
        st.error(error_msg or "Critical Infrastructure Alert: Analytical context dictionary failed initialization.")
        render_footer(dashboard)
        return

    selected_dept = render_department_grid(dashboard)
    
    if selected_dept:
        render_subsystem_workspace(dashboard, selected_dept)
        
    render_footer(dashboard)


if __name__ == "__main__":
    main()
