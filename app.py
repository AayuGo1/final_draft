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

CRITICAL_SYSTEMS = ["NPCL", "DG", "GG", "Air compressor", "Traywasher", "Freon Refrigeration", "Ammonia Refrigeration"]

DEPT_CONFIGS = {
    "NPCL": {"accent": "#3B82F6", "label": "Power & Utilities", "primary_kpi": "Total Energy"},
    "DG": {"accent": "#F59E0B", "label": "Diesel Generation", "primary_kpi": "Power Output"},
    "GG": {"accent": "#EF4444", "label": "Gas Generation", "primary_kpi": "Power Output"},
    "Air compressor": {"accent": "#06B6D4", "label": "Pneumatics", "primary_kpi": "Pressure"},
    "Freon Refrigeration": {"accent": "#0EA5E9", "label": "Cooling Systems", "primary_kpi": "Cooling Load"},
    "Ammonia Refrigeration": {"accent": "#10B981", "label": "Industrial Cooling", "primary_kpi": "Cooling Load"},
    "Traywasher": {"accent": "#14B8A6", "label": "Sanitation", "primary_kpi": "Water Usage"},
    "Dough": {"accent": "#D97706", "label": "Processing", "primary_kpi": "Energy"},
    "Bread": {"accent": "#F59E0B", "label": "Baking", "primary_kpi": "Energy"},
    "Donut": {"accent": "#FBBF24", "label": "Production", "primary_kpi": "Energy"},
    "CLC": {"accent": "#8B5CF6", "label": "Control", "primary_kpi": "Status"},
    "Warehouse": {"accent": "#6366F1", "label": "Storage", "primary_kpi": "Energy"},
    "Transport": {"accent": "#EC4899", "label": "Logistics", "primary_kpi": "Energy"},
    "Engineering": {"accent": "#14B8A6", "label": "Engineering", "primary_kpi": "Energy"},
    "Utility": {"accent": "#06B6D4", "label": "Utilities", "primary_kpi": "Energy"},
}
DEFAULT_CONFIG = {"accent": "#8B5CF6", "label": "Engineering Systems", "primary_kpi": "Energy"}

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
    for key in ("dashboard_data", "dashboard_error", "last_refresh"): 
        st.session_state.pop(key, None)

def inject_global_styles() -> None:
    st.markdown(f"""
        <style>
            #MainMenu {{visibility: hidden;}} 
            footer {{visibility: hidden;}} 
            header[data-testid="stHeader"] {{background: transparent;}}
            .stApp {{ background: #0B0D12 !important; }}
            .block-container {{ padding-top: 1rem; padding-bottom: 2rem; max-width: 1600px; }}

            .app-header {{
                display: flex; justify-content: space-between; align-items: center;
                background: #111827; border: 1px solid #1F2937;
                padding: 12px 20px; margin-bottom: 20px;
            }}
            .header-left {{ display: flex; align-items: center; gap: 12px; }}
            .app-logo {{
                width: 32px; height: 32px; background: #1E293B; border: 1px solid #334155;
                border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 16px;
            }}
            .app-title {{ font-size: 15px; font-weight: 700; color: #F9FAFB; }}
            .header-right {{ display: flex; align-items: center; gap: 20px; }}
            .header-status {{
                display: flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 600;
                color: #9CA3AF; text-transform: uppercase; letter-spacing: 0.5px;
            }}
            .status-dot {{ width: 6px; height: 6px; border-radius: 50%; }}
            .header-time {{ font-size: 11px; font-weight: 600; color: #6B7280; font-variant-numeric: tabular-nums; }}

            .exec-card {{
                background: #111827; border: 1px solid #1F2937; border-radius: 4px;
                padding: 12px 16px; min-height: 90px;
            }}
            .exec-card.active {{ border-left: 3px solid var(--accent, #3B82F6); }}
            .exec-name {{ font-size: 12px; font-weight: 700; color: #F9FAFB; margin-bottom: 4px; }}
            .exec-kpi-label {{ font-size: 10px; color: #6B7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px; }}
            .exec-value {{ font-size: 18px; font-weight: 700; color: #F9FAFB; font-variant-numeric: tabular-nums; margin-bottom: 2px; }}
            .exec-unit {{ font-size: 10px; color: #9CA3AF; margin-bottom: 4px; }}
            .exec-status {{ font-size: 9px; font-weight: 600; color: #10B981; text-transform: uppercase; letter-spacing: 0.5px; }}

            .ops-table {{
                width: 100%; border-collapse: collapse; background: #111827; border-radius: 4px; overflow: hidden;
            }}
            .ops-table th {{
                background: #1F2937; color: #9CA3AF; font-size: 10px; font-weight: 600;
                text-transform: uppercase; letter-spacing: 0.5px; padding: 10px 12px; text-align: left;
                border-bottom: 1px solid #374151;
            }}
            .ops-table td {{
                background: #111827; color: #D1D5DB; font-size: 11px; padding: 10px 12px;
                border-bottom: 1px solid #1F2937; font-variant-numeric: tabular-nums;
            }}
            .ops-table tr:hover td {{ background: #1F2937; }}
            .ops-table tr:nth-child(even) td {{ background: #0F172A; }}
            .ops-table tr:nth-child(even):hover td {{ background: #1F2937; }}

            .process-selector {{
                display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px;
            }}
            .process-tile {{
                background: #111827; border: 1px solid #1F2937; border-radius: 4px;
                padding: 12px; cursor: pointer; transition: all 0.2s;
            }}
            .process-tile:hover {{ border-color: #374151; background: #1F2937; }}
            .process-tile.active {{ border: 1px solid var(--accent, #3B82F6); background: #1F2937; }}
            .process-name {{ font-size: 12px; font-weight: 600; color: #F9FAFB; margin-bottom: 2px; }}
            .process-category {{ font-size: 10px; color: #6B7280; margin-bottom: 6px; }}
            .process-status {{ font-size: 9px; font-weight: 600; color: #10B981; text-transform: uppercase; }}

            .workspace {{
                background: #111827; border: 1px solid #1F2937; border-radius: 4px; padding: 20px;
            }}
            .workspace-header {{
                border-left: 3px solid var(--accent, #3B82F6); padding-left: 12px; margin-bottom: 20px;
            }}
            .workspace-title {{ font-size: 16px; font-weight: 700; color: #F9FAFB; margin: 0; }}
            .workspace-label {{ font-size: 11px; color: #6B7280; text-transform: uppercase; letter-spacing: 0.5px; }}

            .chart-container {{
                background: #111827; border: 1px solid #1F2937; border-radius: 4px; padding: 16px; margin-bottom: 16px;
            }}
            .chart-label {{
                font-size: 10px; font-weight: 600; color: #6B7280; text-transform: uppercase;
                letter-spacing: 0.5px; margin-bottom: 8px;
            }}

            div[data-testid="stDataFrame"] {{
                border: 1px solid #1F2937 !important; border-radius: 4px !important; overflow: hidden !important;
            }}
            div[data-testid="stDataFrame"] th {{
                background: #1F2937 !important; color: #9CA3AF !important; font-weight: 600 !important;
                text-transform: uppercase !important; font-size: 10px !important; letter-spacing: 0.5px !important;
                border-bottom: 1px solid #374151 !important; padding: 8px 12px !important;
            }}
            div[data-testid="stDataFrame"] td {{
                background: #111827 !important; color: #D1D5DB !important; border-bottom: 1px solid #1F2937 !important;
                padding: 8px 12px !important; font-size: 11px !important; font-variant-numeric: tabular-nums;
            }}
            div[data-testid="stDataFrame"] tr:hover td {{ background: #1F2937 !important; }}

            .app-footer {{
                margin-top: 24px; padding: 12px 20px; border-radius: 4px; background: #111827;
                border: 1px solid #1F2937; font-size: 11px; color: #6B7280; text-align: center;
            }}

            ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
            ::-webkit-scrollbar-track {{ background: #0B0D12; }}
            ::-webkit-scrollbar-thumb {{ background: #374151; border-radius: 3px; }}
        </style>""", unsafe_allow_html=True)

def render_header(dashboard: dict[str, Any] | None) -> None:
    now = dt.datetime.now()
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
            <div class="app-title">{APP_NAME}</div>
        </div>
        <div class="header-right">
            <div class="header-status"><span class="status-dot" style="background: {plant_color};"></span>{plant_text}</div>
            <div class="header-status"><span class="status-dot" style="background: {wb_color};"></span>{wb_text}</div>
            <div class="header-time">{now.strftime("%H:%M:%S")}</div>
        </div>
    </div>""", unsafe_allow_html=True)

def render_executive_summary(dashboard: dict[str, Any]) -> None:
    departments = dashboard.get("departments", {})
    
    cols = st.columns(7)
    
    for i, sys_name in enumerate(CRITICAL_SYSTEMS):
        if sys_name not in departments:
            continue
            
        dept_obj = departments[sys_name]
        config = DEPT_CONFIGS.get(sys_name, DEFAULT_CONFIG)
        rep_m = select_representative_meter(dept_obj)
        
        val = dept_obj.get("latest_values", {}).get(rep_m)
        unit = dept_obj.get("units", {}).get(rep_m, "")
        
        if isinstance(val, (int, float)):
            val_str = f"{val:,.0f}"
            status = "ONLINE"
            status_color = "#10B981"
        else:
            val_str = "N/A"
            status = "OFFLINE"
            status_color = "#EF4444"
            
        unit_str = str(unit).strip() if unit else ""
        
        with cols[i]:
            st.markdown(f"""
            <div class="exec-card active" style="--accent: {config['accent']};">
                <div class="exec-name">{sys_name}</div>
                <div class="exec-kpi-label">{config['primary_kpi']}</div>
                <div class="exec-value">{val_str}</div>
                <div class="exec-unit">{unit_str}</div>
                <div class="exec-status" style="color: {status_color};">{status}</div>
            </div>""", unsafe_allow_html=True)

def render_operations_overview(dashboard: dict[str, Any]) -> None:
    departments = dashboard.get("departments", {})
    
    rows = []
    for dept_name, dept_obj in departments.items():
        config = DEPT_CONFIGS.get(dept_name, DEFAULT_CONFIG)
        rep_m = select_representative_meter(dept_obj)
        
        total_val = dept_obj.get("total_values", {}).get(rep_m)
        avg_val = dept_obj.get("average_values", {}).get(rep_m)
        latest_val = dept_obj.get("latest_values", {}).get(rep_m)
        unit = dept_obj.get("units", {}).get(rep_m, "")
        
        total_str = f"{total_val:,.0f}" if isinstance(total_val, (int, float)) else "N/A"
        avg_str = f"{avg_val:,.1f}" if isinstance(avg_val, (int, float)) else "N/A"
        latest_str = f"{latest_val:,.0f}" if isinstance(latest_val, (int, float)) else "N/A"
        unit_str = str(unit).strip() if unit else ""
        
        is_online = latest_val is not None and isinstance(latest_val, (int, float))
        status = "● Online" if is_online else "○ Offline"
        status_color = "#10B981" if is_online else "#6B7280"
        
        rows.append({
            "Process": dept_name,
            "Category": config["label"],
            "Total": f"{total_str} {unit_str}".strip(),
            "Average": f"{avg_str} {unit_str}".strip(),
            "Latest": f"{latest_str} {unit_str}".strip(),
            "Status": f'<span style="color: {status_color};">{status}</span>'
        })
    
    if rows:
        df = pd.DataFrame(rows)
        st.markdown(f"""
        <table class="ops-table">
            <thead>
                <tr>
                    <th>Process</th>
                    <th>Category</th>
                    <th>Total</th>
                    <th>Average</th>
                    <th>Latest</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {''.join([f"<tr><td>{r['Process']}</td><td>{r['Category']}</td><td>{r['Total']}</td><td>{r['Average']}</td><td>{r['Latest']}</td><td>{r['Status']}</td></tr>" for r in rows])}
            </tbody>
        </table>""", unsafe_allow_html=True)

def render_process_selector(dashboard: dict[str, Any]) -> str | None:
    departments = dashboard.get("departments", {})
    
    if "selected_process" not in st.session_state:
        st.session_state["selected_process"] = None
        
    selected = st.session_state["selected_process"]
    
    st.markdown('<div class="process-selector">', unsafe_allow_html=True)
    
    cols = st.columns(4)
    col_idx = 0
    
    for dept_name in sorted(departments.keys()):
        dept_obj = departments[dept_name]
        config = DEPT_CONFIGS.get(dept_name, DEFAULT_CONFIG)
        rep_m = select_representative_meter(dept_obj)
        
        latest_val = dept_obj.get("latest_values", {}).get(rep_m)
        is_online = latest_val is not None and isinstance(latest_val, (int, float))
        status = "●" if is_online else "○"
        status_color = "#10B981" if is_online else "#6B7280"
        
        is_active = (dept_name == selected)
        
        with cols[col_idx % 4]:
            if st.button(
                f"{dept_name}\n\n{config['label']}\n\n{status} {status_color}",
                key=f"proc_{dept_name}",
                use_container_width=True,
                type="primary" if is_active else "secondary"
            ):
                st.session_state["selected_process"] = dept_name
                st.rerun()
        
        col_idx += 1
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    return st.session_state["selected_process"]

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

def render_workspace(dashboard: dict[str, Any], process_name: str) -> None:
    departments = dashboard.get("departments", {})
    dept_obj = departments.get(process_name, {})
    overview_df = dashboard.get("overview", pd.DataFrame())
    
    if not dept_obj:
        return
    
    config = DEPT_CONFIGS.get(process_name, DEFAULT_CONFIG)
    meters = dept_obj.get("meters", [])
    df_block = dept_obj.get("dataframe", pd.DataFrame())
    rep_m = select_representative_meter(dept_obj)
    
    st.markdown(f"""
    <div class="workspace" style="--accent: {config['accent']};">
        <div class="workspace-header">
            <h2 class="workspace-title">{process_name}</h2>
            <div class="workspace-label">{config['label']}</div>
        </div>
    </div>""", unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.markdown('<div class="chart-label">Primary Telemetry</div>', unsafe_allow_html=True)
        fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
        if fig:
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)
        
        if len(meters) > 1:
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            st.markdown('<div class="chart-label">Multi-Channel Analysis</div>', unsafe_allow_html=True)
            fig = chart_service.create_department_multi_line_chart(
                overview_dataframe=overview_df,
                section=dept_obj,
                title="Load Profiles"
            )
            if fig:
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.markdown('<div class="chart-label">Current Status</div>', unsafe_allow_html=True)
        if rep_m:
            latest_val = dept_obj.get("latest_values", {}).get(rep_m, 0.0) or 0.0
            unit_lbl = dept_obj.get("units", {}).get(rep_m, "")
            max_ceiling = get_gauge_max(df_block, rep_m, dept_obj)
            fig = chart_service.create_gauge_chart(latest_val, rep_m, maximum=max_ceiling, unit=unit_lbl)
            if fig:
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.markdown('<div class="chart-label">Channel Summary</div>', unsafe_allow_html=True)
        mini_records = []
        for m in meters[:min(len(meters), 5)]:
            v = dept_obj.get("latest_values", {}).get(m)
            u = dept_obj.get("units", {}).get(m, "N/A")
            mini_records.append({
                "Channel": m[:15],
                "Value": f"{v:,.2f}" if isinstance(v, (int, float)) else "Offline",
                "Unit": u if (u and str(u).strip()) else "N/A"
            })
        if mini_records:
            st.dataframe(pd.DataFrame(mini_records), use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
    st.markdown('<div class="chart-label">Channel Registry</div>', unsafe_allow_html=True)
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
        status_string = "Active" if l_v is not None else "Idle"
        ledger_records.append({
            "Channel": m,
            "Unit": lbl if (lbl and str(lbl).strip()) else "N/A",
            "Latest": round(l_v, 2) if isinstance(l_v, (int, float)) else "N/A",
            "Mean": round(a_v, 2) if isinstance(a_v, (int, float)) else "N/A",
            "Total": round(t_v, 2) if isinstance(t_v, (int, float)) else "N/A",
            "Status": status_string
        })
    if ledger_records:
        st.dataframe(pd.DataFrame(ledger_records), use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

def render_footer(dashboard: dict[str, Any] | None) -> None:
    last_refresh = st.session_state.get("last_refresh")
    refresh_text = last_refresh.strftime("%d %b %Y, %H:%M:%S") if last_refresh else "N/A"
    meta = (dashboard or {}).get("metadata", {})
    sheet_names = meta.get("sheet_names", ["Data Source Unlinked"])
    active_workbook = sheet_names[0] if sheet_names else "N/A"
    st.markdown(f"""<div class="app-footer">Workbook: {active_workbook} · Refreshed: {refresh_text} · v{APP_VERSION}</div>""", unsafe_allow_html=True)

def main() -> None:
    inject_global_styles()
    dashboard, error_msg = get_dashboard()
    
    render_header(dashboard)
    
    if error_msg is not None or dashboard is None:
        st.error(error_msg or "Critical Infrastructure Alert: Analytical context dictionary failed initialization.")
        render_footer(dashboard)
        return
    
    st.markdown('<div style="margin-bottom: 24px;">', unsafe_allow_html=True)
    st.markdown('<div style="font-size: 12px; font-weight: 600; color: #6B7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">Executive Summary</div>', unsafe_allow_html=True)
    render_executive_summary(dashboard)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div style="margin-bottom: 24px;">', unsafe_allow_html=True)
    st.markdown('<div style="font-size: 12px; font-weight: 600; color: #6B7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">Plant Operations Overview</div>', unsafe_allow_html=True)
    render_operations_overview(dashboard)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div style="margin-bottom: 24px;">', unsafe_allow_html=True)
    st.markdown('<div style="font-size: 12px; font-weight: 600; color: #6B7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">Process Selection</div>', unsafe_allow_html=True)
    selected_process = render_process_selector(dashboard)
    st.markdown('</div>', unsafe_allow_html=True)
    
    if selected_process:
        st.markdown('<div style="margin-bottom: 24px;">', unsafe_allow_html=True)
        st.markdown('<div style="font-size: 12px; font-weight: 600; color: #6B7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">Engineering Workspace</div>', unsafe_allow_html=True)
        render_workspace(dashboard, selected_process)
        st.markdown('</div>', unsafe_allow_html=True)
    
    render_footer(dashboard)

if __name__ == "__main__":
    main()
