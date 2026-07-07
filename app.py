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
from dashboard_data import select_representative_meter

st.set_page_config(
    page_title=PAGE_CONFIG.get("page_title", APP_NAME),
    page_icon=PAGE_CONFIG.get("page_icon", "⚙️"),
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Layout constants
GRID_COLUMNS: Final[int] = 4

def get_dashboard() -> tuple[dict[str, Any] | None, str | None]:
    """Retrieve the cached dashboard session payload framework context safely."""
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
            /* ── Global Reset ──────────────────────────────────────────── */
            #MainMenu {{visibility: hidden;}}
            footer {{visibility: hidden;}}
            header[data-testid="stHeader"] {{background: transparent;}}

            .stApp {{
                background: linear-gradient(168deg, #0a0e1a 0%, #0f1629 35%, #111827 70%, #0d1117 100%);
            }}

            .block-container {{
                padding-top: 0.8rem;
                padding-bottom: 2.0rem;
                max-width: 1600px;
            }}

            /* ── SCADA Header ──────────────────────────────────────────── */
            .scada-header {{
                background: linear-gradient(135deg, rgba(108, 99, 255, 0.08), rgba(0, 212, 255, 0.04), rgba(22, 26, 37, 0.92));
                border: 1px solid rgba(0, 212, 255, 0.1);
                border-radius: 14px;
                padding: 18px 24px;
                margin-bottom: 18px;
                backdrop-filter: blur(12px);
                box-shadow: 0 4px 30px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255,255,255,0.03);
            }}

            .scada-title-block {{
                display: flex;
                align-items: center;
                gap: 16px;
            }}

            .scada-logo {{
                width: 48px;
                height: 48px;
                border-radius: 10px;
                background: linear-gradient(135deg, {THEME_PRIMARY_COLOR}, #00D4FF);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 24px;
                box-shadow: 0 4px 20px rgba(0, 212, 255, 0.25), 0 0 40px rgba(0, 212, 255, 0.08);
            }}

            .scada-main-title {{
                font-size: 1.35rem;
                font-weight: 800;
                color: #FAFAFA;
                margin: 0;
                letter-spacing: -0.3px;
                background: linear-gradient(90deg, #F8FAFC, #CBD5E1);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}

            .status-pill {{
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 4px 12px;
                border-radius: 20px;
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.06);
                font-size: 0.68rem;
                color: #94A3B8;
                font-weight: 500;
                letter-spacing: 0.3px;
                text-transform: uppercase;
                transition: border-color 0.2s;
            }}
            .status-pill:hover {{
                border-color: rgba(0, 212, 255, 0.2);
            }}

            .status-dot {{
                width: 7px;
                height: 7px;
                border-radius: 50%;
                display: inline-block;
                animation: pulse-dot 2s ease-in-out infinite;
            }}

            @keyframes pulse-dot {{
                0%, 100% {{ opacity: 1; }}
                50% {{ opacity: 0.5; }}
            }}

            /* ── Metric / KPI Cards ────────────────────────────────────── */
            .metric-card-container {{
                background: linear-gradient(145deg, rgba(30, 41, 59, 0.3), rgba(15, 23, 42, 0.7));
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 12px;
                padding: 16px 20px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255,255,255,0.03);
                backdrop-filter: blur(8px);
                transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
                position: relative;
                overflow: hidden;
            }}
            .metric-card-container::before {{
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 2px;
                background: linear-gradient(90deg, transparent, rgba(0, 212, 255, 0.4), transparent);
                opacity: 0;
                transition: opacity 0.3s;
            }}
            .metric-card-container:hover {{
                transform: translateY(-2px);
                box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4), 0 0 20px rgba(0, 212, 255, 0.06);
                border-color: rgba(0, 212, 255, 0.15);
            }}
            .metric-card-container:hover::before {{
                opacity: 1;
            }}

            .metric-card-icon {{
                font-size: 1.1rem;
                margin-bottom: 6px;
                opacity: 0.8;
            }}

            .metric-card-title {{
                font-size: 0.68rem;
                color: #64748B;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.8px;
                margin: 0 0 6px 0;
            }}

            .metric-card-value {{
                font-size: 1.6rem;
                font-weight: 800;
                color: #F8FAFC;
                margin: 0;
                letter-spacing: -0.5px;
                font-variant-numeric: tabular-nums;
            }}

            .metric-card-footer {{
                font-size: 0.65rem;
                color: #475569;
                margin-top: 6px;
                font-weight: 500;
                letter-spacing: 0.3px;
            }}

            /* ── Section Titles ────────────────────────────────────────── */
            .section-panel-title {{
                font-size: 0.82rem;
                font-weight: 800;
                color: #E2E8F0;
                text-transform: uppercase;
                letter-spacing: 1.2px;
                margin: 20px 0 12px 2px;
                display: flex;
                align-items: center;
                gap: 8px;
            }}
            .section-panel-title::after {{
                content: '';
                flex: 1;
                height: 1px;
                background: linear-gradient(90deg, rgba(148, 163, 184, 0.15), transparent);
                margin-left: 8px;
            }}

            /* ── Department Asset Cards ────────────────────────────────── */
            .scada-asset-card {{
                background: linear-gradient(145deg, rgba(30, 41, 59, 0.35), rgba(15, 23, 42, 0.75));
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 14px;
                padding: 20px;
                box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255,255,255,0.03);
                transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
                min-height: 240px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                box-sizing: border-box;
                margin-bottom: 14px;
                backdrop-filter: blur(10px);
                position: relative;
                overflow: hidden;
            }}
            .scada-asset-card::before {{
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 3px;
                background: linear-gradient(90deg, transparent, rgba(0, 212, 255, 0.5), transparent);
                opacity: 0;
                transition: opacity 0.3s;
            }}
            .scada-asset-card:hover {{
                transform: translateY(-3px);
                box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5), 0 0 30px rgba(0, 212, 255, 0.08);
                border-color: rgba(0, 212, 255, 0.2);
            }}
            .scada-asset-card:hover::before {{
                opacity: 1;
            }}

            .scada-asset-title {{
                font-size: 1.05rem;
                font-weight: 800;
                color: #FAFAFA;
                margin: 0 0 14px 0;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                letter-spacing: -0.2px;
            }}

            .scada-asset-data-row {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin: 5px 0;
                font-size: 0.8rem;
                padding: 4px 0;
                border-bottom: 1px solid rgba(255, 255, 255, 0.03);
            }}
            .scada-asset-data-row:last-of-type {{
                border-bottom: none;
            }}

            .scada-asset-label {{
                color: #64748B;
                font-weight: 600;
                text-transform: uppercase;
                font-size: 0.7rem;
                letter-spacing: 0.5px;
            }}

            .scada-asset-value {{
                color: #F1F5F9;
                font-weight: 700;
                text-align: right;
                white-space: nowrap;
                font-variant-numeric: tabular-nums;
            }}

            .scada-asset-status {{
                display: flex;
                align-items: center;
                gap: 6px;
                font-size: 0.72rem;
                color: #94A3B8;
                margin-top: 12px;
                margin-bottom: 8px;
                font-weight: 500;
            }}

            /* ── Buttons ───────────────────────────────────────────────── */
            div[data-testid="stButton"] > button {{
                width: 100%;
                border-radius: 10px !important;
                border: 1px solid rgba(255, 255, 255, 0.06) !important;
                background: linear-gradient(145deg, rgba(30, 41, 59, 0.25), rgba(15, 23, 42, 0.6)) !important;
                padding: 10px 14px !important;
                text-align: left !important;
                transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
                font-weight: 500 !important;
            }}

            div[data-testid="stButton"] > button:hover {{
                transform: translateY(-1px);
                border-color: rgba(0, 212, 255, 0.3) !important;
                box-shadow: 0 4px 16px rgba(0, 212, 255, 0.1) !important;
                background: linear-gradient(145deg, rgba(30, 41, 59, 0.4), rgba(15, 23, 42, 0.8)) !important;
            }}

            .tile-active > div[data-testid="stButton"] > button {{
                border-color: rgba(0, 212, 255, 0.4) !important;
                background: linear-gradient(145deg, rgba(0, 212, 255, 0.1), rgba(15, 23, 42, 0.8)) !important;
                box-shadow: 0 4px 20px rgba(0, 212, 255, 0.12) !important;
            }}

            .scada-action-btn > div[data-testid="stButton"] > button {{
                text-align: center !important;
                background: linear-gradient(145deg, rgba(0, 212, 255, 0.08), rgba(15, 23, 42, 0.7)) !important;
                border: 1px solid rgba(0, 212, 255, 0.15) !important;
                font-weight: 700 !important;
                color: #CBD5E1 !important;
                letter-spacing: 0.5px !important;
                text-transform: uppercase !important;
                font-size: 0.72rem !important;
            }}

            .scada-action-btn > div[data-testid="stButton"] > button:hover {{
                background: linear-gradient(145deg, rgba(0, 212, 255, 0.18), rgba(15, 23, 42, 0.85)) !important;
                border-color: rgba(0, 212, 255, 0.4) !important;
                color: #FAFAFA !important;
                box-shadow: 0 4px 20px rgba(0, 212, 255, 0.15) !important;
            }}

            /* ── Panel Containers ──────────────────────────────────────── */
            .panel-container {{
                background: linear-gradient(145deg, rgba(22, 26, 37, 0.4), rgba(15, 23, 42, 0.6));
                border: 1px solid rgba(255, 255, 255, 0.04);
                border-radius: 16px;
                padding: 24px;
                margin-top: 14px;
                backdrop-filter: blur(10px);
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            }}

            /* ── Data Tables ───────────────────────────────────────────── */
            div[data-testid="stDataFrame"] {{
                border: 1px solid rgba(255, 255, 255, 0.05) !important;
                border-radius: 10px !important;
                overflow: hidden !important;
            }}
            div[data-testid="stDataFrame"] table {{
                font-size: 0.78rem !important;
            }}
            div[data-testid="stDataFrame"] th {{
                background: rgba(30, 41, 59, 0.7) !important;
                color: #94A3B8 !important;
                font-weight: 700 !important;
                text-transform: uppercase !important;
                font-size: 0.68rem !important;
                letter-spacing: 0.5px !important;
                border-bottom: 1px solid rgba(0, 212, 255, 0.15) !important;
                padding: 10px 12px !important;
            }}
            div[data-testid="stDataFrame"] td {{
                background: rgba(15, 23, 42, 0.4) !important;
                color: #CBD5E1 !important;
                border-bottom: 1px solid rgba(255, 255, 255, 0.03) !important;
                padding: 8px 12px !important;
                font-variant-numeric: tabular-nums;
            }}
            div[data-testid="stDataFrame"] tr:hover td {{
                background: rgba(0, 212, 255, 0.04) !important;
            }}
            div[data-testid="stDataFrame"] tr:nth-child(even) td {{
                background: rgba(30, 41, 59, 0.2) !important;
            }}
            div[data-testid="stDataFrame"] tr:nth-child(even):hover td {{
                background: rgba(0, 212, 255, 0.04) !important;
            }}

            /* ── Selectbox / Filter Styling ────────────────────────────── */
            div[data-baseweb="select"] > div {{
                background: rgba(15, 23, 42, 0.6) !important;
                border: 1px solid rgba(255, 255, 255, 0.08) !important;
                border-radius: 8px !important;
            }}
            div[data-baseweb="select"] > div:hover {{
                border-color: rgba(0, 212, 255, 0.2) !important;
            }}

            /* ── Footer ────────────────────────────────────────────────── */
            .scada-footer {{
                margin-top: 32px;
                padding: 14px 20px;
                border-radius: 10px;
                background: linear-gradient(145deg, rgba(255, 255, 255, 0.01), rgba(15, 23, 42, 0.3));
                border: 1px solid rgba(255, 255, 255, 0.03);
                font-size: 0.68rem;
                color: #475569;
                text-align: center;
                letter-spacing: 0.3px;
            }}

            /* ── Scrollbar ─────────────────────────────────────────────── */
            ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
            ::-webkit-scrollbar-track {{ background: rgba(15, 23, 42, 0.5); }}
            ::-webkit-scrollbar-thumb {{ background: rgba(100, 116, 139, 0.3); border-radius: 3px; }}
            ::-webkit-scrollbar-thumb:hover {{ background: rgba(100, 116, 139, 0.5); }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_top_header(dashboard: dict[str, Any] | None) -> tuple[str, str]:
    """Render the simplified global system supervision header and time controls."""
    now = dt.datetime.now()
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
                        <div style="display: flex; gap: 8px; margin-top: 6px; flex-wrap: wrap;">
                            <div class="status-pill"><span class="status-dot" style="background:{plant_color};box-shadow:0 0 6px {plant_color};"></span>PLANT {plant_text}</div>
                            <div class="status-pill"><span class="status-dot" style="background:{wb_color};box-shadow:0 0 6px {wb_color};"></span>{wb_text}</div>
                            <div class="status-pill">📅 {now.strftime("%d %b %Y")}</div>
                            <div class="status-pill">🕒 {now.strftime("%H:%M:%S")}</div>
                            <div class="status-pill">🔁 {last_refresh.strftime("%H:%M:%S")}</div>
                            <div class="status-pill">🐙 {GITHUB_OWNER}/{GITHUB_REPO}@{GITHUB_BRANCH}</div>
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

    kpi_cards = [
        ("⚡", "Total Consumption", f"{total_consumption:,.1f}", "Sum Active Channels"),
        ("📊", "Average Consumption", f"{global_average:,.1f}", "Channel Array Average"),
        ("📡", "Latest Reading", f"{total_consumption / max(total_reporting_meters, 1):,.1f}", "Mean Vector Output"),
        ("🏭", "Depts Reporting", f"{active_depts_count}", "Functional Systems Feed"),
        ("🔌", "Meters Reporting", f"{total_reporting_meters} / {meter_count}", "Active Subnodes Trace"),
        ("🕐", "Last Updated", latest_ts_display, "Chronological Base Target"),
    ]

    cols = [k_col1, k_col2, k_col3, k_col4, k_col5, k_col6]
    for col, (icon, title, value, footer) in zip(cols, kpi_cards):
        val_style = 'font-size: 1.3rem; font-weight: 800; padding-top: 3px;' if title == "Last Updated" else ''
        with col:
            st.markdown(
                f"""<div class="metric-card-container">
                    <div class="metric-card-icon">{icon}</div>
                    <p class="metric-card-title">{title}</p>
                    <p class="metric-card-value" style="{val_style}">{value}</p>
                    <div class="metric-card-footer">{footer}</div>
                </div>""",
                unsafe_allow_html=True,
            )


def _get_representative_meter(dept_obj: dict[str, Any]) -> str:
    """Safely select the representative meter using centralized business logic."""
    return select_representative_meter(dept_obj)


def render_department_grid(dashboard: dict[str, Any]) -> str:
    """Render specialized structural matrix navigation system grids with modern SCADA-style cards."""
    departments: dict[str, dict[str, Any]] = dashboard.get("departments", {})

    critical_assets = [
        "NPCL", "Dough", "Traywasher", "Air compressor",
        "Freon Refrigeration", "DG", "GG",
    ]

    dept_names = [name for name in critical_assets if name in departments]

    st.markdown('<p class="section-panel-title">🏭 Critical Plant Assets</p>', unsafe_allow_html=True)

    if not dept_names:
        return ""

    if "selected_department" not in st.session_state or st.session_state["selected_department"] not in dept_names:
        st.session_state["selected_department"] = dept_names[0]
    current_selection = st.session_state["selected_department"]

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

            active_border = "rgba(0, 212, 255, 0.35)" if is_active else "rgba(255,255,255,0.05)"
            active_glow = "0 0 25px rgba(0, 212, 255, 0.1)" if is_active else "none"

            with col:
                st.markdown(
                    f"""
                    <div class="scada-asset-card" style="border-color: {active_border}; box-shadow: {active_glow}, 0 6px 24px rgba(0,0,0,0.35); margin-bottom: 0px;">
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
                                <span class="status-dot" style="background: {THEME_SUCCESS_COLOR};box-shadow:0 0 6px {THEME_SUCCESS_COLOR};"></span>
                                Meters : {meter_count}
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.markdown('<div class="scada-action-btn" style="margin-top: -10px; margin-bottom: 14px;">', unsafe_allow_html=True)
                if st.button("Open Dashboard", key=f"nav_tile_{d_name}"):
                    st.session_state["selected_department"] = d_name
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    return st.session_state["selected_department"]


def render_subsystem_workspace(dashboard: dict[str, Any], active_dept: str) -> None:
    """Render comprehensive diagnostic analysis charts and comparative tables for selected block."""
    dept_obj: dict[str, Any] = dashboard.get("departments", {}).get(active_dept, {})
    overview_df: pd.DataFrame = dashboard.get("overview", pd.DataFrame())

    if not dept_obj:
        return

    st.markdown(f'<div class="panel-container">', unsafe_allow_html=True)
    st.markdown(
        f"""<div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;">
            <h3 style="margin:0;font-size:1.1rem;font-weight:800;color:#F1F5F9;letter-spacing:-0.2px;">
                🛡️ Engineering Supervisory System Diagnostics
            </h3>
            <span class="status-pill" style="font-size:0.72rem;">
                <span class="status-dot" style="background:{THEME_SUCCESS_COLOR};box-shadow:0 0 6px {THEME_SUCCESS_COLOR};"></span>
                {active_dept}
            </span>
        </div>""",
        unsafe_allow_html=True,
    )
    st.markdown('<hr style="margin: 8px 0 20px 0; border: none; border-top: 1px solid rgba(255,255,255,0.05);"/>', unsafe_allow_html=True)

    meters = dept_obj.get("meters", [])
    df_block = dept_obj.get("dataframe", pd.DataFrame())
    rep_m = _get_representative_meter(dept_obj)

    chart_col1, chart_col2 = st.columns([6, 4])

    with chart_col1:
        st.markdown("##### 📉 Continuous Timeline Telemetry Profile")
        fig_primary = chart_service.build_section_trend_chart(overview_df, dept_obj)
        if fig_primary:
            st.plotly_chart(fig_primary, use_container_width=True, config={"displayModeBar": True, "displaylogo": False})
        else:
            st.caption("Primary chronological metric profile logs absent or structurally misaligned.")

        if len(meters) > 1:
            st.markdown("<br/>##### 📊 Multi-Variable Process Cross-Channel Analysis", unsafe_allow_html=True)

            fig_compare = chart_service.create_department_multi_line_chart(
                overview_dataframe=overview_df,
                section=dept_obj,
                title="Parallel Operations Diagnostic Load Profiles",
            )

            if fig_compare:
                st.plotly_chart(fig_compare, use_container_width=True, config={"displayModeBar": True, "displaylogo": False})

    with chart_col2:
        st.markdown("##### 🧭 Node Dynamic Scale Instrumentation Gauge")
        if rep_m:
            latest_val = dept_obj.get("latest_values", {}).get(rep_m, 0.0)
            avg_val = dept_obj.get("average_values", {}).get(rep_m, 100.0)
            total_val = dept_obj.get("total_values", {}).get(rep_m, 500.0)
            unit_lbl = dept_obj.get("units", {}).get(rep_m, "")

            max_ceiling = 100.0
            if rep_m and rep_m in df_block.columns:
                numeric_series = pd.to_numeric(df_block[rep_m], errors='coerce').dropna()
                if len(numeric_series) >= 5:
                    base_max = float(numeric_series.quantile(0.95))
                elif not numeric_series.empty:
                    base_max = float(numeric_series.max())
                else:
                    base_max = 0.0

                if base_max > 0:
                    max_ceiling = base_max * 1.15
                else:
                    for potential_max in (total_val, avg_val, latest_val):
                        if isinstance(potential_max, (int, float)) and potential_max > 0:
                            max_ceiling = float(potential_max) * 1.15
                            break
            else:
                for potential_max in (total_val, avg_val, latest_val):
                    if isinstance(potential_max, (int, float)) and potential_max > 0:
                        max_ceiling = float(potential_max) * 1.15
                        break

            fig_gauge = chart_service.create_gauge_chart(
                value=float(latest_val) if isinstance(latest_val, (int, float)) else 0.0,
                title=f"Gauge: {rep_m[:18]}",
                maximum=max_ceiling if max_ceiling > float(latest_val or 0) else float((latest_val or 0) * 1.5),
                unit=str(unit_lbl),
            )
            if fig_gauge:
                st.plotly_chart(fig_gauge, use_container_width=True, config={"displayModeBar": False})
            else:
                st.caption("Gauge visualization failed.")

        st.markdown("<br/>##### 📑 Node Current Process Vector Snapshots", unsafe_allow_html=True)
        mini_records = []
        for m in meters[:min(len(meters), 6)]:
            v = dept_obj.get("latest_values", {}).get(m)
            u = dept_obj.get("units", {}).get(m, "N/A")
            mini_records.append({
                "Channel ID": m[:20],
                "Log Readout": f"{v:,.2f}" if isinstance(v, (int, float)) else "Offline",
                "Unit": u if (u and str(u).strip()) else "N/A",
            })
        if mini_records:
            st.dataframe(pd.DataFrame(mini_records), use_container_width=True, hide_index=True)

    st.markdown("<br/>##### 📋 Instrumentation Node Channel Registry — Detailed Log Ledger", unsafe_allow_html=True)

    units_map = dept_obj.get("units", {})
    latest_vals = dept_obj.get("latest_values", {})
    avg_vals = dept_obj.get("average_values", {})
    total_vals = dept_obj.get("total_values", {})

    ledger_records = []
    for m in meters:
        lbl = units_map.get(m)
        l_v = latest_vals.get(m)
        a_v = avg_vals.get(m)
        t_v = total_vals.get(m)

        status_string = "🟢 Active" if l_v is not None else "⚪ Idle"

        ledger_records.append({
            "Instrumentation Node / Meter Channel": m,
            "Engineering Unit": lbl if (lbl and str(lbl).strip()) else "N/A",
            "Latest Value Check": round(l_v, 2) if isinstance(l_v, (int, float)) else "N/A",
            "Mean Running Load": round(a_v, 2) if isinstance(a_v, (int, float)) else "N/A",
            "Accumulated Quantity Sum": round(t_v, 2) if isinstance(t_v, (int, float)) else "N/A",
            "Operational Status Flag": status_string,
        })

    if ledger_records:
        st.dataframe(pd.DataFrame(ledger_records), use_container_width=True, hide_index=True)

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
            ⚙️ Workbook Context: <b>{active_workbook}</b> · 
            Last Refresh: <b>{refresh_text}</b> · 
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
