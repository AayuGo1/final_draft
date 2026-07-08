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
from services.dashboard_loader import load_dashboard_safe
from dashboard_data import select_representative_meter

st.set_page_config(
    page_title=PAGE_CONFIG.get("page_title", APP_NAME),
    page_icon=PAGE_CONFIG.get("page_icon", "⚙️"),
    layout="wide",
    initial_sidebar_state="collapsed",
)

CRITICAL_SYSTEMS = [
    "NPCL", "DG", "GG", "Air compressor", "Traywasher", 
    "Freon Refrigeration", "Ammonia Refrigeration"
]

DEPT_CONFIGS = {
    "NPCL": {"accent": "#3B82F6", "category": "Incoming Power", "tagline": "Demand • PF • Energy"},
    "DG": {"accent": "#F59E0B", "category": "Diesel Generation", "tagline": "Fuel • Runtime • Load"},
    "GG": {"accent": "#EF4444", "category": "Gas Generation", "tagline": "Gas Flow • Output"},
    "Air compressor": {"accent": "#06B6D4", "category": "Pneumatics", "tagline": "Pressure • Flow • Runtime"},
    "Freon Refrigeration": {"accent": "#0EA5E9", "category": "Cooling Systems", "tagline": "Temperature • COP • Load"},
    "Ammonia Refrigeration": {"accent": "#10B981", "category": "Industrial Cooling", "tagline": "Pressure • Temp • Efficiency"},
    "Traywasher": {"accent": "#14B8A6", "category": "Sanitation", "tagline": "Water • Thermal • Cycles"},
    "Dough": {"accent": "#D97706", "category": "Processing", "tagline": "Batch • Temp • Energy"},
    "Bread": {"accent": "#F59E0B", "category": "Baking", "tagline": "Oven • Temp • Throughput"},
    "Donut": {"accent": "#FBBF24", "category": "Production", "tagline": "Fryer • Temp • Rate"},
    "CLC": {"accent": "#8B5CF6", "category": "Control", "tagline": "Logic • I/O • Status"},
    "Warehouse": {"accent": "#6366F1", "category": "Storage", "tagline": "HVAC • Lighting • Energy"},
    "Transport": {"accent": "#EC4899", "category": "Logistics", "tagline": "Fleet • Fuel • Distance"},
    "Engineering": {"accent": "#14B8A6", "category": "Engineering", "tagline": "Workshop • Tools • Power"},
    "Utility": {"accent": "#06B6D4", "category": "Utilities", "tagline": "Water • Air • Steam"},
}
DEFAULT_CONFIG = {"accent": "#8B5CF6", "category": "Engineering Systems", "tagline": "General Metrics"}


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
    st.markdown(
        f"""
        <style>
            #MainMenu {{visibility: hidden;}} 
            footer {{visibility: hidden;}} 
            header[data-testid="stHeader"] {{background: transparent;}}
            .stApp {{ background: #0B0D12 !important; }}
            .block-container {{ padding-top: 1rem; padding-bottom: 2rem; max-width: 1600px; }}

            /* Header */
            .app-header {{
                display: flex; justify-content: space-between; align-items: center;
                background: #111827; border: 1px solid #1F2937;
                padding: 10px 20px; margin-bottom: 16px; border-radius: 6px;
            }}
            .header-left {{ display: flex; align-items: center; gap: 12px; }}
            .app-logo {{
                width: 28px; height: 28px; background: #1E293B; border: 1px solid #334155;
                border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 14px;
            }}
            .app-title {{ font-size: 14px; font-weight: 700; color: #F9FAFB; letter-spacing: 0.5px; }}
            .header-right {{ display: flex; align-items: center; gap: 16px; }}
            .header-status {{
                display: flex; align-items: center; gap: 6px; font-size: 10px; font-weight: 600;
                color: #9CA3AF; text-transform: uppercase; letter-spacing: 0.5px;
            }}
            .status-dot {{ width: 6px; height: 6px; border-radius: 50%; }}
            .header-time {{ font-size: 10px; font-weight: 600; color: #6B7280; font-variant-numeric: tabular-nums; }}

            /* Section Titles */
            .section-title {{
                font-size: 11px; font-weight: 700; color: #6B7280; text-transform: uppercase; 
                letter-spacing: 1px; margin-bottom: 12px; margin-top: 24px;
                border-bottom: 1px solid #1F2937; padding-bottom: 6px;
            }}

            /* Executive Cards */
            .exec-grid {{ display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px; }}
            .exec-card {{
                background: #111827; border: 1px solid #1F2937; border-radius: 4px;
                padding: 10px 12px; min-height: 70px; display: flex; flex-direction: column; justify-content: space-between;
            }}
            .exec-name {{ font-size: 11px; font-weight: 700; color: #F9FAFB; margin-bottom: 2px; }}
            .exec-label {{ font-size: 9px; color: #6B7280; text-transform: uppercase; letter-spacing: 0.5px; }}
            .exec-value {{ font-size: 16px; font-weight: 700; color: #F9FAFB; font-variant-numeric: tabular-nums; margin: 4px 0; }}
            .exec-unit {{ font-size: 10px; color: #9CA3AF; font-weight: 500; }}
            .exec-status {{ font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }}
            .status-online {{ color: #10B981; }}
            .status-offline {{ color: #EF4444; }}

            /* Operations Table */
            .ops-table {{
                width: 100%; border-collapse: collapse; background: #111827; border-radius: 4px; overflow: hidden;
                border: 1px solid #1F2937;
            }}
            .ops-table th {{
                background: #1F2937; color: #9CA3AF; font-size: 10px; font-weight: 600;
                text-transform: uppercase; letter-spacing: 0.5px; padding: 8px 12px; text-align: left;
                border-bottom: 1px solid #374151;
            }}
            .ops-table td {{
                background: #111827; color: #D1D5DB; font-size: 11px; padding: 8px 12px;
                border-bottom: 1px solid #1F2937; font-variant-numeric: tabular-nums;
            }}
            .ops-table tr:hover td {{ background: #1F2937; }}
            .ops-table tr:nth-child(even) td {{ background: #0F172A; }}
            .ops-table tr:nth-child(even):hover td {{ background: #1F2937; }}

            /* Process Selector */
            .process-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px; }}
            .process-card {{
                background: #111827; border: 1px solid #1F2937; border-radius: 4px;
                padding: 12px; cursor: pointer; transition: all 0.2s;
                border-left: 3px solid var(--accent, #8B5CF6);
            }}
            .process-card:hover {{ background: #1F2937; border-color: #374151; }}
            .process-card.active {{ background: #1F2937; border-color: var(--accent, #8B5CF6); }}
            .process-name {{ font-size: 12px; font-weight: 700; color: #F9FAFB; margin-bottom: 2px; }}
            .process-category {{ font-size: 10px; color: #6B7280; margin-bottom: 4px; }}
            .process-tagline {{ font-size: 10px; color: #9CA3AF; font-style: italic; }}

            /* Workspace */
            .workspace {{
                background: #111827; border: 1px solid #1F2937; border-radius: 6px; padding: 16px;
                border-top: 3px solid var(--accent, #3B82F6);
            }}
            .workspace-header {{ margin-bottom: 16px; }}
            .workspace-title {{ font-size: 16px; font-weight: 700; color: #F9FAFB; margin: 0; }}
            .workspace-label {{ font-size: 10px; color: #6B7280; text-transform: uppercase; letter-spacing: 0.5px; }}
            
            .chart-box {{
                background: #0B0D12; border: 1px solid #1F2937; border-radius: 4px; padding: 12px; margin-bottom: 12px;
            }}
            .chart-label {{
                font-size: 10px; font-weight: 600; color: #6B7280; text-transform: uppercase;
                letter-spacing: 0.5px; margin-bottom: 8px;
            }}

            /* DataFrames */
            div[data-testid="stDataFrame"] {{
                border: 1px solid #1F2937 !important; border-radius: 4px !important; overflow: hidden !important;
            }}
            div[data-testid="stDataFrame"] th {{
                background: #1F2937 !important; color: #9CA3AF !important; font-weight: 600 !important;
                text-transform: uppercase !important; font-size: 10px !important; letter-spacing: 0.5px !important;
                border-bottom: 1px solid #374151 !important; padding: 6px 10px !important;
            }}
            div[data-testid="stDataFrame"] td {{
                background: #111827 !important; color: #D1D5DB !important; border-bottom: 1px solid #1F2937 !important;
                padding: 6px 10px !important; font-size: 11px !important; font-variant-numeric: tabular-nums;
            }}
            div[data-testid="stDataFrame"] tr:hover td {{ background: #1F2937 !important; }}

            /* Footer */
            .app-footer {{
                margin-top: 24px; padding: 10px 20px; border-radius: 4px; background: #111827;
                border: 1px solid #1F2937; font-size: 10px; color: #6B7280; text-align: center;
            }}

            ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
            ::-webkit-scrollbar-track {{ background: #0B0D12; }}
            ::-webkit-scrollbar-thumb {{ background: #374151; border-radius: 3px; }}
        </style>""",
        unsafe_allow_html=True,
    )


def render_header(dashboard: dict[str, Any] | None) -> None:
    now = dt.datetime.now()
    departments = (dashboard or {}).get("departments", {})
    plant_ok = bool(departments)
    plant_color = THEME_SUCCESS_COLOR if plant_ok else THEME_DANGER_COLOR
    plant_text = "ONLINE" if plant_ok else "OFFLINE"
    wb_color = THEME_SUCCESS_COLOR if dashboard else THEME_DANGER_COLOR
    wb_text = "CONNECTED" if dashboard else "DISCONNECTED"

    st.markdown(
        f"""
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
    </div>""",
        unsafe_allow_html=True,
    )


def render_executive_summary(dashboard: dict[str, Any]) -> None:
    departments = dashboard.get("departments", {})
    
    cards_html = ""
    for sys_name in CRITICAL_SYSTEMS:
        if sys_name not in departments:
            continue
            
        dept_obj = departments[sys_name]
        rep_m = select_representative_meter(dept_obj)
        
        total_val = dept_obj.get("total_values", {}).get(rep_m)
        unit = dept_obj.get("units", {}).get(rep_m, "")
        
        if isinstance(total_val, (int, float)):
            val_str = f"{total_val:,.0f}"
            status_class = "status-online"
            status_text = "ONLINE"
        else:
            val_str = "N/A"
            status_class = "status-offline"
            status_text = "OFFLINE"
            
        unit_str = str(unit).strip() if unit else ""
        
        cards_html += f"""
        <div class="exec-card">
            <div>
                <div class="exec-name">{sys_name}</div>
                <div class="exec-label">TOTAL</div>
            </div>
            <div class="exec-value">{val_str} <span class="exec-unit">{unit_str}</span></div>
            <div class="exec-status {status_class}">{status_text}</div>
        </div>"""

    if cards_html:
        st.markdown(f'<div class="exec-grid">{cards_html}</div>', unsafe_allow_html=True)


def render_operations_overview(dashboard: dict[str, Any]) -> None:
    departments = dashboard.get("departments", {})
    
    rows_html = ""
    for dept_name, dept_obj in departments.items():
        rep_m = select_representative_meter(dept_obj)
        
        total_val = dept_obj.get("total_values", {}).get(rep_m)
        avg_val = dept_obj.get("average_values", {}).get(rep_m)
        latest_val = dept_obj.get("latest_values", {}).get(rep_m)
        unit = dept_obj.get("units", {}).get(rep_m, "")
        
        total_str = f"{total_val:,.0f}" if isinstance(total_val, (int, float)) else "—"
        avg_str = f"{avg_val:,.1f}" if isinstance(avg_val, (int, float)) else "—"
        latest_str = f"{latest_val:,.0f}" if isinstance(latest_val, (int, float)) else "—"
        unit_str = str(unit).strip() if unit else ""
        
        is_online = latest_val is not None and isinstance(latest_val, (int, float))
        status_html = f'<span style="color: #10B981;">● Online</span>' if is_online else f'<span style="color: #6B7280;">○ Offline</span>'
        
        rows_html += f"""
        <tr>
            <td style="font-weight: 600; color: #F9FAFB;">{dept_name}</td>
            <td>{total_str} <span style="color:#6B7280; font-size:9px;">{unit_str}</span></td>
            <td>{avg_str} <span style="color:#6B7280; font-size:9px;">{unit_str}</span></td>
            <td>{latest_str} <span style="color:#6B7280; font-size:9px;">{unit_str}</span></td>
            <td>{status_html}</td>
        </tr>"""

    if rows_html:
        st.markdown(
            f"""
        <table class="ops-table">
            <thead>
                <tr>
                    <th>Process</th>
                    <th>Total</th>
                    <th>Average</th>
                    <th>Latest</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>""",
            unsafe_allow_html=True,
        )


def render_process_selector(dashboard: dict[str, Any]) -> str | None:
    departments = dashboard.get("departments", {})
    
    if "selected_process" not in st.session_state:
        st.session_state["selected_process"] = None
        
    selected = st.session_state["selected_process"]
    
    # We use a grid of buttons for interactivity, styled via CSS
    cols = st.columns(4)
    col_idx = 0
    
    for dept_name in sorted(departments.keys()):
        config = DEPT_CONFIGS.get(dept_name, DEFAULT_CONFIG)
        is_active = (dept_name == selected)
        
        label = f"**{dept_name}**\n\n*{config['category']}*\n\n{config['tagline']}"
        
        with cols[col_idx % 4]:
            if st.button(
                label, 
                key=f"proc_{dept_name}",
                use_container_width=True,
                type="primary" if is_active else "secondary"
            ):
                st.session_state["selected_process"] = dept_name
                st.rerun()
        
        col_idx += 1
        
    return st.session_state["selected_process"]


def get_gauge_max(df_block: pd.DataFrame, rep_m: str, dept_obj: dict[str, Any]) -> float:
    if rep_m and rep_m in df_block.columns:
        numeric_series = pd.to_numeric(df_block[rep_m], errors="coerce").dropna()
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

    st.markdown(
        f"""
    <div class="workspace" style="--accent: {config['accent']};">
        <div class="workspace-header">
            <h2 class="workspace-title">{process_name}</h2>
            <div class="workspace-label">{config['category']}</div>
        </div>
    </div>""",
        unsafe_allow_html=True,
    )

    # --- NPCL: Power & Energy ---
    if process_name == "NPCL":
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown('<div class="chart-box"><div class="chart-label">Energy Load Profile</div>', unsafe_allow_html=True)
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="chart-box"><div class="chart-label">Current Demand</div>', unsafe_allow_html=True)
            if rep_m:
                latest_val = dept_obj.get("latest_values", {}).get(rep_m, 0.0) or 0.0
                unit_lbl = dept_obj.get("units", {}).get(rep_m, "")
                max_ceiling = get_gauge_max(df_block, rep_m, dept_obj)
                fig = chart_service.create_gauge_chart(latest_val, "Load", maximum=max_ceiling, unit=unit_lbl)
                if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)

    # --- Air Compressor: Pneumatics ---
    elif process_name == "Air compressor":
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            st.markdown('<div class="chart-box"><div class="chart-label">System Pressure</div>', unsafe_allow_html=True)
            if rep_m:
                latest_val = dept_obj.get("latest_values", {}).get(rep_m, 0.0) or 0.0
                unit_lbl = dept_obj.get("units", {}).get(rep_m, "")
                max_ceiling = get_gauge_max(df_block, rep_m, dept_obj)
                fig = chart_service.create_gauge_chart(latest_val, "Pressure", maximum=max_ceiling, unit=unit_lbl)
                if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="chart-box"><div class="chart-label">Flow Trend</div>', unsafe_allow_html=True)
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)
        with col3:
            st.markdown('<div class="chart-box"><div class="chart-label">Runtime Distribution</div>', unsafe_allow_html=True)
            if len(meters) >= 2:
                vals = {m: dept_obj['total_values'].get(m, 0) or 0 for m in meters[:5]}
                bar_df = pd.DataFrame(list(vals.items()), columns=['Meter', 'Value'])
                fig = chart_service.create_horizontal_bar_chart(bar_df, 'Meter', 'Value', "Runtime")
                if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)

    # --- Freon: Cooling ---
    elif process_name == "Freon Refrigeration":
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown('<div class="chart-box"><div class="chart-label">Temperature Zones</div>', unsafe_allow_html=True)
            fig = chart_service.create_heatmap(df_block, meters[:min(len(meters), 8)], "Thermal Map")
            if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="chart-box"><div class="chart-label">Cooling Load Trend</div>', unsafe_allow_html=True)
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)

    # --- DG: Generation ---
    elif process_name == "DG":
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown('<div class="chart-box"><div class="chart-label">Generator Load</div>', unsafe_allow_html=True)
            if rep_m:
                latest_val = dept_obj.get("latest_values", {}).get(rep_m, 0.0) or 0.0
                unit_lbl = dept_obj.get("units", {}).get(rep_m, "%")
                fig = chart_service.create_gauge_chart(latest_val, "Load %", maximum=100, unit=unit_lbl)
                if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="chart-box"><div class="chart-label">Fuel & Generation</div>', unsafe_allow_html=True)
            vals = {m: dept_obj['total_values'].get(m, 0) or 0 for m in meters[:6]}
            bar_df = pd.DataFrame(list(vals.items()), columns=['Meter', 'Value'])
            fig = chart_service.create_bar_chart(bar_df, 'Meter', 'Value', "Consumption")
            if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)

    # --- Traywasher: Sanitation ---
    elif process_name == "Traywasher":
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown('<div class="chart-box"><div class="chart-label">Water Usage</div>', unsafe_allow_html=True)
            vals = {m: dept_obj['total_values'].get(m, 0) or 0 for m in meters[:5]}
            bar_df = pd.DataFrame(list(vals.items()), columns=['Meter', 'Value'])
            fig = chart_service.create_horizontal_bar_chart(bar_df, 'Meter', 'Value', "Consumption")
            if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="chart-box"><div class="chart-label">Consumption Trend</div>', unsafe_allow_html=True)
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)

    # --- Default Workspace ---
    else:
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown('<div class="chart-box"><div class="chart-label">Primary Telemetry</div>', unsafe_allow_html=True)
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)
            
            if len(meters) > 1:
                st.markdown('<div class="chart-box"><div class="chart-label">Multi-Channel Analysis</div>', unsafe_allow_html=True)
                fig = chart_service.create_department_multi_line_chart(
                    overview_dataframe=overview_df, section=dept_obj, title="Load Profiles"
                )
                if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="chart-box"><div class="chart-label">Current Status</div>', unsafe_allow_html=True)
            if rep_m:
                latest_val = dept_obj.get("latest_values", {}).get(rep_m, 0.0) or 0.0
                unit_lbl = dept_obj.get("units", {}).get(rep_m, "")
                max_ceiling = get_gauge_max(df_block, rep_m, dept_obj)
                fig = chart_service.create_gauge_chart(latest_val, rep_m, maximum=max_ceiling, unit=unit_lbl)
                if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)

    # --- Channel Registry (All Departments) ---
    st.markdown('<div class="chart-box"><div class="chart-label">Channel Registry</div>', unsafe_allow_html=True)
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
        ledger_records.append(
            {
                "Channel": m,
                "Unit": lbl if (lbl and str(lbl).strip()) else "N/A",
                "Latest": round(l_v, 2) if isinstance(l_v, (int, float)) else "N/A",
                "Mean": round(a_v, 2) if isinstance(a_v, (int, float)) else "N/A",
                "Total": round(t_v, 2) if isinstance(t_v, (int, float)) else "N/A",
                "Status": status_string,
            }
        )
    if ledger_records:
        st.dataframe(pd.DataFrame(ledger_records), use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)


def render_footer(dashboard: dict[str, Any] | None) -> None:
    last_refresh = st.session_state.get("last_refresh")
    refresh_text = last_refresh.strftime("%d %b %Y, %H:%M:%S") if last_refresh else "N/A"
    meta = (dashboard or {}).get("metadata", {})
    sheet_names = meta.get("sheet_names", ["Data Source Unlinked"])
    active_workbook = sheet_names[0] if sheet_names else "N/A"
    st.markdown(
        f"""<div class="app-footer">Workbook: {active_workbook} · Refreshed: {refresh_text} · v{APP_VERSION}</div>""",
        unsafe_allow_html=True,
    )


def main() -> None:
    inject_global_styles()
    dashboard, error_msg = get_dashboard()

    render_header(dashboard)

    if error_msg is not None or dashboard is None:
        st.error(error_msg or "Critical Infrastructure Alert: Analytical context dictionary failed initialization.")
        render_footer(dashboard)
        return

    st.markdown('<div class="section-title">Executive Summary</div>', unsafe_allow_html=True)
    render_executive_summary(dashboard)

    st.markdown('<div class="section-title">Plant Operations Overview</div>', unsafe_allow_html=True)
    render_operations_overview(dashboard)

    st.markdown('<div class="section-title">Process Selection</div>', unsafe_allow_html=True)
    selected_process = render_process_selector(dashboard)

    if selected_process:
        st.markdown('<div class="section-title">Engineering Workspace</div>', unsafe_allow_html=True)
        render_workspace(dashboard, selected_process)

    render_footer(dashboard)


if __name__ == "__main__":
    main()
