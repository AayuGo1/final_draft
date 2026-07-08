# ==========================================
# FILE: app.py
# ==========================================
"""Main Entry Point for the Engineering Monitoring Dashboard."""

from __future__ import annotations

import copy
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
import services.chart_service as chart_service
from services.dashboard_loader import load_dashboard_safe
from dashboard_data import select_representative_meter, get_date_columns

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title=PAGE_CONFIG.get("page_title", APP_NAME),
    page_icon=PAGE_CONFIG.get("page_icon", "⚙️"),
    layout="wide",
    initial_sidebar_state="expanded",
)

CRITICAL_SYSTEMS = [
    "NPCL", "DG", "GG", "Air compressor", "Traywasher",
    "Freon Refrigeration", "Ammonia Refrigeration",
]

DEPT_CONFIGS = {
    "NPCL": {"accent": "#005DAA", "category": "Electrical / Incoming Power"},
    "DG": {"accent": "#F59E0B", "category": "Fuel / Diesel Generation"},
    "GG": {"accent": "#E31E24", "category": "Fuel / Gas Generation"},
    "Air compressor": {"accent": "#06B6D4", "category": "Compressed Air"},
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
    "DG": "Diesel Generation",
    "GG": "Gas Generation",
    "Air compressor": "Compressed Air",
    "Traywasher": "Sanitation Water",
    "Freon Refrigeration": "Cooling System",
    "Ammonia Refrigeration": "Cooling System",
}
EXEC_TILE_ICONS: Final[dict[str, str]] = {
    "NPCL": "⚡",
    "DG": "🛢️",
    "GG": "🔥",
    "Air compressor": "🌀",
    "Traywasher": "💧",
    "Freon Refrigeration": "❄️",
    "Ammonia Refrigeration": "❄️",
}

SUBSECTION_RULES: Final[list[tuple[str, list[str]]]] = [
    ("Power & Demand", ["power", "kva", "demand", "load", "kw"]),
    ("Energy & Consumption", ["energy", "kwh", "consumption", "unit"]),
    ("Pressure", ["pressure", "bar", "psi"]),
    ("Flow & Volume", ["flow", "m3", "nm3", "lpm", "volume", "air", "png", "gas", "steam", "water"]),
    ("Temperature & Cooling", ["temp", "°c", "cop", "chill", "cool", "refrigerat"]),
    ("Electrical Parameters", ["voltage", "current", "volt", "amp", "hz", "freq", "pf", "factor"]),
    ("Runtime & Hours", ["hr", "hour", "run", "rpm"]),
]
OTHER_BUCKET_LABEL: Final[str] = "Other Channels"

_chart_counter = 0


def _bucket_meters_dynamically(meters: list[str]) -> "dict[str, list[str]]":
    buckets: dict[str, list[str]] = {label: [] for label, _ in SUBSECTION_RULES}
    buckets[OTHER_BUCKET_LABEL] = []

    for meter in meters:
        lower_name = str(meter).lower()
        placed = False
        for label, keywords in SUBSECTION_RULES:
            if any(kw in lower_name for kw in keywords):
                buckets[label].append(meter)
                placed = True
                break
        if not placed:
            buckets[OTHER_BUCKET_LABEL].append(meter)

    return {label: meters_in_bucket for label, meters_in_bucket in buckets.items() if meters_in_bucket}


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
    
    if cache_key not in st.session_state:
        keys_to_clear = [k for k in st.session_state if k.startswith("dashboard_data_")]
        for k in keys_to_clear:
            if k != cache_key:
                del st.session_state[k]

        dashboard, error = load_dashboard_safe(start_date, end_date)
        st.session_state[cache_key] = dashboard
        st.session_state[f"dashboard_error_{start_date}_{end_date}"] = error
        st.session_state["last_refresh"] = dt.datetime.now()
        
    return st.session_state.get(cache_key), st.session_state.get(f"dashboard_error_{start_date}_{end_date}")


def refresh_dashboard() -> None:
    st.cache_data.clear()
    st.cache_resource.clear()
    keys_to_clear = [k for k in st.session_state if k.startswith("dashboard_data")]
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
                background: #0F172A !important; 
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
                background: #0F172A !important;
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

            /* Equipment / Process Cards */
            .equip-card {
                background: #1E293B;
                border: 1px solid #334155;
                border-left: 3px solid var(--accent, #005DAA);
                border-radius: 4px;
                padding: 6px;
                transition: all 0.2s ease;
                height: 100%;
            }
            .equip-card.active {
                border-color: #005DAA;
                background: #273449;
            }
            .equip-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
            }
            .equip-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 3px; }
            .equip-name { font-size: 11px; font-weight: 600; color: #F8FAFC; }
            .equip-category { font-size: 9px; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.3px; margin-top: 1px; }
            .equip-metrics { display: flex; flex-direction: column; gap: 2px; margin: 3px 0; padding: 3px 0; border-top: 1px solid #334155; border-bottom: 1px solid #334155; }
            .equip-metric-row { display: flex; justify-content: space-between; font-size: 9px; color: #94A3B8; }
            .equip-metric-row span:last-child { color: #F8FAFC; font-weight: 600; }
            .equip-activate { font-size: 9px; font-weight: 600; color: var(--accent, #005DAA); text-align: center; margin-top: 3px; text-transform: uppercase; letter-spacing: 0.3px; }

            /* KPI Strip */
            .kpi-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 4px; margin-bottom: 8px; }
            .kpi-cell {
                background: #1E293B; border: 1px solid #334155; border-radius: 4px; padding: 4px 6px;
            }
            .kpi-cell-label { font-size: 9px; font-weight: 600; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.3px; margin-bottom: 2px; }
            .kpi-cell-value { font-size: 13px; font-weight: 700; color: #F8FAFC; }
            .kpi-cell-unit { font-size: 9px; color: #94A3B8; margin-left: 2px; }

            /* Workspace */
            .workspace {
                background: #1E293B; border: 1px solid #334155; border-radius: 4px; padding: 10px;
                margin-bottom: 10px;
            }
            .workspace-header { display: flex; justify-content: space-between; align-items: baseline; padding-bottom: 6px; border-bottom: 1px solid #334155; margin-bottom: 8px; }
            .workspace-title { font-size: 14px; font-weight: 700; color: #F8FAFC; margin: 0; }
            .workspace-label { font-size: 10px; color: #005DAA; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; }

            /* Chart Box */
            .chart-box {
                background: #1E293B; border: 1px solid #334155; border-radius: 4px; padding: 6px; margin-bottom: 6px;
            }
            .chart-label {
                font-size: 10px; font-weight: 600; color: #94A3B8;
                margin-bottom: 4px; padding: 0 2px; text-transform: uppercase; letter-spacing: 0.3px;
            }
            /* Constrain Plotly Chart Height & Hide Toolbar */
            .chart-box .stPlotlyChart, 
            .chart-box [data-testid="stPlotlyChart"],
            .chart-box .js-plotly-plot,
            .chart-box .plotly {
                height: 220px !important;
                min-height: 220px !important;
                max-height: 220px !important;
            }
            .chart-box .modebar-container {
                display: none !important;
            }

            /* Dataframes / Tables */
            div[data-testid="stDataFrame"] {
                border: 1px solid #334155 !important; border-radius: 4px !important; overflow: hidden !important;
                background: #1E293B !important;
            }
            div[data-testid="stDataFrame"] th {
                background: #273449 !important; color: #94A3B8 !important; font-weight: 600 !important;
                text-transform: uppercase !important; font-size: 9px !important; letter-spacing: 0.3px !important;
                border-bottom: 1px solid #334155 !important; padding: 4px 6px !important;
                position: sticky !important; top: 0 !important; z-index: 1 !important;
            }
            div[data-testid="stDataFrame"] td {
                background: #1E293B !important; color: #F8FAFC !important; border-bottom: 1px solid #334155 !important;
                padding: 2px 6px !important; font-size: 10px !important;
            }
            div[data-testid="stDataFrame"] tr:nth-child(even) td {
                background: #162032 !important;
            }
            div[data-testid="stDataFrame"] tr:hover td { background: #273449 !important; }

            /* Tabs */
            .workspace div[data-testid="stTabs"] {
                border-bottom: 1px solid #334155;
            }
            .workspace div[data-testid="stTabs"] button[data-baseweb="tab"] {
                font-size: 10px; font-weight: 600; color: #94A3B8; padding: 4px 10px;
                border-radius: 4px 4px 0 0;
            }
            .workspace div[data-testid="stTabs"] button[aria-selected="true"] {
                color: #F8FAFC; background: #273449; border-bottom: 2px solid #005DAA;
            }

            /* Metrics */
            div[data-testid="stMetric"] {
                background: #1E293B;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 6px;
            }
            div[data-testid="stMetric"] label {
                color: #94A3B8 !important;
                font-size: 10px !important;
                font-weight: 600 !important;
            }
            div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
                color: #F8FAFC !important;
                font-size: 14px !important;
                font-weight: 700 !important;
            }

            /* Scrollbar */
            ::-webkit-scrollbar { width: 4px; height: 4px; }
            ::-webkit-scrollbar-track { background: #0F172A; }
            ::-webkit-scrollbar-thumb { background: #334155; border-radius: 2px; }
            ::-webkit-scrollbar-thumb:hover { background: #475569; }
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
    
    st.sidebar.markdown("#### ⚡ Quick Filters")
    cols = st.sidebar.columns(2)
    
    with cols[0]:
        if st.button("Today", use_container_width=True, key="qf_today"):
            today = dt.date.today()
            st.session_state.filter_start_date = today
            st.session_state.filter_end_date = today
            st.rerun()
        if st.button("7 Days", use_container_width=True, key="qf_l7d"):
            end = dt.date.today()
            start = end - dt.timedelta(days=6)
            st.session_state.filter_start_date = start
            st.session_state.filter_end_date = end
            st.rerun()
        if st.button("Month", use_container_width=True, key="qf_tm"):
            today = dt.date.today()
            start = today.replace(day=1)
            st.session_state.filter_start_date = start
            st.session_state.filter_end_date = today
            st.rerun()
        if st.button("YTD", use_container_width=True, key="qf_ytd"):
            today = dt.date.today()
            start = today.replace(month=1, day=1)
            st.session_state.filter_start_date = start
            st.session_state.filter_end_date = today
            st.rerun()
            
    with cols[1]:
        if st.button("Yest", use_container_width=True, key="qf_yest"):
            yesterday = dt.date.today() - dt.timedelta(days=1)
            st.session_state.filter_start_date = yesterday
            st.session_state.filter_end_date = yesterday
            st.rerun()
        if st.button("30 Days", use_container_width=True, key="qf_l30d"):
            end = dt.date.today()
            start = end - dt.timedelta(days=29)
            st.session_state.filter_start_date = start
            st.session_state.filter_end_date = end
            st.rerun()
        if st.button("Prev Mo", use_container_width=True, key="qf_pm"):
            today = dt.date.today()
            first_day_of_month = today.replace(day=1)
            last_month_end = first_day_of_month - dt.timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            st.session_state.filter_start_date = last_month_start
            st.session_state.filter_end_date = last_month_end
            st.rerun()
        if st.button("All", use_container_width=True, key="qf_all"):
            st.session_state.filter_start_date = None
            st.session_state.filter_end_date = None
            st.rerun()

    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Refresh", use_container_width=True, key="refresh_btn"):
        refresh_dashboard()
        st.rerun()

    start_str = start_date.strftime("%Y-%m-%d") if start_date else None
    end_str = end_date.strftime("%Y-%m-%d") if end_date else None
    
    return start_str, end_str


def render_sidebar_status(dashboard: dict[str, Any] | None) -> None:
    """Render the system status panel in the sidebar."""
    now = dt.datetime.now()
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


def render_daily_trend(dashboard: dict[str, Any]) -> None:
    overview_df = dashboard.get("overview", pd.DataFrame())
    
    # Debugging: Print dataframe info
    logger.debug(f"Overview DF Shape: {overview_df.shape}")
    logger.debug(f"Overview DF Columns: {overview_df.columns.tolist()}")
    logger.debug(f"Overview DF Head:\n{overview_df.head()}")
    
    if overview_df.empty:
        logger.warning("Overview dataframe is empty.")
        return
    
    date_cols = get_date_columns(overview_df)
    if not date_cols:
        logger.warning("No date columns found in overview.")
        return
    date_col = date_cols[0]
    
    meter_col = chart_service.find_first_numeric_column(overview_df)
    if not meter_col:
        logger.warning("No numeric column found in overview for daily trend.")
        return
        
    try:
        fig, stats = chart_service.get_daily_trend_figure_and_stats(overview_df, meter_col, date_col)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Average", stats.get("Average", "—"))
        col2.metric("Maximum", stats.get("Maximum", "—"))
        col3.metric("Minimum", stats.get("Minimum", "—"))
        col4.metric("Latest", stats.get("Latest", "—"))
        
        if fig:
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    except Exception as e:
        logger.error(f"Error rendering daily trend: {e}", exc_info=True)
        st.error(f"Failed to render daily trend: {e}")


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
        unit_str = resolve_meter_unit(dept_obj, rep_m) if rep_m else ""

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
        is_active = (dept_name == selected)
        
        rep_m = select_representative_meter(dept_obj)
        latest_val = dept_obj.get("latest_values", {}).get(rep_m)
        latest_str = f"{latest_val:,.2f}" if isinstance(latest_val, (int, float)) else "—"
        unit = resolve_meter_unit(dept_obj, rep_m) if rep_m else ""
        
        is_online = latest_val is not None
        status_class = "status-online" if is_online else "status-offline"
        status_text = "ONLINE" if is_online else "OFFLINE"
        live_color = "#22C55E" if is_online else "#E31E24"
        
        avg_val = dept_obj.get("average_values", {}).get(rep_m)
        trend_class, trend_text, trend_arrow = "trend-flat", "Stable", "●"
        if isinstance(latest_val, (int, float)) and isinstance(avg_val, (int, float)) and avg_val != 0:
            ratio = latest_val / avg_val
            if ratio >= 1.08:
                trend_class, trend_text, trend_arrow = "trend-up", "Healthy", "▲"
            elif ratio <= 0.92:
                trend_class, trend_text, trend_arrow = "trend-down", "Low", "▼"

        card_html = f"""
        <div class="equip-card{' active' if is_active else ''}" style="--accent:{config['accent']};">
            <div class="equip-header">
                <div>
                    <div class="equip-name">{dept_name}</div>
                    <div class="equip-category">{config['category']}</div>
                </div>
                <div class="equip-live-dot" style="background:{live_color};box-shadow:0 0 4px {live_color}; width: 6px; height: 6px; border-radius: 50%; margin-top: 3px;"></div>
            </div>
            <div class="equip-metrics">
                <div class="equip-metric-row">
                    <span>Latest Value</span>
                    <span>{latest_str} {unit}</span>
                </div>
                <div class="equip-metric-row">
                    <span>Status</span>
                    <span class="exec-status {status_class}">{status_text}</span>
                </div>
                <div class="equip-metric-row">
                    <span>Trend</span>
                    <span class="exec-trend-chip {trend_class}">{trend_arrow} {trend_text}</span>
                </div>
            </div>
            <div class="equip-activate">
                <span>{'ACTIVE ●' if is_active else 'ACTIVATE'}</span>
            </div>
        </div>"""

        with cols[idx % 4]:
            st.markdown(card_html, unsafe_allow_html=True)
            st.button(" ", key=f"proc_{dept_name}", use_container_width=True)
            if st.session_state.get(f"proc_{dept_name}"):
                st.session_state["selected_process"] = dept_name
                st.rerun()

    return st.session_state["selected_process"]


def _chart_box(label: str, fig) -> None:
    global _chart_counter
    _chart_counter += 1
    unique_key = f"chart_box_{_chart_counter}"
    
    st.markdown(f'<div class="chart-box"><div class="chart-label">{label}</div>', unsafe_allow_html=True)
    if fig:
        try:
            fig_to_render = copy.deepcopy(fig)
        except Exception:
            fig_to_render = fig
            
        st.plotly_chart(fig_to_render, use_container_width=True, config={"displayModeBar": False}, key=unique_key)
    else:
        st.markdown(
            '<div style="font-size:10px;color:#64748B;padding:10px;text-align:center;">No plottable data.</div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def _render_meter_kpi_strip(dept_obj: dict[str, Any], meters: list[str]) -> None:
    latest_vals = dept_obj.get("latest_values", {})
    cells_html = ""
    for m in meters[:6]:
        unit_str = resolve_meter_unit(dept_obj, m)
        v = latest_vals.get(m)
        v_str = _format_exec_value(v) if isinstance(v, (int, float)) else "—"
        cells_html += f"""
        <div class="kpi-cell">
            <div class="kpi-cell-label">{m}</div>
            <div class="kpi-cell-value">{v_str}<span class="kpi-cell-unit">{unit_str}</span></div>
        </div>"""
    if cells_html:
        st.markdown(f'<div class="kpi-strip">{cells_html}</div>', unsafe_allow_html=True)


def _render_overview_tab(dashboard: dict[str, Any], process_name: str, dept_obj: dict[str, Any]) -> None:
    overview_df = dashboard.get("overview", pd.DataFrame())
    meters = dept_obj.get("meters", [])
    df_block = dept_obj.get("dataframe", pd.DataFrame())
    rep_m = select_representative_meter(dept_obj)
    unit_lbl = resolve_meter_unit(dept_obj, rep_m) if rep_m else ""
    
    latest_val = dept_obj.get("latest_values", {}).get(rep_m)
    latest_val = latest_val if isinstance(latest_val, (int, float)) else 0.0
    
    max_ceiling = get_gauge_max(df_block, rep_m, dept_obj) if rep_m else 100.0

    _render_meter_kpi_strip(dept_obj, meters)

    if process_name == "NPCL":
        col1, col2 = st.columns([2, 1])
        with col1:
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            _chart_box("Load Trend", fig)
        with col2:
            fig = chart_service.create_gauge_chart(latest_val, "Demand", maximum=max_ceiling, unit=unit_lbl)
            _chart_box("Demand Gauge", fig)
    elif process_name == "Air compressor":
        col1, col2 = st.columns([1, 1])
        with col1:
            fig = chart_service.create_gauge_chart(latest_val, "Pressure", maximum=max_ceiling, unit=unit_lbl)
            _chart_box("Pressure Gauge", fig)
        with col2:
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            _chart_box("Flow Trend / Stability", fig)
    elif process_name in ("Freon Refrigeration", "Ammonia Refrigeration"):
        col1, col2 = st.columns([2, 1])
        with col1:
            fig = chart_service.create_heatmap(df_block, meters[: min(len(meters), 8)], "Temperature Heatmap")
            _chart_box("Temperature Heatmap", fig)
        with col2:
            fig = chart_service.create_gauge_chart(latest_val, "COP", maximum=max_ceiling, unit=unit_lbl)
            _chart_box("COP", fig)
    elif process_name in ("DG", "GG"):
        col1, col2 = st.columns([1, 2])
        with col1:
            target_val = dept_obj.get("average_values", {}).get(rep_m, latest_val) or latest_val
            fig = chart_service.create_bullet_chart(latest_val, target_val, "Generation vs Target", unit=unit_lbl)
            _chart_box("Generation", fig)
        with col2:
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            _chart_box("Output Trend", fig)
    else:
        col1, col2 = st.columns([2, 1])
        with col1:
            fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
            _chart_box("Primary Telemetry", fig)
        with col2:
            if rep_m:
                fig = chart_service.create_gauge_chart(latest_val, rep_m, maximum=max_ceiling, unit=unit_lbl)
                _chart_box("Current Status", fig)


def _render_subsection_tab(dashboard: dict[str, Any], dept_obj: dict[str, Any], subsection_meters: list[str]) -> None:
    overview_df = dashboard.get("overview", pd.DataFrame())
    _render_meter_kpi_strip(dept_obj, subsection_meters)

    if len(subsection_meters) >= 1:
        sub_section_obj = dict(dept_obj)
        sub_section_obj["meters"] = subsection_meters
        fig = chart_service.create_department_multi_line_chart(
            overview_dataframe=overview_df, section=sub_section_obj, title="Channel Trend"
        )
        _chart_box("Channel Trend", fig)


def _render_history_tab(dashboard: dict[str, Any], dept_obj: dict[str, Any]) -> None:
    overview_df = dashboard.get("overview", pd.DataFrame())
    fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
    _chart_box("Representative Channel History", fig)
    fig2 = chart_service.create_department_multi_line_chart(
        overview_dataframe=overview_df, section=dept_obj, title="All Channels — Full History"
    )
    _chart_box("Multi-Channel History", fig2)


def _render_diagnostics_tab(dept_obj: dict[str, Any]) -> None:
    meters = dept_obj.get("meters", [])
    df_block = dept_obj.get("dataframe", pd.DataFrame())

    if len(meters) >= 3:
        fig = chart_service.create_radar_chart(df_block, meters[:6], "Channel Profile")
        _chart_box("Channel Profile", fig)

    units_map = dept_obj.get("units", {})
    latest_vals = dept_obj.get("latest_values", {})
    avg_vals = dept_obj.get("average_values", {})
    total_vals = dept_obj.get("total_values", {})

    ledger_records = []
    for m in meters:
        l_v = latest_vals.get(m)
        a_v = avg_vals.get(m)
        t_v = total_vals.get(m)
        ledger_records.append(
            {
                "Channel": m,
                "Unit": resolve_meter_unit(dept_obj, m) or "N/A",
                "Latest": round(l_v, 2) if isinstance(l_v, (int, float)) else "N/A",
                "Mean": round(a_v, 2) if isinstance(a_v, (int, float)) else "N/A",
                "Total": round(t_v, 2) if isinstance(t_v, (int, float)) else "N/A",
                "Status": "Active" if l_v is not None else "Idle",
            }
        )
    if ledger_records:
        st.markdown('<div style="font-size: 9px; font-weight: 700; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.5px; margin: 8px 0 4px;">Channel Register</div>', unsafe_allow_html=True)
        st.markdown('<div class="chart-box">', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(ledger_records), use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)


def render_department_workspace(dashboard: dict[str, Any], process_name: str) -> None:
    departments = dashboard.get("departments", {})
    dept_obj = departments.get(process_name, {})
    if not dept_obj:
        return

    config = DEPT_CONFIGS.get(process_name, DEFAULT_CONFIG)
    meters = dept_obj.get("meters", [])

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

    dynamic_buckets = _bucket_meters_dynamically(meters)

    tab_labels = ["Overview", *dynamic_buckets.keys(), "History", "Diagnostics"]
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        _render_overview_tab(dashboard, process_name, dept_obj)

    for tab, (bucket_label, bucket_meters) in zip(tabs[1:-2], dynamic_buckets.items()):
        with tab:
            _render_subsection_tab(dashboard, dept_obj, bucket_meters)

    with tabs[-2]:
        _render_history_tab(dashboard, dept_obj)

    with tabs[-1]:
        _render_diagnostics_tab(dept_obj)


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
    global _chart_counter
    _chart_counter = 0
    
    inject_global_styles()
    
    # 1. Render Sidebar Filters (Date Range & Quick Filters)
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

    st.markdown('<div class="section-title">Process Selection</div>', unsafe_allow_html=True)
    selected_process = render_process_selector(dashboard)

    st.markdown('<div class="section-title">Daily Trend Overview</div>', unsafe_allow_html=True)
    render_daily_trend(dashboard)

    if selected_process:
        st.markdown('<div class="section-title">Engineering Workspace</div>', unsafe_allow_html=True)
        render_department_workspace(dashboard, selected_process)

    render_footer(dashboard)


if __name__ == "__main__":
    main()
