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
    APP_ICON, APP_NAME, APP_VERSION, GITHUB_BRANCH, GITHUB_OWNER, GITHUB_REPO, PAGE_CONFIG,
    THEME_DANGER_COLOR, THEME_PRIMARY_COLOR, THEME_SUCCESS_COLOR,
)
import services.chart_service as chart_service
import services.kpi_service as kpi_service
from services.dashboard_loader import load_dashboard_safe
from dashboard_data import select_representative_meter

st.set_page_config(page_title=PAGE_CONFIG.get("page_title", APP_NAME), page_icon=PAGE_CONFIG.get("page_icon", "⚙️"), layout="wide", initial_sidebar_state="collapsed")

GRID_COLUMNS: Final[int] = 4

DEPT_CONFIGS = {
    "NPCL": {"accent": "#3B82F6", "label": "Power & Utilities"},
    "Air compressor": {"accent": "#06B6D4", "label": "Pneumatics & Compression"},
    "Freon Refrigeration": {"accent": "#0EA5E9", "label": "Thermal & Cooling"},
    "DG": {"accent": "#F59E0B", "label": "Power Generation"},
    "GG": {"accent": "#EF4444", "label": "Gas Generation"},
    "Dough": {"accent": "#D97706", "label": "Processing & Batching"},
    "Traywasher": {"accent": "#14B8A6", "label": "Washing & Thermal"},
}
DEFAULT_CONFIG = {"accent": "#8B5CF6", "label": "Engineering Systems"}

def get_dashboard() -> tuple[dict[str, Any] | None, str | None]:
    if "dashboard_data" not in st.session_state:
        dashboard, error = load_dashboard_safe()
        st.session_state["dashboard_data"] = dashboard
        st.session_state["dashboard_error"] = error
        st.session_state["last_refresh"] = dt.datetime.now()
    return st.session_state.get("dashboard_data"), st.session_state.get("dashboard_error")

def refresh_dashboard() -> None:
    st.cache_data.clear()
    st.cache_resource.clear()
    for key in ("dashboard_data", "dashboard_error", "last_refresh"): st.session_state.pop(key, None)

def inject_global_styles() -> None:
    st.markdown(f"""
        <style>
            /* ── Global Reset ──────────────────────────────────────────── */
            #MainMenu {{visibility: hidden;}} footer {{visibility: hidden;}} header[data-testid="stHeader"] {{background: transparent;}}
            .stApp {{ background: #0B0D12 !important; }}
            .block-container {{ padding-top: 1.5rem; padding-bottom: 2.0rem; max-width: 1600px; }}

            /* ── App Header ────────────────────────────────────────────── */
            .app-header {{
                display: flex; justify-content: space-between; align-items: center;
                background: #151820; border: 1px solid #222631; border-radius: 6px;
                padding: 16px 24px; margin-bottom: 24px;
            }}
            .header-left {{ display: flex; align-items: center; gap: 16px; }}
            .app-logo {{
                width: 36px; height: 36px; background: #1E293B; border: 1px solid #334155;
                border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 18px;
            }}
            .app-title {{ font-size: 16px; font-weight: 700; color: #F1F5F9; }}
            .app-subtitle {{ font-size: 12px; color: #64748B; margin-top: 2px; }}
            .header-right {{ display: flex; align-items: center; gap: 24px; }}
            .header-status {{
                display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 600;
                color: #94A3B8; text-transform: uppercase; letter-spacing: 0.5px;
            }}
            .status-dot {{ width: 8px; height: 8px; border-radius: 50%; }}
            .header-time {{ font-size: 12px; font-weight: 600; color: #64748B; font-variant-numeric: tabular-nums; }}

            /* ── KPI Strip ─────────────────────────────────────────────── */
            .kpi-strip {{
                display: flex; align-items: center; background: #151820; border: 1px solid #222631;
                border-radius: 6px; padding: 16px 24px; margin-bottom: 24px;
            }}
            .kpi-item {{ flex: 1; text-align: center; }}
            .kpi-label {{ font-size: 11px; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }}
            .kpi-value {{ font-size: 20px; font-weight: 700; color: #F1F5F9; font-variant-numeric: tabular-nums; }}
            .kpi-divider {{ width: 1px; height: 40px; background: #222631; margin: 0 12px; }}

            /* ── Department Navigation ─────────────────────────────────── */
            #dept-nav-container {{
                display: flex;
                flex-direction: column;
                gap: 6px;
            }}
            #dept-nav-container div[data-testid="stButton"] > button {{
                display: flex !important;
                flex-direction: column !important;
                align-items: flex-start !important;
                justify-content: center !important;
                text-align: left !important;
                background: #151820 !important;
                border: 1px solid #222631 !important;
                border-radius: 6px !important;
                padding: 12px 16px !important;
                margin: 0 !important;
                height: auto !important;
                min-height: 90px !important;
                box-shadow: none !important;
                transition: all 0.2s ease !important;
                width: 100% !important;
                cursor: pointer !important;
            }}
            #dept-nav-container div[data-testid="stButton"] > button:hover {{
                background: #1E293B !important;
                border-color: #334155 !important;
            }}
            #dept-nav-container div[data-testid="stButton"] > button p {{
                margin: 0 !important;
                line-height: 1.3 !important;
                color: #F1F5F9 !important;
            }}
            #dept-nav-container div[data-testid="stButton"] > button p:nth-child(1) {{
                font-size: 14px !important;
                font-weight: 700 !important;
                color: #F8FAFC !important;
            }}
            #dept-nav-container div[data-testid="stButton"] > button p:nth-child(2) {{
                font-size: 11px !important;
                color: #64748B !important;
                font-style: italic !important;
                margin-top: 2px !important;
            }}
            #dept-nav-container div[data-testid="stButton"] > button p:nth-child(3) {{
                font-size: 18px !important;
                font-weight: 700 !important;
                color: #F1F5F9 !important;
                font-variant-numeric: tabular-nums !important;
                margin-top: 8px !important;
            }}
            #dept-nav-container div[data-testid="stButton"] > button p:nth-child(4) {{
                font-size: 10px !important;
                color: #10B981 !important;
                font-weight: 600 !important;
                text-transform: uppercase !important;
                letter-spacing: 0.5px !important;
                margin-top: 4px !important;
            }}
            #dept-nav-container div[data-testid="stButton"] > button[kind="primary"] {{
                background: #1E293B !important;
                border: 1px solid #3B82F6 !important;
                border-left: 4px solid #3B82F6 !important;
            }}
            #dept-nav-container div[data-testid="stButton"] > button[kind="primary"] p:nth-child(4) {{
                color: #3B82F6 !important;
            }}

            /* ── Workspace Container ───────────────────────────────────── */
            .workspace-container {{
                background: #151820; border: 1px solid #222631; border-radius: 6px; padding: 24px;
            }}
            .workspace-header {{
                border-left: 3px solid var(--accent, #3B82F6); padding-left: 12px; margin-bottom: 24px;
            }}
            .workspace-header h2 {{ margin: 0; font-size: 18px; font-weight: 700; color: #F1F5F9; }}
            .workspace-header span {{ font-size: 12px; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; }}
            
            .chart-title {{
                font-size: 12px;
                font-weight: 600;
                color: #94A3B8;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 8px;
                padding-left: 4px;
            }}

            /* ── Data Tables ───────────────────────────────────────────── */
            div[data-testid="stDataFrame"] {{
                border: 1px solid #222631 !important; border-radius: 6px !important; overflow: hidden !important;
            }}
            div[data-testid="stDataFrame"] th {{
                background: #1E293B !important; color: #94A3B8 !important; font-weight: 600 !important;
                text-transform: uppercase !important; font-size: 11px !important; letter-spacing: 0.5px !important;
                border-bottom: 1px solid #222631 !important; padding: 10px 12px !important;
            }}
            div[data-testid="stDataFrame"] td {{
                background: #151820 !important; color: #CBD5E1 !important; border-bottom: 1px solid #222631 !important;
                padding: 8px 12px !important; font-size: 12px !important; font-variant-numeric: tabular-nums;
            }}
            div[data-testid="stDataFrame"] tr:hover td {{ background: #1E293B !important; }}
            div[data-testid="stDataFrame"] tr:nth-child(even) td {{ background: #12151C !important; }}

            /* ── Footer ────────────────────────────────────────────────── */
            .app-footer {{
                margin-top: 32px; padding: 16px 24px; border-radius: 6px; background: #151820;
                border: 1px solid #222631; font-size: 12px; color: #64748B; text-align: center;
            }}

            ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
            ::-webkit-scrollbar-track {{ background: #0B0D12; }}
            ::-webkit-scrollbar-thumb {{ background: #334155; border-radius: 3px; }}
        </style>""", unsafe_allow_html=True)

def render_top_header(dashboard: dict[str, Any] | None) -> tuple[str, str]:
    now = dt.datetime.now()
    filters_data = (dashboard or {}).get("filters", {})
    departments = (dashboard or {}).get("departments", {})
    plant_ok = bool(departments)
    plant_color = THEME_SUCCESS_COLOR if plant_ok else THEME_DANGER_COLOR
    plant_text = "ONLINE" if plant_ok else "OFFLINE"
    wb_color = THEME_SUCCESS_COLOR if dashboard else THEME_DANGER_COLOR
    wb_text = "CONNECTED" if dashboard else "DISCONNECTED"
    last_refresh = st.session_state.get("last_refresh", now)

    st.markdown(f"""
    <div class="app-header">
        <div class="header-left">
            <div class="app-logo">{APP_ICON}</div>
            <div>
                <div class="app-title">{APP_NAME}</div>
                <div class="app-subtitle">Engineering Monitoring Dashboard</div>
            </div>
        </div>
        <div class="header-right">
            <div class="header-status"><span class="status-dot" style="background: {plant_color};"></span>PLANT {plant_text}</div>
            <div class="header-status"><span class="status-dot" style="background: {wb_color};"></span>{wb_text}</div>
            <div class="header-time">{now.strftime("%d %b %Y %H:%M:%S")}</div>
        </div>
    </div>""", unsafe_allow_html=True)

    h_col1, h_col2, h_col3 = st.columns([2.5, 2.5, 5])
    with h_col1: st.selectbox("Month Sync Context", options=filters_data.get("months", ["N/A"]), index=0, key="header_month_select", disabled=True, help="Filtering by date is managed at downstream visualization layer levels.")
    with h_col2: st.selectbox("Date Sync Context", options=filters_data.get("dates", ["N/A"]), index=0, key="header_date_select", disabled=True, help="Filtering by date is managed at downstream visualization layer levels.")
    with h_col3:
        st.markdown("<div style='padding-top: 24px;'></div>", unsafe_allow_html=True)
        if st.button("Sync Live Remote Ingestion Buffer", key="btn_manual_header_sync"): refresh_dashboard(); st.rerun()
    return "N/A", "N/A"

def render_executive_kpi_strip(dashboard: dict[str, Any]) -> None:
    summary = dashboard.get("summary", {})
    departments = dashboard.get("departments", {})
    total_consumption = 0.0; active_depts_count = 0; total_reporting_meters = 0
    for dept_obj in departments.values():
        latest_map = dept_obj.get("latest_values", {})
        valid_dept_vals = [v for v in latest_map.values() if isinstance(v, (int, float))]
        if valid_dept_vals: total_consumption += sum(valid_dept_vals); active_depts_count += 1
        total_reporting_meters += len(valid_dept_vals)
    flat_averages = [v for dept in summary.get("average_values", {}).values() if isinstance(dept, dict) for v in dept.values() if isinstance(v, (int, float))]
    global_average = sum(flat_averages) / len(flat_averages) if flat_averages else 0.0
    latest_ts_raw = summary.get("latest_timestamp", "N/A")
    latest_ts_display = latest_ts_raw.split()[0] if isinstance(latest_ts_raw, str) and " " in latest_ts_raw else (latest_ts_raw.strftime("%Y-%m-%d") if hasattr(latest_ts_raw, "strftime") else "N/A")
    meter_count = summary.get("meter_count", 0)

    st.markdown(f"""
    <div class="kpi-strip">
        <div class="kpi-item"><div class="kpi-label">Total Consumption</div><div class="kpi-value">{total_consumption:,.1f}</div></div>
        <div class="kpi-divider"></div>
        <div class="kpi-item"><div class="kpi-label">Average Consumption</div><div class="kpi-value">{global_average:,.1f}</div></div>
        <div class="kpi-divider"></div>
        <div class="kpi-item"><div class="kpi-label">Latest Reading</div><div class="kpi-value">{total_consumption / max(total_reporting_meters, 1):,.1f}</div></div>
        <div class="kpi-divider"></div>
        <div class="kpi-item"><div class="kpi-label">Depts Reporting</div><div class="kpi-value">{active_depts_count}</div></div>
        <div class="kpi-divider"></div>
        <div class="kpi-item"><div class="kpi-label">Meters Reporting</div><div class="kpi-value">{total_reporting_meters} / {meter_count}</div></div>
        <div class="kpi-divider"></div>
        <div class="kpi-item"><div class="kpi-label">Last Updated</div><div class="kpi-value">{latest_ts_display}</div></div>
    </div>""", unsafe_allow_html=True)

def _get_representative_meter(dept_obj: dict[str, Any]) -> str:
    return select_representative_meter(dept_obj)

def render_department_grid(dashboard: dict[str, Any]) -> str:
    departments: dict[str, dict[str, Any]] = dashboard.get("departments", {})
    critical_assets = ["NPCL", "Dough", "Traywasher", "Air compressor", "Freon Refrigeration", "DG", "GG"]
    dept_names = [name for name in critical_assets if name in departments]
    
    st.markdown('<div style="font-size: 12px; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">Critical Plant Assets</div>', unsafe_allow_html=True)
    
    if not dept_names: 
        return ""
        
    if "selected_department" not in st.session_state or st.session_state["selected_department"] not in dept_names: 
        st.session_state["selected_department"] = dept_names[0]
        
    current_selection = st.session_state["selected_department"]

    st.markdown('<div id="dept-nav-container">', unsafe_allow_html=True)
    for d_name in dept_names:
        dept_obj = departments[d_name]
        rep_m = _get_representative_meter(dept_obj)
        
        val = dept_obj.get("latest_values", {}).get(rep_m)
        unit = dept_obj.get("units", {}).get(rep_m, "")
        
        if isinstance(val, (int, float)):
            val_str = f"{val:,.2f}"
        else:
            val_str = "N/A"
            
        unit_str = str(unit).strip() if unit else ""
        display_str = f"{val_str} {unit_str}".strip()
        
        config = DEPT_CONFIGS.get(d_name, DEFAULT_CONFIG)
        category = config["label"]
        
        is_online = val is not None and isinstance(val, (int, float))
        status_text = "ONLINE" if is_online else "OFFLINE"
        
        is_active = (d_name == current_selection)
        
        label = f"{d_name}\n\n{category}\n\n{display_str}\n\n{status_text}"
        
        if st.button(
            label, 
            key=f"nav_{d_name}", 
            type="primary" if is_active else "secondary", 
            use_container_width=True
        ):
            st.session_state["selected_department"] = d_name
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
            
    return st.session_state["selected_department"]

def get_gauge_max(df_block: pd.DataFrame, rep_m: str, dept_obj: dict[str, Any]) -> float:
    if rep_m and rep_m in df_block.columns:
        numeric_series = pd.to_numeric(df_block[rep_m], errors='coerce').dropna()
        if len(numeric_series) >= 5:
            return float(numeric_series.quantile(0.95)) * 1.15
        elif not numeric_series.empty:
            return float(numeric_series.max()) * 1.15
    
    total_val = dept_obj.get("total_values", {}).get(rep_m, 500.0) or 500.0
    avg_val = dept_obj.get("average_values", {}).get(rep_m, 100.0) or 100.0
    latest_val = dept_obj.get("latest_values", {}).get(rep_m, 0.0) or 0.0
    
    for potential_max in (total_val, avg_val, latest_val):
        if isinstance(potential_max, (int, float)) and potential_max > 0:
            return float(potential_max) * 1.15
    return 100.0

def render_mini_table(dept_obj: dict[str, Any], meters: list[str]) -> None:
    mini_records = []
    for m in meters[:min(len(meters), 5)]:
        v = dept_obj.get("latest_values", {}).get(m)
        u = dept_obj.get("units", {}).get(m, "N/A")
        mini_records.append({"Channel": m[:15], "Value": f"{v:,.2f}" if isinstance(v, (int, float)) else "Offline", "Unit": u if (u and str(u).strip()) else "N/A"})
    if mini_records: 
        st.dataframe(pd.DataFrame(mini_records), use_container_width=True, hide_index=True)

def render_tables(dept_obj: dict[str, Any], meters: list[str]) -> None:
    st.markdown("<div class='chart-title' style='margin-top:24px;'>Channel Registry</div>", unsafe_allow_html=True)
    units_map = dept_obj.get("units", {}); latest_vals = dept_obj.get("latest_values", {}); avg_vals = dept_obj.get("average_values", {}); total_vals = dept_obj.get("total_values", {})
    ledger_records = []
    for m in meters:
        lbl = units_map.get(m); l_v = latest_vals.get(m); a_v = avg_vals.get(m); t_v = total_vals.get(m)
        status_string = "Active" if l_v is not None else "Idle"
        ledger_records.append({"Channel": m, "Unit": lbl if (lbl and str(lbl).strip()) else "N/A", "Latest": round(l_v, 2) if isinstance(l_v, (int, float)) else "N/A", "Mean": round(a_v, 2) if isinstance(a_v, (int, float)) else "N/A", "Total": round(t_v, 2) if isinstance(t_v, (int, float)) else "N/A", "Status": status_string})
    if ledger_records: st.dataframe(pd.DataFrame(ledger_records), use_container_width=True, hide_index=True)

def render_npcl_workspace(dept_obj, overview_df, rep_m, df_block, meters):
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("<div class='chart-title'>Power & Energy Profile</div>", unsafe_allow_html=True)
        fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
        if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with col2:
        st.markdown("<div class='chart-title'>Current Load</div>", unsafe_allow_html=True)
        if rep_m:
            latest_val = dept_obj.get("latest_values", {}).get(rep_m, 0.0) or 0.0
            unit_lbl = dept_obj.get("units", {}).get(rep_m, "")
            max_ceiling = get_gauge_max(df_block, rep_m, dept_obj)
            fig = chart_service.create_gauge_chart(latest_val, "Load", maximum=max_ceiling, unit=unit_lbl)
            if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("<div class='chart-title' style='margin-top:16px;'>Channel Snapshots</div>", unsafe_allow_html=True)
        render_mini_table(dept_obj, meters)

def render_air_compressor_workspace(dept_obj, overview_df, rep_m, df_block, meters):
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("<div class='chart-title'>Pressure & Flow Dynamics</div>", unsafe_allow_html=True)
        if len(meters) >= 2:
            fig = chart_service.create_combined_line_area_chart(df_block.reset_index(), 'index', meters[0], meters[1], "Pressure vs Flow")
            if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with col2:
        st.markdown("<div class='chart-title'>Runtime & Health</div>", unsafe_allow_html=True)
        vals = {m: dept_obj['total_values'].get(m, 0) or 0 for m in meters[:5]}
        bar_df = pd.DataFrame(list(vals.items()), columns=['Meter', 'Value'])
        fig = chart_service.create_horizontal_bar_chart(bar_df, 'Meter', 'Value', "Runtime Metrics")
        if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

def render_freon_workspace(dept_obj, overview_df, rep_m, df_block, meters):
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("<div class='chart-title'>Temperature Zones</div>", unsafe_allow_html=True)
        fig = chart_service.create_heatmap(df_block, meters[:min(len(meters), 8)], "Thermal Map")
        if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with col2:
        st.markdown("<div class='chart-title'>Cooling Load</div>", unsafe_allow_html=True)
        fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
        if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

def render_dg_workspace(dept_obj, overview_df, rep_m, df_block, meters):
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("<div class='chart-title'>Current Load</div>", unsafe_allow_html=True)
        if rep_m:
            latest_val = dept_obj.get("latest_values", {}).get(rep_m, 0.0) or 0.0
            unit_lbl = dept_obj.get("units", {}).get(rep_m, "%")
            fig = chart_service.create_gauge_chart(latest_val, "Load", maximum=100, unit=unit_lbl)
            if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with col2:
        st.markdown("<div class='chart-title'>Generation & Fuel</div>", unsafe_allow_html=True)
        vals = {m: dept_obj['total_values'].get(m, 0) or 0 for m in meters[:6]}
        bar_df = pd.DataFrame(list(vals.items()), columns=['Meter', 'Value'])
        fig = chart_service.create_bar_chart(bar_df, 'Meter', 'Value', "Fuel / Generation")
        if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

def render_default_workspace(dept_obj, overview_df, rep_m, df_block, meters):
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("<div class='chart-title'>Primary Telemetry Profile</div>", unsafe_allow_html=True)
        fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
        if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        
        if len(meters) > 1:
            st.markdown("<div class='chart-title' style='margin-top:16px;'>Cross-Channel Analysis</div>", unsafe_allow_html=True)
            fig_compare = chart_service.create_department_multi_line_chart(overview_dataframe=overview_df, section=dept_obj, title="Parallel Operations Diagnostic Load Profiles")
            if fig_compare: st.plotly_chart(fig_compare, use_container_width=True, config={"displayModeBar": False})
    with col2:
        st.markdown("<div class='chart-title'>Instrumentation Gauge</div>", unsafe_allow_html=True)
        if rep_m:
            latest_val = dept_obj.get("latest_values", {}).get(rep_m, 0.0)
            unit_lbl = dept_obj.get("units", {}).get(rep_m, "")
            max_ceiling = get_gauge_max(df_block, rep_m, dept_obj)
            fig = chart_service.create_gauge_chart(latest_val, rep_m, maximum=max_ceiling, unit=unit_lbl)
            if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("<div class='chart-title' style='margin-top:16px;'>Vector Snapshots</div>", unsafe_allow_html=True)
        render_mini_table(dept_obj, meters)

def render_subsystem_workspace(dashboard: dict[str, Any], active_dept: str) -> None:
    dept_obj: dict[str, Any] = dashboard.get("departments", {}).get(active_dept, {})
    overview_df: pd.DataFrame = dashboard.get("overview", pd.DataFrame())
    if not dept_obj: return

    config = DEPT_CONFIGS.get(active_dept, DEFAULT_CONFIG)
    accent = config["accent"]

    st.markdown(f"""
    <div class="workspace-container" style="--accent: {accent};">
        <div class="workspace-header">
            <h2>{active_dept}</h2>
            <span>{config['label']}</span>
        </div>
    </div>""", unsafe_allow_html=True)

    meters = dept_obj.get("meters", [])
    df_block = dept_obj.get("dataframe", pd.DataFrame())
    rep_m = _get_representative_meter(dept_obj)

    if active_dept == "NPCL": render_npcl_workspace(dept_obj, overview_df, rep_m, df_block, meters)
    elif active_dept == "Air compressor": render_air_compressor_workspace(dept_obj, overview_df, rep_m, df_block, meters)
    elif active_dept == "Freon Refrigeration": render_freon_workspace(dept_obj, overview_df, rep_m, df_block, meters)
    elif active_dept == "DG": render_dg_workspace(dept_obj, overview_df, rep_m, df_block, meters)
    else: render_default_workspace(dept_obj, overview_df, rep_m, df_block, meters)

    render_tables(dept_obj, meters)

def render_footer(dashboard: dict[str, Any] | None) -> None:
    last_refresh = st.session_state.get("last_refresh")
    refresh_text = last_refresh.strftime("%d %b %Y, %H:%M:%S") if last_refresh else "N/A"
    meta = (dashboard or {}).get("metadata", {})
    sheet_names = meta.get("sheet_names", ["Data Source Unlinked"])
    active_workbook = sheet_names[0] if sheet_names else "N/A"
    st.markdown(f"""<div class="app-footer">Workbook Context: {active_workbook} · Last Refresh: {refresh_text} · Dashboard Baseline Version Suite v{APP_VERSION}</div>""", unsafe_allow_html=True)

def main() -> None:
    inject_global_styles()
    dashboard, error_msg = get_dashboard()
    render_top_header(dashboard)
    if error_msg is not None or dashboard is None:
        st.error(error_msg or "Critical Infrastructure Alert: Analytical context dictionary failed initialization.")
        render_footer(dashboard); return
    selected_dept = render_department_grid(dashboard)
    if selected_dept: render_subsystem_workspace(dashboard, selected_dept)
    render_footer(dashboard)

if __name__ == "__main__": main()
