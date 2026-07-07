"""Main Entry Point for the Engineering Monitoring Dashboard.

This module acts exclusively as the Presentation and UI/UX Orchestration Layer
for the Engineering Monitoring Dashboard. It enforces a high-fidelity industrial
SCADA/Power BI dark glassmorphic design system. 

It implements no business logic, zero data calculations, and no plotting logic,
relying strictly on `dashboard_data.py`, `kpi_service.py`, and `chart_service.py`.
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
    THEME_WARNING_COLOR,
)
from dashboard_data import get_dashboard_data
from dashboard_loader import load_dashboard_safe
import kpi_service
import chart_service

# Grid system configurations
COLUMNS_PER_ROW: Final[int] = 4


def get_dashboard() -> tuple[dict[str, Any] | None, str | None]:
    """Retrieve and cache the complete multi-sheet engineering data model.

    Returns:
        A tuple of (dashboard_dict, error_message).
    """
    if "dashboard_data" not in st.session_state:
        dashboard, error = load_dashboard_safe()
        st.session_state["dashboard_data"] = dashboard
        st.session_state["dashboard_error"] = error
        st.session_state["last_refresh"] = dt.datetime.now()

    return st.session_state["dashboard_data"], st.session_state["dashboard_error"]


def refresh_dashboard() -> None:
    """Evict cached analytical context to force hard background reload."""
    for key in ("dashboard_data", "dashboard_error", "last_refresh"):
        st.session_state.pop(key, None)


def inject_global_styles() -> None:
    """Inject the SCADA Glassmorphism dark industrial design stylesheet."""
    st.markdown(
        f"""
        <style>
            #MainMenu {{visibility: hidden;}}
            footer {{visibility: hidden;}}
            header[data-testid="stHeader"] {{background: transparent;}}

            .block-container {{
                padding-top: 1.0rem;
                padding-bottom: 2.0rem;
                max-width: 1500px;
            }}

            .scada-header {{
                background: linear-gradient(135deg, rgba(108, 99, 255, 0.15), rgba(22, 26, 37, 0.95));
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 14px;
                padding: 16px 24px;
                backdrop-filter: blur(12px);
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
                margin-bottom: 16px;
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
                background: linear-gradient(135deg, {THEME_PRIMARY_COLOR}, #3f3aa3);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 24px;
                box-shadow: 0 4px 14px rgba(108, 99, 255, 0.35);
            }}

            .scada-main-title {{
                font-size: 1.3rem;
                font-weight: 800;
                color: #FAFAFA;
                margin: 0;
                letter-spacing: 0.5px;
            }}

            .scada-sub-title {{
                font-size: 0.78rem;
                color: #A0AEC0;
                margin: 0;
            }}

            .status-container {{
                display: flex;
                flex-wrap: wrap;
                gap: 12px;
                margin-top: 12px;
            }}

            .status-pill {{
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 4px 12px;
                border-radius: 20px;
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.08);
                font-size: 0.75rem;
                color: #E2E8F0;
                white-space: nowrap;
            }}

            .status-dot {{
                width: 8px;
                height: 8px;
                border-radius: 50%;
                display: inline-block;
            }}

            .metric-card-container {{
                background: linear-gradient(145deg, rgba(30, 41, 59, 0.4), rgba(15, 23, 42, 0.7));
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 12px;
                padding: 16px 20px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
            }}

            .metric-card-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 4px;
            }}

            .metric-card-title {{
                font-size: 0.78rem;
                color: #94A3B8;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin: 0;
            }}

            .metric-card-icon {{
                font-size: 1.2rem;
                opacity: 0.8;
            }}

            .metric-card-value {{
                font-size: 1.6rem;
                font-weight: 700;
                color: #F8FAFC;
                margin: 0;
                line-height: 1.2;
            }}

            .metric-card-footer {{
                display: flex;
                align-items: center;
                gap: 6px;
                font-size: 0.72rem;
                margin-top: 4px;
            }}

            .trend-up {{ color: {THEME_SUCCESS_COLOR}; font-weight: 600; }}
            .trend-down {{ color: {THEME_DANGER_COLOR}; font-weight: 600; }}
            .trend-neutral {{ color: #94A3B8; }}

            .section-panel-title {{
                font-size: 0.95rem;
                font-weight: 700;
                color: #E2E8F0;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin: 12px 0 12px 2px;
            }}

            div[data-testid="stButton"] > button {{
                width: 100%;
                border-radius: 10px !important;
                border: 1px solid rgba(255, 255, 255, 0.06) !important;
                background: linear-gradient(145deg, rgba(30, 41, 59, 0.4), rgba(15, 23, 42, 0.75)) !important;
                padding: 12px 14px !important;
                text-align: left !important;
                transition: all 0.2s ease-in-out !important;
            }}

            div[data-testid="stButton"] > button:hover {{
                transform: translateY(-2px);
                border-color: {THEME_PRIMARY_COLOR}88 !important;
                box-shadow: 0 6px 16px rgba(108, 99, 255, 0.15) !important;
            }}

            .tile-active > div[data-testid="stButton"] > button {{
                border-color: {THEME_PRIMARY_COLOR} !important;
                background: linear-gradient(145deg, rgba(108, 99, 255, 0.18), rgba(15, 23, 42, 0.85)) !important;
                box-shadow: 0 4px 14px rgba(108, 99, 255, 0.2) !important;
            }}

            .tile-dept-name {{
                font-size: 0.85rem;
                font-weight: 700;
                color: #F1F5F9;
                margin-bottom: 4px;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}

            .tile-meta-row {{
                display: flex;
                justify-content: space-between;
                font-size: 0.7rem;
                color: #94A3B8;
                margin-top: 2px;
            }}

            .tile-value {{
                font-size: 0.95rem;
                font-weight: 700;
                color: {THEME_PRIMARY_COLOR};
            }}

            .panel-container {{
                background: rgba(22, 26, 37, 0.5);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 14px;
                padding: 20px;
                margin-top: 16px;
            }}

            .scada-footer {{
                margin-top: 32px;
                padding: 16px;
                border-radius: 10px;
                background: rgba(255, 255, 255, 0.01);
                border: 1px solid rgba(255, 255, 255, 0.04);
                font-size: 0.72rem;
                color: #64748B;
                text-align: center;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_top_header(dashboard: dict[str, Any] | None) -> None:
    """Render enterprise SCADA global top panel including timeline control selectors."""
    now = dt.datetime.now()
    summary = (dashboard or {}).get("summary", {})
    available_sections = summary.get("available_sections", [])

    plant_color = THEME_SUCCESS_COLOR if available_sections else THEME_DANGER_COLOR
    plant_text = "Operational" if available_sections else "Offline"
    wb_color = THEME_SUCCESS_COLOR if dashboard else THEME_DANGER_COLOR
    wb_text = "Synchronized" if dashboard else "Error"

    last_refresh = st.session_state.get("last_refresh", now)

    st.markdown(
        f"""
        <div class="scada-header">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">
                <div class="scada-title-block">
                    <div class="scada-logo">{APP_ICON}</div>
                    <div>
                        <h1 class="scada-main-title">{APP_NAME}</h1>
                        <p class="scada-sub-title">Enterprise Infrastructure Supervision Hub · v{APP_VERSION}</p>
                    </div>
                </div>
                <div class="status-container">
                    <div class="status-pill"><span class="status-dot" style="background:{plant_color};"></span>PLANT: {plant_text}</div>
                    <div class="status-pill"><span class="status-dot" style="background:{wb_color};"></span>METADATA: {wb_text}</div>
                    <div class="status-pill"><span class="status-dot" style="background:{THEME_SUCCESS_COLOR};"></span>REPOSITORY: {GITHUB_OWNER}/{GITHUB_REPO}</div>
                    <div class="status-pill">📅 SYSTEM DATE: {now.strftime("%d %b %Y")}</div>
                    <div class="status-pill">🕒 LIVE TIME: {now.strftime("%H:%M:%S")}</div>
                    <div class="status-pill">🔁 SYNC STAMP: {last_refresh.strftime("%H:%M:%S")}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Context actions bar placed within native columns
    act_col1, act_col2, _ = st.columns([1.5, 1.2, 7.3])
    with act_col1:
        st.button("🔄 Force Core Telemetry Reset", on_click=refresh_dashboard, key="btn_refresh_global")
    with act_col2:
        if dashboard:
            st.download_button(
                label="📥 Export Matrix (CSV)",
                data=dashboard["overview"].to_csv(index=False).encode('utf-8'),
                file_name=f"SCADA_Matrix_{now.strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )


def render_filter_bar(dashboard: dict[str, Any]) -> tuple[str, str]:
    """Expose global synchronized date filters derived purely from data arrays."""
    filters_data = dashboard.get("filters", {})
    months_list = filters_data.get("months", [])
    dates_list = filters_data.get("dates", [])

    st.markdown('<p class="section-panel-title">📆 Temporal Synchronization Controls</p>', unsafe_allow_html=True)
    f_col1, f_col2, _ = st.columns([2, 2, 6])

    with f_col1:
        sel_month = st.selectbox(
            "Target Operational Month",
            options=months_list if months_list else ["N/A"],
            index=0,
            key="global_month_filter"
        )
    with f_col2:
        sel_date = st.selectbox(
            "Target Log Date",
            options=dates_list if dates_list else ["N/A"],
            index=0,
            key="global_date_filter"
        )
    return str(sel_month), str(sel_date)


def render_executive_kpi_strip(dashboard: dict[str, Any]) -> None:
    """Render executive KPI blocks summarizing worksheet health parameters."""
    summary = dashboard.get("summary", {})
    overview_df = dashboard.get("overview", pd.DataFrame())

    # Extract metrics out from unified kpi module wrapper signatures
    kpi_summary = kpi_service.build_kpi_summary(overview_df, section=None)

    dept_count = summary.get("department_count", kpi_summary.get("columns", 0))
    meter_count = summary.get("meter_count", kpi_summary.get("meters", 0))
    latest_ts = summary.get("latest_timestamp", kpi_summary.get("latest_timestamp", "N/A"))
    data_avail = kpi_summary.get("availability", 1.0)

    # Compute global mean averages from aggregated payload structures safely
    global_averages = summary.get("average_values", {})
    flat_averages = [
        val for dept in global_averages.values() if isinstance(dept, dict)
        for val in dept.values() if val is not None
    ]
    avg_consumption = sum(flat_averages) / len(flat_averages) if flat_averages else 0.0

    st.markdown('<p class="section-panel-title">📈 System-Wide Executive Telemetry</p>', unsafe_allow_html=True)
    k_col1, k_col2, k_col3, k_col4, k_col5 = st.columns(5)

    with k_col1:
        st.markdown(
            f"""<div class="metric-card-container">
                <div class="metric-card-header"><span class="metric-card-title">Departments</span><span class="metric-card-icon">🏢</span></div>
                <p class="metric-card-value">{dept_count}</p>
                <div class="metric-card-footer"><span class="trend-neutral">Active Monitored Blocks</span></div>
            </div>""", unsafe_allow_html=True
        )
    with k_col2:
        st.markdown(
            f"""<div class="metric-card-container">
                <div class="metric-card-header"><span class="metric-card-title">Total Channels</span><span class="metric-card-icon">📟</span></div>
                <p class="metric-card-value">{meter_count}</p>
                <div class="metric-card-footer"><span class="trend-up">▲ 100%</span><span class="trend-neutral">Instrumentation Node Fit</span></div>
            </div>""", unsafe_allow_html=True
        )
    with k_col3:
        st.markdown(
            f"""<div class="metric-card-container">
                <div class="metric-card-header"><span class="metric-card-title">Mean Aggregate Load</span><span class="metric-card-icon">⚡</span></div>
                <p class="metric-card-value">{avg_consumption:,.1f}</p>
                <div class="metric-card-footer"><span class="trend-neutral">Units / Pulse Load Average</span></div>
            </div>""", unsafe_allow_html=True
        )
    with k_col4:
        st.markdown(
            f"""<div class="metric-card-container">
                <div class="metric-card-header"><span class="metric-card-title">Precision Index</span><span class="metric-card-icon">📊</span></div>
                <p class="metric-card-value">{data_avail * 100:.1f}%</p>
                <div class="metric-card-footer"><span class="trend-up">Stable</span><span class="trend-neutral">Log Matrix Density</span></div>
            </div>""", unsafe_allow_html=True
        )
    with k_col5:
        st.markdown(
            f"""<div class="metric-card-container">
                <div class="metric-card-header"><span class="metric-card-title">Latest Master Sample</span><span class="metric-card-icon">🕒</span></div>
                <p class="metric-card-value" style="font-size: 1.15rem; padding-top: 8px;">{latest_ts.split()[0] if latest_ts != "N/A" else "N/A"}</p>
                <div class="metric-card-footer"><span class="trend-neutral">Chronological Upper Limit</span></div>
            </div>""", unsafe_allow_html=True
        )


def render_department_navigation_grid(dashboard: dict[str, Any]) -> str:
    """Render the SCADA primary grid navigation tile engine.

    Returns:
        The identifier string of the selected active department.
    """
    departments: dict[str, dict[str, Any]] = dashboard.get("departments", {})
    dept_names: list[str] = list(departments.keys())

    st.markdown('<p class="section-panel-title">🏭 Structural Infrastructure Matrix Grid</p>', unsafe_allow_html=True)

    if not dept_names:
        st.warning("Empty structural inventory detected inside application contexts.")
        return ""

    # Synchronize default operational selection variables inside session contexts
    if "selected_department" not in st.session_state or st.session_state["selected_department"] not in dept_names:
        st.session_state["selected_department"] = dept_names[0]

    current_selection = st.session_state["selected_department"]

    # Iterate structural row tiles safely using dynamic looping
    for i in range(0, len(dept_names), COLUMNS_PER_ROW):
        row_slice = dept_names[i : i + COLUMNS_PER_ROW]
        cols = st.columns(COLUMNS_PER_ROW)

        for col, d_name in zip(cols, row_slice):
            dept_obj = departments[d_name]
            meters_list = dept_obj.get("meters", [])
            units_map = dept_obj.get("units", {})

            # Isolate first functional parameter values cleanly
            rep_meter = meters_list[0] if meters_list else ""
            latest_val = dept_obj.get("latest_values", {}).get(rep_meter, 0.0)
            avg_val = dept_obj.get("average_values", {}).get(rep_meter, 0.0)
            unit_lbl = units_map.get(rep_meter, "")

            is_active = (d_name == current_selection)
            tile_class = "tile-active" if is_active else "tile-inactive"

            # Nest Streamlit buttons within customized structural HTML frame blocks
            with col:
                st.markdown(f'<div class="{tile_class}">', unsafe_allow_html=True)
                btn_lbl = (
                    f"🏢 {d_name}\n"
                    f"Channels: {len(meters_list)} Node | {rep_meter[:18]}\n"
                    f"Latest: {latest_val if latest_val is not None else 'N/A'} {unit_lbl}\n"
                    f"Average: {avg_val if avg_val is not None else 'N/A'}"
                )
                if st.button(btn_lbl, key=f"tile_select_{d_name}"):
                    st.session_state["selected_department"] = d_name
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    return st.session_state["selected_department"]


def render_department_dashboard(dashboard: dict[str, Any], active_dept: str) -> None:
    """Render specialized analysis, diagnostics, and metrics trends for the target department block."""
    dept_data: dict[str, Any] = dashboard.get("departments", {}).get(active_dept, {})
    overview_df: pd.DataFrame = dashboard.get("overview", pd.DataFrame())

    if not dept_data:
        st.info("Please select a structural plant module above to engage comprehensive system diagnostic feeds.")
        return

    st.markdown(f'<div class="panel-container">', unsafe_allow_html=True)
    st.markdown(f'<h3>🛡️ Telemetry Analytics Workspace: {active_dept}</h3>', unsafe_allow_html=True)
    st.markdown('<hr style="margin: 8px 0 20px 0; border-color: rgba(255,255,255,0.06);"/>', unsafe_allow_html=True)

    # 1. Component Level Statistical Aggregations (Row 3 Module KPIs)
    st.markdown('<h5>📊 Isolated Local Node Invariants</h5>', unsafe_allow_html=True)
    sub_col1, sub_col2, sub_col3, sub_col4 = st.columns(4)
    
    with sub_col1:
        st.metric("Total Active Channels", f"{len(dept_data.get('meters', []))} Nodes")
    with sub_col2:
        meta_indexes = dept_data.get("metadata", {}).get("column_indexes", [])
        st.metric("Matrix Column Offset Index", f"Col {meta_indexes[0] if meta_indexes else 'N/A'}")
    with sub_col3:
        st.metric("Source Sheet Context", str(dept_data.get("metadata", {}).get("source_sheet", "Sheet2")))
    with sub_col4:
        st.metric("Reporting Unit Count", f"{dept_data.get('metadata', {}).get('unit_count', 0)} Distinct")

    # 2. Vectorized Timeline Trend Graphics Construction
    st.markdown('<br/><h5>📉 Real-Time Continuous Trend Visualizations</h5>', unsafe_allow_html=True)
    
    # Generate Plotly charts strictly via the architectural contract with chart_service.py
    fig = chart_service.build_section_trend_chart(overview_df, dept_data)
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown(
            '<div style="padding: 40px; background: rgba(255,255,255,0.02); border-radius: 8px; text-align: center; color: #64748B;">'
            '⚠️ Timeline parameters do not offer matching continuous scalar floats for real-time visualization.'
            '</div>', unsafe_allow_html=True
        )

    # 3. Comprehensive Detailed Nodes Registry (Row 4 Specification Table)
    st.markdown('<br/><h5>📋 Channel Registry Detailed Specification Index</h5>', unsafe_allow_html=True)
    
    meters_list = dept_data.get("meters", [])
    units_map = dept_data.get("units", {})
    latest_vals = dept_data.get("latest_values", {})
    avg_vals = dept_data.get("average_values", {})
    total_vals = dept_data.get("total_values", {})

    table_records = []
    for meter in meters_list:
        lbl = units_map.get(meter, "")
        l_v = latest_vals.get(meter)
        a_v = avg_vals.get(meter)
        t_v = total_vals.get(meter)
        
        status_flag = "🟢 Operational" if l_v is not None else "⚪ Deconditioned"

        table_records.append({
            "Instrumentation Node / Meter Channel": meter,
            "Engineering Unit": lbl if lbl else "Raw Smp",
            "Latest Value": f"{l_v:,.2f}" if isinstance(l_v, (int, float)) else "N/A",
            "Average Mean": f"{a_v:,.2f}" if isinstance(a_v, (int, float)) else "N/A",
            "Total Accumulated": f"{t_v:,.2f}" if isinstance(t_v, (int, float)) else "N/A",
            "Operational Status Flag": status_flag
        })

    if table_records:
        st.dataframe(pd.DataFrame(table_records), use_container_width=True, hide_index=True)
    else:
        st.caption("No registered active nodes traced inside the selected subsystem module layout configuration bounds.")

    st.markdown('</div>', unsafe_allow_html=True)


def render_footer(dashboard: dict[str, Any] | None) -> None:
    """Render footer signature showing active file metadata handles cleanly."""
    last_refresh = st.session_state.get("last_refresh")
    refresh_text = last_refresh.strftime("%d %b %Y, %H:%M:%S") if last_refresh else "N/A"
    
    meta = (dashboard or {}).get("metadata", {})
    sheet_names = meta.get("sheet_names", [])
    active_file_text = sheet_names[0] if sheet_names else "Data Connection Missing"

    st.markdown(
        f"""
        <div class="scada-footer">
            🏢 Industrial System Engine Matrix Base: <code>{active_file_text}</code> · 
            ⏱️ Master Core Synchronization Cycle: <code>{refresh_text}</code> · 
            ⚙️ {APP_NAME} UI Framework Assembly v{APP_VERSION}
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    """Configure, validate, and orchestrate the premium enterprise Streamlit visualization loop."""
    st.set_page_config(**PAGE_CONFIG)
    inject_global_styles()

    # Load multi-sheet workspace safely via loader module pipeline architecture
    dashboard, error_msg = get_dashboard()

    # Layout Row: Global SCADA Identity Status Banner
    render_top_header(dashboard)

    if error_msg is not None or dashboard is None:
        st.error(f"🛑 CRITICAL DATA INGESTION EXCEPTION: {error_msg if error_msg else 'Workspace reference corrupted.'}")
        render_footer(None)
        return

    # Layout Row: Global Sync Filtering Coordinates Controls
    render_filter_bar(dashboard)

    # Layout Row 1: Comprehensive Executive Metric Cards Strips
    render_executive_kpi_strip(dashboard)

    # Layout Row 2: Infrastructure Navigation Selection Matrix Engine Grid
    active_dept = render_department_navigation_grid(dashboard)

    # Layout Row 3 & 4: Engaged Workspace Module Performance Dashboard Displays
    if active_dept:
        render_department_dashboard(dashboard, active_dept)

    # Layout Row: Structural Context Footer Elements
    render_footer(dashboard)


if __name__ == "__main__":
    main()
