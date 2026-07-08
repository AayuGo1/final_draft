"""Main Entry Point for the Engineering Monitoring Dashboard.

This module serves as the production presentation and UI/UX orchestration layer
for the Engineering Monitoring Dashboard. It interfaces directly with validated
domain logic services to render an enterprise dark SCADA interface.
"""

from __future__ import annotations

import copy
import datetime as dt
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
from dashboard_data import select_representative_meter

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
    """Group a department's real meter names into engineering subsections."""
    buckets: dict[str, list[str]] = {label: [] for label, _ in SUBSECTION_RULES}
    buckets[OTHER_BUCKET_LABEL] = []

    for meter in meters:
        lower_name = meter.lower()
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
    """Resolve a meter's display unit, tolerating within-department name collisions."""
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
    
    base = re.sub(r"_\d+$", "", meter)
    if base != meter:
        val2 = units_map.get(base)
        if _is_valid_unit(val2):
            return str(val2).strip()
            
    return ""


def get_dashboard(start_date: str | None = None, end_date: str | None = None) -> tuple[dict[str, Any] | None, str | None]:
    """Load dashboard data with caching based on date filters."""
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
    """Clear all caches and session state related to dashboard data."""
    st.cache_data.clear()
    st.cache_resource.clear()
    keys_to_clear = [k for k in st.session_state if k.startswith("dashboard_data")]
    for k in keys_to_clear:
        del st.session_state[k]
    st.session_state.pop("last_refresh", None)


def get_gauge_max(df_block: pd.DataFrame, rep_m: str, dept_obj: dict[str, Any]) -> float:
    """Calculate the maximum value for a gauge chart."""
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
    """Format a numeric value for executive summary display."""
    rounded = round(float(value), 2)
    if abs(rounded - round(rounded)) < 0.005:
        return f"{rounded:,.0f}"
    return f"{rounded:,.2f}"


def _exec_trend_chip(latest_val: float, avg_val: Any) -> tuple[str, str]:
    """Determine the trend status chip class and text."""
    if not isinstance(avg_val, (int, float)) or avg_val == 0:
        return "trend-flat", "Stable"
    ratio = latest_val / avg_val
    if ratio >= 1.08:
        return "trend-up", "Healthy"
    if ratio <= 0.92:
        return "trend-down", "Low"
    return "trend-flat", "Stable"


def inject_global_styles() -> None:
    """Inject global CSS for the dark SCADA theme and UI improvements."""
    st.markdown(
        f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');

            #MainMenu {{visibility: hidden;}}
            footer {{visibility: hidden;}}
            header[data-testid="stHeader"] {{background: transparent;}}
            .stApp {{ background: #0A0C10 !important; font-family: 'Inter', -apple-system, sans-serif; }}
            .block-container {{ padding-top: 8px; padding-bottom: 16px; max-width: 1680px; }}

            * {{ box-sizing: border-box; }}
            .tnum {{ font-family: 'JetBrains Mono', 'Inter', monospace; font-variant-numeric: tabular-nums; }}

            /* TASK 1 & 2: Sidebar Styling - Hide default nav, reduce width, compact spacing */
            section[data-testid="stSidebar"] div[data-testid="stSidebarNav"],
            section[data-testid="stSidebar"] ul[data-testid="stSidebarNav"],
            section[data-testid="stSidebar"] nav[data-testid="stSidebarNav"] {{
                display: none !important;
            }}
            section[data-testid="stSidebar"] {{
                width: 240px !important;
                min-width: 240px !important;
                background: rgba(16, 19, 26, 0.95) !important;
                backdrop-filter: blur(10px);
                border-right: 1px solid #1C212B;
            }}
            section[data-testid="stSidebar"] .stMarkdown {{
                margin-bottom: 0.2rem !important;
            }}
            section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] h4 {{
                margin-bottom: 0.2rem !important;
                margin-top: 0.5rem !important;
                font-size: 14px !important;
                font-weight: 700 !important;
                color: #E5E9F0 !important;
            }}
            section[data-testid="stSidebar"] .stDateInput label,
            section[data-testid="stSidebar"] .stSelectbox label {{
                color: #E5E9F0 !important;
                font-weight: 600;
                font-size: 10px;
                text-transform: uppercase;
                letter-spacing: 0.8px;
            }}
            section[data-testid="stSidebar"] div[data-baseweb="select"] > div,
            section[data-testid="stSidebar"] div[data-baseweb="datepicker"] > div {{
                background-color: #14171F !important;
                border: 1px solid #2A3140 !important;
                color: #D1D5DB !important;
            }}
            section[data-testid="stSidebar"] button[kind="secondary"] {{
                background: #14171F !important;
                border: 1px solid #2A3140 !important;
                color: #D1D5DB !important;
                font-size: 10px;
                font-weight: 600;
                width: 100%;
                margin-bottom: 4px;
                border-radius: 4px;
                transition: all 0.2s ease;
                padding: 0.3rem 0.5rem !important;
                min-height: 0 !important;
                line-height: 1.2 !important;
            }}
            section[data-testid="stSidebar"] button[kind="secondary"]:hover {{
                background: #1C212B !important;
                border-color: #3B82F6 !important;
                color: #FFF !important;
            }}
            section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {{
                padding: 6px 10px !important;
                margin-bottom: 2px !important;
                border-radius: 4px !important;
                font-size: 12px !important;
                font-weight: 600 !important;
                color: #D1D5DB !important;
                text-decoration: none !important;
                display: flex !important;
                align-items: center !important;
                gap: 8px !important;
            }}
            section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover {{
                background: #1C212B !important;
                color: #FFF !important;
            }}
            section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] {{
                background: #1C212B !important;
                border-left: 3px solid #3B82F6 !important;
                color: #FFF !important;
            }}

            .scada-header {{
                display: flex; justify-content: space-between; align-items: center;
                background: linear-gradient(180deg, #12151C 0%, #0F1218 100%);
                border: 1px solid #1C212B;
                padding: 8px 14px; margin-bottom: 8px; border-radius: 3px;
                box-shadow: 0 1px 0 rgba(255,255,255,0.02) inset;
            }}
            .header-left {{ display: flex; align-items: center; gap: 10px; }}
            .app-logo {{
                width: 26px; height: 26px; background: #171B24; border: 1px solid #2A3140;
                border-radius: 3px; display: flex; align-items: center; justify-content: center; font-size: 13px;
            }}
            .app-title {{ font-size: 13px; font-weight: 800; color: #E5E9F0; letter-spacing: 0.8px; text-transform: uppercase; }}
            .app-version {{ font-size: 9px; color: #4B5563; font-weight: 700; margin-left: 6px; }}

            .header-status-group {{ display: flex; align-items: stretch; gap: 0; border-left: 1px solid #1C212B; }}
            .header-stat {{
                display: flex; flex-direction: column; align-items: flex-start; justify-content: center; gap: 2px;
                padding: 2px 14px; border-right: 1px solid #1C212B;
            }}
            .header-stat:last-child {{ border-right: none; }}
            .header-stat-label {{ font-size: 8px; font-weight: 700; color: #4B5563; text-transform: uppercase; letter-spacing: 1px; }}
            .header-stat-value {{ display: flex; align-items: center; gap: 5px; font-size: 11px; font-weight: 600; color: #D1D5DB; font-variant-numeric: tabular-nums; }}
            .status-dot {{ width: 6px; height: 6px; border-radius: 1px; flex-shrink: 0; box-shadow: 0 0 4px currentColor; }}

            .section-title {{
                font-size: 10px; font-weight: 800; color: #566072; text-transform: uppercase;
                letter-spacing: 1.4px; margin-bottom: 8px; margin-top: 18px;
                display: flex; align-items: center; gap: 8px;
            }}
            .section-title::before {{ content: ""; width: 3px; height: 10px; background: #3B82F6; border-radius: 1px; }}
            .section-title::after {{ content: ""; flex: 1; height: 1px; background: #1C212B; }}

            /* TASK 3: Executive Summary Cards - Reduced height/padding, increased number size */
            .exec-grid {{ display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px; }}
            .exec-tile {{
                background: #10131A; border: 1px solid #1C212B; border-top: 2px solid var(--accent, #3B82F6);
                border-radius: 4px; padding: 8px 10px; min-height: 80px;
                display: flex; flex-direction: column; justify-content: space-between;
                transition: transform 0.14s ease, border-color 0.14s ease, box-shadow 0.14s ease;
            }}
            .exec-tile:hover {{
                transform: translateY(-2px);
                border-color: var(--accent, #3B82F6);
                box-shadow: 0 6px 16px rgba(0,0,0,0.35);
            }}
            .exec-tile-top {{ display: flex; justify-content: space-between; align-items: flex-start; }}
            .exec-name-group {{ display: flex; align-items: center; gap: 6px; }}
            .exec-icon {{ font-size: 12px; line-height: 1; opacity: 0.9; }}
            .exec-name {{ font-size: 10.5px; font-weight: 800; color: #E5E9F0; text-transform: uppercase; letter-spacing: 0.6px; }}
            .exec-label {{ font-size: 8.5px; color: #566072; font-weight: 700; text-transform: uppercase; letter-spacing: 0.7px; margin-top: 6px; }}
            .exec-value-row {{ display: flex; align-items: baseline; margin-top: 3px; }}
            .exec-value {{ font-size: 22px; font-weight: 700; color: #F3F4F6; font-variant-numeric: tabular-nums; font-family: 'JetBrains Mono', monospace; letter-spacing: -0.2px; }}
            .exec-unit {{ font-size: 9.5px; color: #6B7280; font-weight: 600; margin-left: 4px; font-family: 'Inter', sans-serif; }}
            .exec-bottom-row {{ display: flex; align-items: center; justify-content: space-between; margin-top: 8px; padding-top: 7px; border-top: 1px solid #171B24; }}
            .exec-trend-chip {{
                display: inline-flex; align-items: center; gap: 3px; font-size: 8.5px; font-weight: 800;
                letter-spacing: 0.3px; padding: 2px 6px; border-radius: 2px; text-transform: uppercase;
            }}
            .trend-up {{ color: #10B981; background: rgba(16,185,129,0.08); }}
            .trend-down {{ color: #F59E0B; background: rgba(245,158,11,0.08); }}
            .trend-flat {{ color: #6B7280; background: rgba(107,114,128,0.08); }}
            .exec-status {{ font-size: 8px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.7px; }}
            .status-online {{ color: #10B981; }}
            .status-offline {{ color: #EF4444; }}

            .ops-console {{
                background: #10131A; border: 1px solid #1C212B; border-radius: 3px; overflow: hidden;
            }}
            .console-row {{
                display: grid; grid-template-columns: 1.6fr 1fr 1fr 1fr 0.9fr;
                align-items: center; padding: 4px 14px; border-bottom: 1px solid #15181F;
                transition: background 0.1s ease;
            }}
            .console-row:last-child {{ border-bottom: none; }}
            .console-row-head {{ background: #14171F; padding: 7px 14px; }}
            .console-row-head .console-col {{
                font-size: 8.5px; font-weight: 800; color: #566072; text-transform: uppercase; letter-spacing: 0.7px;
            }}
            .console-row-alt {{ background: #0D0F14; }}
            .console-row:not(.console-row-head):hover {{ background: #1A1F29; }}
            .console-col-name {{ font-size: 11px; font-weight: 700; color: #F3F4F6; letter-spacing: 0.2px; }}
            .console-col-num {{ font-size: 10.5px; font-variant-numeric: tabular-nums; font-family: 'JetBrains Mono', monospace; }}
            .console-col-status {{ font-size: 9.5px; font-weight: 800; letter-spacing: 0.4px; }}
            .ops-val {{ color: #F3F4F6; font-weight: 700; }}
            .ops-unit {{ color: #566072; font-size: 9px; margin-left: 2px; font-family: 'Inter', sans-serif; }}

            .alarm-ribbon {{
                display: flex; align-items: center; gap: 8px;
                background: linear-gradient(90deg, rgba(255,255,255,0.015), transparent);
                border: 1px solid #1C212B; border-left: 3px solid var(--alarm-color, #10B981);
                border-radius: 3px; padding: 7px 14px; margin-bottom: 10px;
                font-size: 10.5px; font-weight: 600; color: #D1D5DB; letter-spacing: 0.2px;
            }}
            .alarm-dot {{ width: 7px; height: 7px; border-radius: 50%; background: var(--alarm-color, #10B981); flex-shrink: 0; box-shadow: 0 0 6px var(--alarm-color, #10B981); }}
            .alarm-label {{ font-size: 8px; font-weight: 800; color: #566072; text-transform: uppercase; letter-spacing: 1px; margin-right: 4px; }}

            div[data-testid="column"] {{ transition: transform 0.15s ease; }}
            div[data-testid="column"]:has(button[kind="secondary"]):hover {{ transform: translateY(-2px); cursor: pointer; }}
            div[data-testid="column"]:has(button[kind="secondary"]):hover .equip-card {{
                border-color: var(--accent, #8B5CF6);
                box-shadow: 0 6px 16px rgba(0,0,0,0.45), 0 0 0 1px var(--accent, #8B5CF6) inset;
            }}

            .equip-card {{
                background: #10131A; border: 1px solid #1C212B; border-radius: 3px;
                padding: 11px 13px 9px 13px; border-top: 2px solid var(--accent, #8B5CF6);
                transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
                position: relative;
            }}
            .equip-card.active {{
                background: #14171F; border-color: var(--accent, #8B5CF6);
                box-shadow: 0 0 0 1px var(--accent, #8B5CF6) inset, 0 4px 14px rgba(0,0,0,0.4);
                animation: cardSelectPulse 0.35s ease;
            }}
            @keyframes cardSelectPulse {{
                0% {{ transform: scale(0.97); }}
                60% {{ transform: scale(1.01); }}
                100% {{ transform: scale(1); }}
            }}
            .equip-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 7px; }}
            .equip-name {{ font-size: 12px; font-weight: 800; color: #F3F4F6; letter-spacing: 0.1px; }}
            .equip-category {{ font-size: 8.5px; color: #566072; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }}
            .equip-live-dot {{ width: 6px; height: 6px; border-radius: 50%; margin-top: 3px; }}
            .equip-metrics {{ display: flex; flex-direction: column; gap: 3px; margin: 7px 0 8px 0; padding-top: 7px; border-top: 1px solid #171B24; }}
            .equip-metric-row {{ display: flex; justify-content: space-between; font-size: 9.5px; color: #8B93A3; }}
            .equip-metric-row span:last-child {{ color: #D1D5DB; font-weight: 700; font-variant-numeric: tabular-nums; font-family: 'JetBrains Mono', monospace; }}
            .equip-activate {{
                display: flex; justify-content: space-between; align-items: center;
                font-size: 8.5px; font-weight: 800; letter-spacing: 0.8px; text-transform: uppercase;
                color: var(--accent, #8B5CF6); padding-top: 6px; margin-top: 2px; border-top: 1px dashed #1C212B;
            }}

            div[data-testid="stButton"] {{ margin-top: -34px; position: relative; z-index: 5; }}
            div[data-testid="stButton"] > button {{
                background: transparent !important; border: none !important; padding: 0 !important;
                width: 100%; height: 30px; text-align: left; color: transparent !important;
                box-shadow: none !important;
            }}
            div[data-testid="stButton"] > button:focus {{ box-shadow: none !important; }}

            .kpi-strip {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 6px; margin-bottom: 8px; }}
            .kpi-cell {{
                background: #0D0F14; border: 1px solid #171B24; border-radius: 3px; padding: 8px 12px;
            }}
            .kpi-cell-label {{ font-size: 8px; font-weight: 800; color: #566072; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 4px; }}
            .kpi-cell-value {{ font-size: 17px; font-weight: 700; color: #F3F4F6; font-family: 'JetBrains Mono', monospace; }}
            .kpi-cell-unit {{ font-size: 9.5px; color: #6B7280; margin-left: 3px; font-family: 'Inter', sans-serif; }}

            @keyframes fadeSlideIn {{
                0% {{ opacity: 0; transform: translateY(6px); }}
                100% {{ opacity: 1; transform: translateY(0); }}
            }}
            .workspace {{
                background: #10131A; border: 1px solid #1C212B; border-radius: 3px; padding: 16px;
                border-top: 2px solid var(--accent, #3B82F6); margin-bottom: 10px;
                animation: fadeSlideIn 0.28s ease;
            }}
            .workspace-header {{ display: flex; justify-content: space-between; align-items: baseline; padding: 4px 6px 12px 6px; border-bottom: 1px solid #171B24; margin-bottom: 4px; }}
            .workspace-title {{ font-size: 20px; font-weight: 800; color: #F3F4F6; margin: 0; letter-spacing: 0.3px; }}
            .workspace-label {{ font-size: 10px; color: #6B7280; text-transform: uppercase; letter-spacing: 0.7px; font-weight: 700; }}

            .subsection-label {{
                font-size: 9px; font-weight: 800; color: #4B5563; text-transform: uppercase;
                letter-spacing: 1px; margin: 12px 2px 6px 2px;
            }}

            .chart-box {{
                background: #0A0C10; border: 1px solid #171B24; border-radius: 3px; padding: 9px; margin-bottom: 6px;
                transition: box-shadow 0.15s ease, border-color 0.15s ease;
            }}
            .chart-box:hover {{ border-color: #262C38; box-shadow: 0 4px 14px rgba(0,0,0,0.35); }}
            .chart-label {{
                font-size: 9px; font-weight: 800; color: #6B7280; text-transform: uppercase;
                letter-spacing: 0.7px; margin-bottom: 5px; padding: 0 2px;
            }}

            .workspace div[data-testid="stTabs"] button[data-baseweb="tab"] {{
                font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;
                color: #6B7280; padding: 8px 12px;
            }}
            .workspace div[data-testid="stTabs"] button[aria-selected="true"] {{
                color: #F3F4F6;
            }}

            /* TASK 4: Tables - Sticky header, alternating rows, rounded borders, better spacing */
            div[data-testid="stDataFrame"] {{
                border: 1px solid #1C212B !important; border-radius: 6px !important; overflow: hidden !important;
            }}
            div[data-testid="stDataFrame"] th {{
                background: #14171F !important; color: #566072 !important; font-weight: 800 !important;
                text-transform: uppercase !important; font-size: 9px !important; letter-spacing: 0.7px !important;
                border-bottom: 1px solid #262C38 !important; padding: 8px 12px !important;
                position: sticky !important; top: 0 !important; z-index: 1 !important;
            }}
            div[data-testid="stDataFrame"] td {{
                background: #10131A !important; color: #C6CBD3 !important; border-bottom: 1px solid #171B24 !important;
                padding: 8px 12px !important; font-size: 10.5px !important; font-variant-numeric: tabular-nums;
                font-family: 'JetBrains Mono', monospace !important;
            }}
            div[data-testid="stDataFrame"] tr:nth-child(even) td {{
                background: #0D0F14 !important;
            }}
            div[data-testid="stDataFrame"] tr:hover td {{ background: #1A1F29 !important; }}

            .app-footer {{
                margin-top: 18px; padding: 7px 16px; border-radius: 3px; background: #10131A;
                border: 1px solid #1C212B; font-size: 9px; color: #4B5563; text-align: center;
                letter-spacing: 0.4px; font-family: 'JetBrains Mono', monospace;
            }}

            ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
            ::-webkit-scrollbar-track {{ background: #0A0C10; }}
            ::-webkit-scrollbar-thumb {{ background: #262C38; border-radius: 3px; }}
        </style>""",
        unsafe_allow_html=True,
    )


def render_header(dashboard: dict[str, Any] | None) -> None:
    """Render the top SCADA-style header."""
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
                <div class="header-stat-value"><span class="status-dot" style="background:{plant_color};color:{plant_color};"></span>{plant_text}</div>
            </div>
            <div class="header-stat">
                <div class="header-stat-label">Workbook</div>
                <div class="header-stat-value"><span class="status-dot" style="background:{wb_color};color:{wb_color};"></span>{wb_text}</div>
            </div>
            <div class="header-stat">
                <div class="header-stat-label">GitHub</div>
                <div class="header-stat-value"><span class="status-dot" style="background:{gh_color};color:{gh_color};"></span>{gh_text}</div>
            </div>
            <div class="header-stat">
                <div class="header-stat-label">Time</div>
                <div class="header-stat-value tnum">{now.strftime("%H:%M:%S")}</div>
            </div>
            <div class="header-stat">
                <div class="header-stat-label">Last Refresh</div>
                <div class="header-stat-value tnum">{refresh_str}</div>
            </div>
        </div>
    </div>""",
        unsafe_allow_html=True,
    )


ALARM_WATCHLIST: Final[dict[str, float]] = {
    "Air compressor": 0.90,
    "DG": 0.90,
    "GG": 0.90,
}


def render_alarm_ribbon(dashboard: dict[str, Any]) -> None:
    """Render the alarm status ribbon."""
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


def render_executive_summary(dashboard: dict[str, Any]) -> None:
    """Render the executive summary tiles."""
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
                <div class="exec-name-group">
                    <span class="exec-icon">{icon}</span>
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
    """Render the operations overview console."""
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


def _top_metrics_for(dept_obj: dict[str, Any], meters: list[str], n: int = 3) -> list[tuple[str, str]]:
    """Get top metrics for a department card."""
    latest_vals = dept_obj.get("latest_values", {})
    out: list[tuple[str, str]] = []
    for m in meters[:n]:
        v = latest_vals.get(m)
        u = resolve_meter_unit(dept_obj, m)
        v_str = f"{v:,.1f}" if isinstance(v, (int, float)) else "—"
        out.append((m, f"{v_str} {u}".strip()))
    return out


def render_process_selector(dashboard: dict[str, Any]) -> str | None:
    """Render the department selection cards with improved UI (TASK 5)."""
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
        
        # TASK 5: Get data for the new card layout
        rep_m = select_representative_meter(dept_obj)
        latest_val = dept_obj.get("latest_values", {}).get(rep_m)
        latest_str = f"{latest_val:,.2f}" if isinstance(latest_val, (int, float)) else "—"
        unit = resolve_meter_unit(dept_obj, rep_m) if rep_m else ""
        
        is_online = latest_val is not None
        status_class = "status-online" if is_online else "status-offline"
        status_text = "ONLINE" if is_online else "OFFLINE"
        live_color = "#10B981" if is_online else "#EF4444"
        
        # Calculate Trend Indicator
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
                <div class="equip-live-dot" style="background:{live_color};box-shadow:0 0 5px {live_color};"></div>
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
    """Render a chart inside a styled container."""
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
            '<div style="font-size:10px;color:#4B5563;padding:10px 2px;">No plottable data for this channel.</div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def _render_meter_kpi_strip(dept_obj: dict[str, Any], meters: list[str]) -> None:
    """Render a strip of KPI cells for the top meters."""
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
    """Render the overview tab for a department."""
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
    """Render a subsection tab."""
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
    """Render the history tab."""
    overview_df = dashboard.get("overview", pd.DataFrame())
    fig = chart_service.build_section_trend_chart(overview_df, dept_obj)
    _chart_box("Representative Channel History", fig)
    fig2 = chart_service.create_department_multi_line_chart(
        overview_dataframe=overview_df, section=dept_obj, title="All Channels — Full History"
    )
    _chart_box("Multi-Channel History", fig2)


def _render_diagnostics_tab(dept_obj: dict[str, Any]) -> None:
    """Render the diagnostics tab."""
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
        st.markdown('<div class="subsection-label">Channel Register</div>', unsafe_allow_html=True)
        st.markdown('<div class="chart-box">', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(ledger_records), use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)


def render_department_workspace(dashboard: dict[str, Any], process_name: str) -> None:
    """Render the dedicated workspace for a selected department."""
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
    """Render the footer."""
    last_refresh = st.session_state.get("last_refresh")
    refresh_text = last_refresh.strftime("%d %b %Y, %H:%M:%S") if last_refresh else "N/A"
    meta = (dashboard or {}).get("metadata", {})
    sheet_names = meta.get("sheet_names", ["Data Source Unlinked"])
    active_workbook = sheet_names[0] if sheet_names else "N/A"
    st.markdown(
        f"""<div class="app-footer">WORKBOOK: {active_workbook} &nbsp;·&nbsp; REFRESHED: {refresh_text} &nbsp;·&nbsp; v{APP_VERSION}</div>""",
        unsafe_allow_html=True,
    )


def render_sidebar_filters() -> tuple[str | None, str | None]:
    """Render the custom compact sidebar with navigation and filters (TASK 1 & 2)."""
    
    # Dashboard Header
    st.sidebar.markdown("### ⚙️ Dashboard")
    
    # Date Range
    st.sidebar.markdown("#### 📅 Date Range")
    
    if "filter_start_date" not in st.session_state:
        st.session_state.filter_start_date = None
    if "filter_end_date" not in st.session_state:
        st.session_state.filter_end_date = None
        
    start_date = st.sidebar.date_input("Start Date", value=st.session_state.filter_start_date, key="start_date_input")
    end_date = st.sidebar.date_input("End Date", value=st.session_state.filter_end_date, key="end_date_input")
    
    # Quick Filters
    st.sidebar.markdown("#### ⚡ Quick Filters")
    cols = st.sidebar.columns(2)
    
    with cols[0]:
        if st.button("Today", use_container_width=True, key="qf_today"):
            today = dt.date.today()
            st.session_state.filter_start_date = today
            st.session_state.filter_end_date = today
            st.rerun()
        if st.button("Last 7 Days", use_container_width=True, key="qf_l7d"):
            end = dt.date.today()
            start = end - dt.timedelta(days=6)
            st.session_state.filter_start_date = start
            st.session_state.filter_end_date = end
            st.rerun()
        if st.button("This Month", use_container_width=True, key="qf_tm"):
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
        if st.button("Yesterday", use_container_width=True, key="qf_yest"):
            yesterday = dt.date.today() - dt.timedelta(days=1)
            st.session_state.filter_start_date = yesterday
            st.session_state.filter_end_date = yesterday
            st.rerun()
        if st.button("Last 30 Days", use_container_width=True, key="qf_l30d"):
            end = dt.date.today()
            start = end - dt.timedelta(days=29)
            st.session_state.filter_start_date = start
            st.session_state.filter_end_date = end
            st.rerun()
        if st.button("Prev Month", use_container_width=True, key="qf_pm"):
            today = dt.date.today()
            first_day_of_month = today.replace(day=1)
            last_month_end = first_day_of_month - dt.timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            st.session_state.filter_start_date = last_month_start
            st.session_state.filter_end_date = last_month_end
            st.rerun()
        if st.button("All Data", use_container_width=True, key="qf_all"):
            st.session_state.filter_start_date = None
            st.session_state.filter_end_date = None
            st.rerun()

    # Navigation
    st.sidebar.markdown("#### 🧭 Navigation")
    st.sidebar.page_link("app.py", label="Dashboard", icon="📊")
    st.sidebar.page_link("pages/engineering.py", label="Engineering", icon="🏭")
    st.sidebar.page_link("pages/air_compressor.py", label="Air Compressor", icon="🌀")
    st.sidebar.page_link("pages/freon_refrigeration.py", label="Freon Refrigeration", icon="❄️")
    st.sidebar.page_link("pages/ammonia_refrigeration.py", label="Ammonia Refrigeration", icon="🧊")
    st.sidebar.page_link("pages/utility.py", label="Utility", icon="💧")
    
    start_str = start_date.strftime("%Y-%m-%d") if start_date else None
    end_str = end_date.strftime("%Y-%m-%d") if end_date else None
    
    return start_str, end_str


def main() -> None:
    """Main execution flow."""
    global _chart_counter
    _chart_counter = 0
    
    inject_global_styles()
    
    start_date, end_date = render_sidebar_filters()
    
    dashboard, error_msg = get_dashboard(start_date, end_date)

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
        render_department_workspace(dashboard, selected_process)

    render_footer(dashboard)


if __name__ == "__main__":
    main()
