# ==========================================
# FILE: app.py
# ==========================================
"""Main Entry Point for the Engineering Monitoring Dashboard."""

from __future__ import annotations

import datetime as dt
import logging
import re
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
from services.dashboard_loader import load_dashboard_safe
import dashboard_data
from dashboard_data import select_representative_meter

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title=PAGE_CONFIG.get("page_title", APP_NAME),
    page_icon=PAGE_CONFIG.get("page_icon", "⚙️"),
    layout="wide",
    initial_sidebar_state="expanded",
)

# Local timezone for the dashboard's operating region (India Standard Time,
# UTC+05:30 — India observes no DST, so a fixed offset is always correct).
# Displayed times are computed against this so the sidebar shows the correct
# local time even when the app runs on a server in a different timezone (e.g.
# a UTC cloud host). Built from datetime only; nothing is hardcoded.
LOCAL_TZ = dt.timezone(dt.timedelta(hours=5, minutes=30))

CRITICAL_SYSTEMS = [
    "NPCL", "Overall PNG", "Air compressor", "Rooftop Solar",
    "Freon Refrigeration", "Ammonia Refrigeration",
]

DEPT_CONFIGS = {
    "NPCL": {"accent": "#005DAA", "category": "Electrical / Incoming Power"},
    "Overall PNG": {"accent": "#E31E24", "category": "Fuel / Piped Natural Gas"},
    "DG": {"accent": "#F59E0B", "category": "Fuel / Diesel Generation"},
    "GG": {"accent": "#E31E24", "category": "Fuel / Gas Generation"},
    "Air compressor": {"accent": "#06B6D4", "category": "Compressed Air"},
    "Rooftop Solar": {"accent": "#F59E0B", "category": "Renewable Generation"},
    "Freon Refrigeration": {"accent": "#8B5CF6", "category": "Cooling System"},
    "Ammonia Refrigeration": {"accent": "#8B5CF6", "category": "Cooling System"},
    "Traywasher": {"accent": "#22C55E", "category": "Sanitation / Water"},
    "Dough": {"accent": "#F59E0B", "category": "Processing"},
    "Bread": {"accent": "#F59E0B", "category": "Baking"},
    "Donut": {"accent": "#F59E0B", "category": "Production"},
    "CLC": {"accent": "#005DAA", "category": "Control Logic"},
    "Warehouse": {"accent": "#005DAA", "category": "Storage / Utility"},
    "Transport": {"accent": "#06B6D4", "category": "Logistics"},
    "Engineering": {"accent": "#22C55E", "category": "Workshop"},
    "Utility": {"accent": "#06B6D4", "category": "Utilities"},
}
DEFAULT_CONFIG = {"accent": "#8B5CF6", "category": "Engineering System"}

EXEC_TILE_LABELS: Final[dict[str, str]] = {
    "NPCL": "Incoming Electrical",
    "Overall PNG": "Piped Natural Gas",
    "Air compressor": "Compressed Air",
    "Rooftop Solar": "Solar Generation",
    "Freon Refrigeration": "Cooling System",
    "Ammonia Refrigeration": "Cooling System",
}
EXEC_TILE_ICONS: Final[dict[str, str]] = {
    "NPCL": "⚡",
    "Overall PNG": "🔥",
    "Air compressor": "🌀",
    "Rooftop Solar": "☀️",
    "Freon Refrigeration": "❄️",
    "Ammonia Refrigeration": "❄️",
}


def resolve_meter_unit(dept_obj: dict[str, Any], meter: str) -> str:
    units_map = dept_obj.get("units", {})
    
    def _is_valid_unit(val: Any) -> bool:
        if not val or not str(val).strip():
            return False
        s = str(val).strip()
        try:
            float(s)
            return False
        except ValueError:
            return True

    val = units_map.get(meter)
    if _is_valid_unit(val):
        return str(val).strip()
    
    base = re.sub(r"_\d+$", "", str(meter))
    if base != meter:
        val2 = units_map.get(base)
        if _is_valid_unit(val2):
            return str(val2).strip()
            
    return ""


def get_dashboard(start_date: str | None = None, end_date: str | None = None) -> tuple[dict[str, Any] | None, str | None]:
    cache_key = f"dashboard_data_{start_date}_{end_date}"
    error_key = f"dashboard_error_{start_date}_{end_date}"

    if cache_key not in st.session_state:
        # Keep only the current selection's cached dashboard + error in session
        # state. Stale keys from previous date selections are removed so state
        # cannot grow unbounded across many selections. (Both the dashboard and
        # error key families are cleaned; previously the error keys accumulated.)
        stale_keys = [
            k for k in list(st.session_state.keys())
            if (k.startswith("dashboard_data_") or k.startswith("dashboard_error_"))
            and k not in (cache_key, error_key)
        ]
        for k in stale_keys:
            del st.session_state[k]

        dashboard, error = load_dashboard_safe(start_date, end_date)
        st.session_state[cache_key] = dashboard
        st.session_state[error_key] = error
        st.session_state["last_refresh"] = dt.datetime.now(LOCAL_TZ)

    return st.session_state.get(cache_key), st.session_state.get(error_key)


def refresh_dashboard() -> None:
    st.cache_data.clear()
    st.cache_resource.clear()
    keys_to_clear = [
        k for k in list(st.session_state.keys())
        if k.startswith("dashboard_data") or k.startswith("dashboard_error")
    ]
    for k in keys_to_clear:
        del st.session_state[k]
    st.session_state.pop("last_refresh", None)


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


def _format_exec_value(value: float) -> str:
    rounded = round(float(value), 2)
    if abs(rounded - round(rounded)) < 0.005:
        return f"{rounded:,.0f}"
    return f"{rounded:,.2f}"


def _exec_trend_chip(latest_val: float, avg_val: Any) -> tuple[str, str]:
    if not isinstance(avg_val, (int, float)) or avg_val == 0:
        return "trend-flat", "Stable"
    ratio = latest_val / avg_val
    if ratio >= 1.08:
        return "trend-up", "Healthy"
    if ratio <= 0.92:
        return "trend-down", "Low"
    return "trend-flat", "Stable"


def inject_global_styles() -> None:
    """Inject global CSS for the compact dark SCADA theme."""
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

            /* Global Resets & Theme */
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header[data-testid="stHeader"] {background: transparent;}
            .stApp { 
                background: #0B1220 !important; 
                color: #F8FAFC !important;
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important; 
            }
            .block-container { padding-top: 10px; padding-bottom: 12px; max-width: 100%; }
            * { box-sizing: border-box; }
            .tnum { font-variant-numeric: tabular-nums; }

            /* Sidebar - FIXED: No fixed widths or margins to allow native Streamlit collapse/expand */
            section[data-testid="stSidebar"] div[data-testid="stSidebarNav"],
            section[data-testid="stSidebar"] ul[data-testid="stSidebarNav"],
            section[data-testid="stSidebar"] nav[data-testid="stSidebarNav"] {
                display: none !important;
            }
            section[data-testid="stSidebar"] {
                background: #0B1220 !important;
                border-right: 1px solid #334155 !important;
                /* Removed width/min-width to let Streamlit handle it */
            }
            section[data-testid="stSidebar"] > div {
                padding: 10px 8px !important;
            }
            section[data-testid="stSidebar"] h1, 
            section[data-testid="stSidebar"] h2, 
            section[data-testid="stSidebar"] h3, 
            section[data-testid="stSidebar"] h4 {
                color: #F8FAFC !important;
                font-weight: 600 !important;
                font-size: 11px !important;
                margin-bottom: 4px !important;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            section[data-testid="stSidebar"] label {
                color: #94A3B8 !important;
                font-size: 10px !important;
                font-weight: 500 !important;
            }
            section[data-testid="stSidebar"] div[data-baseweb="select"] > div,
            section[data-testid="stSidebar"] div[data-baseweb="datepicker"] > div {
                background-color: #1E293B !important;
                border: 1px solid #334155 !important;
                color: #F8FAFC !important;
                border-radius: 4px !important;
                font-size: 10px !important;
            }
            section[data-testid="stSidebar"] input {
                color: #F8FAFC !important;
                font-size: 10px !important;
            }

            /* Buttons */
            div[data-testid="stButton"] > button {
                background: #1E293B !important;
                border: 1px solid #334155 !important;
                color: #F8FAFC !important;
                font-weight: 500 !important;
                font-size: 10px !important;
                border-radius: 4px !important;
                padding: 3px 6px !important;
                transition: all 0.2s ease !important;
                min-height: 0 !important;
                line-height: 1.2 !important;
            }
            div[data-testid="stButton"] > button:hover {
                background: #005DAA !important;
                color: #FFFFFF !important;
                border-color: #005DAA !important;
            }

            /* Section Titles */
            .section-title {
                font-size: 12px; font-weight: 600; color: #F8FAFC; text-transform: uppercase;
                letter-spacing: 0.5px; margin-bottom: 6px; margin-top: 12px;
                display: flex; align-items: center; gap: 6px;
            }
            .section-title::before { content: ""; width: 3px; height: 12px; background: #005DAA; border-radius: 2px; }

            /* Executive Summary / KPI Tiles */
            .exec-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 6px; margin-bottom: 10px; }
            .exec-tile {
                background: #1E293B;
                border: 1px solid #334155;
                border-left: 3px solid var(--accent, #005DAA);
                border-radius: 4px;
                padding: 6px;
                transition: all 0.2s ease;
                height: 100%;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
            }
            .exec-tile:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
            }
            .exec-tile-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 3px; }
            .exec-icon { 
                width: 18px; height: 18px; background: rgba(0, 93, 170, 0.2); 
                border-radius: 3px; display: flex; align-items: center; justify-content: center; 
                font-size: 9px; color: var(--accent, #005DAA);
            }
            .exec-name { font-size: 10px; font-weight: 600; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.3px; }
            .exec-label { font-size: 9px; color: #64748B; margin-top: 1px; }
            .exec-value-row { display: flex; align-items: baseline; margin-top: 3px; }
            .exec-value { font-size: 14px; font-weight: 700; color: #F8FAFC; line-height: 1.2; }
            .exec-unit { font-size: 9px; color: #94A3B8; margin-left: 2px; }
            .exec-bottom-row { display: flex; align-items: center; justify-content: space-between; margin-top: 4px; padding-top: 3px; border-top: 1px solid #334155; }
            .exec-trend-chip {
                display: inline-flex; align-items: center; gap: 2px; font-size: 8px; font-weight: 600;
                padding: 1px 3px; border-radius: 3px;
            }
            .trend-up { color: #22C55E; background: rgba(34, 197, 94, 0.15); }
            .trend-down { color: #E31E24; background: rgba(227, 30, 36, 0.15); }
            .trend-flat { color: #F59E0B; background: rgba(245, 158, 11, 0.15); }
            .exec-status { font-size: 9px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.3px; }
            .status-online { color: #22C55E; }
            .status-offline { color: #E31E24; }

            /* Operations Console Table */
            .ops-console {
                background: #1E293B;
                border: 1px solid #334155;
                border-radius: 4px;
                overflow: hidden;
            }
            .console-row {
                display: grid; grid-template-columns: 2fr 1fr 1fr 1fr 1fr;
                align-items: center; padding: 4px 8px; border-bottom: 1px solid #334155;
                transition: background 0.2s ease;
            }
            .console-row:last-child { border-bottom: none; }
            .console-row-head { background: #273449; padding: 5px 8px; }
            .console-row-head .console-col {
                font-size: 9px; font-weight: 600; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.3px;
            }
            .console-row-alt { background: #162032; }
            .console-row:not(.console-row-head):hover { background: #273449; }
            .console-col-name { font-size: 11px; font-weight: 600; color: #F8FAFC; }
            .console-col-num { font-size: 10px; font-variant-numeric: tabular-nums; color: #F8FAFC; }
            .ops-val { font-weight: 600; color: #F8FAFC; }
            .ops-unit { color: #94A3B8; font-size: 9px; margin-left: 2px; }

            /* Alarm Ribbon */
            .alarm-ribbon {
                display: flex; align-items: center; gap: 6px;
                background: #1E293B;
                border: 1px solid #334155; border-left: 3px solid var(--alarm-color, #22C55E);
                border-radius: 4px; padding: 6px 8px; margin-bottom: 10px;
                font-size: 11px; font-weight: 500; color: #F8FAFC;
            }
            .alarm-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--alarm-color, #22C55E); box-shadow: 0 0 4px var(--alarm-color, #22C55E); }
            .alarm-label { font-size: 9px; font-weight: 700; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.5px; }
            .alarm-message { font-size: 10px; color: #F8FAFC; }

            /* Scrollbar */
            ::-webkit-scrollbar { width: 4px; height: 4px; }
            ::-webkit-scrollbar-track { background: #0B1220; }
            ::-webkit-scrollbar-thumb { background: #334155; border-radius: 2px; }
            ::-webkit-scrollbar-thumb:hover { background: #475569; }

            /* Plant Operations Overview — premium industrial expander cards.
               Scoped to the only expander in the app (this section). Visual
               polish only: spacing, borders, contrast, prominence. */
            div[data-testid="stExpander"] {
                background: #1E293B;
                border: 1px solid #334155;
                border-left: 3px solid #005DAA;
                border-radius: 6px;
                margin-bottom: 8px;
                overflow: hidden;
                transition: border-color 0.2s ease, box-shadow 0.2s ease;
            }
            div[data-testid="stExpander"]:hover {
                border-color: #475569;
                border-left-color: #2E7DD1;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
            }
            div[data-testid="stExpander"] > details {
                background: transparent;
                border: none;
            }
            div[data-testid="stExpander"] > details > summary {
                padding: 10px 14px;
                background: linear-gradient(90deg, rgba(0, 93, 170, 0.10), rgba(30, 41, 59, 0));
                border-radius: 6px 6px 0 0;
                list-style: none;
                cursor: pointer;
                transition: background 0.2s ease;
            }
            div[data-testid="stExpander"] > details > summary:hover {
                background: linear-gradient(90deg, rgba(0, 93, 170, 0.18), rgba(30, 41, 59, 0));
            }
            /* Department name prominent; metrics readable and evenly spaced. */
            div[data-testid="stExpander"] summary p {
                font-size: 12px !important;
                color: #CBD5E1 !important;
                letter-spacing: 0.2px;
                margin: 0 !important;
            }
            div[data-testid="stExpander"] summary p strong {
                font-size: 13px;
                font-weight: 700;
                color: #F8FAFC;
                text-transform: uppercase;
                letter-spacing: 0.4px;
            }
            div[data-testid="stExpander"] summary svg {
                fill: #94A3B8;
            }
            /* Body padding around the subsection table. */
            div[data-testid="stExpander"] > details > div {
                padding: 8px 14px 12px 14px;
                border-top: 1px solid #334155;
                background: #162032;
            }
        </style>""",
        unsafe_allow_html=True,
    )


def render_sidebar_filters() -> tuple[str | None, str | None]:
    """Render the custom compact sidebar with filters."""
    st.sidebar.markdown("""
    <div style="text-align: center; margin-bottom: 10px; padding: 6px 0; border-bottom: 1px solid #334155;">
        <div style="font-size: 18px; font-weight: 800; color: #005DAA; letter-spacing: -0.5px;">JFL</div>
        <div style="font-size: 9px; font-weight: 600; color: #94A3B8; margin-top: 2px;">Jubilant FoodWorks</div>
        <div style="font-size: 10px; font-weight: 700; color: #F8FAFC; margin-top: 3px;">Engineering</div>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("#### 📅 Date Range")
    
    if "filter_start_date" not in st.session_state:
        st.session_state.filter_start_date = None
    if "filter_end_date" not in st.session_state:
        st.session_state.filter_end_date = None
        
    start_date = st.sidebar.date_input("Start Date", value=st.session_state.filter_start_date, key="start_date_input")
    end_date = st.sidebar.date_input("End Date", value=st.session_state.filter_end_date, key="end_date_input")

    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Refresh", use_container_width=True, key="refresh_btn"):
        refresh_dashboard()
        st.rerun()

    start_str = start_date.strftime("%Y-%m-%d") if start_date else None
    end_str = end_date.strftime("%Y-%m-%d") if end_date else None
    
    return start_str, end_str


def render_sidebar_status(dashboard: dict[str, Any] | None) -> None:
    """Render the system status panel in the sidebar."""
    now = dt.datetime.now(LOCAL_TZ)
    last_refresh = st.session_state.get("last_refresh")
    
    wb_ok = dashboard is not None
    gh_ok = dashboard is not None
    
    st.sidebar.markdown(f"""
    <div style="background: #1E293B; border-radius: 4px; padding: 6px; margin-bottom: 6px; border: 1px solid #334155;">
        <div style="font-size: 9px; color: #94A3B8; font-weight: 600; text-transform: uppercase; margin-bottom: 4px; letter-spacing: 0.3px;">System Status</div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 3px; font-size: 10px;">
            <span style="color: #94A3B8; font-weight: 500;">Date</span>
            <span style="font-weight: 600; color: #F8FAFC;">{now.strftime("%b %d")}</span>
        </div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 3px; font-size: 10px;">
            <span style="color: #94A3B8; font-weight: 500;">Time</span>
            <span style="font-weight: 600; color: #F8FAFC;">{now.strftime("%H:%M")}</span>
        </div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 3px; font-size: 10px;">
            <span style="color: #94A3B8; font-weight: 500;">Refresh</span>
            <span style="font-weight: 600; color: #F8FAFC;">{last_refresh.strftime("%H:%M") if last_refresh else "—"}</span>
        </div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 3px; font-size: 10px;">
            <span style="color: #94A3B8; font-weight: 500;">Excel</span>
            <span style="font-weight: 600; color: {'#22C55E' if wb_ok else '#E31E24'};">{'● OK' if wb_ok else '● ERR'}</span>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 10px;">
            <span style="color: #94A3B8; font-weight: 500;">GitHub</span>
            <span style="font-weight: 600; color: {'#22C55E' if gh_ok else '#E31E24'};">{'● OK' if gh_ok else '● ERR'}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


ALARM_WATCHLIST: Final[dict[str, float]] = {
    "Air compressor": 0.90,
    "DG": 0.90,
    "GG": 0.90,
}


def render_alarm_ribbon(dashboard: dict[str, Any]) -> None:
    departments = dashboard.get("departments", {})
    alarms: list[tuple[str, str]] = []

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
        color, label, text = "#22C55E", "STATUS", "No Active Alarms"
    else:
        severities = [a[0] for a in alarms]
        if "red" in severities:
            color, label = "#E31E24", "ALARM"
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
        <span class="alarm-message">{text}</span>
    </div>""",
        unsafe_allow_html=True,
    )


def render_executive_summary(dashboard: dict[str, Any]) -> None:
    departments = dashboard.get("departments", {})
    tiles_html = ""

    for sys_name in CRITICAL_SYSTEMS:
        if sys_name not in departments:
            continue

        dept_obj = departments[sys_name]
        rep_m = select_representative_meter(dept_obj)
        latest_val = dept_obj.get("latest_values", {}).get(rep_m)
        avg_val = dept_obj.get("average_values", {}).get(rep_m)
        unit = resolve_meter_unit(dept_obj, rep_m) if rep_m else ""
        accent = DEPT_CONFIGS.get(sys_name, DEFAULT_CONFIG)["accent"]
        icon = EXEC_TILE_ICONS.get(sys_name, "◆")
        fixed_label = EXEC_TILE_LABELS.get(sys_name, DEPT_CONFIGS.get(sys_name, DEFAULT_CONFIG)["category"])

        if isinstance(latest_val, (int, float)):
            val_str = _format_exec_value(latest_val)
            status_class, status_text = "status-online", "ONLINE"
            trend_class, trend_text = _exec_trend_chip(latest_val, avg_val)
            trend_arrow = "▲" if trend_class == "trend-up" else ("▼" if trend_class == "trend-down" else "●")
        else:
            val_str = "—"
            status_class, status_text = "status-offline", "OFFLINE"
            trend_class, trend_text, trend_arrow = "trend-flat", "No Data", "○"

        tiles_html += f"""
        <div class="exec-tile" style="--accent:{accent};">
            <div class="exec-tile-top">
                <div class="exec-icon">{icon}</div>
                <div class="exec-name-group">
                    <span class="exec-name">{sys_name}</span>
                </div>
            </div>
            <div class="exec-label">{fixed_label}</div>
            <div class="exec-value-row">
                <span class="exec-value">{val_str}</span><span class="exec-unit">{unit}</span>
            </div>
            <div class="exec-bottom-row">
                <span class="exec-trend-chip {trend_class}">{trend_arrow} {trend_text}</span>
                <span class="exec-status {status_class}">{status_text}</span>
            </div>
        </div>"""

    if tiles_html:
        st.markdown(f'<div class="exec-grid">{tiles_html}</div>', unsafe_allow_html=True)


def _ops_fmt_total(value: Any) -> str:
    return f"{value:,.0f}" if isinstance(value, (int, float)) else "—"


def _ops_fmt_avg(value: Any) -> str:
    return f"{value:,.1f}" if isinstance(value, (int, float)) else "—"


def _ops_fmt_latest(value: Any) -> str:
    return f"{value:,.0f}" if isinstance(value, (int, float)) else "—"


def _ops_status_html(online: bool) -> str:
    return (
        '<span class="status-online">● ONLINE</span>' if online
        else '<span class="status-offline">○ OFFLINE</span>'
    )


def _ops_status_text(online: bool) -> str:
    return "● ONLINE" if online else "○ OFFLINE"


def render_operations_overview(dashboard: dict[str, Any]) -> None:
    # Business layer supplies the parent/subsection structure (parsed
    # engineering departments only — no hardcoded names/rows/columns, discovery
    # order preserved). No KPIs are recalculated here.
    overview_rows = dashboard_data.build_operations_overview(dashboard)
    departments = dashboard.get("departments", {})

    for row in overview_rows:
        dept_name = row["department"]
        dept_obj = departments.get(dept_name, {})
        rep_m = row.get("representative_meter", "")
        unit_str = resolve_meter_unit(dept_obj, rep_m) if rep_m else ""
        unit_suffix = f" {unit_str}" if unit_str else ""

        latest_str = _ops_fmt_latest(row["latest"])
        avg_str = _ops_fmt_avg(row["average"])
        total_str = _ops_fmt_total(row["total"])
        status_str = _ops_status_text(row["online"])

        # Native expander title. Expander labels support limited Markdown, so
        # the department name is emphasised for prominence and figures are
        # grouped with clear separators for scannability.
        #   • Multi-subsection (expandable) departments show only the aggregated
        #     Average, Total and Status — "Previous Day" is intentionally hidden,
        #     since a summed previous-day figure is not meaningful for a
        #     multi-meter aggregate.
        #   • Single-subsection departments keep the full format including
        #     "Previous Day".
        # (Values themselves are unchanged; this only controls what is shown.)
        if row["expandable"]:
            expander_label = (
                f"**{dept_name}**  ·  "
                f"Avg {avg_str}{unit_suffix}  ·  "
                f"Total {total_str}{unit_suffix}  ·  "
                f"{status_str}"
            )
        else:
            expander_label = (
                f"**{dept_name}**  ·  "
                f"Previous Day {latest_str}{unit_suffix}  ·  "
                f"Avg {avg_str}{unit_suffix}  ·  "
                f"Total {total_str}{unit_suffix}  ·  "
                f"{status_str}"
            )

        with st.expander(expander_label, expanded=False):
            # Subsection rows come from the ORIGINAL parsed meters (already
            # resolved by the business layer). Multi-meter / aggregated
            # departments expose them in ``subsections``; single-meter
            # departments have one meter (the representative), whose figures
            # equal the parent — no recalculation, no invented names.
            if row["subsections"]:
                sub_rows = row["subsections"]
            elif rep_m:
                sub_rows = [
                    {
                        "name": rep_m,
                        "total": row["total"],
                        "average": row["average"],
                        "latest": row["latest"],
                        "online": row["online"],
                    }
                ]
            else:
                sub_rows = []

            header_html = """
    <div class="console-row console-row-head">
        <div class="console-col console-col-name">Subsection</div>
        <div class="console-col console-col-num">Total</div>
        <div class="console-col console-col-num">Average</div>
        <div class="console-col console-col-num">Previous Day</div>
        <div class="console-col console-col-status">Status</div>
    </div>"""

            rows_html = ""
            for idx, sub in enumerate(sub_rows):
                sub_unit = resolve_meter_unit(dept_obj, sub["name"])
                sub_total = _ops_fmt_total(sub["total"])
                sub_avg = _ops_fmt_avg(sub["average"])
                sub_latest = _ops_fmt_latest(sub["latest"])
                sub_status = _ops_status_html(sub["online"])
                row_shade = "console-row-alt" if idx % 2 else ""
                rows_html += f"""
        <div class="console-row {row_shade}">
            <div class="console-col console-col-name">{sub['name']}</div>
            <div class="console-col console-col-num"><span class="ops-val">{sub_total}</span><span class="ops-unit">{sub_unit}</span></div>
            <div class="console-col console-col-num"><span class="ops-val">{sub_avg}</span><span class="ops-unit">{sub_unit}</span></div>
            <div class="console-col console-col-num"><span class="ops-val">{sub_latest}</span><span class="ops-unit">{sub_unit}</span></div>
            <div class="console-col console-col-status">{sub_status}</div>
        </div>"""

            if rows_html:
                st.markdown(f'<div class="ops-console">{header_html}{rows_html}</div>', unsafe_allow_html=True)


def render_footer(dashboard: dict[str, Any] | None) -> None:
    last_refresh = st.session_state.get("last_refresh")
    refresh_text = last_refresh.strftime("%d %b %Y, %H:%M:%S") if last_refresh else "N/A"
    meta = (dashboard or {}).get("metadata", {})
    sheet_names = meta.get("sheet_names", ["Data Source Unlinked"])
    active_workbook = sheet_names[0] if sheet_names else "N/A"
    st.markdown(
        f"""<div style="margin-top: 10px; padding: 4px; border-radius: 4px; background: #1E293B; border: 1px solid #334155; font-size: 9px; color: #94A3B8; text-align: center;">WORKBOOK: {active_workbook} &nbsp;·&nbsp; REFRESHED: {refresh_text} &nbsp;·&nbsp; v{APP_VERSION}</div>""",
        unsafe_allow_html=True,
    )


def main() -> None:
    inject_global_styles()
    
    # 1. Render Sidebar Filters (Date Range)
    start_date, end_date = render_sidebar_filters()
    
    # 2. Load Data
    dashboard, error_msg = get_dashboard(start_date, end_date)

    # 3. Render Sidebar Status (System Status)
    render_sidebar_status(dashboard)

    if error_msg is not None or dashboard is None:
        st.error(error_msg or "Critical Infrastructure Alert: Analytical context dictionary failed initialization.")
        render_footer(dashboard)
        return

    # 4. Render Main Dashboard Content
    render_alarm_ribbon(dashboard)

    st.markdown('<div class="section-title">Executive Summary</div>', unsafe_allow_html=True)
    render_executive_summary(dashboard)

    st.markdown('<div class="section-title">Plant Operations Overview</div>', unsafe_allow_html=True)
    render_operations_overview(dashboard)

    render_footer(dashboard)


if __name__ == "__main__":
    main()
