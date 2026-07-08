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
            .dept-list {{
                display: flex; flex-direction: column; gap: 4px; background: #151820;
                border: 1px solid #222631; border-radius: 6px; padding: 8px; margin-bottom: 24px;
            }}
            div[data-testid="stButton"] > button {{
                display: flex; justify-content: space-between; align-items: center;
                background: #151820 !important; border: 1px solid #222631 !important;
                border-radius: 4px !important; padding: 12px 16px !important; text-align: left !important;
                color: #F1F5F9 !important; font-weight: 500 !important; font-size: 13px !important;
                transition: all 0.15s !important; margin-bottom: 4px !important; box-shadow: none !important;
            }}
            div[data-testid="stButton"] > button:hover {{
                background: #1E293B !important; border-color: #334155 !important;
            }}
            div[data-testid="stButton"] > button[kind="primary"] {{
                background: #1E293B !important; border-left: 3px solid #3B82F6 !important; color: #F1F5F9 !important;
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
            .workspace-grid {{ display: grid; grid-template-columns: 2fr 1fr; gap: 24px; margin-bottom: 24px; }}
            .workspace-main, .workspace-side {{ display: flex; flex-direction: column; gap: 16px; }}
            .workspace-tables {{ display: flex; flex-direction: column; gap: 16px; }}

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

            /* ── Scrollbar ─────────────────────────────────────────────── */
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
    
    st.markdown('<div style="font-size: 12px; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Critical Plant Assets</div>', unsafe_allow_html=True)
    
    if not dept_names: return ""
    if "selected_department" not in st.session_state or st.session_state["selected_department"] not in dept_names: 
        st.session_state["selected_department"] = dept_names[0]
    current_selection = st.session_state["selected_department"]

    for d_name in dept_names:
        dept_obj = departments[d_name]
        rep_m = _get_representative_meter(dept_obj)
        latest_value = dept_obj.get("latest_values", {}).get(rep_m) if rep_m else None
        unit_label = dept_obj.get("units", {}).get(rep_m, "") if rep_m else ""
        latest_display = f"{latest_value:,.2f}" if isinstance(latest_value, (int, float)) else "N/A"
        
        is_active = (d_name == current_selection)
        btn_type = "primary" if is_active else "secondary"
        
        label = f"""
        <div style="display:flex; justify-content:space-between; width:100%;">
            <span>{d_name}</span>
            <span style="color: #94A3B8; font-variant-numeric: tabular-nums;">{latest_display} <span style="font-size: 11px; color: #64748B;">{unit_label}</span></span>
        </div>"""
        
        if st.button(label, key=f"nav_{d_name}", type=btn_type, use_container_width=True):
            st.session_state["selected_department"] = d_name
            st.rerun()
            
    return st.session_state["selected_department"]

def render_tables(dept_obj: dict[str, Any], meters: list[str]) -> None:
    st.markdown("<div style='font-size: 13px; font-weight: 600; color: #F1F5F9; margin-bottom: 8px;'>Channel Registry</div>", unsafe_allow_html=True)
    units_map = dept_obj.get("units", {}); latest_vals = dept_obj.get("latest_values", {}); avg_vals = dept_obj.get("average_values", {}); total_vals = dept_obj.get("total_values", {})
    ledger_records = []
    for m in meters:
        lbl = units_map.get(m); l_v = latest_vals.get(m); a_v = avg_vals.get(m); t_v = total_vals.get(m)
        status_string = "Active" if l_v is not None else "Idle"
        ledger_records.append({"Channel": m, "Unit": lbl if (lbl and str(lbl).strip()) else "N/A", "Latest": round(l_v, 2) if isinstance(l_v, (int, float)) else "N/A", "Mean": round(a_v, 2) if isinstance(a_v, (int, float)) else "N/A", "Total": round(t_v, 2) if isinstance(t_v, (int, float)) else "N/A", "Status": status_string})
    if ledger_records: st.dataframe(pd.DataFrame(ledger_records), use_container_width=True, hide_index=True)

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
        <div class="workspace-grid">
            <div class="workspace-main" id="main-charts"></div>
            <div class="workspace-side" id="side-charts"></div>
        </div>
        <div class="workspace-tables" id="tables"></div>
    </div>""", unsafe_allow_html=True)

    meters = dept_obj.get("meters", [])
    df_block = dept_obj.get("dataframe", pd.DataFrame())
    rep_m = _get_representative_meter(dept_obj)

    # We use Streamlit columns to populate the grid areas defined above
    # Since Streamlit renders top-to-bottom, we simulate the grid by using columns
    # But to keep it simple and robust, we'll just render them in a clean layout
    
    col_main, col_side = st.columns([2, 1])
    
    with col_main:
        st.markdown("<div style='font-size: 13px; font-weight: 600; color: #F1F5F9; margin-bottom: 8px;'>Primary Telemetry Profile</div>", unsafe_allow_html=True)
        fig_primary = chart_service.build_section_trend_chart(overview_df, dept_obj)
        if fig_primary: 
            st.plotly_chart(fig_primary, use_container_width=True, config={"displayModeBar": False})
        else: 
            st.caption("Primary chronological metric profile logs absent or structurally misaligned.")
            
        if len(meters) > 1:
            st.markdown("<div style='font-size: 13px; font-weight: 600; color: #F1F5F9; margin-top: 16px; margin-bottom: 8px;'>Cross-Channel Analysis</div>", unsafe_allow_html=True)
            fig_compare = chart_service.create_department_multi_line_chart(overview_dataframe=overview_df, section=dept_obj, title="Parallel Operations Diagnostic Load Profiles")
            if fig_compare: 
                st.plotly_chart(fig_compare, use_container_width=True, config={"displayModeBar": False})

    with col_side:
        st.markdown("<div style='font-size: 13px; font-weight: 600; color: #F1F5F9; margin-bottom: 8px;'>Instrumentation Gauge</div>", unsafe_allow_html=True)
        if rep_m:
            latest_val = dept_obj.get("latest_values", {}).get(rep_m, 0.0)
            avg_val = dept_obj.get("average_values", {}).get(rep_m, 100.0)
            total_val = dept_obj.get("total_values", {}).get(rep_m, 500.0)
            unit_lbl = dept_obj.get("units", {}).get(rep_m, "")
            max_ceiling = 100.0
            if rep_m and rep_m in df_block.columns:
                numeric_series = pd.to_numeric(df_block[rep_m], errors='coerce').dropna()
                if len(numeric_series) >= 5: base_max = float(numeric_series.quantile(0.95))
                elif not numeric_series.empty: base_max = float(numeric_series.max())
                else: base_max = 0.0
                if base_max > 0: max_ceiling = base_max * 1.15
                else:
                    for potential_max in (total_val, avg_val, latest_val):
                        if isinstance(potential_max, (int, float)) and potential_max > 0: max_ceiling = float(potential_max) * 1.15; break
            else:
                for potential_max in (total_val, avg_val, latest_val):
                    if isinstance(potential_max, (int, float)) and potential_max > 0: max_ceiling = float(potential_max) * 1.15; break
                    
            fig_gauge = chart_service.create_gauge_chart(value=float(latest_val) if isinstance(latest_val, (int, float)) else 0.0, title=f"{rep_m}", maximum=max_ceiling if max_ceiling > float(latest_val or 0) else float((latest_val or 0) * 1.5), unit=str(unit_lbl))
            if fig_gauge: 
                st.plotly_chart(fig_gauge, use_container_width=True, config={"displayModeBar": False})
            else: 
                st.caption("Gauge visualization failed.")
                
        st.markdown("<div style='font-size: 13px; font-weight: 600; color: #F1F5F9; margin-top: 16px; margin-bottom: 8px;'>Vector Snapshots</div>", unsafe_allow_html=True)
        mini_records = []
        for m in meters[:min(len(meters), 5)]:
            v = dept_obj.get("latest_values", {}).get(m); u = dept_obj.get("units", {}).get(m, "N/A")
            mini_records.append({"Channel": m[:15], "Value": f"{v:,.2f}" if isinstance(v, (int, float)) else "Offline", "Unit": u if (u and str(u).strip()) else "N/A"})
        if mini_records: st.dataframe(pd.DataFrame(mini_records), use_container_width=True, hide_index=True)

    st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)
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
