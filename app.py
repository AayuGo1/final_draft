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
    PAGE_CONFIG,
    THEME_DANGER_COLOR,
    THEME_PRIMARY_COLOR,
    THEME_SUCCESS_COLOR,
    THEME_WARNING_COLOR,
)
import services.chart_service as chart_service
import services.kpi_service as kpi_service

# Layout constants
GRID_COLUMNS: Final[int] = 4


def get_dashboard() -> tuple[dict[str, Any] | None, str | None]:
    """Retrieve the cached dashboard session payload framework context safely.

    Returns:
        A tuple of (dashboard_dict, error_message).
    """
    return st.session_state.get("dashboard_data"), st.session_state.get("dashboard_error")


def refresh_dashboard() -> None:
    """Evict structural context references from active session state layers."""
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
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_top_header(dashboard: dict[str, Any] | None) -> tuple[str, str]:
    """Render the simplified global system supervision header and time controls.

    Returns:
        A tuple of strings representing selected (month, date).
    """
    now = dt.datetime.now()
    summary = (dashboard or {}).get("summary", {})
    filters_data = (dashboard or {}).get("filters", {})
    
    plant_ok = bool(summary.get("available_sections", []))
    plant_color = THEME_SUCCESS_COLOR if plant_ok else THEME_DANGER_COLOR
    plant_text = "ONLINE" if plant_ok else "NO SIGNAL"
    
    last_refresh = st.session_state.get("last_refresh", now)

    st.markdown(
        f"""
        <div class="scada-header">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                <div class="scada-title-block">
                    <div class="scada-logo">{APP_ICON}</div>
                    <div>
                        <h1 class="scada-main-title">{APP_NAME}</h1>
                        <div style="display: flex; gap: 8px; margin-top: 2px;">
                            <div class="status-pill"><span class="status-dot" style="background:{plant_color};"></span>PLANT: {plant_text}</div>
                            <div class="status-pill">📅 {now.strftime("%d %b %Y")}</div>
                            <div class="status-pill">🕒 {now.strftime("%H:%M:%S")}</div>
                            <div class="status-pill">🔁 SYNC: {last_refresh.strftime("%H:%M:%S")}</div>
                        </div>
                    </div>
                </div>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <div class="status-pill">☁️ SOURCE: OK</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    h_col1, h_col2, h_col3 = st.columns([2.5, 2.5, 5])
    with h_col1:
        selected_month = st.selectbox(
            "Filter Month",
            options=filters_data.get("months", ["N/A"]),
            index=0,
            key="header_month_select"
        )
    with h_col2:
        selected_date = st.selectbox(
            "Filter Date",
            options=filters_data.get("dates", ["N/A"]),
            index=0,
            key="header_date_select"
        )
    with h_col3:
        st.markdown("<div style='padding-top: 24px;'></div>", unsafe_allow_html=True)
        if st.button("🔄 Sync Live Ingestion Buffer", key="btn_manual_header_sync"):
            refresh_dashboard()
            st.rerun()

    return str(selected_month), str(selected_date)


def render_executive_kpi_strip(dashboard: dict[str, Any]) -> None:
    """Compile and render industrial engineering KPIs cleanly across nodes."""
    summary = dashboard.get("summary", {})
    departments = dashboard.get("departments", {})

    # Compute explicit analytical aggregates from matching metric channels
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
    
    latest_ts = summary.get("latest_timestamp", "N/A")
    meter_count = summary.get("meter_count", 0)

    st.markdown('<p class="section-panel-title">📊 Enterprise SCADA Operational Aggregates</p>', unsafe_allow_html=True)
    k_col1, k_col2, k_col3, k_col4, k_col5, k_col6 = st.columns(6)

    with k_col1:
        st.markdown(
            f"""<div class="metric-card-container">
                <p class="metric-card-title">Total Load</p>
                <p class="metric-card-value">{total_consumption:,.1f}</p>
                <div class="metric-card-footer">Sum Active Channels</div>
            </div>""", unsafe_allow_html=True
        )
    with k_col2:
        st.markdown(
            f"""<div class="metric-card-container">
                <p class="metric-card-title">Mean Base Load</p>
                <p class="metric-card-value">{global_average:,.1f}</p>
                <div class="metric-card-footer">Channel Array Average</div>
            </div>""", unsafe_allow_html=True
        )
    with k_col3:
        st.markdown(
            f"""<div class="metric-card-container">
                <p class="metric-card-title">Blocks Online</p>
                <p class="metric-card-value">{active_depts_count}</p>
                <div class="metric-card-footer">Depts Reporting Data</div>
            </div>""", unsafe_allow_html=True
        )
    with k_col4:
        st.markdown(
            f"""<div class="metric-card-container">
                <p class="metric-card-title">Nodes Online</p>
                <p class="metric-card-value">{total_reporting_meters} / {meter_count}</p>
                <div class="metric-card-footer">Active Feeds Tracking</div>
            </div>""", unsafe_allow_html=True
        )
    with k_col5:
        st.markdown(
            f"""<div class="metric-card-container">
                <p class="metric-card-title">Ingest Window</p>
                <p class="metric-card-value" style="font-size: 1.1rem; padding-top: 5px; font-weight:700;">{latest_ts.split()[0] if latest_ts != "N/A" else "N/A"}</p>
                <div class="metric-card-footer">Matrix Max Limit</div>
            </div>""", unsafe_allow_html=True
        )
    with k_col6:
        availability = kpi_service.calculate_data_availability(dashboard.get("overview", pd.DataFrame()))
        st.markdown(
            f"""<div class="metric-card-container">
                <p class="metric-card-title">Matrix Density</p>
                <p class="metric-card-value">{availability * 100:.1f}%</p>
                <div class="metric-card-footer">Data Cell Population</div>
            </div>""", unsafe_allow_html=True
        )


def render_department_grid(dashboard: dict[str, Any]) -> str:
    """Render secondary responsive system component button array metrics.

    Returns:
        The string name index of the user selected department workspace.
    """
    departments: dict[str, dict[str, Any]] = dashboard.get("departments", {})
    dept_names = list(departments.keys())

    st.markdown('<p class="section-panel-title">🏭 Infrastructure Component Subsystems Matrix</p>', unsafe_allow_html=True)

    if not dept_names:
        st.info("No architectural components resolved.")
        return ""

    if "selected_department" not in st.session_state or st.session_state["selected_department"] not in dept_names:
        st.session_state["selected_department"] = dept_names[0]

    current_selection = st.session_state["selected_department"]

    for i in range(0, len(dept_names), GRID_COLUMNS):
        row_slice = dept_names[i : i + GRID_COLUMNS]
        cols = st.columns(GRID_COLUMNS)

        for col, d_name in zip(cols, row_slice):
            dept_obj = departments[d_name]
            meters = dept_obj.get("meters", [])
            rep_m = meters[0] if meters else ""
            
            l_v = dept_obj.get("latest_values", {}).get(rep_m)
            u_lbl = dept_obj.get("units", {}).get(rep_m, "")
            
            is_active = (d_name == current_selection)
            active_class = "tile-active" if is_active else "tile-inactive"

            health_dot = "🟢" if l_v is not None else "⚪"
            val_display = f"{l_v:,.1f} {u_lbl}" if isinstance(l_v, (int, float)) else "Offline"

            with col:
                st.markdown(f'<div class="{active_class}">', unsafe_allow_html=True)
                btn_txt = (
                    f"{health_dot} {d_name}\n"
                    f"Nodes: {len(meters)} | Primary: {rep_m[:14]}...\n"
                    f"Value: {val_display}"
                )
                if st.button(btn_txt, key=f"nav_tile_{d_name}"):
                    st.session_state["selected_department"] = d_name
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    return st.session_state["selected_department"]


def render_subsystem_workspace(dashboard: dict[str, Any], active_dept: str) -> None:
    """Render detailed interactive operational trend lines and telemetry channels."""
    dept_obj: dict[str, Any] = dashboard.get("departments", {}).get(active_dept, {})
    overview_df: pd.DataFrame = dashboard.get("overview", pd.DataFrame())

    if not dept_obj:
        return

    st.markdown(f'<div class="panel-container">', unsafe_allow_html=True)
    st.markdown(f"<h3>🛡️ Operational Diagnostic Workspace &mdash; {active_dept}</h3>", unsafe_allow_html=True)
    st.markdown('<hr style="margin: 4px 0 16px 0; border-color: rgba(255,255,255,0.05);"/>', unsafe_allow_html=True)

    # Isolated analytical blocks mapping equipment layout footprints
    is_special_utility = any(k in active_dept.lower() for k in ("compressor", "freon", "ammonia"))
    meters = dept_obj.get("meters", [])
    df_block = dept_obj.get("dataframe", pd.DataFrame())

    # Row A: Graphic Visualizations Layout Blocks
    chart_col1, chart_col2 = st.columns([6, 4])
    
    with chart_col1:
        st.markdown("##### 📉 Continuous Timeline Telemetry Profile")
        fig_primary = chart_service.build_section_trend_chart(overview_df, dept_obj)
        if fig_primary:
            st.plotly_chart(fig_primary, use_container_width=True)
        else:
            st.caption("Primary chronological metric profile logs absent or structurally misaligned.")

    with chart_col2:
        st.markdown("##### 📊 Subsystem Diagnostics & Distribution")
        if is_special_utility and len(meters) > 1:
            # Map a multi-channel aggregate load visualization across parameters
            fig_compare = chart_service.create_multi_line_chart(
                df_block.reset_index(),
                x_column="index",
                y_columns=meters[:3],
                title="Cross-Channel Comparative Load Matrix"
            )
            if fig_compare:
                st.plotly_chart(fig_compare, use_container_width=True)
            else:
                st.caption("Distribution comparisons unrenderable.")
        else:
            # Drop a standard volumetric distribution wheel for standard structures
            rep_m = meters[0] if meters else ""
            latest_val = dept_obj.get("latest_values", {}).get(rep_m, 0.0)
            avg_val = dept_obj.get("average_values", {}).get(rep_m, 100.0)
            
            fig_gauge = chart_service.create_gauge_chart(
                value=float(latest_val) if isinstance(latest_val, (int, float)) else 0.0,
                title=f"Node Scale: {rep_m[:15]}",
                maximum=float(avg_val * 2.0) if isinstance(avg_val, (int, float)) and avg_val > 0 else 100.0,
                unit=str(dept_obj.get("units", {}).get(rep_m, ""))
            )
            if fig_gauge:
                st.plotly_chart(fig_gauge, use_container_width=True)
            else:
                st.caption("Diagnostic indicator gauge unrenderable.")

    # Row B: Grid System Tabular Metric Index Specifications
    st.markdown("<br/>##### 📋 Instrumentation Node Channels Specification Log Index", unsafe_allow_html=True)
    
    units_map = dept_obj.get("units", {})
    latest_vals = dept_obj.get("latest_values", {})
    avg_vals = dept_obj.get("average_values", {})
    total_vals = dept_obj.get("total_values", {})

    records = []
    for m in meters:
        lbl = units_map.get(m, "Smp")
        l_v = latest_vals.get(m)
        a_v = avg_vals.get(m)
        t_v = total_vals.get(m)
        
        status = "🟢 Operational" if l_v is not None else "⚪ Idle / Deconditioned"

        records.append({
            "Instrumentation Node / Meter Channel": m,
            "Engineering Unit": lbl,
            "Latest Value Check": round(l_v, 2) if isinstance(l_v, (int, float)) else "N/A",
            "Mean Running Load": round(a_v, 2) if isinstance(a_v, (int, float)) else "N/A",
            "Accumulated Quantity Sum": round(t_v, 2) if isinstance(t_v, (int, float)) else "N/A",
            "Operational Flag Status": status
        })

    if records:
        st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)
    else:
        st.caption("No registered diagnostic records populated within target column boundary structures.")

    st.markdown("</div>", unsafe_allow_html=True)


def render_footer(dashboard: dict[str, Any] | None) -> None:
    """Render the standardized minimal presentation bottom block."""
    last_refresh = st.session_state.get("last_refresh")
    refresh_text = last_refresh.strftime("%d %b %Y, %H:%M:%S") if last_refresh else "N/A"
    
    meta = (dashboard or {}).get("metadata", {})
    active_sheet = meta.get("sheet_names", ["Data Source Unlinked"])[0]

    st.markdown(
        f"""
        <div class="scada-footer">
            System Operations Cluster Base: <code>{active_sheet}</code> · 
            Master Cycle Clock: <code>{refresh_text}</code> · 
            {APP_NAME} Supervision Suite Framework v{APP_VERSION}
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    """Orchestrate presentation layouts and handle context loading loops safely."""
    inject_global_styles()

    # Load shared Analytical Context dictionary mappings via pipeline loaders
    if "dashboard_data" not in st.session_state:
        dashboard, error_msg = load_dashboard_safe()
        st.session_state["dashboard_data"] = dashboard
        st.session_state["dashboard_error"] = error_msg
        st.session_state["last_refresh"] = dt.datetime.now()

    dashboard, error_msg = get_dashboard()

    # Render SCADA Top Identity Navigation Header Banner
    render_top_header(dashboard)

    if error_msg is not None or dashboard is None:
        st.error(f"⚠️ CRITICAL SYSTEM ACCESS VIOLATION: {error_msg if error_msg else 'Ingestion context fault.'}")
        render_footer(None)
        return

    # Render Analytical Executive KPI Block Strips
    render_executive_kpi_strip(dashboard)

    # Render Subsystem Navigation Grid Component Channels Selection Blocks
    active_dept = render_department_grid(dashboard)

    # Engage Specialized Active Workspaces Displays
    if active_dept:
        render_subsystem_workspace(dashboard, active_dept)

    # Append Minimal Footer Specifications
    render_footer(dashboard)


if __name__ == "__main__":
    # Standard configuration arguments passed directly to st.set_page_config
    st.set_page_config(
        page_title=PAGE_CONFIG.get("page_title", APP_NAME),
        page_icon=PAGE_CONFIG.get("page_icon", "⚙️"),
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    main()
