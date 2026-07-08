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
    "Freon Refrigeration", "Ammonia Refrigeration",
]

# accent = tile/border color, category = equipment class label
DEPT_CONFIGS = {
    "NPCL": {"accent": "#3B82F6", "category": "Electrical / Incoming Power"},
    "DG": {"accent": "#F59E0B", "category": "Fuel / Diesel Generation"},
    "GG": {"accent": "#EF4444", "category": "Fuel / Gas Generation"},
    "Air compressor": {"accent": "#06B6D4", "category": "Compressed Air"},
    "Freon Refrigeration": {"accent": "#8B5CF6", "category": "Cooling System"},
    "Ammonia Refrigeration": {"accent": "#8B5CF6", "category": "Cooling System"},
    "Traywasher": {"accent": "#10B981", "category": "Sanitation / Water"},
    "Dough": {"accent": "#F59E0B", "category": "Processing"},
    "Bread": {"accent": "#F59E0B", "category": "Baking"},
    "Donut": {"accent": "#F59E0B", "category": "Production"},
    "CLC": {"accent": "#3B82F6", "category": "Control Logic"},
    "Warehouse": {"accent": "#3B82F6", "category": "Storage / Utility"},
    "Transport": {"accent": "#06B6D4", "category": "Logistics"},
    "Engineering": {"accent": "#10B981", "category": "Workshop"},
    "Utility": {"accent": "#06B6D4", "category": "Utilities"},
}
DEFAULT_CONFIG = {"accent": "#8B5CF6", "category": "Engineering System"}


# ==================================================================
# Data access (untouched logic, only cached in session_state)
# ==================================================================

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


# ==================================================================
# Styles — industrial SCADA theme, 8px grid
# ==================================================================

def inject_global_styles() -> None:
    st.markdown(
        f"""
        <style>
            #MainMenu {{visibility: hidden;}}
            footer {{visibility: hidden;}}
            header[data-testid="stHeader"] {{background: transparent;}}
            .stApp {{ background: #0A0C10 !important; }}
            .block-container {{ padding-top: 8px; padding-bottom: 16px; max-width: 1680px; }}

            * {{ box-sizing: border-box; }}

            /* ---------- Header ---------- */
            .scada-header {{
                display: flex; justify-content: space-between; align-items: center;
                background: #10131A; border: 1px solid #1C212B;
                padding: 6px 12px; margin-bottom: 6px; border-radius: 2px;
            }}
            .header-left {{ display: flex; align-items: center; gap: 10px; }}
            .app-logo {{
                width: 24px; height: 24px; background: #171B24; border: 1px solid #2A3140;
                border-radius: 2px; display: flex; align-items: center; justify-content: center; font-size: 12px;
            }}
            .app-title {{ font-size: 13px; font-weight: 700; color: #E5E9F0; letter-spacing: 0.6px; text-transform: uppercase; }}
            .app-version {{ font-size: 9px; color: #4B5563; font-weight: 600; margin-left: 4px; }}

            .header-status-group {{ display: flex; align-items: center; gap: 0; border-left: 1px solid #1C212B; }}
            .header-stat {{
                display: flex; flex-direction: column; align-items: flex-start; gap: 1px;
                padding: 0 12px; border-right: 1px solid #1C212B;
            }}
            .header-stat:last-child {{ border-right: none; }}
            .header-stat-label {{ font-size: 8px; font-weight: 700; color: #4B5563; text-transform: uppercase; letter-spacing: 0.8px; }}
            .header-stat-value {{ display: flex; align-items: center; gap: 5px; font-size: 11px; font-weight: 600; color: #D1D5DB; font-variant-numeric: tabular-nums; }}
            .status-dot {{ width: 6px; height: 6px; border-radius: 1px; flex-shrink: 0; }}

            /* ---------- Section headers ---------- */
            .section-title {{
                font-size: 10px; font-weight: 700; color: #4B5563; text-transform: uppercase;
                letter-spacing: 1.2px; margin-bottom: 8px; margin-top: 16px;
                display: flex; align-items: center; gap: 8px;
            }}
            .section-title::after {{ content: ""; flex: 1; height: 1px; background: #1C212B; }}

            /* ---------- Executive tiles ---------- */
            .exec-grid {{ display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }}
            .exec-tile {{
                background: #10131A; border: 1px solid #1C212B; border-left: 3px solid var(--accent, #3B82F6);
                border-radius: 2px; padding: 8px 10px; min-height: 64px;
                display: flex; flex-direction: column; justify-content: space-between;
            }}
            .exec-tile-top {{ display: flex; justify-content: space-between; align-items: flex-start; }}
            .exec-name {{ font-size: 10px; font-weight: 700; color: #D1D5DB; text-transform: uppercase; letter-spacing: 0.4px; }}
            .exec-label {{ font-size: 8px; color: #4B5563; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; }}
            .exec-value {{ font-size: 15px; font-weight: 700; color: #F3F4F6; font-variant-numeric: tabular-nums; }}
            .exec-unit {{ font-size: 9px; color: #6B7280; font-weight: 500; margin-left: 3px; }}
            .exec-status {{ font-size: 8px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; }}
            .status-online {{ color: #10B981; }}
            .status-offline {{ color: #EF4444; }}

            /* ---------- Operations console table ---------- */
            .ops-table {{
                width: 100%; border-collapse: collapse; background: #10131A; border-radius: 2px;
                overflow: hidden; border: 1px solid #1C212B;
            }}
            .ops-table th {{
                background: #171B24; color: #6B7280; font-size: 9px; font-weight: 700;
                text-transform: uppercase; letter-spacing: 0.6px; padding: 6px 10px; text-align: left;
                border-bottom: 1px solid #262C38;
            }}
            .ops-table td {{
                background: #10131A; color: #C6CBD3; font-size: 10.5px; padding: 5px 10px;
                border-bottom: 1px solid #171B24; font-variant-numeric: tabular-nums;
            }}
            .ops-table tr:nth-child(even) td {{ background: #0D0F14; }}
            .ops-table tr:hover td {{ background: #1C212B; }}
            .ops-val {{ color: #F3F4F6; font-weight: 600; }}
            .ops-unit {{ color: #4B5563; font-size: 9px; margin-left: 2px; }}

            /* ---------- Operations console (row-based, no table/dataframe) ---------- */
            .ops-console {{
                background: #10131A; border: 1px solid #1C212B; border-radius: 2px; overflow: hidden;
            }}
            .console-row {{
                display: grid; grid-template-columns: 1.6fr 1fr 1fr 1fr 0.9fr;
                align-items: center; padding: 5px 12px; border-bottom: 1px solid #171B24;
                transition: background 0.1s ease;
            }}
            .console-row:last-child {{ border-bottom: none; }}
            .console-row-head {{
                background: #171B24; padding: 6px 12px;
            }}
            .console-row-head .console-col {{
                font-size: 9px; font-weight: 700; color: #6B7280; text-transform: uppercase; letter-spacing: 0.6px;
            }}
            .console-row-alt {{ background: #0D0F14; }}
            .console-row:not(.console-row-head):hover {{ background: #1C212B; }}
            .console-col-name {{ font-size: 11px; font-weight: 600; color: #F3F4F6; }}
            .console-col-num {{ font-size: 10.5px; font-variant-numeric: tabular-nums; }}
            .console-col-status {{ font-size: 9.5px; font-weight: 700; letter-spacing: 0.4px; }}

            /* ---------- Alarm ribbon ---------- */
            .alarm-ribbon {{
                display: flex; align-items: center; gap: 8px;
                background: #10131A; border: 1px solid #1C212B; border-left: 3px solid var(--alarm-color, #10B981);
                border-radius: 2px; padding: 6px 12px; margin-bottom: 8px;
                font-size: 10.5px; font-weight: 600; color: #D1D5DB; letter-spacing: 0.2px;
            }}
            .alarm-dot {{ width: 7px; height: 7px; border-radius: 50%; background: var(--alarm-color, #10B981); flex-shrink: 0; }}
            .alarm-label {{ font-size: 8px; font-weight: 700; color: #4B5563; text-transform: uppercase; letter-spacing: 0.8px; margin-right: 4px; }}

            /* ---------- Equipment selector cards ---------- */
            .equip-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 6px; }}
            .equip-card {{
                background: #10131A; border: 1px solid #1C212B; border-radius: 2px;
                padding: 10px 12px; border-top: 2px solid var(--accent, #8B5CF6);
            }}
            .equip-card.active {{ background: #171B24; border-color: var(--accent, #8B5CF6); }}
            .equip-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px; }}
            .equip-name {{ font-size: 11.5px; font-weight: 700; color: #F3F4F6; }}
            .equip-category {{ font-size: 9px; color: #6B7280; text-transform: uppercase; letter-spacing: 0.4px; margin-top: 1px; }}
            .equip-metrics {{ display: flex; flex-direction: column; gap: 2px; margin: 6px 0 8px 0; }}
            .equip-metric-row {{ display: flex; justify-content: space-between; font-size: 9.5px; color: #9CA3AF; }}
            .equip-metric-row span:last-child {{ color: #D1D5DB; font-weight: 600; font-variant-numeric: tabular-nums; }}
            .equip-footer {{ display: flex; justify-content: flex-end; }}

            div[data-testid="stButton"] > button {{
                background: transparent !important; border: none !important; padding: 0 !important;
                width: 100%; text-align: left;
            }}

            /* ---------- Workspace / control room ---------- */
            .workspace {{
                background: #10131A; border: 1px solid #1C212B; border-radius: 2px; padding: 10px;
                border-top: 2px solid var(--accent, #3B82F6); margin-bottom: 8px;
            }}
            .workspace-header {{ display: flex; justify-content: space-between; align-items: baseline; padding: 4px 6px 8px 6px; }}
            .workspace-title {{ font-size: 14px; font-weight: 700; color: #F3F4F6; margin: 0; letter-spacing: 0.3px; }}
            .workspace-label {{ font-size: 9px; color: #6B7280; text-transform: uppercase; letter-spacing: 0.6px; }}

            .chart-box {{
                background: #0A0C10; border: 1px solid #171B24; border-radius: 2px; padding: 8px; margin-bottom: 6px;
            }}
            .chart-label {{
                font-size: 9px; font-weight: 700; color: #6B7280; text-transform: uppercase;
                letter-spacing: 0.6px; margin-bottom: 4px; padding: 0 2px;
            }}

            /* ---------- DataFrames (registers) ---------- */
            div[data-testid="stDataFrame"] {{
                border: 1px solid #1C212B !important; border-radius: 2px !important; overflow: hidden !important;
            }}
            div[data-testid="stDataFrame"] th {{
                background: #171B24 !important; color: #6B7280 !important; font-weight: 700 !important;
                text-transform: uppercase !important; font-size: 9px !important; letter-spacing: 0.6px !important;
                border-bottom: 1px solid #262C38 !important; padding: 4px 8px !important;
            }}
            div[data-testid="stDataFrame"] td {{
                background: #10131A !important; color: #C6CBD3 !important; border-bottom: 1px solid #171B24 !important;
                padding: 4px 8px !important; font-size: 10.5px !important; font-variant-numeric: tabular-nums;
            }}
            div[data-testid="stDataFrame"] tr:hover td {{ background: #1C212B !important; }}

            /* ---------- Footer ---------- */
            .app-footer {{
                margin-top: 16px; padding: 6px 16px; border-radius: 2px; background: #10131A;
                border: 1px solid #1C212B; font-size: 9px; color: #4B5563; text-align: center;
                letter-spacing: 0.3px;
            }}

            ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
            ::-webkit-scrollbar-track {{ background: #0A0C10; }}
            ::-webkit-scrollbar-thumb {{ background: #262C38; border-radius: 3px; }}
        </style>""",
        unsafe_allow_html=True,
    )


# ==================================================================
# Header
# ==================================================================

def render_header(dashboard: dict[str, Any] | None) -> None:
    now = dt.datetime.now()
    departments = (dashboard or {}).get("departments", {})
    last_refresh = st.session_state.get("last_refresh")

    plant_ok = bool(departments)
    plant_color = THEME_SUCCESS_COLOR if plant_ok else THEME_DANGER_COLOR
    plant_text = "ONLINE" if plant_ok else "OFFLINE"

    wb_ok = dashboard is not None
    wb_color = THEME_SUCCESS_COLOR if wb_ok else THEME_DANGER_COLOR
    wb_text = "LINKED" if wb_ok else "UNLINKED"

    gh_ok = dashboard is not None
    gh_color = THEME_SUCCESS_COLOR if gh_ok else THEME_DANGER_COLOR
    gh_text = "SYNCED" if gh_ok else "ERROR"

    refresh_str = last_refresh.strftime("%H:%M:%S") if last_refresh else "—"

    st.markdown(
        f"""
    <div class="scada-header">
        <div class="header-left">
            <div class="app-logo">{APP_ICON}</div>
            <div><span class="app-title">{APP_NAME}</span><span class="app-version">v{APP_VERSION}</span></div>
        </div>
        <div class="header-status-group">
            <div class="header-stat">
                <div class="header-stat-label">Plant</div>
                <div class="header-stat-value"><span class="status-dot" style="background:{plant_color};"></span>{plant_text}</div>
            </div>
            <div class="header-stat">
                <div class="header-stat-label">Workbook</div>
                <div class="header-stat-value"><span class="status-dot" style="background:{wb_color};"></span>{wb_text}</div>
            </div>
            <div class="header-stat">
                <div class="header-stat-label">GitHub</div>
                <div class="header-stat-value"><span class="status-dot" style="background:{gh_color};"></span>{gh_text}</div>
            </div>
            <div class="header-stat">
                <div class="header-stat-label">Time</div>
                <div class="header-stat-value">{now.strftime("%H:%M:%S")}</div>
            </div>
            <div class="header-stat">
                <div class="header-stat-label">Last Refresh</div>
                <div class="header-stat-value">{refresh_str}</div>
            </div>
        </div>
    </div>""",
        unsafe_allow_html=True,
    )


# ==================================================================
# Alarm Ribbon
# ==================================================================

# Soft, non-authoritative thresholds used only to color the ribbon.
# These do NOT alter any engineering calculation — display hint only.
ALARM_WATCHLIST: Final[dict[str, float]] = {
    "Air compressor": 0.90,   # latest / gauge-ceiling ratio
    "DG": 0.90,
    "GG": 0.90,
}


def render_alarm_ribbon(dashboard: dict[str, Any]) -> None:
    departments = dashboard.get("departments", {})
    alarms: list[tuple[str, str]] = []  # (severity, message)

    for dept_name, threshold_ratio in ALARM_WATCHLIST.items():
        dept_obj = departments.get(dept_name)
        if not dept_obj:
            continue
        rep_m = select_representative_meter(dept_obj)
        if not rep_m:
            continue
        latest_val = dept_obj.get("latest_values", {}).get(rep_m)
        df_block = dept_obj.get("dataframe", pd.DataFrame())
        if not isinstance(latest_val, (int, float)):
            continue
        ceiling = get_gauge_max(df_block, rep_m, dept_obj)
        if ceiling <= 0:
            continue
        ratio = latest_val / ceiling
        if ratio >= 1.0:
            alarms.append(("red", f"{dept_name} {rep_m} Exceeded"))
        elif ratio >= threshold_ratio:
            alarms.append(("amber", f"{dept_name} {rep_m} High"))

    if not alarms:
        color, label, text = "#10B981", "STATUS", "No Active Alarms"
    else:
        severities = [a[0] for a in alarms]
        if "red" in severities:
            color, label = "#EF4444", "ALARM"
            text = next(msg for sev, msg in alarms if sev == "red")
        else:
            color, label = "#F59E0B", "WARNING"
            text = alarms[0][1]
        if len(alarms) > 1:
            text += f" (+{len(alarms) - 1} more)"

    st.markdown(
        f"""
    <div class="alarm-ribbon" style="--alarm-color:{color};">
        <span class="alarm-dot"></span>
        <span class="alarm-label">{label}</span>
        <span>{text}</span>
    </div>""",
        unsafe_allow_html=True,
    )


# ==================================================================
# Section 1 — Executive Summary
# ==================================================================

def render_executive_summary(dashboard: dict[str, Any]) -> None:
    departments = dashboard.get("departments", {})
    tiles_html = ""

    for sys_name in CRITICAL_SYSTEMS:
        if sys_name not in departments:
            continue

        dept_obj = departments[sys_name]
        rep_m = select_representative_meter(dept_obj)
        latest_val = dept_obj.get("latest_values", {}).get(rep_m)
        unit = dept_obj.get("units", {}).get(rep_m, "")
        accent = DEPT_CONFIGS.get(sys_name, DEFAULT_CONFIG)["accent"]

        if isinstance(latest_val, (int, float)):
            val_str = f"{latest_val:,.0f}"
            status_class, status_text = "status-online", "ONLINE"
        else:
            val_str = "—"
            status_class, status_text = "status-offline", "OFFLINE"

        unit_str = str(unit).strip() if unit else ""
        metric_label = str(rep_m) if rep_m else "No Meter"

        tiles_html += f"""
        <div class="exec-tile" style="--accent:{accent};">
            <div class="exec-tile-top">
                <div class="exec-name">{sys_name}</div>
            </div>
            <div class="exec-label">{metric_label}</div>
            <div class="exec-value">{val_str}<span class="exec-unit">{unit_str}</span></div>
            <div class="exec-status {status_class}">{status_text}</div>
        </div>"""

    if tiles_html:
        st.markdown(f'<div class="exec-grid">{tiles_html}</div>', unsafe_allow_html=True)


# ==================================================================
# Section 2 — Operations Overview
# ==================================================================

OPS_CONSOLE_PROCESSES: Final[list[str]] = [
    "NPCL",
    "Overall PNG",
    "Dough",
    "Traywasher",
    "Freon Refrigeration",
    "Ammonia Refrigeration",
    "Bread",
    "Donut",
]


def render_operations_overview(dashboard: dict[str, Any]) -> None:
    departments = dashboard.get("departments", {})
    rows_html = ""

    header_html = """
    <div class="console-row console-row-head">
        <div class="console-col console-col-name">Process</div>
        <div class="console-col console-col-num">Total</div>
        <div class="console-col console-col-num">Average</div>
        <div class="console-col console-col-num">Latest</div>
        <div class="console-col console-col-status">Status</div>
    </div>"""

    for idx, dept_name in enumerate(OPS_CONSOLE_PROCESSES):
        if dept_name not in departments:
            continue
        dept_obj = departments[dept_name]
        rep_m = select_representative_meter(dept_obj)
        total_val = dept_obj.get("total_values", {}).get(rep_m)
        avg_val = dept_obj.get("average_values", {}).get(rep_m)
        latest_val = dept_obj.get("latest_values", {}).get(rep_m)
        unit = dept_obj.get("units", {}).get(rep_m, "")
        unit_str = str(unit).strip() if unit else ""

        total_str = f"{total_val:,.0f}" if isinstance(total_val, (int, float)) else "—"
        avg_str = f"{avg_val:,.1f}" if isinstance(avg_val, (int, float)) else "—"
        latest_str = f"{latest_val:,.0f}" if isinstance(latest_val, (int, float)) else "—"

        is_online = isinstance(latest_val, (int, float))
        status_html = (
            '<span class="status-online">● ONLINE</span>' if is_online
            else '<span class="status-offline">○ OFFLINE</span>'
        )
        row_shade = "console-row-alt" if idx % 2 else ""

        rows_html += f"""
        <div class="console-row {row_shade}">
            <div class="console-col console-col-name">{dept_name}</div>
            <div class="console-col console-col-num"><span class="ops-val">{total_str}</span><span class="ops-unit">{unit_str}</span></div>
            <div class="console-col console-col-num"><span class="ops-val">{avg_str}</span><span class="ops-unit">{unit_str}</span></div>
            <div class="console-col console-col-num"><span class="ops-val">{latest_str}</span><span class="ops-unit">{unit_str}</span></div>
            <div class="console-col console-col-status">{status_html}</div>
        </div>"""

    if rows_html:
        st.markdown(f'<div class="ops-console">{header_html}{rows_html}</div>', unsafe_allow_html=True)


# ==================================================================
# Section 3 — Equipment / Process Selector
# ==================================================================

def _top_metrics_for(dept_obj: dict[str, Any], meters: list[str], n: int = 3) -> list[tuple[str, str]]:
    """Pull up to n (meter_name, formatted latest value + unit) pairs for a card."""
    latest_vals = dept_obj.get("latest_values", {})
    units = dept_obj.get("units", {})
    out: list[tuple[str, str]] = []
    for m in meters[:n]:
        v = latest_vals.get(m)
        u = str(units.get(m, "") or "").strip()
        v_str = f"{v:,.1f}" if isinstance(v, (int, float)) else "—"
        out.append((m, f"{v_str} {u}".strip()))
    return out


def render_process_selector(dashboard: dict[str, Any]) -> str | None:
    departments = dashboard.get("departments", {})

    if "selected_process" not in st.session_state:
        st.session_state["selected_process"] = None

    selected = st.session_state["selected_process"]
    dept_names = sorted(departments.keys())
    cols = st.columns(4)

    for idx, dept_name in enumerate(dept_names):
        dept_obj = departments[dept_name]
        config = DEPT_CONFIGS.get(dept_name, DEFAULT_CONFIG)
        meters = dept_obj.get("meters", [])
        is_active = (dept_name == selected)
        metrics = _top_metrics_for(dept_obj, meters, n=3)
        is_online = any(dept_obj.get("latest_values", {}).get(m) is not None for m in meters)
        status_class = "status-online" if is_online else "status-offline"
        status_text = "ONLINE" if is_online else "OFFLINE"

        metrics_html = "".join(
            f'<div class="equip-metric-row"><span>{name}</span><span>{val}</span></div>'
            for name, val in metrics
        )

        card_html = f"""
        <div class="equip-card{' active' if is_active else ''}" style="--accent:{config['accent']};">
            <div class="equip-header">
                <div>
                    <div class="equip-name">{dept_name}</div>
                    <div class="equip-category">{config['category']}</div>
                </div>
            </div>
            <div class="equip-metrics">{metrics_html}</div>
            <div class="equip-footer"><span class="exec-status {status_class}">{status_text}</span></div>
        </div>"""

        with cols[idx % 4]:
            st.markdown(card_html, unsafe_allow_html=True)
            if st.button("Select", key=f"proc_{dept_name}", use_container_width=True):
                st.session_state["selected_process"] = dept_name
                st.rerun()

    return st.session_state["selected_process"]


# ==================================================================
# Section 4 — Workspace / control room, per-department layouts
# ==================================================================

def _chart_box(label: str, fig) -> None:
    st.markdown(f'<div class="chart-box"><div class="chart-label">{label}</div>', unsafe_allow_html=True)
    if fig:
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)


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
    unit_lbl = dept_obj.get("units", {}).get(rep_m, "") if rep_m else ""
    latest_val = dept_obj.get("latest_values", {}).get(rep_m, 0.0) or 0.0 if rep_m else 0.0
    max_ceiling = get_gauge_max(df_block, rep_m, dept_obj) if rep_m else 100.0

    st.markdown(
        f"""
    <div class="workspace" style="--accent:{config['accent']};">
        <div class="workspace-header">
            <h2 class="workspace-title">{process_name}</h2>
            <div class="workspace-label">{config['category']}</div>
        </div>
    </div>""",
        unsafe_allow_html=True,
    )

    # ---------------- NPCL: Electrical — Demand Gauge / PF Area / Energy Donut ----------------
    if process_name == "NPCL":
        col1, col2 = st.columns([2, 1])
        with col1:
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            _chart_box("Load Trend", fig)
            if len(meters) >= 2:
                fig = chart_service.create_area_chart(df_block, x_column=df_block.columns[0] if not df_block.empty else "", y_columns=meters[:3], title="Power Factor / Load Area") if not df_block.empty else None
                if fig:
                    _chart_box("Power Distribution", fig)
        with col2:
            fig = chart_service.create_gauge_chart(latest_val, "Demand", maximum=max_ceiling, unit=unit_lbl)
            _chart_box("Demand Gauge", fig)
            if len(meters) >= 2:
                vals = {m: dept_obj["total_values"].get(m, 0) or 0 for m in meters[:5]}
                bar_df = pd.DataFrame(list(vals.items()), columns=["Meter", "Value"])
                fig = chart_service.create_donut_chart(bar_df, "Meter", "Value", "Energy Distribution")
                _chart_box("Energy Distribution", fig)

    # ---------------- Air Compressor: Pressure Gauge / Stability / Flow / Runtime / Efficiency ----------------
    elif process_name == "Air compressor":
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            fig = chart_service.create_gauge_chart(latest_val, "Pressure", maximum=max_ceiling, unit=unit_lbl)
            _chart_box("Pressure Gauge", fig)
        with col2:
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            _chart_box("Flow Trend / Stability", fig)
        with col3:
            if len(meters) >= 2:
                vals = {m: dept_obj["total_values"].get(m, 0) or 0 for m in meters[:5]}
                bar_df = pd.DataFrame(list(vals.items()), columns=["Meter", "Value"])
                fig = chart_service.create_horizontal_bar_chart(bar_df, "Meter", "Value", "Runtime")
                _chart_box("Runtime", fig)
        if len(meters) >= 3:
            fig = chart_service.create_radar_chart(df_block, meters[:6], "Efficiency Profile")
            _chart_box("Efficiency", fig)

    # ---------------- Freon / Ammonia Refrigeration: Heatmap / Cooling Trend / COP / Distribution ----------------
    elif process_name in ("Freon Refrigeration", "Ammonia Refrigeration"):
        col1, col2 = st.columns([2, 1])
        with col1:
            fig = chart_service.create_heatmap(df_block, meters[: min(len(meters), 8)], "Temperature Heatmap")
            _chart_box("Temperature Heatmap", fig)
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            _chart_box("Cooling Trend", fig)
        with col2:
            fig = chart_service.create_gauge_chart(latest_val, "COP", maximum=max_ceiling, unit=unit_lbl)
            _chart_box("COP", fig)
            if len(meters) >= 2:
                fig = chart_service.create_histogram(df_block, meters[0], "Temperature Distribution")
                _chart_box("Temperature Distribution", fig)

    # ---------------- DG / GG: Generation Bullet / Fuel Bar / Runtime / Output Trend ----------------
    elif process_name in ("DG", "GG"):
        col1, col2 = st.columns([1, 2])
        with col1:
            target_val = dept_obj.get("average_values", {}).get(rep_m, latest_val) or latest_val
            fig = chart_service.create_bullet_chart(latest_val, target_val, "Generation vs Target", unit=unit_lbl)
            _chart_box("Generation", fig)
            fig = chart_service.create_gauge_chart(latest_val, "Runtime Load", maximum=100, unit="%")
            _chart_box("Runtime", fig)
        with col2:
            vals = {m: dept_obj["total_values"].get(m, 0) or 0 for m in meters[:6]}
            bar_df = pd.DataFrame(list(vals.items()), columns=["Meter", "Value"])
            fig = chart_service.create_bar_chart(bar_df, "Meter", "Value", "Fuel Consumption")
            _chart_box("Fuel Consumption", fig)
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            _chart_box("Output Trend", fig)

    # ---------------- Traywasher: Water Usage / Thermal Trend / Cycles / Efficiency ----------------
    elif process_name == "Traywasher":
        col1, col2 = st.columns([1, 1])
        with col1:
            vals = {m: dept_obj["total_values"].get(m, 0) or 0 for m in meters[:5]}
            bar_df = pd.DataFrame(list(vals.items()), columns=["Meter", "Value"])
            fig = chart_service.create_horizontal_bar_chart(bar_df, "Meter", "Value", "Water Usage")
            _chart_box("Water Usage", fig)
        with col2:
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            _chart_box("Thermal Trend", fig)
        if len(meters) >= 3:
            fig = chart_service.create_radar_chart(df_block, meters[:6], "Cycle Efficiency")
            _chart_box("Efficiency", fig)

    # ---------------- Default control-room layout ----------------
    else:
        col1, col2 = st.columns([2, 1])
        with col1:
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            _chart_box("Primary Telemetry", fig)
            if len(meters) > 1:
                fig = chart_service.create_department_multi_line_chart(
                    overview_dataframe=overview_df, section=dept_obj, title="Load Profiles"
                )
                _chart_box("Multi-Channel Analysis", fig)
        with col2:
            if rep_m:
                fig = chart_service.create_gauge_chart(latest_val, rep_m, maximum=max_ceiling, unit=unit_lbl)
                _chart_box("Current Status", fig)

    # ---------------- Channel Registry (compact register, all departments) ----------------
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
        ledger_records.append(
            {
                "Channel": m,
                "Unit": lbl if (lbl and str(lbl).strip()) else "N/A",
                "Latest": round(l_v, 2) if isinstance(l_v, (int, float)) else "N/A",
                "Mean": round(a_v, 2) if isinstance(a_v, (int, float)) else "N/A",
                "Total": round(t_v, 2) if isinstance(t_v, (int, float)) else "N/A",
                "Status": "Active" if l_v is not None else "Idle",
            }
        )
    if ledger_records:
        st.markdown('<div class="chart-box"><div class="chart-label">Channel Registry</div>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(ledger_records), use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)


# ==================================================================
# Footer
# ==================================================================

def render_footer(dashboard: dict[str, Any] | None) -> None:
    last_refresh = st.session_state.get("last_refresh")
    refresh_text = last_refresh.strftime("%d %b %Y, %H:%M:%S") if last_refresh else "N/A"
    meta = (dashboard or {}).get("metadata", {})
    sheet_names = meta.get("sheet_names", ["Data Source Unlinked"])
    active_workbook = sheet_names[0] if sheet_names else "N/A"
    st.markdown(
        f"""<div class="app-footer">WORKBOOK: {active_workbook} &nbsp;·&nbsp; REFRESHED: {refresh_text} &nbsp;·&nbsp; v{APP_VERSION}</div>""",
        unsafe_allow_html=True,
    )


# ==================================================================
# Main
# ==================================================================

def main() -> None:
    inject_global_styles()
    dashboard, error_msg = get_dashboard()

    render_header(dashboard)

    if error_msg is not None or dashboard is None:
        st.error(error_msg or "Critical Infrastructure Alert: Analytical context dictionary failed initialization.")
        render_footer(dashboard)
        return

    render_alarm_ribbon(dashboard)

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
