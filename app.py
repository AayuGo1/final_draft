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
    """Render specialized structural matrix navigation system grids."""
    departments: dict[str, dict[str, Any]] = dashboard.get("departments", {})
    dept_names = list(departments.keys())

    st.markdown('<p class="section-panel-title">🏭 Infrastructure Component Subsystems Matrix</p>', unsafe_allow_html=True)

    if not dept_names:
        return ""

    if "selected_department" not in st.session_state or st.session_state["selected_department"] not in dept_names:
        st.session_state["selected_department"] = dept_names[0]

    current_selection = st.session_state["selected_department"]
    total_depts = len(dept_names)

    for i in range(0, total_depts, GRID_COLUMNS):
        row_slice = dept_names[i : i + GRID_COLUMNS]
        cols = st.columns(len(row_slice)) if len(row_slice) < GRID_COLUMNS else st.columns(GRID_COLUMNS)

        for col, d_name in zip(cols, row_slice):
            dept_obj = departments[d_name]
            meters = dept_obj.get("meters", [])
            
            rep_m = _get_representative_meter(dept_obj)
            l_v = dept_obj.get("latest_values", {}).get(rep_m) if rep_m else None
            u_lbl = dept_obj.get("units", {}).get(rep_m, "") if rep_m else ""
            avg_m = dept_obj.get("average_values", {}).get(rep_m, 0.0) if rep_m else 0.0
            
            is_active = (d_name == current_selection)
            active_class = "tile-active" if is_active else "tile-inactive"

            val_display = f"{l_v:,.1f} {u_lbl}" if isinstance(l_v, (int, float)) else "N/A"
            avg_display = f"{avg_m:,.1f}" if isinstance(avg_m, (int, float)) else "N/A"

            with col:
                st.markdown(f'<div class="{active_class}">', unsafe_allow_html=True)
                btn_txt = (
                    f"🔷 {d_name}\n"
                    f"Data Available | Nodes: {len(meters)}\n"
                    f"Latest: {val_display} | Avg: {avg_display}"
                )
                if st.button(btn_txt, key=f"nav_tile_{d_name}"):
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
    st.markdown(f"<h3>🛡️ Engineering Supervisory System Diagnostics &mdash; {active_dept}</h3>", unsafe_allow_html=True)
    st.markdown('<hr style="margin: 4px 0 16px 0; border-color: rgba(255,255,255,0.05);"/>', unsafe_allow_html=True)

    meters = dept_obj.get("meters", [])
    df_block = dept_obj.get("dataframe", pd.DataFrame())
    rep_m = _get_representative_meter(dept_obj)

    chart_col1, chart_col2 = st.columns([6, 4])
    
    with chart_col1:
        st.markdown("##### 📉 Continuous Timeline Telemetry Profile")
        fig_primary = chart_service.build_section_trend_chart(overview_df, dept_obj)
        if fig_primary:
            st.plotly_chart(fig_primary, use_container_width=True)
        else:
            st.caption("Primary chronological metric profile logs absent or structurally misaligned.")

        if len(meters) > 1:
            st.markdown("<br/>##### 📊 Multi-Variable Process Cross-Channel Analysis", unsafe_allow_html=True)
            date_cols = get_date_columns(overview_df)
            if date_cols and overview_df.shape[0] > 3:
                dates_axis = overview_df.iloc[3:, date_cols[0]].reset_index(drop=True)
                plot_df = df_block.copy().reset_index(drop=True)
                plot_df["DateAxis"] = dates_axis[:len(plot_df)]
                x_col_name = "DateAxis"
            else:
                plot_df = df_block.reset_index()
                x_col_name = "index"

            fig_compare = chart_service.create_department_multi_line_chart(
                overview_dataframe=overview_df,
                section=dept_obj,
                title="Parallel Operations Diagnostic Load Profiles",
            )
            
            if fig_compare:
                st.plotly_chart(fig_compare, use_container_width=True)

    with chart_col2:
        st.markdown("##### 🧭 Node Dynamic Scale Instrumentation Gauge")
        if rep_m:
            latest_val = dept_obj.get("latest_values", {}).get(rep_m, 0.0)
            avg_val = dept_obj.get("average_values", {}).get(rep_m, 100.0)
            total_val = dept_obj.get("total_values", {}).get(rep_m, 500.0)
            unit_lbl = dept_obj.get("units", {}).get(rep_m, "")
            
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
                st.caption("Gauge visualization failed.")
        
        st.markdown("<br/>##### 📑 Node Current Process Vector Snapshots", unsafe_allow_html=True)
        mini_records = []
        for m in meters[:min(len(meters), 6)]:
            v = dept_obj.get("latest_values", {}).get(m)
            u = dept_obj.get("units", {}).get(m, "N/A")
            mini_records.append({
                "Channel ID": m[:20],
                "Log Readout": f"{v:,.2f}" if isinstance(v, (int, float)) else "Offline",
                "Unit": u if (u and str(u).strip()) else "N/A"
            })
        if mini_records:
            st.dataframe(pd.DataFrame(mini_records), use_container_width=True, hide_index=True)

    st.markdown("<br/>##### 📋 Instrumentation Node Channel Registry Detailed Log Ledger", unsafe_allow_html=True)
    
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
            "Operational Status Flag": status_string
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

    render_executive_kpi_strip(dashboard)
    selected_dept = render_department_grid(dashboard)
    
    if selected_dept:
        render_subsystem_workspace(dashboard, selected_dept)
        
    render_footer(dashboard)


if __name__ == "__main__":
    main()
